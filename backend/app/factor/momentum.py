from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


def _price_at_minutes_ago(bars: list[dict], minutes: int, fallback: float) -> float:
    if not bars:
        return fallback
    idx = max(0, len(bars) - 1 - minutes)
    return float(bars[idx].get("close", fallback))


class Momentum1mFactor(BaseFactor):
    name = "1分钟动量"
    key = "momentum_1m"

    def calculate(self, market_data: MarketData) -> FactorResult:
        prev = _price_at_minutes_ago(market_data.minute_bars, 1, market_data.price)
        mom = (market_data.price / prev - 1) * 100 if prev > 0 else 0.0
        status = self._status_from_value(mom, 0.1, -0.1)
        return FactorResult(name=self.name, value=round(mom, 4), status=status)


class Momentum5mFactor(BaseFactor):
    name = "5分钟动量"
    key = "momentum_5m"

    def calculate(self, market_data: MarketData) -> FactorResult:
        prev = _price_at_minutes_ago(market_data.minute_bars, 5, market_data.price)
        mom = (market_data.price / prev - 1) * 100 if prev > 0 else 0.0
        status = self._status_from_value(mom, 0.2, -0.2)
        return FactorResult(name=self.name, value=round(mom, 4), status=status)
