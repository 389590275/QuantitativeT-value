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
            if resp.status_code != 200:
                logger.warning("wecom http %s: %s", resp.status_code, resp.text[:500])
                return False
            try:
                body = resp.json()
            except Exception:
                return True
            # 企业微信：errcode=0 表示成功
            if isinstance(body, dict) and body.get("errcode", 0) != 0:
                logger.warning("wecom api err: %s", body)
                return False
            return True
    except Exception as e:
        logger.warning("wecom send failed: %s", e)
        return False
