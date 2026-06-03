from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderBookLevel(BaseModel):
    price: float = 0.0
    volume: float = 0.0


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
    timestamp: datetime = Field(default_factory=datetime.now)


class FactorResult(BaseModel):
    name: str
    value: float
    status: str = "中性"


class SignalOutput(BaseModel):
    signal: str = "HOLD"
    score: float = 50.0
    reasons: list[str] = Field(default_factory=list)


class RealtimePayload(BaseModel):
    symbol: str
    name: str = ""
    trade_date: str = ""
    quote_time: str = ""
    price: float = 0.0
    change_pct: Optional[float] = None
    signal: str = "HOLD"
    score: float = 50.0
    reasons: list[str] = Field(default_factory=list)
    factors: dict[str, float] = Field(default_factory=dict)
    factor_status: dict[str, str] = Field(default_factory=dict)
    factor_scores: dict[str, float] = Field(default_factory=dict)
    vwap: float = 0.0
    minute_points: list[dict[str, Any]] = Field(default_factory=list)
    signal_marks: list[dict[str, Any]] = Field(default_factory=list)
    pending_buy: Optional[dict[str, Any]] = None
    t0_position: str = "flat"
    buy_count: int = 0
    sell_count: int = 0
    data_status: str = "ok"
