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

        kdj_strong = bool(kdj5 and kdj5.status == "强")
        macd_strong = bool(macd_fs and macd_fs.status == "强")
        kdj_death = bool(kdj5 and kdj5.status in ("死叉", "弱"))
        macd_death = bool(macd_fs and macd_fs.status in ("死叉", "弱"))
        kdj_turn_down = bool(kdj5 and kdj5.status == "拐头向下")
        macd_turn_down = bool(macd_fs and macd_fs.status == "拐头向下")

        if kdj_strong:
            reasons.append("5分钟KDJ底部金叉/拐头")
        elif kdj_death:
            reasons.append("5分钟KDJ死叉")
        elif kdj_turn_down:
            reasons.append("5分钟KDJ拐头向下")

        if macd_strong:
            reasons.append("MACD底部金叉/拐头")
        elif macd_death:
            reasons.append("MACD死叉")
        elif macd_turn_down:
            reasons.append("MACD拐头向下")

        if buy_zone and (macd_strong or kdj_strong):
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
                    reasons=reasons[:5] or ["已低于分时均线，等待KDJ/MACD金叉或拐头"],
                ),
                {},
            )
        if kdj_turn_down or macd_turn_down:
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
