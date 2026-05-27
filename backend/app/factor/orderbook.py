from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class OrderbookDeltaFactor(BaseFactor):
    name = "盘口买卖差"
    key = "orderbook_delta"

    def calculate(self, market_data: MarketData) -> FactorResult:
        delta = market_data.bid1.volume - market_data.ask1.volume
        status = self._status_from_value(delta, 1000, -1000)
        return FactorResult(name=self.name, value=round(delta, 2), status=status)
