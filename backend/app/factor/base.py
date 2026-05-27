from abc import ABC, abstractmethod

from app.models.schemas import FactorResult, MarketData


class BaseFactor(ABC):
    name: str = "base"
    key: str = "base"

    @abstractmethod
    def calculate(self, market_data: MarketData) -> FactorResult:
        pass

    def _status_from_value(self, value: float, strong: float, weak: float) -> str:
        if value >= strong:
            return "强"
        if value <= weak:
            return "弱"
        return "中性"
