from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class VolumeRatioFactor(BaseFactor):
    name = "成交量放大"
    key = "volume_ratio"

    def calculate(self, market_data: MarketData) -> FactorResult:
        bars = market_data.minute_bars
        if len(bars) < 2:
            return FactorResult(name=self.name, value=1.0, status="中性")
        recent = [float(b.get("volume", 0)) for b in bars[-5:]]
        avg_vol = sum(recent[:-1]) / max(len(recent) - 1, 1)
        cur_vol = recent[-1] if recent else 0.0
        ratio = cur_vol / avg_vol if avg_vol > 0 else 1.0
        status = self._status_from_value(ratio, 2.0, 0.8)
        return FactorResult(name=self.name, value=round(ratio, 4), status=status)
