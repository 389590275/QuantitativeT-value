from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class NorthboundFlowFactor(BaseFactor):
    name = "北向资金方向"
    key = "northbound_flow"

    def calculate(self, market_data: MarketData) -> FactorResult:
        flow = market_data.northbound_net
        status = self._status_from_value(flow, 1.0, -1.0)
        return FactorResult(name=self.name, value=round(flow, 4), status=status)
