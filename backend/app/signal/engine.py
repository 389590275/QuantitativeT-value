from __future__ import annotations

from app.models.schemas import FactorResult, SignalOutput, VwapThresholdsInfo
from app.signal.vwap_thresholds import DEFAULT_VWAP_THRESHOLDS


_MACD_BUY_DIF_THRESHOLD = -0.07


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
        macd_fs = factors.get("macd_fs")

        reasons: list[str] = []

        vwap_bias = vwap.value if vwap else 0.0
        buy_zone = vwap_bias <= -t.buy_zone_pct

        if buy_zone:
            reasons.append(f"低于分时均线{abs(vwap_bias):.2f}%")

        macd_golden = bool(macd_fs and macd_fs.status == "金叉")
        macd_impending_golden = bool(macd_fs and macd_fs.status == "即将金叉")
        macd_unavailable = bool(macd_fs and macd_fs.status == "未预热")
        macd_dif_low = bool(macd_fs and macd_fs.value < _MACD_BUY_DIF_THRESHOLD)
        macd_buy_ready = macd_unavailable or (macd_dif_low and macd_golden)
        macd_death = bool(macd_fs and macd_fs.status in ("死叉", "弱"))
        macd_turn_down = bool(macd_fs and macd_fs.status == "即将死叉")

        if macd_dif_low and macd_golden:
            reasons.append(f"1分MACD DIF<{_MACD_BUY_DIF_THRESHOLD:.2f}且金叉")
        elif macd_dif_low and macd_impending_golden:
            reasons.append("1分MACD即将金叉，等待金叉")
        elif macd_impending_golden:
            reasons.append("1分MACD即将金叉，等待DIF<-0.07且金叉")
        elif macd_golden:
            reasons.append("1分MACD金叉，等待DIF<-0.07")
        elif macd_unavailable and buy_zone:
            reasons.append("1分MACD未预热，忽略MACD条件")
        elif macd_death:
            reasons.append("1分MACD死叉")
        elif macd_turn_down:
            reasons.append("1分MACD即将死叉")

        if buy_zone and macd_buy_ready:
            return (
                SignalOutput(signal="BUY", reasons=reasons[:5]),
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
                    reasons=reasons[:5] or ["已低于分时均线，等待1分MACD DIF<-0.07且金叉"],
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
