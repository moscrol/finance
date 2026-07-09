#!/usr/bin/env python3
"""飞书主动告警：给用户/群发一条文本消息（复盘链失败告警等运维通知用）。

- 凭证复用 chat bot 的自建应用：env `FEISHU_APP_ID`/`FEISHU_APP_SECRET`
  优先，否则读 `~/.claude/shared/feishu_config.json`（仓外，永不进 git）。
- 收件人：env `FEISHU_ALERT_CHAT_ID`（群 chat_id）优先；未配置则自动取
  bot 所在的第一个群（`GET /im/v1/chats`）——个人使用场景下 bot 只在
  一个会话里，够用；多群时必须显式配置。
- 零第三方依赖（urllib），任何异常只打印不抛出，退出码 0=已发送 1=失败，
  方便 shell 里 `|| true` 兜底、绝不拖垮复盘链本身。

用法：python3 scripts/notify_feishu.py "复盘链失败：同步段 rc=3"
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

FEISHU_CONFIG = Path.home() / ".claude" / "shared" / "feishu_config.json"
_BASE = "https://open.feishu.cn/open-apis"


def _load_credentials() -> tuple[str, str] | None:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if app_id and app_secret:
        return app_id, app_secret
    try:
        cfg = json.loads(FEISHU_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return None
    app_id = str(cfg.get("app_id") or "").strip()
    app_secret = str(cfg.get("app_secret") or "").strip()
    return (app_id, app_secret) if app_id and app_secret else None


def _post(path: str, body: dict, token: str | None = None, timeout: float = 10.0) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{_BASE}{path}", data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, token: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(
        f"{_BASE}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tenant_token(app_id: str, app_secret: str) -> str | None:
    payload = _post(
        "/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    return payload.get("tenant_access_token") if payload.get("code") == 0 else None


def _resolve_chat_id(token: str) -> str | None:
    chat_id = os.environ.get("FEISHU_ALERT_CHAT_ID", "").strip()
    if chat_id:
        return chat_id
    payload = _get("/im/v1/chats?page_size=10", token)
    items = ((payload.get("data") or {}).get("items")) or []
    return str(items[0].get("chat_id")) if items else None


def send_alert(text: str) -> bool:
    creds = _load_credentials()
    if creds is None:
        print("notify_feishu: 缺飞书凭证（env 或 feishu_config.json）", file=sys.stderr)
        return False
    try:
        token = _tenant_token(*creds)
        if not token:
            print("notify_feishu: tenant_access_token 获取失败", file=sys.stderr)
            return False
        chat_id = _resolve_chat_id(token)
        if not chat_id:
            print("notify_feishu: 找不到收件会话（配 FEISHU_ALERT_CHAT_ID）", file=sys.stderr)
            return False
        payload = _post(
            "/im/v1/messages?receive_id_type=chat_id",
            {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            token=token,
        )
        if payload.get("code") != 0:
            print(f"notify_feishu: 发送失败 {payload.get('code')} {payload.get('msg')}", file=sys.stderr)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - 告警脚本自身绝不抛出
        print(f"notify_feishu: 异常 {exc}", file=sys.stderr)
        return False


def main() -> int:
    text = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not text:
        print("用法: notify_feishu.py <消息文本>", file=sys.stderr)
        return 1
    return 0 if send_alert(text) else 1


if __name__ == "__main__":
    sys.exit(main())
