from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class AggressiveBuyFactor(BaseFactor):
    name = "主动买盘强度"
    key = "aggressive_buy_ratio"

    def calculate(self, market_data: MarketData) -> FactorResult:
        ticks = market_data.tick_history[-20:]
        if len(ticks) < 2:
            ratio = 0.5
        else:
            up_ticks = sum(
                1 for i in range(1, len(ticks))
                if float(ticks[i].get("price", 0)) > float(ticks[i - 1].get("price", 0))
            )
            ratio = up_ticks / (len(ticks) - 1)
        status = self._status_from_value(ratio, 0.6, 0.4)
        return FactorResult(name=self.name, value=round(ratio, 4), status=status)
