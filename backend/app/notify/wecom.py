from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_wecom(
    title: str,
    content: str,
    webhook: str | None = None,
) -> bool:
    url = webhook or settings.wecom_webhook
    if not url:
        return False
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"### {title}\n{content}"},
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.warning("wecom send failed: %s", e)
        return False
