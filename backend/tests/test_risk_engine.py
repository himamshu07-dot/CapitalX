import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.risk_engine import RiskEngine


@pytest.fixture
def risk_engine():
    return RiskEngine(trading_days=252)


def test_effective_bets_uncorrelated(risk_engine):
    """If assets are completely uncorrelated (Identity correlation), N_eff should equal N."""
    n = 4
    corr_identity = np.eye(n)
    enb_entropy, enb_herf, eigenvals = risk_engine.calculate_effective_bets(corr_identity)

    assert pytest.approx(enb_entropy, abs=1e-2) == float(n)
    assert pytest.approx(enb_herf, abs=1e-2) == float(n)
    for ev in eigenvals:
        assert pytest.approx(ev, abs=1e-4) == 1.0


def test_effective_bets_perfectly_correlated(risk_engine):
    """If assets are perfectly collinear, N_eff should collapse to 1.0."""
    n = 4
    corr_perfect = np.ones((n, n))
    enb_entropy, enb_herf, eigenvals = risk_engine.calculate_effective_bets(corr_perfect)

    assert pytest.approx(enb_entropy, abs=1e-2) == 1.0
    assert pytest.approx(enb_herf, abs=1e-2) == 1.0
    # First eigenvalue explains all variance = n
    assert pytest.approx(eigenvals[0], abs=1e-3) == float(n)


def test_annualized_metrics_and_covariance_consistency(risk_engine):
    """Check that covariance matrix Sigma = D * C * D matches direct sample covariance."""
    np.random.seed(42)
    # Generate 500 daily returns for 3 assets
    daily_returns = np.random.normal(loc=0.0005, scale=0.015, size=(500, 3))
    df = pd.DataFrame(daily_returns, columns=["A", "B", "C"])

    summary = risk_engine.compute_summary_metrics(df)
    vols = np.array([summary.annualized_volatilities[t] for t in ["A", "B", "C"]])
    d_mat = np.diag(vols)

    corr_mat = np.array([[summary.correlation_matrix[r][c] for c in ["A", "B", "C"]] for r in ["A", "B", "C"]])
    reconstructed_cov = d_mat @ corr_mat @ d_mat

    direct_cov = np.array(summary.covariance_matrix)
    np.testing.assert_allclose(direct_cov, reconstructed_cov, rtol=1e-5, atol=1e-5)
    assert 1.0 <= summary.effective_bets <= 3.0


def test_rolling_volatility(risk_engine):
    """Check rolling volatility returns non-empty series."""
    np.random.seed(42)
    daily_returns = np.random.normal(loc=0.0004, scale=0.01, size=(200, 2))
    df = pd.DataFrame(daily_returns, columns=["X", "Y"])
    weights = np.array([0.5, 0.5])

    roll = risk_engine.calculate_rolling_volatility(df, weights=weights, window=30)
    assert len(roll) == 200
    valid_points = roll["portfolio"].dropna()
    assert len(valid_points) > 150
    assert (valid_points > 0).all()
