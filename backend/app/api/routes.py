from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.engine import engine
from app.notify.wecom import send_wecom

router = APIRouter(prefix="/api", tags=["api"])


class SymbolRequest(BaseModel):
    symbol: str


class TradeDateRequest(BaseModel):
    trade_date: str


class TradeDateShiftRequest(BaseModel):
    offset: int
    trade_date: Optional[str] = None


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


@router.post("/trade-date/shift")
async def shift_trade_date(req: TradeDateShiftRequest) -> dict:
    return await engine.shift_trade_date(req.offset, req.trade_date)


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


@router.post("/test-wecom")
async def test_wecom() -> dict:
    """发送一条测试消息到 .env 中配置的企业微信机器人。"""
    if not (settings.wecom_webhook or "").strip():
        return {"ok": False, "message": "未配置 WECOM_WEBHOOK"}
    ok = await send_wecom(
        "T0 企微通知测试",
        "**说明**: API 测试消息，Webhook 配置正常。",
    )
    return {
        "ok": ok,
        "message": "已发送到企业微信群" if ok else "发送失败，请查看后端日志",
    }
