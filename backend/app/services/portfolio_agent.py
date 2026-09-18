"""
CapitalX Portfolio Agent — Unified Quantitative Pipeline Orchestrator
=====================================================================

Autonomous execution engine that coordinates:
  A. Async data ingestion with TTL-cached yfinance downloads
  B. Ledoit-Wolf shrinkage covariance + nearest-PSD spectral projection
  C. James-Stein cross-sectional return shrinkage
  D. Parameterized CVXPY Efficient Frontier with OSQP warm-starting
  E. Charnes-Cooper Tangency QP (Max Sharpe) with 3-tier fallback
  F. Hierarchical Risk Parity (López de Prado 2016)
  G. Vectorized tail-risk analytics (Cornish-Fisher VaR, CVaR, Sortino)
  H. Self-correcting weight validation and rebalance generation

Solver fallback chain: CVXPY(OSQP) → CVXPY(CLARABEL) → SciPy SLSQP
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import minimize
from scipy.spatial.distance import squareform
from scipy.stats import kurtosis as sp_kurtosis
from scipy.stats import skew as sp_skew

from app.core.exceptions import OptimizationError
from app.models.response import (
    EfficientFrontierPoint,
    OptimizationMetadata,
    OptimizationResponse,
    PortfolioSummary,
    RebalanceAction,
    RiskMetricsResponse,
    RollingMetricsResponse,
    HealthScore,
    AiCommentary,
    InstitutionalMemo,
    RoastMemo,
    StressTestScenario,
)
from app.services.ai_diagnostics import DiagnosticsEngine
from app.services.data_ingestion import MarketDataService

# ── Optional heavy imports with graceful fallback ────────────────────
_CVXPY_AVAILABLE = True
try:
    import cvxpy as cp
except ImportError:  # pragma: no cover
    _CVXPY_AVAILABLE = False

_SKLEARN_AVAILABLE = True
try:
    from sklearn.covariance import LedoitWolf
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False

logger = logging.getLogger("capitalx.agent")

_TRADING_DAYS = 252
_HOLD_THRESHOLD = 0.005  # 0.5 % delta → HOLD


# =====================================================================
#  PortfolioAgent — Singleton Pipeline Orchestrator
# =====================================================================


class PortfolioAgent:
    """
    Institutional-grade quantitative pipeline that replaces fragmented
    service calls with a single, high-speed, self-healing execution engine.

    Usage::

        agent = PortfolioAgent.get_instance()
        response = await agent.run_full_pipeline(
            tickers=[...], current_weights={...}, lookback_years=3,
            risk_free_rate=0.045, max_asset_weight=1.0, frontier_points=50,
        )
    """

    _instance: Optional["PortfolioAgent"] = None
    _init_lock: threading.Lock = threading.Lock()

    # ── Singleton accessor ───────────────────────────────────────────
    @classmethod
    def get_instance(cls) -> "PortfolioAgent":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("PortfolioAgent singleton initialised")
        return cls._instance

    def __init__(self) -> None:
        self._cache: Dict[Tuple, Tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl: int = 3600  # seconds
        self._market_svc = MarketDataService()

    # =================================================================
    #  A. Async Data Ingestion with TTL Cache
    # =================================================================

    def _cache_key(self, tickers: List[str], lookback_years: int) -> Tuple:
        return (tuple(sorted(tickers)), lookback_years)

    def _get_cache(self, key: Tuple) -> Optional[Any]:
        with self._cache_lock:
            if key in self._cache:
                ts, payload = self._cache[key]
                if time.time() - ts < self._cache_ttl:
                    return payload
                del self._cache[key]
        return None

    def _set_cache(self, key: Tuple, payload: Any) -> None:
        with self._cache_lock:
            self._cache[key] = (time.time(), payload)

    def _fetch_data_sync(
        self, tickers: List[str], lookback_years: int
    ) -> Tuple[pd.DataFrame, List[str], str, str]:
        """Fetch via MarketDataService, compute log returns, cache results."""
        key = self._cache_key(tickers, lookback_years)
        cached = self._get_cache(key)
        if cached is not None:
            logger.info("Agent cache hit for %s", key)
            return cached

        clean_prices, excluded, start, end = self._market_svc.fetch_historical_prices(
            tickers=tickers, lookback_years=lookback_years
        )
        # Continuous log returns: r_t = ln(P_t / P_{t-1})
        returns_df = np.log(clean_prices / clean_prices.shift(1)).dropna()
        result = (returns_df, excluded, start, end)
        self._set_cache(key, result)
        return result

    # =================================================================
    #  B. Covariance Estimation & Matrix Conditioning
    # =================================================================

    def _estimate_covariance(
        self, returns_df: pd.DataFrame
    ) -> Tuple[np.ndarray, float]:
        """
        Ledoit-Wolf shrinkage covariance on daily returns.
        Returns (cov_daily, shrinkage_intensity).
        Falls back to sample covariance + ridge if sklearn unavailable.
        """
        X = returns_df.values
        if _SKLEARN_AVAILABLE:
            lw = LedoitWolf().fit(X)
            cov_daily = lw.covariance_
            shrinkage = float(lw.shrinkage_)
            logger.info("Ledoit-Wolf shrinkage intensity α = %.4f", shrinkage)
        else:
            cov_daily = np.cov(X, rowvar=False, ddof=1)
            shrinkage = 0.0
            logger.warning("sklearn unavailable — using raw sample covariance")
        return cov_daily, shrinkage

    def _nearest_psd(self, cov: np.ndarray) -> np.ndarray:
        """
        Project matrix to nearest PSD via spectral eigenvalue clipping.
        Preserves original diagonal variances by rescaling.
        """
        cov_sym = (cov + cov.T) / 2.0
        eigvals, eigvecs = np.linalg.eigh(cov_sym)
        eigvals_clipped = np.maximum(eigvals, 1e-6)
        cov_clean = eigvecs @ np.diag(eigvals_clipped) @ eigvecs.T

        # Rescale to preserve original per-asset variances
        orig_diag = np.diag(cov_sym)
        clean_diag = np.diag(cov_clean)
        # Avoid division by zero
        scale = np.sqrt(np.where(clean_diag > 1e-12, orig_diag / clean_diag, 1.0))
        cov_clean = np.diag(scale) @ cov_clean @ np.diag(scale)
        return (cov_clean + cov_clean.T) / 2.0

    def _condition_matrix(self, cov: np.ndarray) -> np.ndarray:
        """
        Full conditioning pipeline:
        1. Symmetrise
        2. Inspect condition number κ = λ_max / λ_min
        3. If ill-conditioned (κ > 1e4 or λ_min ≤ 1e-8) → nearest PSD projection
        """
        cov = (cov + cov.T) / 2.0
        eigvals = np.linalg.eigvalsh(cov)
        lam_min, lam_max = float(eigvals[0]), float(eigvals[-1])
        kappa = lam_max / max(lam_min, 1e-15)

        if lam_min <= 1e-8 or kappa > 1e4:
            logger.info(
                "Ill-conditioned Σ (κ=%.1e, λ_min=%.2e) → PSD projection", kappa, lam_min
            )
            cov = self._nearest_psd(cov)
        return cov

    # =================================================================
    #  C. James-Stein Cross-Sectional Return Shrinkage
    # =================================================================

    def _james_stein_shrink(
        self, mu: np.ndarray, cov: np.ndarray, T: int
    ) -> np.ndarray:
        """
        Shrink annualised expected returns toward the grand mean:
            μ̂ = (1 - α)·μ + α·μ̄·𝟏
        where α = min(1, (N-2) / (T · (μ-μ̄)ᵀ Σ⁻¹ (μ-μ̄)))
        Requires N ≥ 3; returns raw μ otherwise.
        """
        N = len(mu)
        if N < 3:
            return mu.copy()

        grand_mean = float(np.mean(mu))
        mu_centred = mu - grand_mean

        # Regularised inverse for Mahalanobis distance
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov)

        mahal_sq = float(mu_centred @ cov_inv @ mu_centred)
        if mahal_sq < 1e-12:
            return mu.copy()

        alpha = min(1.0, max(0.0, (N - 2) / (T * mahal_sq)))
        mu_shrunk = (1.0 - alpha) * mu + alpha * grand_mean
        logger.info("James-Stein shrinkage α = %.4f", alpha)
        return mu_shrunk

    # =================================================================
    #  D. Convex Optimisation Solvers
    # =================================================================

    # ── Global Minimum Volatility (QP) ───────────────────────────────

    def _solve_gmv_cvxpy(
        self, cov: np.ndarray, max_w: float, N: int
    ) -> Optional[np.ndarray]:
        """min w'Σw  s.t. 𝟏'w=1, 0≤w≤w_max  via OSQP → CLARABEL."""
        if not _CVXPY_AVAILABLE:
            return None
        w = cp.Variable(N, nonneg=True)
        objective = cp.Minimize(cp.quad_form(w, cov, assume_PSD=True))
        constraints = [cp.sum(w) == 1, w <= max_w]
        prob = cp.Problem(objective, constraints)

        for solver in [cp.OSQP, cp.CLARABEL]:
            try:
                kwargs = {"verbose": False}
                if solver == cp.OSQP:
                    kwargs.update(max_iter=10_000, eps_abs=1e-7, eps_rel=1e-7, polishing=True)
                prob.solve(solver=solver, **kwargs)
                if prob.status in ("optimal", "optimal_inaccurate") and w.value is not None:
                    logger.info("GMV solved via %s", solver)
                    return np.asarray(w.value).flatten()
            except Exception as exc:
                logger.warning("GMV %s failed: %s", solver, exc)
        return None

    def _slsqp_gmv(self, cov: np.ndarray, max_w: float, N: int) -> np.ndarray:
        """SciPy SLSQP fallback for GMV."""
        w0 = np.ones(N) / N
        res = minimize(
            lambda w: float(w @ cov @ w),
            w0,
            method="SLSQP",
            bounds=[(0.0, max_w)] * N,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
            options={"ftol": 1e-9, "maxiter": 500},
        )
        if not res.success:
            raise OptimizationError(f"GMV SLSQP failed: {res.message}")
        return res.x / np.sum(res.x)

    # ── Max Sharpe / Tangency (Charnes-Cooper QP) ────────────────────

    def _solve_tangency_cc(
        self, mu: np.ndarray, cov: np.ndarray, rf: float, max_w: float, N: int
    ) -> Optional[np.ndarray]:
        """
        Charnes-Cooper fractional-program transform:
            y = w / (w'(μ-rf·𝟏)),  w* = y*/Σy*
            min y'Σy   s.t.  (μ-rf)ᵀy = 1,  y ≤ w_max·Σy,  y ≥ 0
        Falls back to GMV if all excess returns ≤ 0.
        """
        excess = mu - rf
        if np.all(excess <= 1e-10):
            logger.info("All excess returns ≤ 0; tangency undefined → GMV fallback")
            return None

        if not _CVXPY_AVAILABLE:
            return None

        y = cp.Variable(N, nonneg=True)
        objective = cp.Minimize(cp.quad_form(y, cov, assume_PSD=True))
        constraints = [
            excess @ y == 1,
            y <= max_w * cp.sum(y),
        ]
        prob = cp.Problem(objective, constraints)

        for solver in [cp.OSQP, cp.CLARABEL]:
            try:
                kwargs = {"verbose": False}
                if solver == cp.OSQP:
                    kwargs.update(max_iter=10_000, eps_abs=1e-7, eps_rel=1e-7, polishing=True)
                prob.solve(solver=solver, **kwargs)
                if prob.status in ("optimal", "optimal_inaccurate") and y.value is not None:
                    y_val = np.asarray(y.value).flatten()
                    kappa = float(np.sum(y_val))
                    if kappa > 1e-10:
                        logger.info("Tangency (Charnes-Cooper) solved via %s", solver)
                        return y_val / kappa
            except Exception as exc:
                logger.warning("Tangency %s failed: %s", solver, exc)
        return None

    def _slsqp_max_sharpe(
        self, mu: np.ndarray, cov: np.ndarray, rf: float, max_w: float, N: int
    ) -> np.ndarray:
        """SciPy SLSQP fallback for Max Sharpe (non-convex negative-Sharpe)."""
        def neg_sharpe(w: np.ndarray) -> float:
            ret = float(w @ mu)
            vol = float(np.sqrt(w @ cov @ w + 1e-12))
            return -(ret - rf) / vol

        w0 = np.ones(N) / N
        res = minimize(
            neg_sharpe,
            w0,
            method="SLSQP",
            bounds=[(0.0, max_w)] * N,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
            options={"ftol": 1e-9, "maxiter": 500},
        )
        if res.success and not np.isnan(res.x).any():
            return res.x / np.sum(res.x)
        # Ultimate fallback to GMV
        logger.warning("SLSQP Max-Sharpe failed → GMV")
        return self._slsqp_gmv(cov, max_w, N)

    # ── Risk Parity / Equal Risk Contribution ────────────────────────

    def _solve_risk_parity(self, cov: np.ndarray, N: int) -> np.ndarray:
        """
        Spinu (2013) convex formulation with logarithmic barrier:
            min  ½ y'Σy − (1/N) Σ ln(yᵢ)
        Then w = y / Σyᵢ.
        Solved with CLARABEL (exponential cone) → SciPy fallback.
        """
        if _CVXPY_AVAILABLE:
            try:
                y = cp.Variable(N, pos=True)
                objective = cp.Minimize(
                    0.5 * cp.quad_form(y, cov, assume_PSD=True)
                    - (1.0 / N) * cp.sum(cp.log(y))
                )
                prob = cp.Problem(objective)
                prob.solve(solver=cp.CLARABEL, verbose=False)
                if prob.status in ("optimal", "optimal_inaccurate") and y.value is not None:
                    y_val = np.asarray(y.value).flatten()
                    y_val = np.maximum(y_val, 1e-10)
                    logger.info("Risk Parity solved via CLARABEL")
                    return y_val / np.sum(y_val)
            except Exception as exc:
                logger.warning("CVXPY Risk Parity failed: %s", exc)

        return self._rp_scipy_fallback(cov, N)

    def _rp_scipy_fallback(self, cov: np.ndarray, N: int) -> np.ndarray:
        """SciPy SLSQP fallback targeting equal risk contributions."""
        def objective(w: np.ndarray) -> float:
            sigma = float(np.sqrt(w @ cov @ w + 1e-12))
            mrc = (cov @ w) / sigma
            rc = w * mrc
            target = sigma / N
            return float(np.sum((rc - target) ** 2))

        w0 = np.ones(N) / N
        res = minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=[(1e-6, 1.0)] * N,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        w = res.x
        w = np.maximum(w, 0.0)
        return w / np.sum(w)

    # ── Hierarchical Risk Parity (López de Prado 2016) ───────────────

    def _solve_hrp(self, cov: np.ndarray, corr: np.ndarray, N: int) -> np.ndarray:
        """
        HRP is estimation-error-free (never inverts Σ):
        1. Correlation distance  D_ij = √(0.5(1−ρ_ij))
        2. Single-linkage hierarchical clustering
        3. Quasi-diagonalise via dendrogram leaf ordering
        4. Recursive bisection by inverse-variance weighting
        """
        # 1. Distance matrix
        dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
        np.fill_diagonal(dist, 0.0)
        dist = (dist + dist.T) / 2.0

        # 2. Hierarchical clustering
        condensed = squareform(dist, checks=False)
        link = linkage(condensed, method="single")

        # 3. Quasi-diagonalisation
        sort_ix = list(leaves_list(link))

        # 4. Recursive bisection
        w = np.ones(N)
        clusters = [sort_ix]
        while clusters:
            next_clusters: List[List[int]] = []
            for items in clusters:
                if len(items) <= 1:
                    continue
                half = len(items) // 2
                left, right = items[:half], items[half:]

                # Inverse-variance sub-allocation within each cluster
                var_l = self._cluster_var(cov, left)
                var_r = self._cluster_var(cov, right)

                alpha = 1.0 - var_l / (var_l + var_r + 1e-15)
                for i in left:
                    w[i] *= alpha
                for i in right:
                    w[i] *= 1.0 - alpha

                if len(left) > 1:
                    next_clusters.append(left)
                if len(right) > 1:
                    next_clusters.append(right)
            clusters = next_clusters

        w = np.maximum(w, 0.0)
        return w / np.sum(w)

    @staticmethod
    def _cluster_var(cov: np.ndarray, indices: List[int]) -> float:
        """Variance of the inverse-variance sub-portfolio within a cluster."""
        sub_cov = cov[np.ix_(indices, indices)]
        ivp = 1.0 / np.maximum(np.diag(sub_cov), 1e-12)
        ivp /= np.sum(ivp)
        return float(ivp @ sub_cov @ ivp)

    # ── Parameterised Efficient Frontier (CVXPY warm-start) ──────────

    def _solve_frontier(
        self,
        mu: np.ndarray,
        cov: np.ndarray,
        rf: float,
        max_w: float,
        N: int,
        n_points: int,
        w_gmv: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Compile a single CVXPY Problem with a cp.Parameter for the target
        return, then sweep n_points values with OSQP warm-starting enabled.
        """
        ret_gmv = float(mu @ w_gmv)

        # Maximum achievable return under weight cap
        sorted_idx = np.argsort(mu)[::-1]
        ret_max, remaining = 0.0, 1.0
        for idx in sorted_idx:
            alloc = min(max_w, remaining)
            ret_max += alloc * mu[int(idx)]
            remaining -= alloc
            if remaining <= 1e-10:
                break
        if ret_max <= ret_gmv:
            ret_max = ret_gmv + 0.05

        targets = np.linspace(ret_gmv, ret_max, n_points)
        frontier: List[Dict[str, Any]] = []

        if _CVXPY_AVAILABLE:
            frontier = self._frontier_cvxpy(mu, cov, rf, max_w, N, targets)

        # SLSQP fallback for any missing points
        if len(frontier) < max(5, n_points // 3):
            logger.info("CVXPY frontier sparse (%d pts) → SLSQP fallback", len(frontier))
            frontier = self._frontier_slsqp(mu, cov, rf, max_w, N, targets)

        return frontier

    def _frontier_cvxpy(
        self,
        mu: np.ndarray,
        cov: np.ndarray,
        rf: float,
        max_w: float,
        N: int,
        targets: np.ndarray,
    ) -> List[Dict[str, Any]]:
        w_var = cp.Variable(N, nonneg=True)
        target_ret = cp.Parameter()
        objective = cp.Minimize(cp.quad_form(w_var, cov, assume_PSD=True))
        constraints = [cp.sum(w_var) == 1, w_var <= max_w, mu @ w_var >= target_ret]
        prob = cp.Problem(objective, constraints)

        frontier: List[Dict[str, Any]] = []
        for t in targets:
            target_ret.value = float(t)
            solved = False
            for solver in [cp.OSQP, cp.CLARABEL]:
                try:
                    kwargs = {"verbose": False, "warm_start": True}
                    if solver == cp.OSQP:
                        kwargs.update(max_iter=10_000, eps_abs=1e-7, eps_rel=1e-7, polishing=True)
                    prob.solve(solver=solver, **kwargs)
                    if prob.status in ("optimal", "optimal_inaccurate") and w_var.value is not None:
                        w = self._validate_weights(np.asarray(w_var.value).flatten(), max_w)
                        ret = float(mu @ w)
                        vol = float(np.sqrt(max(w @ cov @ w, 1e-12)))
                        frontier.append(
                            {"weights": w, "expected_return": ret, "volatility": vol,
                             "sharpe_ratio": (ret - rf) / (vol + 1e-12)}
                        )
                        solved = True
                        break
                except Exception:
                    continue
            if not solved:
                pass  # skip this target silently
        return frontier

    def _frontier_slsqp(
        self,
        mu: np.ndarray,
        cov: np.ndarray,
        rf: float,
        max_w: float,
        N: int,
        targets: np.ndarray,
    ) -> List[Dict[str, Any]]:
        frontier: List[Dict[str, Any]] = []
        w_prev = np.ones(N) / N
        for t in targets:
            res = minimize(
                lambda w: float(w @ cov @ w),
                w_prev,
                method="SLSQP",
                bounds=[(0.0, max_w)] * N,
                constraints=[
                    {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
                    {"type": "ineq", "fun": lambda w, _t=t: float(w @ mu) - _t},
                ],
                options={"ftol": 1e-8, "maxiter": 300},
            )
            if res.success:
                w = self._validate_weights(res.x, max_w)
                w_prev = w
                ret = float(mu @ w)
                vol = float(np.sqrt(max(w @ cov @ w, 1e-12)))
                frontier.append(
                    {"weights": w, "expected_return": ret, "volatility": vol,
                     "sharpe_ratio": (ret - rf) / (vol + 1e-12)}
                )
        return frontier

    # =================================================================
    #  E. Portfolio Performance & Risk Analytics
    # =================================================================

    @staticmethod
    def _portfolio_performance(
        w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float
    ) -> Tuple[float, float, float]:
        """Returns (annualised_return, annualised_vol, sharpe_ratio)."""
        ret = float(np.dot(w, mu))
        vol = float(np.sqrt(max(np.dot(w, cov @ w), 1e-12)))
        sharpe = (ret - rf) / (vol + 1e-12)
        return ret, vol, sharpe

    def _compute_tail_risk(
        self, daily_port_returns: np.ndarray, rf_daily: float
    ) -> Dict[str, float]:
        """
        Vectorised tail-risk analytics on a daily portfolio return series:
        • Cornish-Fisher VaR 95% / 99%
        • Historical CVaR (Expected Shortfall) 95% / 99%
        • Maximum Drawdown
        """
        r = daily_port_returns
        mu_d = float(np.mean(r))
        sigma_d = float(np.std(r, ddof=1))
        S = float(sp_skew(r))
        K = float(sp_kurtosis(r, fisher=True))  # excess kurtosis

        # Cornish-Fisher z-adjustment
        def cf_z(z: float) -> float:
            return (
                z
                + (z**2 - 1) * S / 6
                + (z**3 - 3 * z) * K / 24
                - (2 * z**3 - 5 * z) * S**2 / 36
            )

        z95, z99 = -1.6449, -2.3263  # norm.ppf(0.05), norm.ppf(0.01)
        var_95_d = -(mu_d + cf_z(z95) * sigma_d)
        var_99_d = -(mu_d + cf_z(z99) * sigma_d)

        # Annualise VaR (sqrt-T scaling, standard approximation)
        sqrt252 = np.sqrt(_TRADING_DAYS)
        var_95 = float(var_95_d * sqrt252)
        var_99 = float(var_99_d * sqrt252)

        # Historical CVaR
        n = len(r)
        sorted_r = np.sort(r)
        cutoff_95 = max(int(np.floor(0.05 * n)), 1)
        cutoff_99 = max(int(np.floor(0.01 * n)), 1)
        cvar_95 = float(-np.mean(sorted_r[:cutoff_95]) * sqrt252)
        cvar_99 = float(-np.mean(sorted_r[:cutoff_99]) * sqrt252)

        # Maximum Drawdown
        cum = np.cumprod(1.0 + r)
        peak = np.maximum.accumulate(cum)
        drawdown = (peak - cum) / np.where(peak > 0, peak, 1.0)
        max_dd = float(np.max(drawdown))

        return {
            "var_95": var_95,
            "var_99": var_99,
            "cvar_95": cvar_95,
            "cvar_99": cvar_99,
            "max_drawdown": max_dd,
        }

    @staticmethod
    def _compute_sortino(
        daily_port_returns: np.ndarray, rf_annual: float
    ) -> float:
        """Annualised Sortino ratio: (μ_p − Rf) / σ_downside."""
        rf_daily = rf_annual / _TRADING_DAYS
        downside = np.minimum(daily_port_returns - rf_daily, 0.0)
        downside_dev = float(np.sqrt(np.mean(downside**2))) * np.sqrt(_TRADING_DAYS)
        mu_ann = float(np.mean(daily_port_returns)) * _TRADING_DAYS
        return float((mu_ann - rf_annual) / (downside_dev + 1e-12))

    @staticmethod
    def _compute_effective_bets(corr: np.ndarray) -> Tuple[float, List[float]]:
        """
        Shannon-entropy Effective Number of Bets:
            N_eff = exp(−Σ pₖ ln(pₖ + ε))
        where pₖ = λₖ / Σλ from the eigenvalues of the correlation matrix.
        """
        eigvals = np.linalg.eigvalsh(corr)
        eigvals = np.sort(np.maximum(eigvals, 1e-10))[::-1]
        p = eigvals / np.sum(eigvals)
        entropy = -float(np.sum(p * np.log(p + 1e-12)))
        enb = min(max(float(np.exp(entropy)), 1.0), float(len(eigvals)))
        return enb, eigvals.tolist()

    # =================================================================
    #  F. Rolling Volatility Metrics
    # =================================================================

    def _compute_rolling_metrics(
        self,
        returns_df: pd.DataFrame,
        w_current: np.ndarray,
        w_optimal: np.ndarray,
        valid_tickers: List[str],
    ) -> RollingMetricsResponse:
        """63-day rolling annualised volatility, downsampled to ~60 points."""
        window, min_p = 63, 32

        # Portfolio return series
        curr_ret = pd.Series(returns_df.values @ w_current, index=returns_df.index)
        opt_ret = pd.Series(returns_df.values @ w_optimal, index=returns_df.index)

        sqrt252 = np.sqrt(_TRADING_DAYS)
        curr_roll = curr_ret.rolling(window, min_periods=min_p).std(ddof=1) * sqrt252
        opt_roll = opt_ret.rolling(window, min_periods=min_p).std(ddof=1) * sqrt252

        # Joint dropna for downsampling reference
        ref = pd.DataFrame({"c": curr_roll, "o": opt_roll}).dropna()
        step = max(1, len(ref) // 60)
        sampled_idx = ref.index[::step]

        dates = [d.strftime("%Y-%m-%d") for d in sampled_idx]

        def _safe(s: pd.Series, idx: pd.DatetimeIndex) -> List[Optional[float]]:
            return [
                round(float(s.loc[d]), 4)
                if d in s.index and pd.notna(s.loc[d])
                else None
                for d in idx
            ]

        # Per-asset rolling
        asset_rolls = returns_df.rolling(window, min_periods=min_p).std(ddof=1) * sqrt252
        asset_map = {t: _safe(asset_rolls[t], sampled_idx) for t in valid_tickers}

        return RollingMetricsResponse(
            dates=dates,
            current_portfolio_vol=_safe(curr_roll, sampled_idx),
            max_sharpe_vol=_safe(opt_roll, sampled_idx),
            asset_rolling_vols=asset_map,
        )

    # =================================================================
    #  G. Weight Validation & Self-Correction
    # =================================================================

    @staticmethod
    def _validate_weights(w: np.ndarray, max_w: float) -> np.ndarray:
        """
        Iterative clipping projection onto the feasible set
        {w ≥ 0, wᵢ ≤ max_w, Σw = 1}.

        A naive clip → normalize can push weights back above max_w because
        redistributing the normalisation mass may lift a capped asset.
        Iterative clipping converges in at most N passes.
        """
        w = np.maximum(w, 0.0)
        total = np.sum(w)
        if total < 1e-10:
            return np.ones(len(w)) / len(w)
        w = w / total  # initial normalisation

        # Iterative projection: at most N rounds
        for _ in range(len(w)):
            excess = np.sum(np.maximum(w - max_w, 0.0))
            if excess < 1e-10:
                break  # all weights within cap
            w = np.minimum(w, max_w)
            free_mass = np.sum(w < max_w - 1e-10)
            if free_mass < 1e-10:
                break
            # Redistribute excess equally among uncapped assets
            w[w < max_w - 1e-10] += excess / free_mass

        # Final normalisation guard
        w = np.maximum(w, 0.0)
        total = np.sum(w)
        return w / total if total > 1e-10 else np.ones(len(w)) / len(w)

    @staticmethod
    def _build_weight_vector(
        weights_dict: Optional[Dict[str, float]], tickers: List[str]
    ) -> np.ndarray:
        """Convert user weight dict to ordered numpy array; default to 1/N."""
        N = len(tickers)
        if weights_dict is None or len(weights_dict) == 0:
            return np.ones(N) / N
        raw = np.array([weights_dict.get(t, 0.0) for t in tickers], dtype=float)
        total = np.sum(raw)
        return raw / total if total > 1e-6 else np.ones(N) / N

    @staticmethod
    def _generate_rebalance_actions(
        w_curr: np.ndarray, w_target: np.ndarray, tickers: List[str]
    ) -> List[Dict[str, Any]]:
        """BUY / SELL / HOLD trade instructions."""
        actions: List[Dict[str, Any]] = []
        for i, t in enumerate(tickers):
            cw, tw = float(w_curr[i]), float(w_target[i])
            delta = tw - cw
            if delta > _HOLD_THRESHOLD:
                action = "BUY"
            elif delta < -_HOLD_THRESHOLD:
                action = "SELL"
            else:
                action = "HOLD"
            actions.append({
                "ticker": t,
                "current_weight": round(cw, 4),
                "target_weight": round(tw, 4),
                "delta_weight": round(delta, 4),
                "action": action,
            })
        return actions

    # =================================================================
    #  Main Pipeline
    # =================================================================

    async def run_full_pipeline(
        self,
        tickers: List[str],
        current_weights: Optional[Dict[str, float]],
        lookback_years: int = 3,
        risk_free_rate: float = 0.045,
        max_asset_weight: float = 1.0,
        frontier_points: int = 50,
    ) -> OptimizationResponse:
        """
        Async entry point. Offloads all CPU-bound computation to a
        worker thread via ``asyncio.to_thread``.
        """
        return await asyncio.to_thread(
            self._execute_sync,
            tickers,
            current_weights,
            lookback_years,
            risk_free_rate,
            max_asset_weight,
            frontier_points,
        )

    # ── Synchronous computational core ───────────────────────────────

    def _execute_sync(
        self,
        tickers: List[str],
        current_weights: Optional[Dict[str, float]],
        lookback_years: int,
        risk_free_rate: float,
        max_asset_weight: float,
        frontier_points: int,
    ) -> OptimizationResponse:
        t0 = time.perf_counter()
        logger.info("Pipeline start: %s, lookback=%dy", tickers, lookback_years)

        # ── 1. Data Ingestion ────────────────────────────────────────
        returns_df, excluded, start_date, end_date = self._fetch_data_sync(
            tickers, lookback_years
        )
        valid_tickers = list(returns_df.columns)
        N = len(valid_tickers)
        T = len(returns_df)

        # ── 2. Covariance Estimation & Conditioning ──────────────────
        cov_daily, shrinkage_alpha = self._estimate_covariance(returns_df)
        cov_annual = cov_daily * _TRADING_DAYS
        cov = self._condition_matrix(cov_annual)

        # ── 3. Return Estimation (James-Stein shrinkage) ─────────────
        mu_raw = returns_df.mean().values * _TRADING_DAYS
        mu = self._james_stein_shrink(mu_raw, cov, T)

        # ── 4. Correlation & Spectral Diversification ────────────────
        corr_matrix = returns_df.corr(method="pearson").values
        enb, eigenvals = self._compute_effective_bets(corr_matrix)

        # ── 5. Multi-Strategy Optimisation ───────────────────────────
        # GMV
        w_gmv = self._solve_gmv_cvxpy(cov, max_asset_weight, N)
        if w_gmv is None:
            w_gmv = self._slsqp_gmv(cov, max_asset_weight, N)
        w_gmv = self._validate_weights(w_gmv, max_asset_weight)

        # Max Sharpe (Charnes-Cooper)
        w_ms = self._solve_tangency_cc(mu, cov, risk_free_rate, max_asset_weight, N)
        if w_ms is None:
            w_ms = self._slsqp_max_sharpe(mu, cov, risk_free_rate, max_asset_weight, N)
        w_ms = self._validate_weights(w_ms, max_asset_weight)

        # Risk Parity
        w_rp = self._solve_risk_parity(cov, N)
        w_rp = self._validate_weights(w_rp, 1.0)

        # HRP
        w_hrp = self._solve_hrp(cov, corr_matrix, N)
        w_hrp = self._validate_weights(w_hrp, 1.0)

        # Current portfolio
        w_curr = self._build_weight_vector(current_weights, valid_tickers)

        # ── 6. Portfolio Metrics ─────────────────────────────────────
        m_curr = self._portfolio_performance(w_curr, mu, cov, risk_free_rate)
        m_ms = self._portfolio_performance(w_ms, mu, cov, risk_free_rate)
        m_gmv = self._portfolio_performance(w_gmv, mu, cov, risk_free_rate)
        m_rp = self._portfolio_performance(w_rp, mu, cov, risk_free_rate)
        m_hrp = self._portfolio_performance(w_hrp, mu, cov, risk_free_rate)

        # ── 7. Efficient Frontier ────────────────────────────────────
        frontier_data = self._solve_frontier(
            mu, cov, risk_free_rate, max_asset_weight, N, frontier_points, w_gmv
        )

        # ── 8. Tail Risk Analytics ───────────────────────────────────
        R = returns_df.values
        port_rets_ms = R @ w_ms
        tail = self._compute_tail_risk(port_rets_ms, risk_free_rate / _TRADING_DAYS)
        sortino_ms = self._compute_sortino(port_rets_ms, risk_free_rate)
        sortino_curr = self._compute_sortino(R @ w_curr, risk_free_rate)

        # ── 9. Rolling Stress Volatility ─────────────────────────────
        rolling = self._compute_rolling_metrics(returns_df, w_curr, w_ms, valid_tickers)

        # ── 10. Rebalance Actions ────────────────────────────────────
        rebalance = self._generate_rebalance_actions(w_curr, w_ms, valid_tickers)

        # ── 11. Per-Asset Display Statistics ─────────────────────────
        ann_returns = {t: round(float(mu[i]), 6) for i, t in enumerate(valid_tickers)}
        ann_vols = {
            t: round(float(np.sqrt(cov[i, i])), 6) for i, t in enumerate(valid_tickers)
        }
        corr_dict: Dict[str, Dict[str, float]] = {}
        for i, t1 in enumerate(valid_tickers):
            corr_dict[t1] = {
                t2: round(float(corr_matrix[i, j]), 6)
                for j, t2 in enumerate(valid_tickers)
            }

        elapsed = time.perf_counter() - t0
        logger.info("Pipeline completed in %.3fs (%d assets, %d obs)", elapsed, N, T)

        # ── 12. Assemble Response (backward-compatible) ──────────────
        def _w_dict(w: np.ndarray) -> Dict[str, float]:
            return {t: round(float(w[i]), 4) for i, t in enumerate(valid_tickers)}

        def _summary(
            w: np.ndarray, m: Tuple[float, float, float], sortino: Optional[float] = None
        ) -> PortfolioSummary:
            return PortfolioSummary(
                weights=_w_dict(w),
                expected_return=round(m[0], 4),
                volatility=round(m[1], 4),
                sharpe_ratio=round(m[2], 4),
                sortino_ratio=round(sortino, 4) if sortino is not None else None,
            )

        # ── 13. AI Diagnostics, Health Score & Crisis Stress Testing ──
        curr_w_dict = _w_dict(w_curr)
        opt_w_dict = _w_dict(w_ms)
        health_dict = DiagnosticsEngine.calculate_health_score(
            effective_bets=enb,
            num_assets=N,
            curr_sharpe=m_curr[2],
            opt_sharpe=m_ms[2],
            curr_vol=m_curr[1],
            max_drawdown=tail.get("max_drawdown"),
            var_95=tail.get("var_95"),
        )
        stress_list = DiagnosticsEngine.run_stress_simulations(
            tickers=valid_tickers,
            curr_weights=curr_w_dict,
            opt_weights=opt_w_dict,
            ann_vols=ann_vols,
        )
        memos_dict = DiagnosticsEngine.generate_plain_english_memos(
            tickers=valid_tickers,
            curr_weights=curr_w_dict,
            opt_weights=opt_w_dict,
            curr_ret=m_curr[0],
            curr_vol=m_curr[1],
            curr_sharpe=m_curr[2],
            opt_ret=m_ms[0],
            opt_vol=m_ms[1],
            opt_sharpe=m_ms[2],
            effective_bets=enb,
            health_score=health_dict,
            rebalance_actions=rebalance,
            stress_tests=stress_list,
        )

        return OptimizationResponse(
            status="success",
            metadata=OptimizationMetadata(
                start_date=start_date,
                end_date=end_date,
                data_points=T,
                tickers=valid_tickers,
                excluded_tickers=excluded,
                risk_free_rate=risk_free_rate,
            ),
            current_portfolio=_summary(w_curr, m_curr, sortino_curr),
            max_sharpe_portfolio=_summary(w_ms, m_ms, sortino_ms),
            min_volatility_portfolio=_summary(w_gmv, m_gmv),
            risk_parity_portfolio=_summary(w_rp, m_rp),
            hrp_portfolio=_summary(w_hrp, m_hrp),
            rebalance_actions=[RebalanceAction(**a) for a in rebalance],
            risk_metrics=RiskMetricsResponse(
                effective_bets=round(enb, 3),
                annualized_returns=ann_returns,
                annualized_volatilities=ann_vols,
                correlation_matrix=corr_dict,
                covariance_matrix=[
                    [round(float(cov[i, j]), 8) for j in range(N)] for i in range(N)
                ],
                var_95=round(tail["var_95"], 4),
                var_99=round(tail["var_99"], 4),
                cvar_95=round(tail["cvar_95"], 4),
                cvar_99=round(tail["cvar_99"], 4),
                max_drawdown=round(tail["max_drawdown"], 4),
                sortino_ratio=round(sortino_ms, 4),
                shrinkage_intensity=round(shrinkage_alpha, 4),
                return_estimator="james_stein",
            ),
            efficient_frontier=[
                EfficientFrontierPoint(
                    expected_return=round(p["expected_return"], 4),
                    volatility=round(p["volatility"], 4),
                    sharpe_ratio=round(p["sharpe_ratio"], 4),
                    weights=_w_dict(p["weights"]),
                )
                for p in frontier_data
            ],
            rolling_metrics=rolling,
            health_score=HealthScore(**health_dict),
            ai_commentary=AiCommentary(
                institutional_memo=InstitutionalMemo(**memos_dict["institutional_memo"]),
                roast_memo=RoastMemo(**memos_dict["roast_memo"]),
            ),
            stress_tests=[StressTestScenario(**s) for s in stress_list],
        )
