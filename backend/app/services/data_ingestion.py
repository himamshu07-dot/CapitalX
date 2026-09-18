import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from app.core.exceptions import InsufficientDataError, TickerNotFoundError

logger = logging.getLogger(__name__)

# Simple thread-safe in-memory cache for downloaded price DataFrames
_PRICE_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


class DataIngestionConfig:
    MAX_MISSING_TOLERANCE_PCT: float = 0.10  # Max 10% missing rows allowed
    MAX_CONSECUTIVE_FFILL_DAYS: int = 3
    MIN_REQUIRED_DAYS: int = 60  # Need at least ~3 months of trading days


class MarketDataService:
    """Handles fetching, sanitizing, aligning, and computing returns from Yahoo Finance."""

    def __init__(self, config: Optional[DataIngestionConfig] = None):
        self.config = config or DataIngestionConfig()

    def _get_cache_key(self, tickers: List[str], start_date: str, end_date: str) -> str:
        sorted_tickers = "_".join(sorted(tickers))
        return f"{sorted_tickers}:{start_date}:{end_date}"

    def fetch_historical_prices(
        self,
        tickers: List[str],
        lookback_years: int = 3
    ) -> Tuple[pd.DataFrame, List[str], str, str]:
        """
        Fetches adjusted close prices for the specified tickers over lookback_years.
        Returns:
            Tuple of (cleaned_price_df, excluded_tickers, start_date_str, end_date_str)
        """
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=int(lookback_years * 365.25))
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        cache_key = self._get_cache_key(tickers, start_str, end_str)
        now = time.time()
        if cache_key in _PRICE_CACHE:
            cached_time, cached_df = _PRICE_CACHE[cache_key]
            if now - cached_time < CACHE_TTL_SECONDS:
                logger.info(f"Cache hit for key {cache_key}")
                clean_df, excluded = self.clean_prices(cached_df.copy(), tickers)
                return clean_df, excluded, start_str, end_str

        logger.info(f"Fetching market data for {tickers} from {start_str} to {end_str}")
        try:
            # Download adjusted close prices
            raw_data = yf.download(
                tickers=tickers,
                start=start_str,
                end=end_str,
                auto_adjust=True,
                progress=False,
                threads=True
            )
        except Exception as e:
            logger.error(f"yfinance download failed: {str(e)}")
            raise InsufficientDataError(f"Failed to fetch market data from data provider: {str(e)}")

        if raw_data is None or raw_data.empty:
            raise TickerNotFoundError(tickers)

        # Handle yfinance multi-index vs single-index structure
        price_df = pd.DataFrame()
        if isinstance(raw_data.columns, pd.MultiIndex):
            # Check if 'Close' exists at top level
            if 'Close' in raw_data.columns.levels[0]:
                price_df = raw_data['Close']
            else:
                price_df = raw_data.xs('Close', axis=1, level=0, drop_level=True)
        else:
            # Single ticker download or flat columns
            if 'Close' in raw_data.columns:
                price_df = raw_data[['Close']].rename(columns={'Close': tickers[0]})
            else:
                price_df = raw_data

        # Store in cache
        _PRICE_CACHE[cache_key] = (now, price_df.copy())

        clean_df, excluded = self.clean_prices(price_df, tickers)
        return clean_df, excluded, start_str, end_str

    def clean_prices(
        self,
        raw_prices: pd.DataFrame,
        requested_tickers: List[str]
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Cleans and aligns the price matrix:
        1. Identifies missing or mostly NaN tickers.
        2. Drops tickers failing the missing threshold.
        3. Forward-fills small gaps (<= MAX_CONSECUTIVE_FFILL_DAYS).
        4. Drops leading NaNs where any asset wasn't yet trading.
        """
        excluded_tickers: List[str] = []
        valid_columns: List[str] = []

        total_rows = len(raw_prices)
        if total_rows == 0:
            raise InsufficientDataError("Downloaded dataset is completely empty.")

        for ticker in requested_tickers:
            if ticker not in raw_prices.columns:
                excluded_tickers.append(ticker)
                continue

            col_data = raw_prices[ticker]
            nan_count = col_data.isna().sum()
            missing_pct = nan_count / total_rows

            if missing_pct > self.config.MAX_MISSING_TOLERANCE_PCT:
                logger.warning(
                    f"Excluding ticker {ticker}: {missing_pct:.1%} missing data "
                    f"(tolerance: {self.config.MAX_MISSING_TOLERANCE_PCT:.1%})"
                )
                excluded_tickers.append(ticker)
            else:
                valid_columns.append(ticker)

        if len(valid_columns) < 2:
            raise InsufficientDataError(
                f"Only {len(valid_columns)} valid assets remain after data quality checks "
                f"({valid_columns}). At least 2 valid assets are required for portfolio optimization. "
                f"Excluded assets: {excluded_tickers}"
            )

        df = raw_prices[valid_columns].copy()

        # Forward fill up to limited consecutive trading days (e.g., market holidays)
        df = df.ffill(limit=self.config.MAX_CONSECUTIVE_FFILL_DAYS)

        # Drop rows where any asset still has NaNs (e.g., inception date alignment)
        df = df.dropna()

        if len(df) < self.config.MIN_REQUIRED_DAYS:
            raise InsufficientDataError(
                f"Insufficient overlapping trading history: only {len(df)} days found. "
                f"At least {self.config.MIN_REQUIRED_DAYS} days are required."
            )

        return df, excluded_tickers

    def compute_daily_returns(
        self,
        cleaned_prices: pd.DataFrame,
        method: str = "arithmetic"
    ) -> pd.DataFrame:
        """
        Computes discrete daily returns from cleaned prices:
        Arithmetic: (P_t - P_{t-1}) / P_{t-1}
        Logarithmic: ln(P_t / P_{t-1})
        """
        if method == "log":
            returns = np.log(cleaned_prices / cleaned_prices.shift(1))
        else:
            returns = cleaned_prices.pct_change()

        return returns.dropna()
