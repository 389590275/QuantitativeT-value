from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


class SectorEtfStrengthFactor(BaseFactor):
    name = "行业ETF联动"
    key = "sector_etf_strength"

    def calculate(self, market_data: MarketData) -> FactorResult:
        chg = market_data.sector_etf_change
        status = self._status_from_value(chg, 0.3, -0.3)
        return FactorResult(name=self.name, value=round(chg, 4), status=status)
