from __future__ import annotations

from app.models.schemas import FactorResult, SignalOutput, VwapThresholdsInfo
from app.signal.vwap_thresholds import DEFAULT_VWAP_THRESHOLDS


class SignalEngine:
    def evaluate(self, factors: dict[str, FactorResult], price: float) -> SignalOutput:
        signal, _meta = self.evaluate_with_meta(factors, price)
        return signal

    def evaluate_with_meta(
        self,
        factors: dict[str, FactorResult],
        price: float,
        thresholds: VwapThresholdsInfo | None = None,
    ) -> tuple[SignalOutput, dict[str, float]]:
        t = thresholds or DEFAULT_VWAP_THRESHOLDS
        vwap = factors.get("vwap_bias")
        kdj5 = factors.get("kdj_5m")
        macd_fs = factors.get("macd_fs")

        reasons: list[str] = []

        vwap_bias = vwap.value if vwap else 0.0
        buy_zone = vwap_bias <= -t.buy_zone_pct

        if buy_zone:
            reasons.append(f"低于分时均线{abs(vwap_bias):.2f}%")

        kdj_oversold = bool(kdj5 and kdj5.value < 20)
        macd_underwater_golden = bool(macd_fs and macd_fs.status == "水下金叉")
        macd_impending_golden = bool(macd_fs and macd_fs.status == "即将金叉")
        macd_unavailable = bool(macd_fs and macd_fs.status == "未预热")
        macd_buy_ready = macd_underwater_golden or macd_impending_golden or macd_unavailable
        kdj_death = bool(kdj5 and kdj5.status in ("死叉", "弱"))
        macd_death = bool(macd_fs and macd_fs.status in ("死叉", "弱"))
        macd_turn_down = bool(macd_fs and macd_fs.status == "拐头向下")

        if kdj_oversold:
            reasons.append(f"5分钟KDJ J<20（J={kdj5.value:.2f}）")
        elif kdj_death:
            reasons.append("5分钟KDJ死叉")

        if macd_underwater_golden:
            reasons.append("MACDFS水下金叉")
        elif macd_impending_golden:
            reasons.append("MACDFS即将金叉")
        elif macd_unavailable and buy_zone:
            reasons.append("MACDFS未预热，忽略水下条件")
        elif macd_death:
            reasons.append("MACDFS死叉")
        elif macd_turn_down:
            reasons.append("MACDFS即将死叉")

        if buy_zone and (macd_buy_ready or kdj_oversold):
            return (
                SignalOutput(signal="BUY", reasons=reasons[:5]),
                {},
            )
        if kdj_death:
            return (
                SignalOutput(signal="SELL", reasons=reasons[:5]),
                {},
            )
        if macd_death:
            return (
                SignalOutput(signal="SELL", reasons=reasons[:5]),
                {},
            )
        if buy_zone:
            return (
                SignalOutput(
                    signal="WATCH",
                    reasons=reasons[:5] or ["已低于分时均线，等待MACDFS水下金叉/即将金叉或5分钟KDJ J<20"],
                ),
                {},
            )
        if macd_turn_down:
            return (
                SignalOutput(signal="WATCH", reasons=reasons[:5]),
                {},
            )
        return (
            SignalOutput(
                signal="HOLD",
                reasons=reasons[:3] or ["观望"],
            ),
            {},
        )
