from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderBookLevel(BaseModel):
    price: float = 0.0
    volume: float = 0.0


class VwapThresholdsInfo(BaseModel):
    """分时买点阈值。"""

    avg_amplitude_5d: float = 0.6
    buy_zone_pct: float = 0.5
    extreme_down_pct: float = 2.0
    extreme_up_pct: float = 2.0
    full_deviation_pct: float = 0.5
    bias_status_pct: float = 0.75
    early_session_active: bool = False


class MarketData(BaseModel):
    symbol: str
    name: str = ""
    price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    change_pct: Optional[float] = None
    bid1: OrderBookLevel = Field(default_factory=OrderBookLevel)
    ask1: OrderBookLevel = Field(default_factory=OrderBookLevel)
    minute_bars: list[dict[str, Any]] = Field(default_factory=list)
    tick_history: list[dict[str, Any]] = Field(default_factory=list)
    vwap: float = 0.0
    index_hs300_change: float = 0.0
    index_cyb_change: float = 0.0
    northbound_net: float = 0.0
    sector_etf_change: float = 0.0
    vwap_thresholds: VwapThresholdsInfo = Field(default_factory=VwapThresholdsInfo)
    timestamp: datetime = Field(default_factory=datetime.now)


class FactorResult(BaseModel):
    name: str
    value: float
    status: str = "中性"


class SignalOutput(BaseModel):
    signal: str = "HOLD"
    reasons: list[str] = Field(default_factory=list)


class RealtimePayload(BaseModel):
    symbol: str
    name: str = ""
    trade_date: str = ""
    quote_time: str = ""
    price: float = 0.0
    prev_close: float = 0.0
    change_pct: Optional[float] = None
    signal: str = "HOLD"
    reasons: list[str] = Field(default_factory=list)
    factors: dict[str, float] = Field(default_factory=dict)
    factor_status: dict[str, str] = Field(default_factory=dict)
    vwap: float = 0.0
    minute_points: list[dict[str, Any]] = Field(default_factory=list)
    signal_marks: list[dict[str, Any]] = Field(default_factory=list)
    pending_buy: Optional[dict[str, Any]] = None
    t0_position: str = "flat"
    buy_count: int = 0
    sell_count: int = 0
    data_status: str = "ok"
    vwap_thresholds: VwapThresholdsInfo = Field(default_factory=VwapThresholdsInfo)
