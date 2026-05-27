from __future__ import annotations

import re
from datetime import datetime

from app.factor.base import BaseFactor
from app.models.schemas import FactorResult, MarketData


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def _bar_clock_minutes(time_str: str) -> int | None:
    s = str(time_str).strip()
    if " " in s:
        s = s.split(" ")[-1]
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            dt = datetime.strptime(s[:8], fmt)
            return dt.hour * 60 + dt.minute
        except ValueError:
            continue
    m = re.search(r"(\d{1,2}):(\d{2})", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def _session_5m_bucket(total_min: int) -> int | None:
    """与同花顺 5 分钟 K 对齐：上午 09:30 起、下午 13:00 起每 5 分钟一根。"""
    morn_start = 9 * 60 + 30
    morn_end = 11 * 60 + 30
    aft_start = 13 * 60
    aft_end = 15 * 60
    if morn_start <= total_min <= morn_end:
        return morn_start + ((total_min - morn_start) // 5) * 5
    if aft_start <= total_min <= aft_end:
        return aft_start + ((total_min - aft_start) // 5) * 5
    return None


def _aggregate_5m_ths(bars: list[dict]) -> list[dict[str, float]]:
    """1 分钟合成 5 分钟 OHLC（含未走完的当前 5 分钟柱）。"""
    buckets: dict[int, dict[str, float]] = {}
    order: list[int] = []

    for bar in bars:
        close = _to_float(bar.get("close"))
        if close <= 0:
            continue
        tm = _bar_clock_minutes(str(bar.get("time", "")))
        if tm is None:
            continue
        key = _session_5m_bucket(tm)
        if key is None:
            continue

        high = _to_float(bar.get("high"), close)
        low = _to_float(bar.get("low"), close)
        open_ = _to_float(bar.get("open"), close)

        if key not in buckets:
            buckets[key] = {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
            order.append(key)
            continue

        b = buckets[key]
        b["high"] = max(b["high"], high)
        b["low"] = min(b["low"], low)
        b["close"] = close

    return [buckets[k] for k in sorted(order)]


def _kdj_ths(bars: list[dict[str, float]], n: int = 9) -> list[dict[str, float]]:
    """
    与同花顺 KDJ(9,3,3) 一致（在 5 分钟 K 上）：
    RSV = (C - Ln) / (Hn - Ln) * 100，Hn/Ln 为含当根在内的 n 周期高低
    K = (2/3)*K_prev + (1/3)*RSV，D = (2/3)*D_prev + (1/3)*K，J = 3K - 2D
    首日 K、D 初值 50。
    """
    k = 50.0
    d = 50.0
    series: list[dict[str, float]] = []
    for i in range(len(bars)):
        start = max(0, i - (n - 1))
        window = bars[start : i + 1]
        low_n = min(_to_float(b.get("low")) for b in window)
        high_n = max(_to_float(b.get("high")) for b in window)
        close = _to_float(bars[i].get("close"))
        if high_n == low_n:
            rsv = 50.0
        else:
            rsv = (close - low_n) / (high_n - low_n) * 100.0
        k = (2 / 3) * k + (1 / 3) * rsv
        d = (2 / 3) * d + (1 / 3) * k
        j = 3 * k - 2 * d
        series.append({"k": k, "d": d, "j": j})
    return series


class Kdj5mFactor(BaseFactor):
    name = "5分钟KDJ"
    key = "kdj_5m"
    bottom_threshold = 20.0
    top_threshold = 65.0

    def calculate(self, market_data: MarketData) -> FactorResult:
        bars_5m = _aggregate_5m_ths(market_data.minute_bars)
        if not bars_5m:
            return FactorResult(name=self.name, value=0.0, status="中性")

        series = _kdj_ths(bars_5m, n=9)
        cur = series[-1]
        k, d, j = cur["k"], cur["d"], cur["j"]

        if len(series) < 3:
            return FactorResult(name=self.name, value=round(j, 2), status="中性")

        prev2 = series[-3]
        prev = series[-2]
        prev_k, prev_d, prev_j = prev["k"], prev["d"], prev["j"]
        prev2_j = prev2["j"]

        bottom_level = min(prev2_j, prev_j, j)
        top_level = max(prev2_j, prev_j, j)
        bottom_zone = bottom_level <= self.bottom_threshold
        top_zone = top_level >= self.top_threshold

        bottom_golden_cross = bottom_zone and prev_k <= prev_d and k > d
        bottom_turn_up = bottom_zone and j > prev_j and prev_j <= prev2_j
        top_death_cross = top_zone and prev_k >= prev_d and k < d
        top_turn_down = top_zone and j < prev_j and prev_j >= prev2_j

        if bottom_golden_cross or bottom_turn_up:
            status = "强"
        elif top_death_cross or top_turn_down:
            status = "弱"
        else:
            status = "中性"

        return FactorResult(name=self.name, value=round(j, 2), status=status)


def _macd_ths(
    closes: list[float], short: int = 12, long: int = 26, signal: int = 9
) -> tuple[float, float, float]:
    """
    与同花顺 MACD 一致：
    DIF = EMA(CLOSE, SHORT) - EMA(CLOSE, LONG)
    DEA = EMA(DIF, M)
    MACD柱 = 2 * (DIF - DEA)
    """
    if not closes:
        return 0.0, 0.0, 0.0
    ema_short = _ema(closes, short)
    ema_long = _ema(closes, long)
    dif_series = [a - b for a, b in zip(ema_short, ema_long)]
    dea_series = _ema(dif_series, signal)
    dif = dif_series[-1]
    dea = dea_series[-1]
    bar = 2.0 * (dif - dea)
    return dif, dea, bar


class MacdFastSlowFactor(BaseFactor):
    name = "MACD快慢线差"
    key = "macd_fs"

    def calculate(self, market_data: MarketData) -> FactorResult:
        closes = [
            _to_float(b.get("close"))
            for b in market_data.minute_bars
            if _to_float(b.get("close")) > 0
        ]
        if len(closes) < 26 + 9 + 2:
            return FactorResult(name=self.name, value=0.0, status="中性")

        ema_short = _ema(closes, 12)
        ema_long = _ema(closes, 26)
        dif_series = [a - b for a, b in zip(ema_short, ema_long)]
        dea_series = _ema(dif_series, 9)
        dif = dif_series[-1]
        dea = dea_series[-1]
        if len(dif_series) < 3:
            return FactorResult(name=self.name, value=round(dif, 4), status="中性")

        prev2_dif = dif_series[-3]
        prev_dif, prev_dea = dif_series[-2], dea_series[-2]

        # T0 反转：零轴下方金叉或 DIF 拐头向上。
        golden_cross = prev_dif <= prev_dea and dif > dea
        dif_turn_up = dif > prev_dif and prev_dif <= prev2_dif

        # 零轴上方回落用于卖点侧判断。
        death_cross = prev_dif >= prev_dea and dif < dea
        dif_turn_down = dif < prev_dif and prev_dif >= prev2_dif

        if golden_cross and dif < 0:
            status = "强"
        elif death_cross and dif > 0:
            status = "弱"
        elif dif_turn_up and dif < 0:
            status = "强"
        elif dif_turn_down and dif > 0:
            status = "弱"
        else:
            status = "中性"

        return FactorResult(name=self.name, value=round(dif, 4), status=status)
