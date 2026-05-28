"""
企业微信机器人 Webhook 测试脚本。

用法（在项目 backend 目录下）:
    ..\\venv\\Scripts\\python scripts\\test_wecom.py

或在项目根目录:
    venv\\Scripts\\python backend\\scripts\\test_wecom.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 保证能 import app.*
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import settings
from app.notify.wecom import send_wecom


async def main() -> int:
    webhook = (settings.wecom_webhook or "").strip()
    if not webhook:
        print("未配置 WECOM_WEBHOOK，请在项目根目录 .env 中填写企业微信机器人地址。")
        return 1

    if "qyapi.weixin.qq.com/cgi-bin/webhook/send" not in webhook:
        print("WECOM_WEBHOOK 格式不对。")
        print("应填写「发送消息」用的 Webhook，形如：")
        print("  https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx")
        print("不要填 work.weixin.qq.com 上的机器人介绍/管理页链接。")
        print(f"当前配置: {webhook[:80]}...")
        return 1

    masked = webhook
    if "key=" in webhook:
        key_part = webhook.split("key=", 1)[1]
        if len(key_part) > 8:
            masked = webhook.replace(key_part, key_part[:4] + "****" + key_part[-4:])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = "T0 企微通知测试"
    content = (
        f"**时间**: {now}\n"
        f"**说明**: 这是一条测试消息，表示 Webhook 配置正确。\n"
        f"**股票**: {settings.symbol}\n"
        f"**Webhook**: `{masked}`"
    )

    print(f"正在发送测试消息到企业微信…\nWebhook: {masked}")
    ok = await send_wecom(title, content, webhook=webhook)
    if ok:
        print("发送成功，请到企业微信群查看是否收到「T0 企微通知测试」。")
        return 0

    print("发送失败。请检查：")
    print("  1. Webhook 地址是否完整、key 是否正确")
    print("  2. 机器人是否仍在群内、未被删除")
    print("  3. 本机网络能否访问 qyapi.weixin.qq.com")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
