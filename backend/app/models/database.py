from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from app.core.config import settings


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal TEXT NOT NULL,
            score REAL NOT NULL,
            price REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            volume REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS minute_bar_cache (
            symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            bars_json TEXT NOT NULL,
            cached_at DATETIME NOT NULL,
            PRIMARY KEY (symbol, trade_date)
        );
        """
    )
    conn.commit()


def init_db() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _init_schema(conn)


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def insert_signal(
    symbol: str,
    signal: str,
    score: float,
    price: float,
    created_at: datetime | str | None = None,
) -> None:
    ts = _iso_datetime(created_at)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO signals (symbol, signal, score, price, created_at) VALUES (?, ?, ?, ?, ?)",
            (symbol, signal, score, price, ts),
        )
        conn.commit()


def get_today_signal_marks(symbol: str) -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    return get_signal_marks(symbol, today)


def get_signal_marks(symbol: str, trade_date: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT signal, price, score, created_at FROM signals
            WHERE symbol = ? AND signal IN ('BUY', 'SELL')
              AND date(created_at) = date(?)
            ORDER BY created_at ASC
            """,
            (symbol, trade_date),
        ).fetchall()
    marks = []
    for r in rows:
        ts = str(r["created_at"])
        time_part = ts.split("T")[-1][:8] if "T" in ts else ts.split(" ")[-1][:8]
        marks.append(
            {
                "time": time_part,
                "signal": r["signal"],
                "price": float(r["price"]),
                "score": float(r["score"]),
            }
        )
    return marks


def clear_today_data(symbol: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    return clear_day_data(symbol, today)


def clear_day_data(symbol: str, trade_date: str) -> dict:
    with _connect() as conn:
        signal_count = conn.execute(
            """
            SELECT COUNT(*) FROM signals
            WHERE symbol = ? AND substr(created_at, 1, 10) = ?
            """,
            (symbol, trade_date),
        ).fetchone()[0]
        tick_count = conn.execute(
            """
            SELECT COUNT(*) FROM ticks
            WHERE symbol = ? AND substr(created_at, 1, 10) = ?
            """,
            (symbol, trade_date),
        ).fetchone()[0]
        conn.execute(
            """
            DELETE FROM signals
            WHERE symbol = ? AND substr(created_at, 1, 10) = ?
            """,
            (symbol, trade_date),
        )
        conn.execute(
            """
            DELETE FROM ticks
            WHERE symbol = ? AND substr(created_at, 1, 10) = ?
            """,
            (symbol, trade_date),
        )
        conn.commit()
    return {"signals": signal_count, "ticks": tick_count}


def insert_tick(
    symbol: str,
    price: float,
    volume: float,
    created_at: datetime | str | None = None,
) -> None:
    ts = _iso_datetime(created_at)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO ticks (symbol, price, volume, created_at) VALUES (?, ?, ?, ?)",
            (symbol, price, volume, ts),
        )
        conn.commit()


def get_cached_minute_bars(symbol: str, trade_date: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT bars_json FROM minute_bar_cache
            WHERE symbol = ? AND trade_date = ?
            """,
            (symbol, trade_date),
        ).fetchone()
    if row is None:
        return []
    try:
        bars = json.loads(str(row["bars_json"]))
        return bars if isinstance(bars, list) else []
    except json.JSONDecodeError:
        return []


def save_cached_minute_bars(
    symbol: str,
    trade_date: str,
    bars: list[dict[str, Any]],
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO minute_bar_cache
                (symbol, trade_date, bars_json, cached_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                symbol,
                trade_date,
                json.dumps(bars, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()


def _iso_datetime(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value
    return datetime.now().isoformat()
