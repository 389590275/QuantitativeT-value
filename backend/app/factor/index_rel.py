from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class IndexRelativeStrengthFactor(BaseFactor):
    name = "指数同步强度"
    key = "index_relative_strength"

    def calculate(self, market_data: MarketData) -> FactorResult:
        change_pct = market_data.change_pct if market_data.change_pct is not None else 0.0
        rel = change_pct - (
            market_data.index_hs300_change + market_data.index_cyb_change
        ) / 2
        status = self._status_from_value(rel, 0.2, -0.2)
        return FactorResult(name=self.name, value=round(rel, 4), status=status)
