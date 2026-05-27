from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class VwapBiasFactor(BaseFactor):
    name = "分时均线偏离"
    key = "vwap_bias"

    def calculate(self, market_data: MarketData) -> FactorResult:
        vwap = market_data.vwap or market_data.price
        if vwap <= 0:
            return FactorResult(name=self.name, value=0.0, status="中性")
        bias = (market_data.price - vwap) / vwap * 100
        if bias <= -0.8:
            status = "低位"
        elif bias >= 0.8:
            status = "高位"
        elif bias <= -0.3:
            status = "偏低"
        elif bias >= 0.3:
            status = "偏高"
        else:
            status = "中性"
        return FactorResult(name=self.name, value=round(bias, 4), status=status)
