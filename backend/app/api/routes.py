from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.core.engine import engine

router = APIRouter(prefix="/api", tags=["api"])


class SymbolRequest(BaseModel):
    symbol: str


class TradeDateRequest(BaseModel):
    trade_date: str


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/status")
async def status() -> dict:
    return engine.get_status()


@router.post("/symbol")
async def set_symbol(req: SymbolRequest) -> dict:
    return await engine.set_symbol(req.symbol)


@router.post("/trade-date")
async def set_trade_date(req: TradeDateRequest) -> dict:
    return await engine.load_trade_date(req.trade_date)


@router.post("/start")
async def start_engine() -> dict:
    await engine.start()
    return {"running": True}


@router.post("/stop")
async def stop_engine() -> dict:
    await engine.stop()
    return {"running": False}


@router.post("/clear-recalculate")
async def clear_recalculate(req: Optional[TradeDateRequest] = None) -> dict:
    return await engine.clear_and_recalculate(req.trade_date if req else None)


@router.post("/refresh-cache")
async def refresh_cache(req: Optional[TradeDateRequest] = None) -> dict:
    return await engine.refresh_cache_and_recalculate(req.trade_date if req else None)
