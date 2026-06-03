from app.factor.technical import Kdj5mFactor, MacdFastSlowFactor
from app.factor.vwap import VwapBiasFactor
from app.models.schemas import FactorResult, MarketData


class FactorEngine:
    def __init__(self) -> None:
        self._factors = [
            VwapBiasFactor(),
            Kdj5mFactor(),
            MacdFastSlowFactor(),
        ]

    def run(self, market_data: MarketData) -> dict[str, FactorResult]:
        return {f.key: f.calculate(market_data) for f in self._factors}
