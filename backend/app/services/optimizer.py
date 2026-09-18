from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import minimize

from app.core.exceptions import OptimizationError


@dataclass
class PortfolioMetrics:
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float


@dataclass
class EfficientFrontierPointData:
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]


class PortfolioOptimizer:
    """Solves Modern Portfolio Theory (MPT) mean-variance optimization problems using SciPy."""

    def __init__(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        tickers: List[str],
        risk_free_rate: float = 0.045
    ):
        self.mu = np.asarray(expected_returns, dtype=float)
        self.cov = np.asarray(cov_matrix, dtype=float)
        self.tickers = tickers
        self.rf = float(risk_free_rate)
        self.n = len(tickers)

        # Numerical conditioning: ensure covariance matrix is symmetric
        self.cov = (self.cov + self.cov.T) / 2.0
        # Add slight ridge regularization if nearly singular
        min_eigenval = np.min(np.linalg.eigvalsh(self.cov))
        if min_eigenval < 1e-8:
            self.cov += np.eye(self.n) * (1e-6 - min(0.0, min_eigenval))

    def _portfolio_performance(self, w: np.ndarray) -> Tuple[float, float, float]:
        """Calculates (expected_return, volatility, sharpe_ratio) for weight vector w."""
        port_return = float(np.dot(w, self.mu))
        port_variance = float(np.dot(w.T, np.dot(self.cov, w)))
        port_vol = float(np.sqrt(max(port_variance, 1e-12)))
        sharpe = float((port_return - self.rf) / port_vol)
        return port_return, port_vol, sharpe

    def evaluate_weights(self, weights_dict: Optional[Dict[str, float]] = None) -> PortfolioMetrics:
        """Evaluates metrics for a given dictionary of weights, defaulting to equal weights (1/N)."""
        if weights_dict is None or len(weights_dict) == 0:
            w = np.ones(self.n) / self.n
        else:
            raw_w = np.array([weights_dict.get(t, 0.0) for t in self.tickers], dtype=float)
            total = np.sum(raw_w)
            if total > 1e-6:
                w = raw_w / total
            else:
                w = np.ones(self.n) / self.n

        ret, vol, sharpe = self._portfolio_performance(w)
        weight_map = {t: round(float(w[i]), 4) for i, t in enumerate(self.tickers)}
        return PortfolioMetrics(
            weights=weight_map,
            expected_return=round(ret, 4),
            volatility=round(vol, 4),
            sharpe_ratio=round(sharpe, 4)
        )

    def optimize_min_volatility(self, max_weight: float = 1.0) -> PortfolioMetrics:
        """
        Solves for the Global Minimum Volatility portfolio:
        min w^T Sigma w
        s.t. sum(w) = 1, 0 <= w_i <= max_weight
        """
        def objective(w):
            return float(np.dot(w.T, np.dot(self.cov, w)))

        w0 = np.ones(self.n) / self.n
        bounds = tuple((0.0, max_weight) for _ in range(self.n))
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]

        res = minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9, 'maxiter': 500}
        )

        if not res.success:
            raise OptimizationError(f"Minimum volatility optimization failed: {res.message}")

        opt_w = res.x / np.sum(res.x)  # Clean normalization
        ret, vol, sharpe = self._portfolio_performance(opt_w)
        weight_map = {t: round(float(opt_w[i]), 4) for i, t in enumerate(self.tickers)}
        return PortfolioMetrics(
            weights=weight_map,
            expected_return=round(ret, 4),
            volatility=round(vol, 4),
            sharpe_ratio=round(sharpe, 4)
        )

    def optimize_max_sharpe(self, max_weight: float = 1.0) -> PortfolioMetrics:
        """
        Solves for the Maximum Sharpe Ratio (Tangency) portfolio:
        max (w^T mu - Rf) / sqrt(w^T Sigma w)  <=> min - (w^T mu - Rf) / sqrt(w^T Sigma w)
        s.t. sum(w) = 1, 0 <= w_i <= max_weight
        """
        def neg_sharpe(w):
            ret = np.dot(w, self.mu)
            vol = np.sqrt(np.dot(w.T, np.dot(self.cov, w)))
            return -float((ret - self.rf) / (vol + 1e-12))

        w0 = np.ones(self.n) / self.n
        bounds = tuple((0.0, max_weight) for _ in range(self.n))
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]

        res = minimize(
            neg_sharpe,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-9, 'maxiter': 500}
        )

        # If optimization had numerical difficulty or if max return < rf, fallback to min vol
        if not res.success or np.isnan(res.x).any():
            return self.optimize_min_volatility(max_weight=max_weight)

        opt_w = res.x / np.sum(res.x)
        ret, vol, sharpe = self._portfolio_performance(opt_w)
        weight_map = {t: round(float(opt_w[i]), 4) for i, t in enumerate(self.tickers)}
        return PortfolioMetrics(
            weights=weight_map,
            expected_return=round(ret, 4),
            volatility=round(vol, 4),
            sharpe_ratio=round(sharpe, 4)
        )

    def generate_efficient_frontier(
        self,
        n_points: int = 30,
        max_weight: float = 1.0
    ) -> List[EfficientFrontierPointData]:
        """
        Sweeps target returns between the minimum volatility portfolio return
        and the maximum individual asset return, solving for minimum variance at each point.
        """
        min_vol_port = self.optimize_min_volatility(max_weight=max_weight)
        min_ret = min_vol_port.expected_return
        
        # Max achievable return with bounded weights
        sorted_indices = np.argsort(self.mu)[::-1]
        max_possible_return = 0.0
        remaining_alloc = 1.0
        for idx in sorted_indices:
            alloc = min(max_weight, remaining_alloc)
            max_possible_return += alloc * self.mu[idx]
            remaining_alloc -= alloc
            if remaining_alloc <= 0:
                break

        if max_possible_return <= min_ret:
            max_possible_return = min_ret + 0.05

        target_returns = np.linspace(min_ret, max_possible_return, n_points)
        frontier_points: List[EfficientFrontierPointData] = []

        bounds = tuple((0.0, max_weight) for _ in range(self.n))

        # Re-use last successful weights as warm-start
        current_w = np.array([min_vol_port.weights[t] for t in self.tickers])

        for target in target_returns:
            def objective(w):
                return float(np.dot(w.T, np.dot(self.cov, w)))

            constraints = [
                {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
                {'type': 'ineq', 'fun': lambda w, t=target: np.dot(w, self.mu) - t}
            ]

            res = minimize(
                objective,
                current_w,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'ftol': 1e-8, 'maxiter': 200}
            )

            if res.success:
                opt_w = res.x / np.sum(res.x)
                current_w = opt_w
                ret, vol, sharpe = self._portfolio_performance(opt_w)
                weight_map = {t: round(float(opt_w[i]), 4) for i, t in enumerate(self.tickers)}
                frontier_points.append(
                    EfficientFrontierPointData(
                        expected_return=round(ret, 4),
                        volatility=round(vol, 4),
                        sharpe_ratio=round(sharpe, 4),
                        weights=weight_map
                    )
                )

        # Always include the min vol portfolio point if empty
        if not frontier_points:
            frontier_points.append(
                EfficientFrontierPointData(
                    expected_return=min_vol_port.expected_return,
                    volatility=min_vol_port.volatility,
                    sharpe_ratio=min_vol_port.sharpe_ratio,
                    weights=min_vol_port.weights
                )
            )

        return frontier_points

    @staticmethod
    def generate_rebalance_actions(
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        threshold: float = 0.005
    ) -> List[Dict[str, any]]:
        """
        Generates actionable rebalance signals (BUY/SELL/HOLD) based on weight deviations.
        """
        all_tickers = sorted(list(set(list(current_weights.keys()) + list(target_weights.keys()))))
        actions = []

        for ticker in all_tickers:
            cw = current_weights.get(ticker, 0.0)
            tw = target_weights.get(ticker, 0.0)
            delta = tw - cw

            if delta > threshold:
                action_str = "BUY"
            elif delta < -threshold:
                action_str = "SELL"
            else:
                action_str = "HOLD"

            actions.append({
                "ticker": ticker,
                "current_weight": round(cw, 4),
                "target_weight": round(tw, 4),
                "delta_weight": round(delta, 4),
                "action": action_str
            })

        return actions
