"""
JoinQuant version of the three active factors used by this project:

1. VWAP bias
2. 5-minute KDJ
3. MACD fast/slow line difference

Paste this file into a JoinQuant strategy, then change g.security.
Run the backtest with minute frequency for the intraday factors to work.
"""

from datetime import datetime

import pandas as pd


VWAP_WEIGHT = 50.0
KDJ_WEIGHT = 25.0
MACD_WEIGHT = 25.0


def initialize(context):
    set_benchmark("600519.XSHG")
    set_option("use_real_price", True)

    # Change this to the stock you want to backtest, e.g. "000001.XSHE".
    g.security = "600519.XSHG"
    g.bar_count = 260
    g.cash_ratio = 0.95


def handle_data(context, data):
    result = calc_three_factor_signal(g.security, context.current_dt, g.bar_count)
    if result is None:
        return

    signal = result["signal"]
    score = result["score"]
    factors = result["factors"]
    statuses = result["statuses"]

    log.info(
        "%s signal=%s score=%.1f vwap=%.4f/%s kdj=%.2f/%s macd=%.4f/%s"
        % (
            context.current_dt,
            signal,
            score,
            factors["vwap_bias"],
            statuses["vwap_bias"],
            factors["kdj_5m"],
            statuses["kdj_5m"],
            factors["macd_fs"],
            statuses["macd_fs"],
        )
    )

    current_position = context.portfolio.positions[g.security].total_amount
    if signal == "BUY" and current_position == 0:
        order_value(g.security, context.portfolio.available_cash * g.cash_ratio)
    elif signal == "SELL" and current_position > 0:
        order_target(g.security, 0)


def calc_three_factor_signal(security, end_dt, count=260):
    df = get_price(
        security,
        count=count,
        end_date=end_dt,
        frequency="1m",
        fields=["open", "high", "low", "close", "volume", "money"],
        skip_paused=True,
        fq="pre",
    )
    if df is None or df.empty:
        return None

    bars = _minute_bars_from_price_df(df)
    if not bars:
        return None

    price = float(bars[-1]["close"])
    vwap = _intraday_vwap(bars, price)

    vwap_value, vwap_status = calc_vwap_bias(price, vwap)
    kdj_value, kdj_status = calc_kdj_5m(bars)
    macd_value, macd_status = calc_macd_fs(bars)

    signal, score, reasons, factor_scores = evaluate_signal(
        vwap_value,
        vwap_status,
        kdj_value,
        kdj_status,
        macd_value,
        macd_status,
    )

    return {
        "signal": signal,
        "score": score,
        "reasons": reasons,
        "factors": {
            "vwap_bias": vwap_value,
            "kdj_5m": kdj_value,
            "macd_fs": macd_value,
        },
        "statuses": {
            "vwap_bias": vwap_status,
            "kdj_5m": kdj_status,
            "macd_fs": macd_status,
        },
        "factor_scores": factor_scores,
    }


def calc_vwap_bias(price, vwap):
    if vwap <= 0:
        return 0.0, "neutral"

    bias = (price - vwap) / vwap * 100
    if bias <= -0.8:
        status = "low"
    elif bias >= 0.8:
        status = "high"
    elif bias <= -0.3:
        status = "slightly_low"
    elif bias >= 0.3:
        status = "slightly_high"
    else:
        status = "neutral"
    return round(bias, 4), status


def calc_kdj_5m(minute_bars):
    bars_5m = _aggregate_5m_ths(minute_bars)
    if not bars_5m:
        return 0.0, "neutral"

    series = _kdj_ths(bars_5m, n=9)
    cur = series[-1]
    k, d, j = cur["k"], cur["d"], cur["j"]

    if len(series) < 3:
        return round(j, 2), "neutral"

    prev2 = series[-3]
    prev = series[-2]
    prev_k, prev_d, prev_j = prev["k"], prev["d"], prev["j"]
    prev2_j = prev2["j"]

    bottom_level = min(prev2_j, prev_j, j)
    top_level = max(prev2_j, prev_j, j)
    bottom_zone = bottom_level <= 20.0
    top_zone = top_level >= 65.0

    bottom_golden_cross = bottom_zone and prev_k <= prev_d and k > d
    bottom_turn_up = bottom_zone and j > prev_j and prev_j <= prev2_j
    top_death_cross = top_zone and prev_k >= prev_d and k < d
    top_turn_down = top_zone and j < prev_j and prev_j >= prev2_j

    if bottom_golden_cross or bottom_turn_up:
        status = "strong"
    elif top_death_cross or top_turn_down:
        status = "weak"
    else:
        status = "neutral"
    return round(j, 2), status


def calc_macd_fs(minute_bars):
    closes = [_to_float(bar.get("close")) for bar in minute_bars]
    closes = [value for value in closes if value > 0]
    if len(closes) < 37:
        return 0.0, "neutral"

    ema_short = _ema(closes, 12)
    ema_long = _ema(closes, 26)
    dif_series = [a - b for a, b in zip(ema_short, ema_long)]
    dea_series = _ema(dif_series, 9)

    dif = dif_series[-1]
    dea = dea_series[-1]
    prev2_dif = dif_series[-3]
    prev_dif, prev_dea = dif_series[-2], dea_series[-2]

    golden_cross = prev_dif <= prev_dea and dif > dea
    dif_turn_up = dif > prev_dif and prev_dif <= prev2_dif
    death_cross = prev_dif >= prev_dea and dif < dea
    dif_turn_down = dif < prev_dif and prev_dif >= prev2_dif

    if golden_cross and dif < 0:
        status = "strong"
    elif death_cross and dif > 0:
        status = "weak"
    elif dif_turn_up and dif < 0:
        status = "strong"
    elif dif_turn_down and dif > 0:
        status = "weak"
    else:
        status = "neutral"
    return round(dif, 4), status


def evaluate_signal(vwap_bias, vwap_status, kdj_value, kdj_status, macd_value, macd_status):
    long_score = 0.0
    short_score = 0.0
    factor_scores = {
        "vwap_bias": 0.0,
        "kdj_5m": 0.0,
        "macd_fs": 0.0,
    }
    reasons = []
    buy_points = 0
    sell_points = 0

    buy_zone = vwap_bias <= -0.2
    sell_ready = vwap_bias >= -0.2
    above_avg = vwap_bias > 0
    extreme_down = vwap_bias <= -0.8
    extreme_up = vwap_bias >= 0.8

    if vwap_status:
        buy_deviation_score = _abs_strength(abs(vwap_bias), 0.2, 1.2, VWAP_WEIGHT)
        sell_deviation_score = _abs_strength(max(vwap_bias + 0.2, 0), 0.0, 1.2, VWAP_WEIGHT)
        if buy_zone:
            buy_points += 1
            long_score += buy_deviation_score
            factor_scores["vwap_bias"] += buy_deviation_score
            reasons.append("below VWAP %.2f%%" % abs(vwap_bias))
            if extreme_down:
                buy_points += 1
                reasons.append("VWAP oversold")
        elif sell_ready:
            sell_points += 1
            if above_avg:
                contribution = max(15.0, sell_deviation_score)
                short_score += contribution
                factor_scores["vwap_bias"] -= contribution
                reasons.append("above VWAP %.2f%%" % vwap_bias)
            else:
                contribution = 15.0
                short_score += contribution
                factor_scores["vwap_bias"] -= contribution
                reasons.append("near VWAP %.2f%%" % vwap_bias)
            if extreme_up:
                sell_points += 1
                reasons.append("VWAP overbought")

    if kdj_status == "strong":
        buy_points += 1
        long_score += KDJ_WEIGHT
        factor_scores["kdj_5m"] += KDJ_WEIGHT
        reasons.append("5m KDJ bottom cross/turn")
    elif kdj_status == "weak":
        sell_points += 1
        short_score += KDJ_WEIGHT
        factor_scores["kdj_5m"] -= KDJ_WEIGHT
        reasons.append("5m KDJ top cross/turn")

    if macd_status == "strong":
        buy_points += 1
        long_score += MACD_WEIGHT
        factor_scores["macd_fs"] += MACD_WEIGHT
        reasons.append("MACD bottom cross/turn")
    elif macd_status == "weak":
        sell_points += 1
        short_score += MACD_WEIGHT
        factor_scores["macd_fs"] -= MACD_WEIGHT
        reasons.append("MACD top cross/turn")

    long_score = max(0.0, min(100.0, long_score))
    short_score = max(0.0, min(100.0, short_score))
    score = long_score if long_score >= short_score else 100.0 - short_score

    if buy_points >= 3 and long_score >= 75 and buy_zone:
        return "BUY", round(long_score, 1), reasons[:5], factor_scores
    if sell_points >= 3 and short_score >= 75 and sell_ready:
        return "SELL", round(100.0 - short_score, 1), reasons[:5], factor_scores
    if buy_points >= 2 and long_score >= 55 and buy_zone:
        return "WATCH", round(long_score, 1), reasons[:5], factor_scores
    if sell_points >= 2 and short_score >= 55 and sell_ready:
        return "WATCH", round(100.0 - short_score, 1), reasons[:5], factor_scores
    return "HOLD", round(score, 1), reasons[:3] or ["wait"], factor_scores


def _minute_bars_from_price_df(df):
    bars = []
    for dt, row in df.iterrows():
        close = _to_float(row.get("close"))
        if close <= 0:
            continue
        bars.append(
            {
                "time": _format_time(dt),
                "open": _to_float(row.get("open"), close),
                "high": _to_float(row.get("high"), close),
                "low": _to_float(row.get("low"), close),
                "close": close,
                "volume": _to_float(row.get("volume")),
                "amount": _to_float(row.get("money")),
            }
        )
    return bars


def _intraday_vwap(bars, fallback_price):
    if not bars:
        return fallback_price

    last_day = str(bars[-1]["time"])[:10]
    total_amount = 0.0
    total_volume = 0.0
    close_sum = 0.0
    close_count = 0
    for bar in bars:
        if str(bar["time"])[:10] != last_day:
            continue
        close = _to_float(bar.get("close"))
        volume = _to_float(bar.get("volume"))
        amount = _to_float(bar.get("amount"))
        if amount <= 0 and volume > 0 and close > 0:
            amount = close * volume
        total_amount += amount
        total_volume += volume
        if close > 0:
            close_sum += close
            close_count += 1

    if total_amount > 0 and total_volume > 0:
        return total_amount / total_volume
    if close_count > 0:
        return close_sum / close_count
    return fallback_price


def _aggregate_5m_ths(bars):
    buckets = {}
    order = []
    for bar in bars:
        close = _to_float(bar.get("close"))
        if close <= 0:
            continue
        clock_min = _bar_clock_minutes(str(bar.get("time", "")))
        if clock_min is None:
            continue
        key = _session_5m_bucket(clock_min)
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
        else:
            bucket = buckets[key]
            bucket["high"] = max(bucket["high"], high)
            bucket["low"] = min(bucket["low"], low)
            bucket["close"] = close
    return [buckets[key] for key in sorted(order)]


def _kdj_ths(bars, n=9):
    k = 50.0
    d = 50.0
    series = []
    for i in range(len(bars)):
        start = max(0, i - (n - 1))
        window = bars[start : i + 1]
        low_n = min(_to_float(bar.get("low")) for bar in window)
        high_n = max(_to_float(bar.get("high")) for bar in window)
        close = _to_float(bars[i].get("close"))
        rsv = 50.0 if high_n == low_n else (close - low_n) / (high_n - low_n) * 100.0
        k = (2.0 / 3.0) * k + (1.0 / 3.0) * rsv
        d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
        j = 3.0 * k - 2.0 * d
        series.append({"k": k, "d": d, "j": j})
    return series


def _ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def _abs_strength(value, start, full, max_score):
    if value <= start:
        return 0.0
    if full <= start:
        return max_score
    ratio = min(1.0, (value - start) / (full - start))
    return ratio * max_score


def _bar_clock_minutes(time_str):
    s = str(time_str).strip()
    if " " in s:
        s = s.split(" ")[-1]
    if len(s) >= 5 and ":" in s:
        parts = s[:8].split(":")
        return int(parts[0]) * 60 + int(parts[1])
    return None


def _session_5m_bucket(total_min):
    morning_start = 9 * 60 + 30
    morning_end = 11 * 60 + 30
    afternoon_start = 13 * 60
    afternoon_end = 15 * 60
    if morning_start <= total_min <= morning_end:
        return morning_start + ((total_min - morning_start) // 5) * 5
    if afternoon_start <= total_min <= afternoon_end:
        return afternoon_start + ((total_min - afternoon_start) // 5) * 5
    return None


def _format_time(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _to_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default
