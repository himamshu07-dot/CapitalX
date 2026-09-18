from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.exceptions import CapitalXException
from app.api.v1.api_router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("capitalx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan handler — replaces deprecated @app.on_event."""
    from app.services.portfolio_agent import PortfolioAgent
    PortfolioAgent.get_instance()
    logger.info("PortfolioAgent singleton ready")
    yield
    # Shutdown hook (nothing to clean up for the in-memory agent)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Institutional-grade Portfolio Optimization API — "
        "Ledoit-Wolf covariance, James-Stein return shrinkage, "
        "CVXPY convex QP (OSQP/CLARABEL), Charnes-Cooper tangency, "
        "Risk Parity, HRP, Cornish-Fisher tail risk."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows Vercel frontend and local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom domain exception handler
@app.exception_handler(CapitalXException)
async def capitalx_exception_handler(request: Request, exc: CapitalXException):
    logger.warning(f"Domain exception: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message}
    )

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": "2.0.0",
        "docs": "/docs",
        "status": "online"
    }
