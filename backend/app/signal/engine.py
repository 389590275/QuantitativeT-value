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
        macd_fs = factors.get("macd_fs")

        reasons: list[str] = []

        vwap_bias = vwap.value if vwap else 0.0
        buy_zone = vwap_bias <= -t.buy_zone_pct

        if buy_zone:
            reasons.append(f"低于分时均线{abs(vwap_bias):.2f}%")

        macd_volume_golden = bool(macd_fs and macd_fs.status == "金叉放量")
        macd_golden = bool(macd_fs and macd_fs.status == "金叉")
        macd_unavailable = bool(macd_fs and macd_fs.status == "未预热")
        macd_volume_not_ready = bool(macd_fs and macd_fs.status == "金叉量能未预热")
        macd_volume_weak = bool(macd_fs and macd_fs.status == "金叉量能不足")
        macd_prev_not_shrink = bool(macd_fs and macd_fs.status == "金叉前未缩量")
        macd_buy_ready = macd_volume_golden
        macd_death = bool(macd_fs and macd_fs.status in ("死叉", "弱"))

        if macd_volume_golden:
            reasons.append("1分MACD DIF<-0.07且放量金叉")
        elif macd_volume_not_ready:
            reasons.append("1分MACD金叉，等待5分钟量能均线")
        elif macd_volume_weak:
            reasons.append("1分MACD金叉，成交量未放大")
        elif macd_prev_not_shrink:
            reasons.append("1分MACD金叉，金叉前一根未缩量")
        elif macd_golden:
            reasons.append("1分MACD金叉，等待DIF<-0.07")
        elif macd_unavailable and buy_zone:
            reasons.append("1分MACD未预热，等待金叉")
        elif macd_death:
            reasons.append("1分MACD死叉")

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
                    reasons=reasons[:5] or ["已低于分时均线，等待1分MACD DIF<-0.07且放量金叉"],
                ),
                {},
            )
        return (
            SignalOutput(
                signal="HOLD",
                reasons=reasons[:3] or ["观望"],
            ),
            {},
        )
