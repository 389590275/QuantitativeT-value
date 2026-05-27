from app.models.schemas import FactorResult, SignalOutput


VWAP_WEIGHT = 50.0
KDJ_WEIGHT = 25.0
MACD_WEIGHT = 25.0


def _abs_strength(value: float, start: float, full: float, max_score: float) -> float:
    """Map an absolute deviation to a bounded score contribution."""
    if value <= start:
        return 0.0
    if full <= start:
        return max_score
    ratio = min(1.0, (value - start) / (full - start))
    return ratio * max_score


class SignalEngine:
    def evaluate(self, factors: dict[str, FactorResult], price: float) -> SignalOutput:
        signal, _factor_scores = self.evaluate_with_scores(factors, price)
        return signal

    def evaluate_with_scores(
        self, factors: dict[str, FactorResult], price: float
    ) -> tuple[SignalOutput, dict[str, float]]:
        vwap = factors.get("vwap_bias")
        kdj5 = factors.get("kdj_5m")
        macd_fs = factors.get("macd_fs")

        long_score = 0.0
        short_score = 0.0
        factor_scores: dict[str, float] = {
            "vwap_bias": 0.0,
            "kdj_5m": 0.0,
            "macd_fs": 0.0,
        }
        reasons: list[str] = []
        buy_points = 0
        sell_points = 0

        vwap_bias = vwap.value if vwap else 0.0
        buy_zone = vwap_bias <= -0.2
        sell_ready = vwap_bias >= -0.2
        above_avg = vwap_bias > 0
        extreme_down = vwap_bias <= -0.8
        extreme_up = vwap_bias >= 0.8

        if vwap:
            buy_deviation_score = _abs_strength(
                abs(vwap_bias), 0.2, 1.2, VWAP_WEIGHT
            )
            sell_deviation_score = _abs_strength(
                max(vwap_bias + 0.2, 0), 0.0, 1.2, VWAP_WEIGHT
            )
            if buy_zone:
                buy_points += 1
                long_score += buy_deviation_score
                factor_scores["vwap_bias"] += buy_deviation_score
                reasons.append(f"低于分时均线{abs(vwap_bias):.2f}%")
                if extreme_down:
                    buy_points += 1
                    reasons.append("分时超跌反转概率提高")
            elif sell_ready:
                sell_points += 1
                if above_avg:
                    contribution = max(15.0, sell_deviation_score)
                    short_score += contribution
                    factor_scores["vwap_bias"] -= contribution
                    reasons.append(f"高于分时均线{vwap_bias:.2f}%")
                else:
                    contribution = 15.0
                    short_score += contribution
                    factor_scores["vwap_bias"] -= contribution
                    reasons.append(f"接近分时均线{vwap_bias:.2f}%")
                if extreme_up:
                    sell_points += 1
                    reasons.append("分时超涨回落概率提高")

        if kdj5:
            if kdj5.status == "强":
                buy_points += 1
                reasons.append("5分钟KDJ底部金叉/拐头")
                long_score += KDJ_WEIGHT
                factor_scores["kdj_5m"] += KDJ_WEIGHT
            elif kdj5.status == "弱":
                sell_points += 1
                reasons.append("5分钟KDJ顶部死叉/拐头")
                short_score += KDJ_WEIGHT
                factor_scores["kdj_5m"] -= KDJ_WEIGHT

        if macd_fs:
            if macd_fs.status == "强":
                buy_points += 1
                reasons.append("MACD底部金叉/拐头")
                long_score += MACD_WEIGHT
                factor_scores["macd_fs"] += MACD_WEIGHT
            elif macd_fs.status == "弱":
                sell_points += 1
                reasons.append("MACD顶部死叉/拐头")
                short_score += MACD_WEIGHT
                factor_scores["macd_fs"] -= MACD_WEIGHT

        long_score = max(0.0, min(100.0, long_score))
        short_score = max(0.0, min(100.0, short_score))
        score = long_score if long_score >= short_score else 100.0 - short_score

        if buy_points >= 3 and long_score >= 75 and buy_zone:
            return (
                SignalOutput(signal="BUY", score=round(long_score, 1), reasons=reasons[:5]),
                factor_scores,
            )
        if sell_points >= 3 and short_score >= 75 and sell_ready:
            return (
                SignalOutput(signal="SELL", score=round(100.0 - short_score, 1), reasons=reasons[:5]),
                factor_scores,
            )
        if buy_points >= 2 and long_score >= 55 and buy_zone:
            return (
                SignalOutput(signal="WATCH", score=round(long_score, 1), reasons=reasons[:5]),
                factor_scores,
            )
        if sell_points >= 2 and short_score >= 55 and sell_ready:
            return (
                SignalOutput(signal="WATCH", score=round(100.0 - short_score, 1), reasons=reasons[:5]),
                factor_scores,
            )
        return (
            SignalOutput(signal="HOLD", score=round(score, 1), reasons=reasons[:3] or ["观望"]),
            factor_scores,
        )
