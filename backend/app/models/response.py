from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class PortfolioSummary(BaseModel):
    weights: Dict[str, float] = Field(..., description="Normalized asset allocation weights (sum to 1.0)")
    expected_return: float = Field(..., description="Annualized expected return (mean daily returns * 252)")
    volatility: float = Field(..., description="Annualized portfolio standard deviation")
    sharpe_ratio: float = Field(..., description="Annualized Sharpe ratio against benchmark risk-free rate")
    # ── New optional fields (backward-compatible) ──
    sortino_ratio: Optional[float] = Field(default=None, description="Annualized Sortino ratio (downside deviation)")

class EfficientFrontierPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]

class RiskMetricsResponse(BaseModel):
    effective_bets: float = Field(
        ..., 
        description="Spectral Effective Number of Bets (ENB) derived via Shannon entropy of correlation eigenvalues."
    )
    annualized_returns: Dict[str, float] = Field(..., description="Individual asset annualized mean returns")
    annualized_volatilities: Dict[str, float] = Field(..., description="Individual asset annualized standard deviations")
    correlation_matrix: Dict[str, Dict[str, float]] = Field(..., description="Pairwise Pearson correlation matrix")
    covariance_matrix: List[List[float]] = Field(..., description="Full 252-day annualized covariance matrix")
    # ── New optional tail-risk fields (backward-compatible) ──
    var_95: Optional[float] = Field(default=None, description="Cornish-Fisher Value-at-Risk at 95% confidence (annualized)")
    var_99: Optional[float] = Field(default=None, description="Cornish-Fisher Value-at-Risk at 99% confidence (annualized)")
    cvar_95: Optional[float] = Field(default=None, description="Conditional VaR / Expected Shortfall at 95% (annualized)")
    cvar_99: Optional[float] = Field(default=None, description="Conditional VaR / Expected Shortfall at 99% (annualized)")
    max_drawdown: Optional[float] = Field(default=None, description="Maximum peak-to-trough drawdown of the optimal portfolio")
    sortino_ratio: Optional[float] = Field(default=None, description="Annualized Sortino ratio of the optimal portfolio")
    shrinkage_intensity: Optional[float] = Field(default=None, description="Ledoit-Wolf optimal shrinkage intensity alpha")
    return_estimator: Optional[str] = Field(default=None, description="Return estimation method used (e.g. 'james_stein')")

class RebalanceAction(BaseModel):
    ticker: str
    current_weight: float
    target_weight: float
    delta_weight: float
    action: str  # "BUY", "SELL", or "HOLD"

class OptimizationMetadata(BaseModel):
    start_date: str
    end_date: str
    data_points: int
    tickers: List[str]
    excluded_tickers: List[str] = []
    risk_free_rate: float

class RollingMetricsResponse(BaseModel):
    dates: List[str]
    current_portfolio_vol: List[Optional[float]]
    max_sharpe_vol: List[Optional[float]]
    asset_rolling_vols: Dict[str, List[Optional[float]]]

class OptimizationResponse(BaseModel):
    status: str = "success"
    metadata: OptimizationMetadata
    current_portfolio: PortfolioSummary
    max_sharpe_portfolio: PortfolioSummary
    min_volatility_portfolio: PortfolioSummary
    rebalance_actions: List[RebalanceAction]
    risk_metrics: RiskMetricsResponse
    efficient_frontier: List[EfficientFrontierPoint]
    rolling_metrics: RollingMetricsResponse
    # ── New optional multi-strategy portfolios (backward-compatible) ──
    risk_parity_portfolio: Optional[PortfolioSummary] = Field(default=None, description="Equal Risk Contribution portfolio")
    hrp_portfolio: Optional[PortfolioSummary] = Field(default=None, description="Hierarchical Risk Parity portfolio")
