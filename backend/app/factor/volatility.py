import math

from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class Volatility5mFactor(BaseFactor):
    name = "短时波动率"
    key = "volatility_5m"

    def calculate(self, market_data: MarketData) -> FactorResult:
        bars = market_data.minute_bars[-6:]
        if len(bars) < 2:
            return FactorResult(name=self.name, value=0.0, status="中性")
        closes = [float(b.get("close", 0)) for b in bars if float(b.get("close", 0)) > 0]
        if len(closes) < 2:
            return FactorResult(name=self.name, value=0.0, status="中性")
        returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        vol = math.sqrt(var) * 100
        status = "弱" if vol > 1.5 else ("强" if vol < 0.3 else "中性")
        return FactorResult(name=self.name, value=round(vol, 4), status=status)
