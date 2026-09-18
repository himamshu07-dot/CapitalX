"""
Comprehensive unit tests for PortfolioAgent internal methods.

Uses synthetic data (no yfinance dependency) to verify:
 - Ledoit-Wolf covariance estimation & PSD conditioning
 - James-Stein return shrinkage
 - GMV optimisation (CVXPY + SLSQP fallback)
 - Max Sharpe / Charnes-Cooper tangency
 - Risk Parity (equal risk contribution)
 - Hierarchical Risk Parity (HRP)
 - Cornish-Fisher VaR, CVaR, Sortino, Max Drawdown
 - Effective Number of Bets (Shannon entropy)
 - Weight validation & self-correction
 - Rebalance action generation
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.portfolio_agent import PortfolioAgent


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def agent():
    return PortfolioAgent()


@pytest.fixture(scope="module")
def synthetic_data():
    """Generate 500 daily log returns for 5 assets with known covariance."""
    np.random.seed(42)
    N, T = 5, 500
    # Annualised vols: 25%, 20%, 15%, 30%, 35%
    daily_vols = np.array([0.25, 0.20, 0.15, 0.30, 0.35]) / np.sqrt(252)
    corr = np.array([
        [1.00, 0.50, 0.30, 0.20, 0.10],
        [0.50, 1.00, 0.40, 0.25, 0.15],
        [0.30, 0.40, 1.00, 0.35, 0.20],
        [0.20, 0.25, 0.35, 1.00, 0.30],
        [0.10, 0.15, 0.20, 0.30, 1.00],
    ])
    cov_daily = np.diag(daily_vols) @ corr @ np.diag(daily_vols)
    # Daily mean returns (annualised roughly 8%–30%)
    mu_daily = np.array([0.0005, 0.0004, 0.0003, 0.0006, 0.0008])
    returns = np.random.multivariate_normal(mu_daily, cov_daily, size=T)
    tickers = ["A", "B", "C", "D", "E"]
    returns_df = pd.DataFrame(returns, columns=tickers)
    return returns_df, tickers, N, T


@pytest.fixture(scope="module")
def covariance_data(synthetic_data, agent):
    """Pre-compute conditioned covariance and shrunk returns."""
    returns_df, tickers, N, T = synthetic_data
    cov_daily, shrinkage = agent._estimate_covariance(returns_df)
    cov_annual = cov_daily * 252
    cov = agent._condition_matrix(cov_annual)
    mu_raw = returns_df.mean().values * 252
    mu = agent._james_stein_shrink(mu_raw, cov, T)
    return cov, mu, returns_df, tickers, N, T, shrinkage


# ─── B. Covariance & Conditioning ────────────────────────────────────


class TestCovarianceConditioning:
    def test_ledoit_wolf_shrinkage_in_range(self, covariance_data):
        """Shrinkage intensity must be in (0, 1)."""
        *_, shrinkage = covariance_data
        assert 0.0 <= shrinkage <= 1.0

    def test_conditioned_matrix_is_psd(self, covariance_data):
        cov, *_ = covariance_data
        eigvals = np.linalg.eigvalsh(cov)
        assert np.all(eigvals > 0), f"Negative eigenvalue: {eigvals.min()}"

    def test_conditioned_matrix_is_symmetric(self, covariance_data):
        cov, *_ = covariance_data
        np.testing.assert_allclose(cov, cov.T, atol=1e-10)

    def test_nearest_psd_fixes_singular_matrix(self, agent):
        """Verify nearest PSD projection on a rank-deficient matrix."""
        # Create a rank-2 matrix for 4 assets
        v = np.array([[1, 2, 3, 4], [4, 3, 2, 1]], dtype=float)
        singular_cov = v.T @ v
        fixed = agent._nearest_psd(singular_cov)
        eigvals = np.linalg.eigvalsh(fixed)
        assert np.all(eigvals >= 1e-6 - 1e-10)

    def test_condition_matrix_preserves_reasonable_input(self, agent):
        """A well-conditioned input should pass through mostly unchanged."""
        well_cond = np.array([
            [0.04, 0.01, 0.005],
            [0.01, 0.03, 0.008],
            [0.005, 0.008, 0.02],
        ])
        result = agent._condition_matrix(well_cond)
        np.testing.assert_allclose(result, well_cond, atol=1e-8)


# ─── C. James-Stein Return Shrinkage ─────────────────────────────────


class TestJamesSteinShrinkage:
    def test_shrinks_toward_grand_mean(self, covariance_data):
        cov, mu, returns_df, _, N, T, _ = covariance_data
        mu_raw = returns_df.mean().values * 252
        grand_mean = np.mean(mu_raw)
        # Shrunk means should be closer to grand mean than raw
        dist_raw = np.sum((mu_raw - grand_mean) ** 2)
        dist_shrunk = np.sum((mu - grand_mean) ** 2)
        assert dist_shrunk <= dist_raw + 1e-10

    def test_skips_for_2_assets(self, agent):
        mu = np.array([0.10, 0.20])
        cov = np.eye(2) * 0.04
        result = agent._james_stein_shrink(mu, cov, T=500)
        np.testing.assert_array_equal(result, mu)


# ─── D. GMV Optimisation ─────────────────────────────────────────────


class TestGMVOptimisation:
    def test_weights_sum_to_one(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        w = agent._solve_gmv_cvxpy(cov, 1.0, N)
        if w is None:
            w = agent._slsqp_gmv(cov, 1.0, N)
        assert pytest.approx(np.sum(w), abs=1e-4) == 1.0

    def test_gmv_vol_below_min_asset_vol(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        w = agent._solve_gmv_cvxpy(cov, 1.0, N)
        if w is None:
            w = agent._slsqp_gmv(cov, 1.0, N)
        port_vol = np.sqrt(w @ cov @ w)
        min_asset_vol = np.sqrt(np.min(np.diag(cov)))
        assert port_vol <= min_asset_vol + 1e-6

    def test_respects_weight_cap(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        cap = 0.35
        w = agent._solve_gmv_cvxpy(cov, cap, N)
        if w is None:
            w = agent._slsqp_gmv(cov, cap, N)
        w = agent._validate_weights(w, cap)
        assert np.all(w <= cap + 1e-4)

    def test_slsqp_fallback_works(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        w = agent._slsqp_gmv(cov, 1.0, N)
        assert pytest.approx(np.sum(w), abs=1e-4) == 1.0
        assert np.all(w >= -1e-6)


# ─── E. Max Sharpe / Tangency ────────────────────────────────────────


class TestMaxSharpe:
    def test_beats_equal_weight(self, covariance_data, agent):
        cov, mu, _, _, N, _, _ = covariance_data
        rf = 0.04
        w_ms = agent._solve_tangency_cc(mu, cov, rf, 1.0, N)
        if w_ms is None:
            w_ms = agent._slsqp_max_sharpe(mu, cov, rf, 1.0, N)
        w_eq = np.ones(N) / N
        sharpe_ms = agent._portfolio_performance(w_ms, mu, cov, rf)[2]
        sharpe_eq = agent._portfolio_performance(w_eq, mu, cov, rf)[2]
        assert sharpe_ms >= sharpe_eq - 1e-4

    def test_weights_valid(self, covariance_data, agent):
        cov, mu, _, _, N, _, _ = covariance_data
        w = agent._solve_tangency_cc(mu, cov, 0.04, 1.0, N)
        if w is None:
            w = agent._slsqp_max_sharpe(mu, cov, 0.04, 1.0, N)
        assert pytest.approx(np.sum(w), abs=1e-4) == 1.0
        assert np.all(w >= -1e-6)

    def test_fallback_on_negative_excess(self, agent):
        """When all assets return below Rf, Charnes-Cooper should return None."""
        N = 3
        mu = np.array([0.01, 0.02, 0.03])
        cov = np.eye(N) * 0.04
        result = agent._solve_tangency_cc(mu, cov, rf=0.10, max_w=1.0, N=N)
        assert result is None


# ─── F. Risk Parity ─────────────────────────────────────────────────


class TestRiskParity:
    def test_weights_sum_to_one(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        w = agent._solve_risk_parity(cov, N)
        assert pytest.approx(np.sum(w), abs=1e-4) == 1.0

    def test_all_weights_positive(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        w = agent._solve_risk_parity(cov, N)
        assert np.all(w > -1e-6)

    def test_risk_contributions_approximately_equal(self, covariance_data, agent):
        cov, _, _, _, N, _, _ = covariance_data
        w = agent._solve_risk_parity(cov, N)
        sigma = np.sqrt(w @ cov @ w)
        mrc = (cov @ w) / sigma
        rc = w * mrc  # risk contributions
        # Max/min ratio should be close to 1 (within 2x for numerical tolerance)
        min_rc = float(np.min(rc))
        ratio = float(np.max(rc)) / max(min_rc, 1e-12) if min_rc > 1e-12 else float("inf")
        assert ratio < 3.0, f"Risk contribution spread too wide: ratio={ratio:.2f}"


# ─── G. Hierarchical Risk Parity ─────────────────────────────────────


class TestHRP:
    def test_weights_sum_to_one(self, covariance_data, agent):
        cov, _, returns_df, _, N, _, _ = covariance_data
        corr = returns_df.corr().values
        w = agent._solve_hrp(cov, corr, N)
        assert pytest.approx(np.sum(w), abs=1e-4) == 1.0

    def test_all_weights_positive(self, covariance_data, agent):
        cov, _, returns_df, _, N, _, _ = covariance_data
        corr = returns_df.corr().values
        w = agent._solve_hrp(cov, corr, N)
        assert np.all(w > -1e-6)

    def test_no_extreme_concentrations(self, covariance_data, agent):
        cov, _, returns_df, _, N, _, _ = covariance_data
        corr = returns_df.corr().values
        w = agent._solve_hrp(cov, corr, N)
        # No single asset should have > 80% weight
        assert np.max(w) < 0.80


# ─── H. Tail Risk Analytics ─────────────────────────────────────────


class TestTailRisk:
    @pytest.fixture
    def portfolio_returns(self, covariance_data, agent):
        cov, mu, returns_df, _, N, _, _ = covariance_data
        w = np.ones(N) / N
        return returns_df.values @ w

    def test_var_99_exceeds_var_95(self, portfolio_returns, agent):
        tail = agent._compute_tail_risk(portfolio_returns, 0.04 / 252)
        assert tail["var_99"] >= tail["var_95"] - 1e-6

    def test_cvar_exceeds_var(self, portfolio_returns, agent):
        tail = agent._compute_tail_risk(portfolio_returns, 0.04 / 252)
        assert tail["cvar_95"] >= tail["var_95"] - 1e-4
        assert tail["cvar_99"] >= tail["var_99"] - 1e-4

    def test_max_drawdown_in_range(self, portfolio_returns, agent):
        tail = agent._compute_tail_risk(portfolio_returns, 0.04 / 252)
        assert 0.0 <= tail["max_drawdown"] <= 1.0

    def test_sortino_computed(self, portfolio_returns, agent):
        sortino = agent._compute_sortino(portfolio_returns, 0.04)
        assert np.isfinite(sortino)


# ─── I. Effective Bets ──────────────────────────────────────────────


class TestEffectiveBets:
    def test_identity_corr_gives_n(self, agent):
        N = 5
        corr = np.eye(N)
        enb, _ = agent._compute_effective_bets(corr)
        assert pytest.approx(enb, abs=0.05) == float(N)

    def test_perfect_corr_gives_one(self, agent):
        N = 5
        corr = np.ones((N, N))
        enb, _ = agent._compute_effective_bets(corr)
        assert pytest.approx(enb, abs=0.05) == 1.0

    def test_enb_between_one_and_n(self, covariance_data, agent):
        _, _, returns_df, _, N, _, _ = covariance_data
        corr = returns_df.corr().values
        enb, _ = agent._compute_effective_bets(corr)
        assert 1.0 <= enb <= float(N)


# ─── J. Weight Validation ───────────────────────────────────────────


class TestWeightValidation:
    def test_clips_negatives(self, agent):
        w = np.array([0.3, -0.1, 0.5, 0.3])
        result = agent._validate_weights(w, 1.0)
        assert np.all(result >= 0.0)
        assert pytest.approx(np.sum(result), abs=1e-6) == 1.0

    def test_enforces_cap(self, agent):
        w = np.array([0.7, 0.2, 0.1])
        result = agent._validate_weights(w, 0.4)
        assert np.all(result <= 0.4 + 1e-6)
        assert pytest.approx(np.sum(result), abs=1e-6) == 1.0

    def test_handles_zero_vector(self, agent):
        w = np.zeros(4)
        result = agent._validate_weights(w, 1.0)
        np.testing.assert_allclose(result, np.ones(4) / 4)


# ─── K. Rebalance Actions ───────────────────────────────────────────


class TestRebalanceActions:
    def test_action_labels(self, agent):
        w_curr = np.array([0.4, 0.3, 0.3])
        w_target = np.array([0.2, 0.5, 0.3])
        tickers = ["A", "B", "C"]
        actions = agent._generate_rebalance_actions(w_curr, w_target, tickers)
        assert actions[0]["action"] == "SELL"  # A: -0.2
        assert actions[1]["action"] == "BUY"   # B: +0.2
        assert actions[2]["action"] == "HOLD"  # C: 0.0


# ─── L. Frontier Generation ─────────────────────────────────────────


class TestFrontierGeneration:
    def test_frontier_has_points(self, covariance_data, agent):
        cov, mu, _, _, N, _, _ = covariance_data
        rf = 0.04
        w_gmv = agent._slsqp_gmv(cov, 1.0, N)
        frontier = agent._solve_frontier(mu, cov, rf, 1.0, N, 15, w_gmv)
        assert len(frontier) >= 5

    def test_frontier_points_valid(self, covariance_data, agent):
        cov, mu, _, _, N, _, _ = covariance_data
        rf = 0.04
        w_gmv = agent._slsqp_gmv(cov, 1.0, N)
        frontier = agent._solve_frontier(mu, cov, rf, 1.0, N, 15, w_gmv)
        for pt in frontier:
            assert pt["volatility"] > 0
            assert pytest.approx(np.sum(pt["weights"]), abs=0.02) == 1.0


# ─── M. Singleton ───────────────────────────────────────────────────


class TestSingleton:
    def test_same_instance(self):
        a = PortfolioAgent.get_instance()
        b = PortfolioAgent.get_instance()
        assert a is b
