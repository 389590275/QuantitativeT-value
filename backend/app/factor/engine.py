from app.factor.aggressive import AggressiveBuyFactor
from app.factor.index_rel import IndexRelativeStrengthFactor
from app.factor.momentum import Momentum1mFactor, Momentum5mFactor
from app.factor.northbound import NorthboundFlowFactor
from app.factor.orderbook import OrderbookDeltaFactor
from app.factor.sector import SectorEtfStrengthFactor
from app.factor.technical import Kdj5mFactor, MacdFastSlowFactor
from app.factor.volatility import Volatility5mFactor
from app.factor.volume import VolumeRatioFactor
from app.factor.vwap import VwapBiasFactor
from app.models.schemas import FactorResult, MarketData


class FactorEngine:
    def __init__(self) -> None:
        self._factors = [
            VwapBiasFactor(),
            Momentum1mFactor(),
            Momentum5mFactor(),
            VolumeRatioFactor(),
            OrderbookDeltaFactor(),
            AggressiveBuyFactor(),
            Volatility5mFactor(),
            NorthboundFlowFactor(),
            SectorEtfStrengthFactor(),
            IndexRelativeStrengthFactor(),
            Kdj5mFactor(),
            MacdFastSlowFactor(),
        ]

    def run(self, market_data: MarketData) -> dict[str, FactorResult]:
        return {f.key: f.calculate(market_data) for f in self._factors}
