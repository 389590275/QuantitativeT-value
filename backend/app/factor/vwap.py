from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class VwapBiasFactor(BaseFactor):
    name = "分时均线偏离"
    key = "vwap_bias"

    def calculate(self, market_data: MarketData) -> FactorResult:
        price = market_data.price
        vwap = market_data.vwap or price
        if price <= 0 or vwap <= 0:
            return FactorResult(name=self.name, value=0.0, status="中性")

        ratio = vwap / price
        if ratio < 0.5 or ratio > 1.5:
            return FactorResult(name=self.name, value=0.0, status="中性")

        bias = (price - vwap) / vwap * 100
        t = market_data.vwap_thresholds
        if bias <= -t.extreme_down_pct:
            status = "低位"
        elif bias >= t.extreme_up_pct:
            status = "高位"
        elif bias <= -t.bias_status_pct:
            status = "偏低"
        elif bias >= t.bias_status_pct:
            status = "偏高"
        else:
            status = "中性"
        return FactorResult(name=self.name, value=round(bias, 4), status=status)
