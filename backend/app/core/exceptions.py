class CapitalXException(Exception):
    """Base exception for all CapitalX domain errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TickerNotFoundError(CapitalXException):
    """Raised when one or more requested tickers cannot be resolved."""
    def __init__(self, tickers: list[str]):
        super().__init__(
            f"The following tickers could not be found or have no trading data: {', '.join(tickers)}",
            status_code=404
        )
        self.tickers = tickers


class InsufficientDataError(CapitalXException):
    """Raised when historical data does not meet minimum lookback or quality thresholds."""
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class OptimizationError(CapitalXException):
    """Raised when numerical optimizer fails to converge or constraints are infeasible."""
    def __init__(self, message: str):
        super().__init__(message, status_code=422)
