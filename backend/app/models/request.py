from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List

class OptimizationRequest(BaseModel):
    tickers: List[str] = Field(
        ..., 
        min_length=2, 
        max_length=30, 
        description="List of asset ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'JPM'])"
    )
    current_weights: Optional[Dict[str, float]] = Field(
        default=None, 
        description="User's current portfolio weight allocation mapped by ticker symbol."
    )
    lookback_years: Optional[int] = Field(
        default=3, 
        ge=1, 
        le=10, 
        description="Historical price lookback window in years."
    )
    risk_free_rate: Optional[float] = Field(
        default=0.045, 
        ge=0.0, 
        le=0.20, 
        description="Annualized risk-free benchmark rate (e.g. 0.045 for 4.5%)."
    )
    max_asset_weight: Optional[float] = Field(
        default=1.0, 
        gt=0.0, 
        le=1.0, 
        description="Maximum permissible allocation limit per individual asset."
    )
    frontier_points: Optional[int] = Field(
        default=30, 
        ge=10, 
        le=100, 
        description="Number of discrete points calculated along the efficient frontier curve."
    )

    @field_validator("tickers")
    @classmethod
    def sanitize_tickers(cls, v: List[str]) -> List[str]:
        cleaned = [t.strip().upper() for t in v if t.strip()]
        unique_tickers = list(dict.fromkeys(cleaned))
        if len(unique_tickers) < 2:
            raise ValueError("At least 2 distinct valid asset tickers must be provided.")
        return unique_tickers

    @field_validator("max_asset_weight")
    @classmethod
    def validate_max_weight(cls, v: float, info) -> float:
        tickers = info.data.get("tickers")
        if tickers and len(tickers) > 0:
            min_feasible_cap = 1.0 / len(tickers)
            if v < min_feasible_cap - 1e-4:
                raise ValueError(
                    f"max_asset_weight ({v:.2f}) cannot be less than 1/N ({min_feasible_cap:.4f}) "
                    f"for {len(tickers)} assets, or weights cannot sum to 100%."
                )
        return v
