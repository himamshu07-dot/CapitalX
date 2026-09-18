from pydantic import BaseModel
import os

class Settings(BaseModel):
    PROJECT_NAME: str = "CapitalX Portfolio Optimizer"
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
        "https://capitalx.vercel.app",
        "*"
    ]
    DEFAULT_RISK_FREE_RATE: float = 0.045
    MAX_ASSETS_LIMIT: int = 30
    DEFAULT_LOOKBACK_YEARS: int = 3
    CACHE_EXPIRY_SECONDS: int = 3600  # 1 hour market data cache

settings = Settings()
