from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, time, timedelta

from app.core.config import settings
from app.datafeed.akshare_feed import AkshareDataFeed
from app.factor.engine import FactorEngine
from app.models.database import (
    clear_day_data,
    get_signal_marks,
    init_db,
    insert_signal,
    insert_tick,
)
from app.models.schemas import MarketData, RealtimePayload, SignalOutput
from app.notify.desktop import send_desktop_notification
from app.notify.wecom import send_wecom
from app.signal.engine import SignalEngine
from app.signal.t0_pairer import T0SignalPairer

logger = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self) -> None:
        self.symbol = settings.symbol
        self.trade_date = datetime.now().strftime("%Y-%m-%d")
        self.datafeed = AkshareDataFeed()
        self.factor_engine = FactorEngine()
        self.signal_engine = SignalEngine()
        self.t0_pairer = T0SignalPairer()
        init_db()
        self._subscribers: list[asyncio.Queue] = []
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tick_history: list[dict] = []
        self._factor_snapshots: dict[str, dict] = {}
        self._latest: RealtimePayload | None = None
        self._last_offhours_replay_at: datetime | None = None
        self._last_offhours_payload_key: tuple[str, str, int] | None = None
        self._calc_lock = threading.RLock()
        self._restore_t0_state()

    def _restore_t0_state(self, trade_date: str | None = None) -> None:
        date_key = trade_date or self.trade_date
        marks = get_signal_marks(self.symbol, date_key)
        self.t0_pairer.restore_from_marks(
            date_key, marks
        )

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def set_symbol(self, symbol: str) -> dict:
        self.symbol = symbol.strip()
        self._tick_history.clear()
        self._factor_snapshots.clear()
        self._latest = None
        self._last_offhours_replay_at = None
        self._last_offhours_payload_key = None
        self._restore_t0_state()
        name = await asyncio.to_thread(self.datafeed.get_stock_name, self.symbol)
        if self.trade_date != self._today():
            await self.load_trade_date(self.trade_date)
        return {"symbol": self.symbol, "name": name}

    async def load_trade_date(self, trade_date: str) -> dict:
        self.trade_date = trade_date
        replayed = await asyncio.to_thread(self._load_trade_date_sync, trade_date)
        await self._broadcast(self._latest)
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "replayed_points": replayed,
            "no_data": replayed == 0,
            "buy_count": self.t0_pairer.buy_count,
            "sell_count": self.t0_pairer.sell_count,
            "t0_position": self.t0_pairer.position,
        }

    async def shift_trade_date(self, offset: int, base_trade_date: str | None = None) -> dict:
        date_key = base_trade_date or self.trade_date
        next_trade_date = await asyncio.to_thread(
            self.datafeed.find_shifted_trade_date,
            self.symbol,
            date_key,
            offset,
        )
        if not next_trade_date:
            return {
                "symbol": self.symbol,
                "trade_date": self.trade_date,
                "replayed_points": 0,
                "no_data": True,
                "message": "未找到可切换的交易日",
                "buy_count": self.t0_pairer.buy_count,
                "sell_count": self.t0_pairer.sell_count,
                "t0_position": self.t0_pairer.position,
            }
        return await self.load_trade_date(next_trade_date)

    async def clear_and_recalculate(self, trade_date: str | None = None) -> dict:
        date_key = trade_date or self.trade_date
        self.trade_date = date_key
        deleted, replayed = await asyncio.to_thread(
            self._clear_recalculate_sync,
            date_key,
            False,
            "未获取到该交易日分钟数据，未计算买卖点",
        )
        await self._broadcast(self._latest)
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "deleted": deleted,
            "replayed_points": replayed,
            "no_data": replayed == 0,
            "buy_count": self.t0_pairer.buy_count,
            "sell_count": self.t0_pairer.sell_count,
            "t0_position": self.t0_pairer.position,
        }

    async def refresh_cache_and_recalculate(self, trade_date: str | None = None) -> dict:
        date_key = trade_date or self.trade_date
        self.trade_date = date_key
        deleted, replayed = await asyncio.to_thread(
            self._clear_recalculate_sync,
            date_key,
            True,
            "刷新行情缓存失败，未计算买卖点",
        )
        await self._broadcast(self._latest)
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "deleted": deleted,
            "replayed_points": replayed,
            "no_data": replayed == 0,
            "cache_refreshed": replayed > 0,
            "buy_count": self.t0_pairer.buy_count,
            "sell_count": self.t0_pairer.sell_count,
            "t0_position": self.t0_pairer.position,
        }

    def _load_trade_date_sync(self, trade_date: str) -> int:
        with self._calc_lock:
            self._tick_history.clear()
            self._factor_snapshots.clear()
            self._latest = None
            self.t0_pairer.reset_day(trade_date)
            replayed = self._recalculate_history_locked(trade_date, False)
            if self._latest is None:
                self._latest = self._empty_payload(
                    trade_date, "未获取到该交易日分钟数据，未计算买卖点"
                )
            return replayed

    def _clear_recalculate_sync(
        self, trade_date: str, refresh_cache: bool, no_data_reason: str
    ) -> tuple[dict, int]:
        with self._calc_lock:
            deleted = clear_day_data(self.symbol, trade_date)
            self._tick_history.clear()
            self._factor_snapshots.clear()
            self._latest = None
            self.t0_pairer.reset_day(trade_date)
            replayed = self._recalculate_history_locked(trade_date, refresh_cache)
            if self._latest is None:
                self._latest = self._empty_payload(trade_date, no_data_reason)
            return deleted, replayed

    def _recalculate_history(self, trade_date: str, refresh_cache: bool = False) -> int:
        with self._calc_lock:
            return self._recalculate_history_locked(trade_date, refresh_cache)

    def _recalculate_history_locked(self, trade_date: str, refresh_cache: bool = False) -> int:
        md = self.datafeed.fetch_history_day(
            self.symbol, trade_date, refresh_cache=refresh_cache
        )
        if md is None or not md.minute_bars:
            return 0

        self._tick_history = []
        self._factor_snapshots = {}
        self.t0_pairer.reset_day(trade_date)

        latest_signal = SignalOutput()
        latest_factors: dict[str, float] = {}
        latest_factor_status: dict[str, str] = {}

        for i, bar in enumerate(md.minute_bars):
            price = float(bar.get("close", 0) or 0)
            if price <= 0:
                continue
            time_key = self._normalize_point_time(str(bar.get("time", "")))
            partial_bars = md.minute_bars[: i + 1]
            replay_md = self._build_replay_market_data(md, partial_bars, bar, price)

            self._tick_history.append(
                {"price": price, "time": time_key or replay_md.timestamp.isoformat()}
            )
            if len(self._tick_history) > 100:
                self._tick_history = self._tick_history[-100:]
            replay_md.tick_history = list(self._tick_history)

            if self._market_data_is_synthetic(replay_md):
                factors = {}
                factor_scores = {}
                raw_signal = SignalOutput(
                    signal="HOLD",
                    score=50.0,
                    reasons=["分钟数据源不可用，使用日线估算分时展示"],
                )
            else:
                factors = self.factor_engine.run(replay_md)
                raw_signal, factor_scores = self.signal_engine.evaluate_with_scores(
                    factors, price
                )
            decision = self.t0_pairer.apply(raw_signal, price, time_key, replay_md.timestamp)
            latest_signal = decision.display_signal
            latest_factors = {k: v.value for k, v in factors.items()}
            latest_factor_status = {k: v.status for k, v in factors.items()}

            self._factor_snapshots[time_key] = {
                "factors": latest_factors,
                "factor_status": latest_factor_status,
                "factor_scores": factor_scores,
                "signal": latest_signal.signal,
                "score": latest_signal.score,
                "reasons": latest_signal.reasons,
            }

            for persisted in decision.persist_signals or []:
                self._persist_signal(
                    replay_md,
                    SignalOutput(
                        signal=str(persisted["signal"]),
                        score=float(persisted.get("score", latest_signal.score)),
                        reasons=latest_signal.reasons,
                    ),
                    price=float(persisted.get("price", price)),
                )
            insert_tick(replay_md.symbol, replay_md.price, replay_md.volume, replay_md.timestamp)

        minute_points = [self._build_minute_point(b) for b in md.minute_bars]
        if not minute_points:
            self._latest = self._empty_payload(
                trade_date, "未获取到有效行情数据，暂不计算买卖点"
            )
            return 0
        self._latest = RealtimePayload(
            symbol=md.symbol,
            name=md.name,
            trade_date=trade_date,
            price=md.price,
            change_pct=md.change_pct,
            signal=latest_signal.signal,
            score=latest_signal.score,
            reasons=latest_signal.reasons,
            factors=latest_factors,
            factor_status=latest_factor_status,
            factor_scores=self._factor_snapshots.get(
                self._normalize_point_time(str(md.minute_bars[-1].get("time", ""))),
                {},
            ).get("factor_scores", {}),
            vwap=md.vwap,
            minute_points=minute_points,
            signal_marks=self.t0_pairer.marks,
            pending_buy=self.t0_pairer.pending_buy,
            t0_position=self.t0_pairer.position,
            buy_count=self.t0_pairer.buy_count,
            sell_count=self.t0_pairer.sell_count,
            data_status="synthetic" if self._market_data_is_synthetic(md) else "ok",
        )
        return len(md.minute_bars)

    def get_status(self) -> dict:
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "running": self._running,
            "buy_count": self.t0_pairer.buy_count,
            "sell_count": self.t0_pairer.sell_count,
            "t0_position": self.t0_pairer.position,
            "latest": self._latest.model_dump(mode="json") if self._latest else None,
        }

    def _empty_payload(self, trade_date: str, reason: str) -> RealtimePayload:
        return RealtimePayload(
            symbol=self.symbol,
            name=self.symbol,
            trade_date=trade_date,
            signal="HOLD",
            score=50.0,
            reasons=[reason],
            minute_points=[],
            signal_marks=[],
            pending_buy=None,
            t0_position="flat",
            buy_count=0,
            sell_count=0,
            data_status="loading",
        )

    async def start(self) -> None:
        if self._running:
            return
        self._loop = asyncio.get_running_loop()
        self._running = True
        asyncio.create_task(self._loop_task())

    async def stop(self) -> None:
        self._running = False

    async def _loop_task(self) -> None:
        while self._running:
            try:
                await asyncio.to_thread(self._tick_sync)
            except Exception as e:
                logger.exception("engine tick: %s", e)
            await asyncio.sleep(settings.quote_interval)

    def _tick_sync(self) -> None:
        if not self._calc_lock.acquire(blocking=False):
            return
        try:
            self._tick_sync_locked()
        finally:
            self._calc_lock.release()

    def _tick_sync_locked(self) -> None:
        if self.trade_date != self._today():
            return
        md = self.datafeed.fetch_quote(self.symbol)
        if md is None:
            if self._is_trading_time(datetime.now()):
                self._publish_loading_payload_locked("行情加载中，暂不计算买卖点")
            else:
                self._publish_offhours_snapshot_locked()
            return
        if self._loop is None:
            return

        if self._latest and self._latest.trade_date != self.trade_date:
            self._tick_history.clear()
            self._factor_snapshots.clear()
            self._restore_t0_state(self.trade_date)
        self._last_offhours_replay_at = None
        self._last_offhours_payload_key = None

        self._tick_history.append(
            {"price": md.price, "time": md.timestamp.isoformat()}
        )
        if len(self._tick_history) > 100:
            self._tick_history = self._tick_history[-100:]
        md.tick_history = list(self._tick_history)

        if self._market_data_is_synthetic(md):
            factors = {}
            factor_scores = {}
            raw_signal = SignalOutput(
                signal="HOLD",
                score=50.0,
                reasons=["分钟数据源不可用，使用日线估算分时展示"],
            )
        else:
            factors = self.factor_engine.run(md)
            raw_signal, factor_scores = self.signal_engine.evaluate_with_scores(
                factors, md.price
            )
        if not self._is_trading_time(md.timestamp):
            raw_signal = SignalOutput(
                signal="HOLD",
                score=50.0,
                reasons=["休盘时间不触发买卖点"],
            )

        bar_time = ""
        if md.minute_bars:
            bar_time = str(md.minute_bars[-1].get("time", ""))

        decision = self.t0_pairer.apply(
            raw_signal, md.price, bar_time, md.timestamp
        )
        signal = decision.display_signal

        factor_values = {k: v.value for k, v in factors.items()}
        factor_status = {k: v.status for k, v in factors.items()}

        latest_point_time = self._normalize_point_time(bar_time or md.timestamp.strftime("%H:%M:%S"))
        self._factor_snapshots[latest_point_time] = {
            "factors": factor_values,
            "factor_status": factor_status,
            "factor_scores": factor_scores,
            "signal": signal.signal,
            "score": signal.score,
            "reasons": signal.reasons,
        }
        if len(self._factor_snapshots) > 260:
            keep_keys = list(self._factor_snapshots.keys())[-260:]
            self._factor_snapshots = {k: self._factor_snapshots[k] for k in keep_keys}

        minute_points = [
            self._build_minute_point(b)
            for b in md.minute_bars
        ]
        if minute_points:
            minute_points[-1]["price"] = md.price
            minute_points[-1].update(self._factor_snapshots.get(latest_point_time, {}))

        has_notification = decision.notify_signal is not None
        for persisted in decision.persist_signals or []:
            self._persist_signal(
                md,
                SignalOutput(
                    signal=str(persisted["signal"]),
                    score=float(persisted.get("score", signal.score)),
                    reasons=signal.reasons,
                ),
                price=float(persisted.get("price", md.price)),
            )

        if has_notification and decision.notify_signal:
            send_desktop_notification(
                f"{md.name} {decision.notify_signal.signal}",
                f"价格: {md.price} | 强度: {decision.notify_signal.score}\n"
                f"今日买{self.t0_pairer.buy_count}/卖{self.t0_pairer.sell_count}\n"
                f"{', '.join(decision.notify_signal.reasons)}",
            )

        payload = RealtimePayload(
            symbol=md.symbol,
            name=md.name,
            trade_date=self.trade_date,
            price=md.price,
            change_pct=md.change_pct,
            signal=signal.signal,
            score=signal.score,
            reasons=signal.reasons,
            factors=factor_values,
            factor_status=factor_status,
            factor_scores=factor_scores,
            vwap=md.vwap,
            minute_points=minute_points,
            signal_marks=self.t0_pairer.marks,
            pending_buy=self.t0_pairer.pending_buy,
            t0_position=self.t0_pairer.position,
            buy_count=self.t0_pairer.buy_count,
            sell_count=self.t0_pairer.sell_count,
            data_status="synthetic" if self._market_data_is_synthetic(md) else "ok",
        )
        self._latest = payload

        insert_tick(md.symbol, md.price, md.volume)

        asyncio.run_coroutine_threadsafe(
            self._post_tick(payload, has_notification), self._loop
        )

    def _publish_loading_payload_locked(self, reason: str) -> None:
        if self._loop is None:
            return
        payload = self._empty_payload(self.trade_date, reason)
        payload.name = self._latest.name if self._latest else self.symbol
        payload.data_status = "loading"
        self._latest = payload
        asyncio.run_coroutine_threadsafe(
            self._post_tick(payload, False), self._loop
        )

    def _publish_offhours_snapshot_locked(self) -> None:
        if self._loop is None:
            return

        now = datetime.now()
        if self._is_trading_time(now):
            return

        needs_history = (
            self._latest is None
            or self._latest.symbol != self.symbol
            or not self._latest.minute_points
            or (self._latest.trade_date != self.trade_date and now.weekday() < 5)
        )
        can_retry = (
            self._last_offhours_replay_at is None
            or (now - self._last_offhours_replay_at).total_seconds() >= 60
        )
        if needs_history and can_retry:
            self._last_offhours_replay_at = now
            self._load_latest_available_history_locked(now)

        if self._latest is None:
            return

        payload_key = (
            self._latest.symbol,
            self._latest.trade_date,
            len(self._latest.minute_points),
        )
        if payload_key == self._last_offhours_payload_key:
            return

        self._last_offhours_payload_key = payload_key
        asyncio.run_coroutine_threadsafe(
            self._post_tick(self._latest, False), self._loop
        )

    def _load_latest_available_history_locked(self, now: datetime) -> None:
        original_trade_date = self.trade_date
        for days_back in range(0, 16):
            candidate = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
            self._tick_history.clear()
            self._factor_snapshots.clear()
            self._latest = None
            if self._recalculate_history_locked(candidate, False) > 0:
                return

        self._tick_history.clear()
        self._factor_snapshots.clear()
        self._latest = self._empty_payload(
            original_trade_date,
            "非交易时段未获取到最近可用分钟数据",
        )

    def _persist_signal(self, md, signal: SignalOutput, price: float | None = None) -> None:
        insert_signal(
            md.symbol,
            signal.signal,
            signal.score,
            md.price if price is None else price,
            md.timestamp,
        )

    def _build_replay_market_data(
        self,
        source: MarketData,
        partial_bars: list[dict],
        current_bar: dict,
        price: float,
    ) -> MarketData:
        closes = [float(b.get("close", 0) or 0) for b in partial_bars]
        highs = [float(b.get("high", b.get("close", 0)) or 0) for b in partial_bars]
        lows = [float(b.get("low", b.get("close", 0)) or 0) for b in partial_bars]
        return MarketData(
            symbol=source.symbol,
            name=source.name,
            price=price,
            open=float(partial_bars[0].get("open", partial_bars[0].get("close", price)) or price),
            high=max(highs) if highs else price,
            low=min(lows) if lows else price,
            prev_close=source.prev_close,
            volume=float(current_bar.get("volume", 0) or 0),
            amount=float(current_bar.get("amount", 0) or 0),
            change_pct=(price / source.prev_close - 1) * 100 if source.prev_close > 0 else None,
            bid1=source.bid1,
            ask1=source.ask1,
            minute_bars=partial_bars,
            vwap=float(current_bar.get("vwap", price) or price),
            index_hs300_change=source.index_hs300_change,
            index_cyb_change=source.index_cyb_change,
            northbound_net=source.northbound_net,
            sector_etf_change=source.sector_etf_change,
            timestamp=self._datetime_from_point_time(
                str(current_bar.get("time", "")), source.timestamp
            ),
        )

    @staticmethod
    def _market_data_is_synthetic(md: MarketData) -> bool:
        return bool(md.minute_bars) and all(bool(b.get("synthetic")) for b in md.minute_bars)

    def _build_minute_point(self, bar: dict) -> dict:
        time_key = self._normalize_point_time(str(bar.get("time", "")))
        point = {
            "time": time_key,
            "price": bar.get("close", 0),
            "vwap": bar.get("vwap", bar.get("close", 0)),
        }
        snapshot = self._factor_snapshots.get(time_key)
        if snapshot:
            point.update(snapshot)
        return point

    @staticmethod
    def _normalize_point_time(raw: str) -> str:
        part = str(raw).strip().split()[-1] if raw else ""
        if ":" not in part:
            return part
        if len(part) >= 8:
            return part[:8]
        if len(part) == 5:
            return f"{part}:00"
        return part

    @staticmethod
    def _is_trading_time(now: datetime) -> bool:
        if now.weekday() >= 5:
            return False
        current = now.time()
        return (
            time(9, 30) <= current <= time(11, 30)
            or time(13, 0) <= current <= time(15, 0)
        )

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _datetime_from_point_time(self, raw: str, fallback: datetime) -> datetime:
        time_key = self._normalize_point_time(raw)
        try:
            parts = [int(p) for p in time_key.split(":")]
            if len(parts) >= 2:
                hour = parts[0]
                minute = parts[1]
                second = parts[2] if len(parts) >= 3 else 0
                return fallback.replace(hour=hour, minute=minute, second=second, microsecond=0)
        except (TypeError, ValueError):
            pass
        return fallback

    async def _post_tick(self, payload: RealtimePayload, is_new_signal: bool) -> None:
        await self._broadcast(payload)
        if is_new_signal and payload.signal in ("BUY", "SELL"):
            await self._notify_wecom(payload)

    async def _broadcast(self, payload: RealtimePayload) -> None:
        data = payload.model_dump(mode="json")
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(data)
                except Exception:
                    dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    async def _notify_wecom(self, payload: RealtimePayload) -> None:
        content = (
            f"**股票**: {payload.name} ({payload.symbol})\n"
            f"**信号**: {payload.signal}\n"
            f"**价格**: {payload.price}\n"
            f"**强度**: {payload.score}\n"
            f"**今日**: 买{payload.buy_count} / 卖{payload.sell_count}\n"
            f"**原因**: {', '.join(payload.reasons)}"
        )
        await send_wecom("T0 交易信号", content)


engine = TradingEngine()
