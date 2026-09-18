from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class RiskMetricsResult:
    annualized_returns: Dict[str, float]
    annualized_volatilities: Dict[str, float]
    correlation_matrix: Dict[str, Dict[str, float]]
    covariance_matrix: List[List[float]]
    effective_bets: float
    effective_bets_herfindahl: float
    eigenvalues: List[float]


class RiskEngine:
    """Computes quantitative risk metrics, covariance, spectral decompositions, and rolling time-series."""

    def __init__(self, trading_days: int = 252):
        self.trading_days = trading_days

    def calculate_annualized_returns(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """Calculates arithmetic annualized expected returns (mean daily return * 252)."""
        mean_daily = returns_df.mean()
        annualized = mean_daily * self.trading_days
        return annualized.to_dict()

    def calculate_annualized_volatilities(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """Calculates annualized standard deviation of returns (std * sqrt(252))."""
        daily_std = returns_df.std(ddof=1)
        annualized_std = daily_std * np.sqrt(self.trading_days)
        return annualized_std.to_dict()

    def calculate_correlation_matrix(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates pairwise Pearson correlation matrix."""
        return returns_df.corr(method="pearson")

    def calculate_covariance_matrix(self, returns_df: pd.DataFrame) -> np.ndarray:
        """Calculates full 252-day annualized sample covariance matrix: Cov(R) * 252."""
        cov_daily = returns_df.cov(ddof=1).to_numpy()
        cov_annualized = cov_daily * self.trading_days
        return cov_annualized

    def calculate_effective_bets(self, corr_matrix: np.ndarray) -> Tuple[float, float, List[float]]:
        """
        Derives the Effective Number of Bets (ENB) from the spectral decomposition
        of the correlation matrix.
        
        Let lambda_1 ... lambda_N be the eigenvalues of Pearson correlation C.
        Since trace(C) = N, sum(lambda_k) = N.
        p_k = lambda_k / N is the probability distribution of variance across orthogonal risk factors.
        
        1. Shannon Entropy formulation (Meucci):
           N_eff = exp( - sum_{k=1}^N p_k * ln(p_k) )
        2. Inverse Simpson / Herfindahl formulation:
           N_herf = 1 / sum_{k=1}^N p_k^2
           
        Returns: (N_eff_entropy, N_eff_herfindahl, sorted_eigenvalues)
        """
        # Eigenvalues of symmetric correlation matrix
        eigenvals = np.linalg.eigvalsh(corr_matrix)
        # Sort descending and clip any slight negative numerical noise to epsilon
        eigenvals = np.sort(np.maximum(eigenvals, 1e-10))[::-1]
        
        n = len(eigenvals)
        total_variance = np.sum(eigenvals)
        p = eigenvals / total_variance  # normalized fractions

        # Shannon entropy
        # Note: p * log(p) -> 0 as p -> 0
        entropy = -np.sum(p * np.log(p + 1e-12))
        enb_entropy = float(np.exp(entropy))

        # Herfindahl-based participation ratio
        herfindahl = np.sum(p ** 2)
        enb_herf = float(1.0 / herfindahl)

        # Cap at n and floor at 1.0
        enb_entropy = min(max(enb_entropy, 1.0), float(n))
        enb_herf = min(max(enb_herf, 1.0), float(n))

        return enb_entropy, enb_herf, eigenvals.tolist()

    def compute_summary_metrics(self, returns_df: pd.DataFrame) -> RiskMetricsResult:
        """Aggregates all second-order and spectral metrics for the given returns."""
        ann_returns = self.calculate_annualized_returns(returns_df)
        ann_vols = self.calculate_annualized_volatilities(returns_df)
        corr_df = self.calculate_correlation_matrix(returns_df)
        cov_matrix = self.calculate_covariance_matrix(returns_df)
        
        enb_entropy, enb_herf, eigenvals = self.calculate_effective_bets(corr_df.to_numpy())

        # Convert corr_df to nested dict for API serialization
        corr_dict = {
            col: {idx: float(val) for idx, val in row.items()}
            for col, row in corr_df.to_dict().items()
        }

        return RiskMetricsResult(
            annualized_returns=ann_returns,
            annualized_volatilities=ann_vols,
            correlation_matrix=corr_dict,
            covariance_matrix=cov_matrix.tolist(),
            effective_bets=round(enb_entropy, 3),
            effective_bets_herfindahl=round(enb_herf, 3),
            eigenvalues=[round(e, 4) for e in eigenvals]
        )

    def calculate_rolling_volatility(
        self,
        returns_df: pd.DataFrame,
        weights: Optional[np.ndarray] = None,
        window: int = 63  # ~3 months
    ) -> pd.DataFrame:
        """
        Calculates rolling annualized volatility over a moving window of trading days.
        If weights is provided, calculates the rolling volatility of the weighted portfolio:
        sigma_p = std(R_p) * sqrt(252)
        """
        if weights is not None:
            # Weighted daily portfolio return series
            portfolio_returns = returns_df.dot(weights)
            rolling_vol = portfolio_returns.rolling(window=window, min_periods=max(20, window // 2)).std(ddof=1) * np.sqrt(self.trading_days)
            return pd.DataFrame({"portfolio": rolling_vol}, index=returns_df.index)
        else:
            rolling_vols = returns_df.rolling(window=window, min_periods=max(20, window // 2)).std(ddof=1) * np.sqrt(self.trading_days)
            return rolling_vols
