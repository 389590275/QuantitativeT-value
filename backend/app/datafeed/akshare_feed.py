from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd

from app.core.config import settings
from app.models.database import get_cached_minute_bars, save_cached_minute_bars
from app.models.schemas import MarketData, OrderBookLevel

logger = logging.getLogger(__name__)

_CACHE_TTL = 60.0


def _symbol_with_prefix(symbol: str) -> str:
    s = symbol.strip()
    if s.startswith(("sh", "sz", "SH", "SZ")):
        return s.lower()
    if s.startswith("6"):
        return f"sh{s}"
    return f"sz{s}"


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


class AkshareDataFeed:
    def __init__(self) -> None:
        self._name_cache: dict[str, str] = {}
        self._prev_close_cache: dict[str, float] = {}
        self._northbound_prev: float | None = None
        self._aux_cache: dict[str, tuple[float, Any]] = {}

    def _cached(self, key: str, fetcher) -> Any:
        now = time.time()
        if key in self._aux_cache:
            ts, val = self._aux_cache[key]
            if now - ts < _CACHE_TTL:
                return val
        val = fetcher()
        self._aux_cache[key] = (now, val)
        return val

    def get_stock_name(self, symbol: str) -> str:
        if symbol in self._name_cache:
            return self._name_cache[symbol]
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            row = df[df["item"] == "股票简称"]
            if not row.empty:
                self._name_cache[symbol] = str(row.iloc[0]["value"])
                return self._name_cache[symbol]
        except Exception as e:
            logger.warning("get_stock_name failed: %s", e)
        return symbol

    def _get_prev_close(self, symbol: str) -> float:
        if symbol in self._prev_close_cache:
            return self._prev_close_cache[symbol]
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            row = df[df["item"] == "昨收"]
            if not row.empty:
                val = _safe_float(row.iloc[0]["value"])
                self._prev_close_cache[symbol] = val
                return val
        except Exception as e:
            logger.warning("prev_close: %s", e)
        return 0.0

    def fetch_quote(self, symbol: str) -> MarketData | None:
        try:
            minute_bars = self._fetch_minute_bars(symbol)
            if not minute_bars:
                minute_bars = self._fetch_minute_bars_alt(symbol)
            if not minute_bars:
                return None
            minute_bars = self._add_intraday_avg(minute_bars)

            last = minute_bars[-1]
            price = _safe_float(last.get("close"))
            volume = _safe_float(last.get("volume"))
            amount = _safe_float(last.get("amount"))
            prev_close = self._get_prev_close(symbol)
            change_pct = (
                (price / prev_close - 1) * 100 if prev_close > 0 else 0.0
            )

            bid1, ask1 = self._fetch_orderbook(symbol, price)
            vwap = self._calc_vwap(minute_bars, price, amount, volume)
            index_hs300, index_cyb = self._cached(
                "index", self._fetch_index_changes
            )
            northbound = self._cached("northbound", self._fetch_northbound)
            sector_chg = self._cached(
                f"etf_{settings.sector_etf}",
                lambda: self._fetch_sector_etf_change(settings.sector_etf),
            )

            highs = [_safe_float(b.get("high"), _safe_float(b.get("close"))) for b in minute_bars]
            lows = [_safe_float(b.get("low"), _safe_float(b.get("close"))) for b in minute_bars]
            return MarketData(
                symbol=symbol,
                name=self.get_stock_name(symbol),
                price=price,
                open=_safe_float(minute_bars[0].get("close")),
                high=max(highs) if highs else price,
                low=min(lows) if lows else price,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
                change_pct=change_pct,
                bid1=bid1,
                ask1=ask1,
                minute_bars=minute_bars,
                vwap=vwap,
                index_hs300_change=index_hs300,
                index_cyb_change=index_cyb,
                northbound_net=northbound,
                sector_etf_change=sector_chg,
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.exception("fetch_quote failed: %s", e)
            return None

    def fetch_history_day(
        self, symbol: str, trade_date: str, refresh_cache: bool = False
    ) -> MarketData | None:
        try:
            minute_bars = [] if refresh_cache else get_cached_minute_bars(symbol, trade_date)
            if not minute_bars:
                minute_bars = self._fetch_minute_bars_for_date(symbol, trade_date)
                minute_bars = self._completed_minute_bars(minute_bars, trade_date)
                if minute_bars:
                    save_cached_minute_bars(symbol, trade_date, minute_bars)
            if not minute_bars:
                return None

            minute_bars = self._add_intraday_avg(minute_bars)
            last = minute_bars[-1]
            price = _safe_float(last.get("close"))
            prev_close = self._get_prev_close_for_date(symbol, trade_date)
            highs = [
                _safe_float(b.get("high"), _safe_float(b.get("close")))
                for b in minute_bars
            ]
            lows = [
                _safe_float(b.get("low"), _safe_float(b.get("close")))
                for b in minute_bars
            ]
            trade_dt = datetime.strptime(trade_date, "%Y-%m-%d")
            timestamp = (
                datetime.now()
                if trade_date == datetime.now().strftime("%Y-%m-%d")
                else trade_dt.replace(hour=15, minute=0, second=0)
            )
            return MarketData(
                symbol=symbol,
                name=self.get_stock_name(symbol),
                price=price,
                open=_safe_float(minute_bars[0].get("open"), _safe_float(minute_bars[0].get("close"))),
                high=max(highs) if highs else price,
                low=min(lows) if lows else price,
                prev_close=prev_close,
                volume=_safe_float(last.get("volume")),
                amount=_safe_float(last.get("amount")),
                change_pct=(price / prev_close - 1) * 100 if prev_close > 0 else 0.0,
                bid1=OrderBookLevel(price=price),
                ask1=OrderBookLevel(price=price),
                minute_bars=minute_bars,
                vwap=_safe_float(last.get("vwap"), price),
                timestamp=timestamp,
            )
        except Exception as e:
            logger.exception("fetch_history_day failed: %s", e)
            return None

    def _fetch_minute_bars(self, symbol: str) -> list[dict[str, Any]]:
        return self._fetch_minute_bars_for_date(
            symbol, datetime.now().strftime("%Y-%m-%d")
        )

    def _fetch_minute_bars_alt(self, symbol: str) -> list[dict[str, Any]]:
        try:
            prefix = _symbol_with_prefix(symbol)
            df = ak.stock_zh_a_minute(symbol=prefix, period="1", adjust="")
            if df is None or df.empty:
                return []
            bars = []
            trade_date = datetime.now().strftime("%Y-%m-%d")
            for _, row in df.iterrows():
                raw_time = str(row.get("day", row.get("datetime", "")))
                if raw_time and not raw_time.startswith(trade_date):
                    continue
                bars.append(
                    {
                        "time": raw_time,
                        "open": _safe_float(row.get("open")),
                        "high": _safe_float(row.get("high")),
                        "low": _safe_float(row.get("low")),
                        "close": _safe_float(row.get("close")),
                        "volume": _safe_float(row.get("volume")),
                        "amount": _safe_float(row.get("amount", 0)),
                    }
                )
            return bars
        except Exception as e:
            logger.warning("minute alt: %s", e)
            return []

    def _fetch_minute_bars_for_date(
        self, symbol: str, trade_date: str
    ) -> list[dict[str, Any]]:
        start = f"{trade_date} 09:30:00"
        end = f"{trade_date} 15:00:00"
        try:
            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                start_date=start,
                end_date=end,
                period="1",
                adjust="",
            )
            bars = self._completed_minute_bars(
                self._bars_from_minute_df(df, trade_date), trade_date
            )
            if bars:
                return bars
        except Exception as e:
            logger.warning("history minute em: %s", e)

        try:
            prefix = _symbol_with_prefix(symbol)
            df = ak.stock_zh_a_minute(symbol=prefix, period="1", adjust="")
            return self._completed_minute_bars(
                self._bars_from_minute_df(df, trade_date), trade_date
            )
        except Exception as e:
            logger.warning("history minute alt: %s", e)
            return []

    def _bars_from_minute_df(
        self, df: pd.DataFrame | None, trade_date: str
    ) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []
        bars: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw_time = str(row.get("时间", row.get("day", row.get("datetime", ""))))
            if not raw_time.startswith(trade_date):
                continue
            bars.append(
                {
                    "time": raw_time,
                    "open": _safe_float(row.get("开盘", row.get("open"))),
                    "high": _safe_float(row.get("最高", row.get("high"))),
                    "low": _safe_float(row.get("最低", row.get("low"))),
                    "close": _safe_float(row.get("收盘", row.get("close"))),
                    "volume": _safe_float(row.get("成交量", row.get("volume"))),
                    "amount": _safe_float(row.get("成交额", row.get("amount", 0))),
                }
            )
        return sorted(bars, key=lambda b: self._bar_datetime_key(b, trade_date))

    def _completed_minute_bars(
        self, bars: list[dict[str, Any]], trade_date: str
    ) -> list[dict[str, Any]]:
        if trade_date != datetime.now().strftime("%Y-%m-%d"):
            return bars
        current_minute = datetime.now().replace(second=0, microsecond=0)
        completed: list[dict[str, Any]] = []
        for bar in bars:
            bar_dt = self._parse_bar_datetime(str(bar.get("time", "")), trade_date)
            if bar_dt is not None and bar_dt < current_minute:
                completed.append(bar)
        return completed

    def _bar_datetime_key(self, bar: dict[str, Any], trade_date: str) -> datetime:
        return self._parse_bar_datetime(str(bar.get("time", "")), trade_date) or datetime.max

    @staticmethod
    def _parse_bar_datetime(raw: str, trade_date: str) -> datetime | None:
        text = str(raw).strip()
        candidates = [text]
        if " " not in text and ":" in text:
            candidates.append(f"{trade_date} {text}")
        for candidate in candidates:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
                try:
                    dt = datetime.strptime(candidate[:19], fmt)
                    if fmt.startswith("%H"):
                        base = datetime.strptime(trade_date, "%Y-%m-%d")
                        return base.replace(hour=dt.hour, minute=dt.minute, second=dt.second)
                    return dt
                except ValueError:
                    continue
        return None

    def _get_prev_close_for_date(self, symbol: str, trade_date: str) -> float:
        try:
            dt = datetime.strptime(trade_date, "%Y-%m-%d")
            start = (dt - timedelta(days=15)).strftime("%Y%m%d")
            end = dt.strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="",
            )
            if df is None or df.empty:
                return 0.0
            rows = df.sort_values("日期")
            current_idx = None
            for i, row in rows.reset_index(drop=True).iterrows():
                if str(row.get("日期"))[:10] == trade_date:
                    current_idx = i
                    break
            if current_idx is not None and current_idx > 0:
                return _safe_float(rows.reset_index(drop=True).iloc[current_idx - 1].get("收盘"))
        except Exception as e:
            logger.warning("history prev_close: %s", e)
        return 0.0

    def _fetch_orderbook(self, symbol: str, price: float) -> tuple[OrderBookLevel, OrderBookLevel]:
        try:
            df = ak.stock_bid_ask_em(symbol=symbol)
            if df is None or df.empty:
                return OrderBookLevel(price=price), OrderBookLevel(price=price)
            buy = df[df["item"] == "buy_1"] if "item" in df.columns else None
            sell = df[df["item"] == "sell_1"] if "item" in df.columns else None
            bid_vol, ask_vol = 0.0, 0.0
            bid_price, ask_price = price, price
            if buy is not None and not buy.empty:
                bid_vol = _safe_float(buy.iloc[0].get("value", 0))
            if sell is not None and not sell.empty:
                ask_vol = _safe_float(sell.iloc[0].get("value", 0))
            return (
                OrderBookLevel(price=bid_price, volume=bid_vol),
                OrderBookLevel(price=ask_price, volume=ask_vol),
            )
        except Exception as e:
            logger.warning("orderbook: %s", e)
            return OrderBookLevel(price=price), OrderBookLevel(price=price)

    def _calc_vwap(
        self, bars: list[dict], price: float, amount: float, volume: float
    ) -> float:
        if bars:
            last_avg = _safe_float(bars[-1].get("vwap"))
            if last_avg > 0:
                return last_avg
        if bars:
            total_amt = sum(_safe_float(b.get("amount")) for b in bars)
            total_vol = sum(_safe_float(b.get("volume")) for b in bars)
            if total_vol > 0 and total_amt > 0:
                return total_amt / total_vol
            closes = [
                _safe_float(b.get("close"))
                for b in bars
                if _safe_float(b.get("close")) > 0
            ]
            if closes:
                return sum(closes) / len(closes)
        if volume > 0 and amount > 0:
            return amount / volume
        return price

    def _add_intraday_avg(self, bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        total_amount = 0.0
        total_volume = 0.0
        fallback_sum = 0.0
        fallback_count = 0
        enriched: list[dict[str, Any]] = []

        for bar in bars:
            item = dict(bar)
            close = _safe_float(item.get("close"))
            volume = _safe_float(item.get("volume"))
            amount = _safe_float(item.get("amount"))

            if close > 0:
                fallback_sum += close
                fallback_count += 1

            if amount <= 0 and volume > 0 and close > 0:
                amount = close * volume

            total_amount += amount
            total_volume += volume

            if total_amount > 0 and total_volume > 0:
                item["vwap"] = total_amount / total_volume
            elif fallback_count > 0:
                item["vwap"] = fallback_sum / fallback_count
            else:
                item["vwap"] = close

            enriched.append(item)

        return enriched

    def _fetch_index_changes(self) -> tuple[float, float]:
        hs300, cyb = 0.0, 0.0
        try:
            idx = ak.stock_zh_index_spot_em()
            for code, attr in [("000300", "hs300"), ("399006", "cyb")]:
                row = idx[idx["代码"] == code]
                if not row.empty:
                    val = _safe_float(row.iloc[0].get("涨跌幅"))
                    if attr == "hs300":
                        hs300 = val
                    else:
                        cyb = val
        except Exception as e:
            logger.warning("index: %s", e)
        return hs300, cyb

    def _fetch_northbound(self) -> float:
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            if df is None or df.empty:
                return 0.0
            col = "value" if "value" in df.columns else df.columns[-1]
            net = _safe_float(df.iloc[-1][col])
            delta = 0.0
            if self._northbound_prev is not None:
                delta = net - self._northbound_prev
            self._northbound_prev = net
            return delta
        except Exception as e:
            logger.warning("northbound: %s", e)
            return 0.0

    def _fetch_sector_etf_change(self, etf_code: str) -> float:
        try:
            df = ak.fund_etf_hist_em(
                symbol=etf_code, period="daily", adjust=""
            )
            if df is not None and len(df) >= 2:
                c0 = _safe_float(df.iloc[-2].get("收盘", 0))
                c1 = _safe_float(df.iloc[-1].get("收盘", 0))
                if c0 > 0:
                    return (c1 / c0 - 1) * 100
        except Exception as e:
            logger.warning("sector etf: %s", e)
        return 0.0
