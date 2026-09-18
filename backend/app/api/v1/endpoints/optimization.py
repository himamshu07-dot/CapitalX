"""
Portfolio optimization endpoint — routes through PortfolioAgent.

All computation is delegated to the unified pipeline orchestrator,
which handles data ingestion, robust estimation, convex optimisation,
and risk analytics in a single async call.
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.request import OptimizationRequest
from app.models.response import OptimizationResponse
from app.services.portfolio_agent import PortfolioAgent
from app.core.exceptions import CapitalXException

logger = logging.getLogger("capitalx.api")
router = APIRouter()


@router.post(
    "/optimize",
    response_model=OptimizationResponse,
    summary="Compute optimal portfolio weights, risk metrics, and efficient frontier",
    tags=["Optimization"],
)
async def optimize_portfolio(request: OptimizationRequest):
    """
    Runs the full quantitative pipeline:
      1. Market data ingestion (cached, async)
      2. Ledoit-Wolf covariance + nearest-PSD conditioning
      3. James-Stein return shrinkage
      4. Multi-strategy optimisation (Max Sharpe, GMV, Risk Parity, HRP)
      5. Parameterised efficient frontier (CVXPY warm-start)
      6. Tail-risk analytics (VaR, CVaR, Sortino, MaxDD)
      7. Rolling stress volatility
    """
    try:
        agent = PortfolioAgent.get_instance()
        result = await agent.run_full_pipeline(
            tickers=request.tickers,
            current_weights=request.current_weights,
            lookback_years=request.lookback_years,
            risk_free_rate=request.risk_free_rate,
            max_asset_weight=request.max_asset_weight,
            frontier_points=request.frontier_points,
        )
        return result
    except CapitalXException as ce:
        raise HTTPException(status_code=ce.status_code, detail=ce.message)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as ex:
        logger.exception("Pipeline error")
        raise HTTPException(
            status_code=500,
            detail=f"Internal quantitative engine error: {str(ex)}",
        )
