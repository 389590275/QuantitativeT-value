from __future__ import annotations

from datetime import datetime

from app.models.schemas import VwapThresholdsInfo

_DEFAULT_AVG_AMPLITUDE_5D = 0.6
_FIXED_BUY_PCT = 0.5
_EXTREME_MULT = 4.0
_BIAS_STATUS_MULT = 1.5


def _build_fixed_thresholds(avg_amplitude_5d: float) -> VwapThresholdsInfo:
    buy_pct = _FIXED_BUY_PCT
    return VwapThresholdsInfo(
        avg_amplitude_5d=round(avg_amplitude_5d, 4),
        buy_zone_pct=round(buy_pct, 4),
        extreme_down_pct=round(buy_pct * _EXTREME_MULT, 4),
        extreme_up_pct=round(buy_pct * _EXTREME_MULT, 4),
        full_deviation_pct=round(buy_pct, 4),
        bias_status_pct=round(buy_pct * _BIAS_STATUS_MULT, 4),
        early_session_active=False,
    )


def build_vwap_thresholds(avg_amplitude_5d: float) -> VwapThresholdsInfo:
    """买点固定：低于分时均线 0.5%。"""
    avg = avg_amplitude_5d if avg_amplitude_5d > 0 else _DEFAULT_AVG_AMPLITUDE_5D
    return _build_fixed_thresholds(avg)


def resolve_vwap_thresholds(
    base: VwapThresholdsInfo, at: datetime | None = None
) -> VwapThresholdsInfo:
    """保留调用入口；当前不再按时间切换阈值。"""
    return _build_fixed_thresholds(base.avg_amplitude_5d)


DEFAULT_VWAP_THRESHOLDS = build_vwap_thresholds(_DEFAULT_AVG_AMPLITUDE_5D)
