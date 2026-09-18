import numpy as np
import pytest
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.optimizer import PortfolioOptimizer


@pytest.fixture
def sample_portfolio_setup():
    # 3 assets: Stock A (high return, high vol), Stock B (moderate), Stock C (low vol/safe)
    mu = np.array([0.22, 0.14, 0.08])
    # Covariance matrix:
    # A has 25% vol, B has 18% vol, C has 10% vol, positive correlations
    std = np.array([0.25, 0.18, 0.10])
    corr = np.array([
        [1.0, 0.4, 0.2],
        [0.4, 1.0, 0.3],
        [0.2, 0.3, 1.0]
    ])
    cov = np.diag(std) @ corr @ np.diag(std)
    tickers = ["AAPL", "JNJ", "BND"]
    return mu, cov, tickers


def test_portfolio_optimizer_min_volatility(sample_portfolio_setup):
    mu, cov, tickers = sample_portfolio_setup
    optimizer = PortfolioOptimizer(mu, cov, tickers, risk_free_rate=0.04)

    min_vol_res = optimizer.optimize_min_volatility(max_weight=1.0)
    w_values = list(min_vol_res.weights.values())

    # Constraints: sum to 1, all >= 0
    assert pytest.approx(sum(w_values), abs=1e-3) == 1.0
    for w in w_values:
        assert w >= -1e-5

    # Volatility should be lower than single asset minimum vol (BND has 10% vol)
    assert min_vol_res.volatility <= 0.10


def test_portfolio_optimizer_max_sharpe(sample_portfolio_setup):
    mu, cov, tickers = sample_portfolio_setup
    optimizer = PortfolioOptimizer(mu, cov, tickers, risk_free_rate=0.04)

    max_sharpe_res = optimizer.optimize_max_sharpe(max_weight=1.0)
    equal_weight_res = optimizer.evaluate_weights()

    # Max Sharpe should beat or equal equal-weight Sharpe
    assert max_sharpe_res.sharpe_ratio >= equal_weight_res.sharpe_ratio - 1e-4

    # Weights sum to 1
    assert pytest.approx(sum(max_sharpe_res.weights.values()), abs=1e-3) == 1.0


def test_portfolio_optimizer_max_weight_constraint(sample_portfolio_setup):
    mu, cov, tickers = sample_portfolio_setup
    optimizer = PortfolioOptimizer(mu, cov, tickers, risk_free_rate=0.04)

    # Impose 40% cap per asset
    max_cap = 0.40
    res = optimizer.optimize_max_sharpe(max_weight=max_cap)
    for t, w in res.weights.items():
        assert w <= max_cap + 1e-4, f"Weight for {t} ({w}) exceeded cap of {max_cap}"


def test_efficient_frontier_generation(sample_portfolio_setup):
    mu, cov, tickers = sample_portfolio_setup
    optimizer = PortfolioOptimizer(mu, cov, tickers, risk_free_rate=0.04)

    frontier = optimizer.generate_efficient_frontier(n_points=15, max_weight=1.0)
    assert len(frontier) >= 5

    # Check frontier points are non-empty and have valid weights
    for pt in frontier:
        assert pt.volatility > 0
        assert pytest.approx(sum(pt.weights.values()), abs=1e-2) == 1.0
