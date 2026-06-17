"""飞书回声 bot（B-S0）——长连接打通验证，尚未接 ``ask``。

阶段定位
========
这是「飞书 chat」链路的第一步（B-S0）：只验证**长连接（WebSocket）**能收到
``im.message.receive_v1`` 事件、并能把回复发回飞书。收到文本消息就把同样的文本回声给
你；收到非文本（图片/语音/文件等）则回一句友好提示。**还没有**接 ``intelligence.cli
ask``——把回声替换为 in-process 调 ``ask`` + 六段引用 + 交互卡片，是后续 B 阶段的事。

为什么用长连接
==============
bot 进程从 Mac **主动外连**飞书开放平台，全程出站连接：

- 不需要公网回调 URL、不需要域名 ICP 备案、不需要入站隧道；
- 与 ``exec.industry7view.com`` 通用 exec 隧道完全无关，也不碰 DuckDB；
- 配 ``launchd`` 常驻即可（见 ``intelligence/chat/README.md``）。

凭证
====
复用现有飞书自建应用的 ``app_id`` / ``app_secret``，**永不进 git**。来源优先级：

1. 环境变量 ``FEISHU_APP_ID`` / ``FEISHU_APP_SECRET``（便于 launchd / 临时覆盖）；
2. ``~/.claude/shared/feishu_config.json``（仓外，本机现有飞书配置；沿用 sync 脚本约定）。

依赖
====
长连接需官方 SDK ``lark-oapi``（见 ``intelligence/chat/requirements.txt``）。为不污染
本仓「零依赖、可离线」的其余命令，``lark_oapi`` 一律**惰性导入**在 :func:`run` 内部——
没装 SDK 也能 ``import intelligence.chat.feishu_bot``、跑单测、构造 argparse。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SHARED_DIR = Path.home() / ".claude" / "shared"
FEISHU_CONFIG = SHARED_DIR / "feishu_config.json"

# feishu_config.json 里 app_id / app_secret 的候选键名（兼容历史命名）。
_APP_ID_KEYS = ("app_id", "appId", "appid", "APP_ID")
_APP_SECRET_KEYS = ("app_secret", "appSecret", "appsecret", "APP_SECRET")

log = logging.getLogger("feishu_bot")


# --------------------------------------------------------------------------- #
# 配置 / 凭证
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BotConfig:
    """启动参数。``app_id`` / ``app_secret`` 在 :func:`build_config` 里解析填好。"""

    app_id: str
    app_secret: str
    log_level: str = "info"
    prefix: str = ""  # 回声前缀；默认空=逐字回声。设非空便于一眼区分 bot 回复。
    dedup_window: int = 512  # 近期 message_id 去重窗口（飞书超时会重投事件）。


def _first_present(cfg: dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        val = cfg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _load_config_file() -> dict[str, Any]:
    """读取仓外飞书配置；优先复用 shared/feishu_utils.load_config()，回退直接读 JSON。"""
    if SHARED_DIR.exists() and str(SHARED_DIR) not in sys.path:
        sys.path.insert(0, str(SHARED_DIR))
    try:
        from feishu_utils import load_config  # type: ignore[import-not-found]

        cfg = load_config()
        if isinstance(cfg, dict):
            return cfg
    except Exception as exc:  # noqa: BLE001 - feishu_utils 不可用时回退直读文件
        log.debug("feishu_utils.load_config() 不可用，回退直读 JSON：%s", exc)
    if FEISHU_CONFIG.is_file():
        try:
            data = json.loads(FEISHU_CONFIG.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("读取 %s 失败：%s", FEISHU_CONFIG, exc)
    return {}


def resolve_credentials(
    app_id: Optional[str] = None, app_secret: Optional[str] = None
) -> tuple[str, str]:
    """解析飞书应用凭证：显式入参 > 环境变量 > feishu_config.json。

    解析不到时抛 ``SystemExit`` 并给出可操作的指引（永不打印密钥本身）。
    """
    app_id = app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
    if app_id and app_secret:
        return app_id, app_secret

    cfg = _load_config_file()
    app_id = app_id or _first_present(cfg, _APP_ID_KEYS)
    app_secret = app_secret or _first_present(cfg, _APP_SECRET_KEYS)
    if app_id and app_secret:
        return app_id, app_secret

    missing = []
    if not app_id:
        missing.append("app_id")
    if not app_secret:
        missing.append("app_secret")
    raise SystemExit(
        "无法解析飞书应用凭证（缺：{missing}）。请二选一：\n"
        "  1) 设环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET（launchd plist 已留位）；\n"
        "  2) 在 {cfg} 写入 app_id / app_secret 字段。\n"
        "（凭证永不进 git；本提示不含密钥值。）".format(
            missing="、".join(missing), cfg=FEISHU_CONFIG
        )
    )


# --------------------------------------------------------------------------- #
# 消息解析（纯函数，可单测，不依赖 lark_oapi）
# --------------------------------------------------------------------------- #
def extract_text(content: Optional[str], message_type: Optional[str]) -> Optional[str]:
    """从飞书消息 ``content``（JSON 字符串）取纯文本；非文本返回 ``None``。

    - ``text``  -> ``{"text": "..."}``
    - ``post``（富文本）-> 拼接其中的 ``text`` 段，取不到则 ``None``
    - 其余类型（image/audio/file/...）-> ``None``，交由上层回友好提示
    """
    if message_type not in (None, "text", "post"):
        return None
    if not content:
        return None
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    if message_type in (None, "text") and isinstance(payload.get("text"), str):
        text = payload["text"].strip()
        return text or None

    if message_type == "post":
        parts: list[str] = []
        blocks = payload.get("content")
        if isinstance(blocks, list):
            for line in blocks:
                if not isinstance(line, list):
                    continue
                for seg in line:
                    if isinstance(seg, dict) and seg.get("tag") == "text":
                        seg_text = seg.get("text")
                        if isinstance(seg_text, str) and seg_text.strip():
                            parts.append(seg_text.strip())
        joined = " ".join(parts).strip()
        return joined or None

    return None


def compose_reply(text: Optional[str], message_type: Optional[str], prefix: str = "") -> str:
    """根据解析结果拼回声文本：文本回声本身，非文本回友好提示。"""
    if text is None:
        return f"[回声 bot S0] 已收到「{message_type or '未知'}」类型消息；当前仅回声文本。"
    return f"{prefix}{text}" if prefix else text


# --------------------------------------------------------------------------- #
# 运行（lark_oapi 在此惰性导入）
# --------------------------------------------------------------------------- #
def run(config: BotConfig) -> int:
    """启动长连接 echo bot（阻塞运行，Ctrl+C 退出）。"""
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            P2ImMessageReceiveV1,
            ReplyMessageRequest,
            ReplyMessageRequestBody,
        )
    except ImportError as exc:
        raise SystemExit(
            "缺少依赖 lark-oapi（长连接所需）。请先安装：\n"
            "  pip install -r intelligence/chat/requirements.txt\n"
            f"原始错误：{exc}"
        )

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 回复走 HTTP 客户端（reply 到原消息）；长连接客户端只负责收事件。
    http_client = (
        lark.Client.builder()
        .app_id(config.app_id)
        .app_secret(config.app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )

    seen_ids: "deque[str]" = deque(maxlen=config.dedup_window)
    seen_set: set[str] = set()

    def _already_handled(message_id: Optional[str]) -> bool:
        if not message_id:
            return False
        if message_id in seen_set:
            return True
        if len(seen_ids) == seen_ids.maxlen:
            seen_set.discard(seen_ids[0])
        seen_ids.append(message_id)
        seen_set.add(message_id)
        return False

    def _reply(message_id: str, text: str) -> None:
        body = (
            ReplyMessageRequestBody.builder()
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .msg_type("text")
            .build()
        )
        request = (
            ReplyMessageRequest.builder().message_id(message_id).request_body(body).build()
        )
        resp = http_client.im.v1.message.reply(request)
        if not resp.success():
            log.error(
                "回复失败 code=%s msg=%s log_id=%s",
                resp.code,
                resp.msg,
                getattr(resp, "get_log_id", lambda: "")(),
            )

    def on_message_receive(data: "P2ImMessageReceiveV1") -> None:
        message = data.event.message
        message_id = message.message_id
        if _already_handled(message_id):
            log.info("跳过重复事件 message_id=%s", message_id)
            return
        text = extract_text(message.content, message.message_type)
        reply = compose_reply(text, message.message_type, prefix=config.prefix)
        log.info("收到 type=%s id=%s -> 回声 %d 字", message.message_type, message_id, len(reply))
        if message_id:
            _reply(message_id, reply)

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message_receive)
        .build()
    )

    ws_client = lark.ws.Client(
        config.app_id,
        config.app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    log.info("飞书回声 bot 启动：长连接接入中（Ctrl+C 退出）……")
    try:
        ws_client.start()
    except KeyboardInterrupt:
        log.info("收到中断，退出。")
    return 0


# --------------------------------------------------------------------------- #
# CLI 接线（供 intelligence.cli 调用，模式同 server.add_arguments）
# --------------------------------------------------------------------------- #
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--app-id", default=None, help="飞书应用 app_id（默认 env / feishu_config.json）")
    parser.add_argument("--app-secret", default=None, help="飞书应用 app_secret（默认 env / feishu_config.json）")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="日志级别（默认 info）",
    )
    parser.add_argument("--prefix", default="", help="回声前缀（默认空=逐字回声；设非空便于区分 bot 回复）")
    parser.add_argument("--dedup-window", type=int, default=512, help="近期 message_id 去重窗口（默认 512）")


def build_config(args: argparse.Namespace) -> BotConfig:
    app_id, app_secret = resolve_credentials(args.app_id, args.app_secret)
    return BotConfig(
        app_id=app_id,
        app_secret=app_secret,
        log_level=args.log_level,
        prefix=args.prefix,
        dedup_window=args.dedup_window,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="飞书回声 bot（B-S0，长连接打通验证）")
    add_arguments(parser)
    args = parser.parse_args(argv)
    return run(build_config(args))


if __name__ == "__main__":
    raise SystemExit(main())
