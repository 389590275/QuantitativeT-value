from __future__ import annotations

from datetime import datetime, time

from app.models.schemas import VwapThresholdsInfo

_DEFAULT_AVG_AMPLITUDE_5D = 0.6
_EXTREME_MULT = 4.0
_BIAS_STATUS_MULT = 1.5

# 早盘 9:50–10:10：低于分时均线触发买点的偏离阈值（%）
_EARLY_SESSION_BUY_PCT = 0.5
_EARLY_SESSION_START = time(9, 50)
_EARLY_SESSION_END = time(10, 10)


def is_early_session_window(at: datetime) -> bool:
    current = at.time()
    return _EARLY_SESSION_START <= current <= _EARLY_SESSION_END


def build_vwap_thresholds(avg_amplitude_5d: float) -> VwapThresholdsInfo:
    """常规时段买点：低于分时均线 五日平均振幅÷3。"""
    avg = avg_amplitude_5d if avg_amplitude_5d > 0 else _DEFAULT_AVG_AMPLITUDE_5D
    buy_pct = avg / 3.0
    return VwapThresholdsInfo(
        avg_amplitude_5d=round(avg, 4),
        buy_zone_pct=round(buy_pct, 4),
        extreme_down_pct=round(buy_pct * _EXTREME_MULT, 4),
        extreme_up_pct=round(buy_pct * _EXTREME_MULT, 4),
        full_deviation_pct=round(buy_pct, 4),
        bias_status_pct=round(buy_pct * _BIAS_STATUS_MULT, 4),
        early_session_active=False,
    )


def resolve_vwap_thresholds(
    base: VwapThresholdsInfo, at: datetime | None = None
) -> VwapThresholdsInfo:
    """早盘窗口内买点阈值固定为低于分时均线 0.5%。"""
    if at is None or not is_early_session_window(at):
        return base.model_copy(update={"early_session_active": False})
    buy_pct = _EARLY_SESSION_BUY_PCT
    return base.model_copy(
        update={
            "buy_zone_pct": round(buy_pct, 4),
            "full_deviation_pct": round(buy_pct, 4),
            "extreme_down_pct": round(buy_pct * _EXTREME_MULT, 4),
            "extreme_up_pct": round(buy_pct * _EXTREME_MULT, 4),
            "bias_status_pct": round(buy_pct * _BIAS_STATUS_MULT, 4),
            "early_session_active": True,
        }
    )


DEFAULT_VWAP_THRESHOLDS = build_vwap_thresholds(_DEFAULT_AVG_AMPLITUDE_5D)
