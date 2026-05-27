from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from app.models.schemas import SignalOutput

# A股收盘前需平仓，保证当日买卖对等
_FORCE_CLOSE_TIME = time(14, 54)
_MARKET_CLOSE_TIME = time(15, 0)


@dataclass
class T0Decision:
    display_signal: SignalOutput
    notify_signal: SignalOutput | None = None
    persist_signals: list[dict] | None = None
    completed_marks: list[dict] | None = None
    pending_mark: dict | None = None


class T0SignalPairer:
    """T0 配对器。

    - BUY 先进入 pending，不进入图表已完成买卖点。
    - SELL 出现时，把 pending BUY 和当前 SELL 一起提交为一组完成交易。
    - 对外暴露的 marks 永远只包含已完成配对，所以图上买卖点数量保持相等。
    """

    def __init__(self) -> None:
        self._trade_date: str = ""
        self._position: str = "flat"  # flat | long
        self._marks: list[dict] = []
        self._pending_buy: dict | None = None

    @property
    def buy_count(self) -> int:
        return sum(1 for m in self._marks if m.get("signal") == "BUY")

    @property
    def sell_count(self) -> int:
        return sum(1 for m in self._marks if m.get("signal") == "SELL")

    @property
    def position(self) -> str:
        return self._position

    @property
    def pending_buy(self) -> dict | None:
        return dict(self._pending_buy) if self._pending_buy else None

    @property
    def marks(self) -> list[dict]:
        return list(self._marks)

    def reset_day(self, trade_date: str) -> None:
        self._trade_date = trade_date
        self._position = "flat"
        self._marks = []
        self._pending_buy = None

    def restore_from_marks(self, trade_date: str, marks: list[dict]) -> None:
        self.reset_day(trade_date)
        pending_buy: dict | None = None
        for mark in marks:
            sig = mark.get("signal", "")
            if sig == "BUY" and pending_buy is None:
                pending_buy = mark
            elif sig == "SELL" and pending_buy is not None:
                self._marks.extend([pending_buy, mark])
                pending_buy = None

        # 旧数据里可能有未配对 BUY。它不进入图表 completed marks，
        # 但恢复为当前持仓，等待后续 SELL 完成配对。
        self._pending_buy = pending_buy
        self._position = "long" if pending_buy else "flat"

    def apply(
        self,
        raw: SignalOutput,
        price: float,
        bar_time: str,
        now: datetime | None = None,
    ) -> T0Decision:
        now = now or datetime.now()
        trade_date = now.strftime("%Y-%m-%d")
        if trade_date != self._trade_date:
            self.reset_day(trade_date)

        time_key = self._normalize_time(bar_time, now)

        # 收盘前强制平仓，保证买卖对等
        if self._position == "long" and _FORCE_CLOSE_TIME <= now.time() <= _MARKET_CLOSE_TIME:
            raw = SignalOutput(
                signal="SELL",
                score=raw.score,
                reasons=["收盘前T0平仓"] + raw.reasons[:3],
            )

        if raw.signal == "BUY" and self._position == "flat":
            self._position = "long"
            self._pending_buy = {
                "time": time_key,
                "signal": "BUY",
                "price": price,
                "score": raw.score,
                "reason": " / ".join(raw.reasons[:3]),
            }
            return T0Decision(
                display_signal=raw,
                notify_signal=raw,
                persist_signals=[self._pending_buy],
                completed_marks=[],
                pending_mark=self.pending_buy,
            )

        elif raw.signal == "SELL" and self._position == "long":
            if self._pending_buy is None:
                self._position = "flat"
                return T0Decision(
                    display_signal=SignalOutput(
                        signal="HOLD",
                        score=raw.score,
                        reasons=["缺少买点，卖点已忽略"],
                    )
                )
            self._position = "flat"
            sell_mark = {
                "time": time_key,
                "signal": "SELL",
                "price": price,
                "score": raw.score,
                "reason": " / ".join(raw.reasons[:3]),
            }
            pair = [self._pending_buy, sell_mark]
            self._marks.extend(pair)
            self._pending_buy = None
            return T0Decision(
                display_signal=raw,
                notify_signal=raw,
                persist_signals=[sell_mark],
                completed_marks=pair,
                pending_mark=None,
            )

        else:
            if self._position == "long":
                return T0Decision(
                    display_signal=SignalOutput(
                    signal="HOLD",
                    score=raw.score,
                    reasons=["已买入，等待卖点配对"] + raw.reasons[:2],
                    ),
                    pending_mark=self.pending_buy,
                )
            elif raw.signal in ("BUY", "SELL"):
                return T0Decision(
                    display_signal=SignalOutput(
                        signal="HOLD",
                        score=raw.score,
                        reasons=["T0配对过滤"] + raw.reasons[:2],
                    )
                )
            else:
                return T0Decision(display_signal=raw, pending_mark=self.pending_buy)

    @staticmethod
    def _normalize_time(bar_time: str, now: datetime) -> str:
        if bar_time:
            part = str(bar_time).strip().split()[-1]
            if ":" in part:
                return part[:8] if len(part) >= 8 else part[:5] + ":00"
        return now.strftime("%H:%M:%S")
