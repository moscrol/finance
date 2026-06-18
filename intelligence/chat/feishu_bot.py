"""飞书 chat bot（B-S2）——长连接收消息、in-process 调 ``ask`` 回六段答复。

阶段定位
========
「飞书 chat」链路：长连接（WebSocket）收到 ``im.message.receive_v1`` 文本消息后，
**in-process 直接调** :func:`intelligence.workflows.ask.run_ask`，把六段检索答复
（结论/证据链/分歧反证/后续验证点/交易含义/引用来源，每条带 ``[S#]/[G#]/[R#]`` 编号引用）
渲染成飞书**交互卡片**回去（抬头按召回状态变色；``--reply-format text`` 可退回纯文本）。
``ask`` 只读盘面快照 JSON + 知识库 ``wiki/relations``，**不碰 DuckDB**。

- 非文本（图片/语音/文件等）回一句「暂仅支持文本提问」提示（多模态属后续阶段）；
- ``--echo`` 可退回 B-S0 逐字回声（仅用于长连接打通自检）；
- 题材词路由的 theme-radar 模块 fan-out 默认**关**（子进程较慢），``--ask-modules`` 显式开。

交互卡片渲染 + 卡片按钮交互（深钻/换题材/看证据链）均已接入（B-S3b）：按钮点击经
``card.action.trigger`` 回调路由（深钻=展开题材模块 + detail 重跑、换题材=引导换词重问、
看证据链=展开完整证据链卡片），**需在飞书后台开启「卡片回调」事件订阅**。
``--reply-format text`` 退回纯文本（无按钮）。

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
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
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
    # dream-loop C-1A-S0 采集源：把每轮 Q/A append 到此 jsonl（正文本地保存、已 gitignore）。
    # 默认 None=关闭（不改变回声行为）；由 --transcript-log / env FEISHU_TRANSCRIPT_LOG 开启。
    transcript_log: Optional[str] = None

    # B-S2：回复模式。"ask"=调 ask 回六段（默认）；"echo"=B-S0 逐字回声（--echo 自检用）。
    mode: str = "ask"
    # ask 透传参数（均只读，绝不碰 DuckDB）。
    kb_wiki: Optional[str] = None          # 知识库 wiki 根（含 relations/）；None=env/auto
    exports_dir: Optional[str] = None      # 盘面 theme-candidates 快照目录；None=仓内默认
    ask_use_modules: bool = False          # theme-radar 模块 fan-out（子进程，较慢）；默认关
    ask_module_timeout: int = 180          # 单模块子进程超时秒数
    ask_top_companies: int = 12            # 公司暴露召回上限
    ask_use_llm: bool = False              # 用 LLM 精修 结论/交易含义（无 key 自动降级模板）
    ask_llm_model: Optional[str] = None
    ask_llm_timeout: int = 60
    ask_max_chars: int = 3500              # 回复正文截断预算（卡片/纯文本通用）
    # B-S3：ask 回复格式。"card"=飞书交互卡片（默认）；"text"=纯文本（B-S2 行为，回退用）。
    reply_format: str = "card"


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


def nontext_notice(message_type: Optional[str]) -> str:
    """ask 模式下对非文本消息的友好提示（多模态属后续阶段）。"""
    return f"（暂仅支持文本提问；收到「{message_type or '未知'}」类型消息，多模态为后续阶段。）"


def _truncate(text: str, max_chars: int) -> str:
    """把回复截到 max_chars 以内（尽量在换行处断开），超出则附截断说明。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    marker = "\n…（回复已截断；换更聚焦的提问，或用 CLI `ask` 看完整六段。）"
    budget = max(0, max_chars - len(marker))
    cut = text[:budget]
    nl = cut.rfind("\n")
    if nl > budget * 0.6:
        cut = cut[:nl]
    return cut.rstrip() + marker


def render_ask_reply(result: "AskResult", max_chars: int = 3500) -> str:
    """把 :class:`AskResult` 渲染成飞书纯文本：抬头 + 六段（每条带编号引用）。"""
    from intelligence.services.ask import SECTION_ORDER, SUBHEAD

    lines: list[str] = [
        f"📌 {result.query}",
        f"主题={result.matched_theme or '—'} ｜ 盘面={result.trade_date or '—'} ｜ 召回={result.status}",
    ]
    for name in SECTION_ORDER:
        lines.append("")
        lines.append(f"【{name}】")
        items = result.sections.get(name) or []
        if not items:
            lines.append("（无）")
            continue
        for item in items:
            if item.startswith(SUBHEAD):
                lines.append(f"· {item[len(SUBHEAD):]}")
            else:
                lines.append(f"- {item}")
    return _truncate("\n".join(lines), max_chars)


# --------------------------------------------------------------------------- #
# 交互卡片渲染（B-S3，纯函数，可单测，不依赖 lark_oapi）
# --------------------------------------------------------------------------- #
# 抬头底色按召回状态：PASS=绿（盘面+图谱齐全）/ WARN=橙（仅一侧命中）/ FAIL=灰（皆空）。
_HEADER_TEMPLATE = {"PASS": "green", "WARN": "orange", "FAIL": "grey"}
_CARD_TITLE_MAX = 100  # 飞书卡片 plain_text 标题长度上限。


def _card_title(query: str) -> str:
    title = f"📌 {query}"
    if len(title) > _CARD_TITLE_MAX:
        title = title[: _CARD_TITLE_MAX - 1].rstrip() + "…"
    return title


def _md_div(content: str) -> dict[str, Any]:
    """一个 lark_md 文本块。"""
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def _section_markdown(items: list[str], subhead: str) -> str:
    """把一段的条目渲染成 lark_md：SUBHEAD 哨兵转粗体小标题，其余转列表项。"""
    lines: list[str] = []
    for item in items or ["（无）"]:
        if item.startswith(subhead):
            lines.append(f"**{item[len(subhead):]}**")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


# 卡片底部交互按钮（B-S3b）：点击经 ``card.action.trigger`` 回调路由。按钮 ``value`` 里带
# ``action``/``query``/``theme``，回调据此重跑或引导（见 :func:`compute_action_payload`）。
ACTION_DRILL = "drill"        # 深钻：展开题材模块 + detail 重跑，回更全的卡片
ACTION_THEME = "theme"        # 换题材：引导用户回复一个新题材词重新提问
ACTION_EVIDENCE = "evidence"  # 看证据链：展开完整「证据链」段（不截断）


def _action_elements(query: str, theme: str = "") -> list[dict[str, Any]]:
    """卡片底部 3 个交互按钮（深钻/换题材/看证据链）。

    每个按钮的 ``value`` 是一个 dict，点击后经 ``card.action.trigger`` 原样回传，
    回调用 :func:`parse_action_value` 解出 ``(action, query, theme)`` 再路由。
    """
    base = {"query": query, "theme": theme or ""}
    return [
        {"tag": "hr"},
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "🔍 深钻"},
                    "type": "primary",
                    "value": {**base, "action": ACTION_DRILL},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "🔁 换题材"},
                    "type": "default",
                    "value": {**base, "action": ACTION_THEME},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "🔗 看证据链"},
                    "type": "default",
                    "value": {**base, "action": ACTION_EVIDENCE},
                },
            ],
        },
    ]


def render_ask_card(result: "AskResult", max_chars: int = 3500) -> dict[str, Any]:
    """把 :class:`AskResult` 渲染成飞书交互卡片 dict（``msg_type="interactive"`` 的 content）。

    抬头按召回状态变色，摘要行给 主题/盘面/召回，六段各自一个 markdown 块，
    引用 ``[S#]/[G#]/[R#]`` 原样保留。正文累计超 ``max_chars`` 时按段截断并附说明。
    """
    from intelligence.services.ask import SECTION_ORDER, SUBHEAD

    summary = (
        f"**主题** {result.matched_theme or '—'}　｜　"
        f"**盘面** {result.trade_date or '—'}　｜　**召回** {result.status}"
    )
    elements: list[dict[str, Any]] = [_md_div(summary)]

    remaining = max_chars
    truncated = False
    for name in SECTION_ORDER:
        body = _section_markdown(result.sections.get(name) or [], SUBHEAD)
        block = f"**【{name}】**\n{body}"
        if len(block) > remaining:
            block = block[: max(0, remaining)].rstrip()
            truncated = True
        elements.append({"tag": "hr"})
        elements.append(_md_div(block))
        remaining -= len(block)
        if truncated:
            break
    if truncated:
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": "回复已截断；换更聚焦的提问，或用 CLI ask 看完整六段。"}
                ],
            }
        )

    elements.extend(_action_elements(result.query, result.matched_theme or ""))

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": _HEADER_TEMPLATE.get(result.status, "grey"),
            "title": {"tag": "plain_text", "content": _card_title(result.query)},
        },
        "elements": elements,
    }


def render_evidence_card(result: "AskResult") -> dict[str, Any]:
    """「看证据链」按钮回调返回：只展开「证据链」整段（不按 max_chars 截断）。"""
    from intelligence.services.ask import SUBHEAD

    body = _section_markdown(result.sections.get("证据链") or [], SUBHEAD)
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": _HEADER_TEMPLATE.get(result.status, "grey"),
            "title": {"tag": "plain_text", "content": _card_title(f"证据链 · {result.query}")},
        },
        "elements": [
            _md_div(
                f"**主题** {result.matched_theme or '—'}　｜　**盘面** {result.trade_date or '—'}"
            ),
            {"tag": "hr"},
            _md_div(f"**【证据链】**\n{body}"),
        ],
    }


def render_theme_switch_card(query: str, theme: str = "") -> dict[str, Any]:
    """「换题材」按钮回调返回：引导用户直接回复一个新题材词重新检索（不重跑 ask）。"""
    cur = theme or "（未匹配到题材）"
    lines = [
        f"**当前题材** {cur}",
        "想换个角度？**直接回复一个新的题材词**（如 `CPO` / `铜连接` / `固态电池`），"
        "我就按新题材重新检索六段。",
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": _card_title(f"换题材 · {query}")},
        },
        "elements": [_md_div("\n".join(lines))],
    }


def _notice_card(query: str, notice: str) -> dict[str, Any]:
    """检索失败/降级时的极简灰底卡片。"""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "grey",
            "title": {"tag": "plain_text", "content": _card_title(query)},
        },
        "elements": [_md_div(notice)],
    }


def _run_ask_workflow(
    query: str,
    config: BotConfig,
    *,
    use_modules: Optional[bool] = None,
    detail: bool = False,
) -> "AskResult":
    """In-process 调 ``ask`` workflow（惰性导入，避免污染离线 import / 不引入 DuckDB）。

    ``use_modules`` 为 None / ``detail`` 为 False 时沿用 ``config`` 默认（与 B-S2/B-S3a 行为一致）；
    「深钻」按钮回调会显式传 ``use_modules=True, detail=True`` 跑更深一层。
    """
    from intelligence.workflows.ask import AskWorkflowOptions, run_ask

    _summary, result, _answer = run_ask(
        AskWorkflowOptions(
            query=query,
            kb_wiki=config.kb_wiki,
            exports_dir=config.exports_dir,
            top_companies=config.ask_top_companies,
            use_modules=config.ask_use_modules if use_modules is None else use_modules,
            module_timeout=config.ask_module_timeout,
            use_llm=config.ask_use_llm,
            llm_model=config.ask_llm_model,
            llm_timeout=config.ask_llm_timeout,
            detail=detail,
        )
    )
    return result


def _ask_failure_notice(exc: Exception) -> str:
    return f"⚠️ 检索暂时失败，请稍后重试或换个问法。（{type(exc).__name__}）"


def answer_text(query: str, config: BotConfig) -> str:
    """跑 ``ask`` 并渲染飞书纯文本；任何异常都降级为友好提示，绝不让 bot 崩。"""
    try:
        result = _run_ask_workflow(query, config)
    except Exception as exc:  # noqa: BLE001 - 检索失败绝不影响 bot 存活
        log.warning("ask 检索失败（已降级提示）：%s", exc)
        return _ask_failure_notice(exc)
    return render_ask_reply(result, max_chars=config.ask_max_chars)


def compute_ask_payload(query: str, config: BotConfig) -> tuple[str, Any, str]:
    """跑一次 ``ask``，按 ``config.reply_format`` 返回 ``(msg_type, content, transcript_text)``。

    - ``msg_type``：``"interactive"``（卡片 dict）或 ``"text"``（纯文本 str）；
    - ``transcript_text``：始终是纯文本版（供 dream-loop 采集落盘，卡片也记文本）。

    任何异常都降级为友好提示，绝不让 bot 崩。
    """
    try:
        result = _run_ask_workflow(query, config)
    except Exception as exc:  # noqa: BLE001 - 检索失败绝不影响 bot 存活
        log.warning("ask 检索失败（已降级提示）：%s", exc)
        notice = _ask_failure_notice(exc)
        if config.reply_format == "card":
            return "interactive", _notice_card(query, notice), notice
        return "text", notice, notice
    transcript_text = render_ask_reply(result, max_chars=config.ask_max_chars)
    if config.reply_format == "card":
        return "interactive", render_ask_card(result, max_chars=config.ask_max_chars), transcript_text
    return "text", transcript_text, transcript_text


# --------------------------------------------------------------------------- #
# 卡片按钮回调路由（B-S3b，纯函数，可单测，不依赖 lark_oapi）
# --------------------------------------------------------------------------- #
def parse_action_value(value: Any) -> tuple[str, str, str]:
    """从按钮回调 ``value`` 解出 ``(action, query, theme)``；非 dict / 缺字段都安全返回空串。"""
    if not isinstance(value, dict):
        return "", "", ""
    action = str(value.get("action") or "").strip()
    query = str(value.get("query") or "").strip()
    theme = str(value.get("theme") or "").strip()
    return action, query, theme


# card.action.trigger 的即时 toast（飞书要求秒级响应，重活在后台线程里补卡片）。
_ACTION_TOAST = {
    ACTION_DRILL: "正在深钻（展开题材模块），稍候补一张更全的卡片…",
    ACTION_THEME: "想换题材？直接回复一个新的题材词即可。",
    ACTION_EVIDENCE: "正在展开完整证据链…",
}


def action_toast(action: str) -> dict[str, str]:
    """按 ``action`` 返回 ``card.action.trigger`` 的即时 toast 提示。"""
    if action in _ACTION_TOAST:
        return {"type": "info", "content": _ACTION_TOAST[action]}
    return {"type": "warning", "content": "未知操作（按钮已失效，请重新提问）"}


def compute_action_payload(
    action: str, query: str, theme: str, config: BotConfig
) -> Optional[tuple[str, Any, str]]:
    """按钮动作的「后续卡片」负载 ``(msg_type, content, transcript_text)``。

    - ``drill``：``use_modules=True, detail=True`` 重跑，回更大预算的完整卡片；
    - ``evidence``：重跑后只展开完整「证据链」卡片；
    - ``theme``：纯引导卡（不重跑 ask）。

    未知 action / 空 query 返回 ``None``（不补发）；重跑异常降级为灰底提示卡（bot 不崩）。
    """
    if not query or action not in (ACTION_DRILL, ACTION_THEME, ACTION_EVIDENCE):
        return None
    if action == ACTION_THEME:
        card = render_theme_switch_card(query, theme)
        text = f"换题材：当前题材 {theme or '—'}；回复一个新题材词即可重新检索六段。"
        return "interactive", card, text
    try:
        if action == ACTION_DRILL:
            result = _run_ask_workflow(query, config, use_modules=True, detail=True)
        else:  # ACTION_EVIDENCE
            result = _run_ask_workflow(query, config)
    except Exception as exc:  # noqa: BLE001 - 重跑失败绝不影响 bot 存活
        log.warning("按钮动作 ask 重跑失败（已降级提示）：%s", exc)
        notice = _ask_failure_notice(exc)
        return "interactive", _notice_card(query, notice), notice
    if action == ACTION_EVIDENCE:
        text = render_ask_reply(result, max_chars=config.ask_max_chars)
        return "interactive", render_evidence_card(result), text
    budget = max(config.ask_max_chars, 8000)  # 深钻给更大预算，少截断
    text = render_ask_reply(result, max_chars=budget)
    return "interactive", render_ask_card(result, max_chars=budget), text


def build_transcript_event(
    message_id: Optional[str],
    chat_id: Optional[str],
    message_type: Optional[str],
    text: Optional[str],
    reply: str,
) -> dict[str, Any]:
    """构造一条 dream-loop 采集用的原始事件（与 dream.collector 的飞书适配对齐）。

    正文未脱敏（脱敏在 collector 内统一施加）；本文件仅本地留存、已 gitignore。
    """
    return {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "feishu",
        "message_id": message_id,
        "chat_id": chat_id,
        "message_type": message_type,
        "text": text,
        "reply": reply,
        "direction": "received",
    }


def append_transcript(path: str, event: dict[str, Any]) -> None:
    """把一条事件 append 到 jsonl（按需建目录）。失败由调用方吞掉，绝不影响回声。"""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# 运行（lark_oapi 在此惰性导入）
# --------------------------------------------------------------------------- #
def run(config: BotConfig) -> int:
    """启动长连接 bot（阻塞运行，Ctrl+C 退出）：ask 模式调 ask 回六段，echo 模式逐字回声。"""
    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            P2ImMessageReceiveV1,
            ReplyMessageRequest,
            ReplyMessageRequestBody,
        )
        from lark_oapi.event.callback.model.p2_card_action_trigger import (
            P2CardActionTrigger,
            P2CardActionTriggerResponse,
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

    def _reply(message_id: str, content_obj: Any, msg_type: str = "text") -> None:
        if msg_type == "interactive":
            content = json.dumps(content_obj, ensure_ascii=False)
        else:
            content = json.dumps({"text": content_obj}, ensure_ascii=False)
        body = (
            ReplyMessageRequestBody.builder()
            .content(content)
            .msg_type(msg_type)
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

    def _record_transcript(
        message_id: Optional[str],
        chat_id: Optional[str],
        message_type: Optional[str],
        text: Optional[str],
        reply: str,
    ) -> None:
        if not config.transcript_log:
            return
        try:
            event = build_transcript_event(message_id, chat_id, message_type, text, reply)
            append_transcript(config.transcript_log, event)
        except Exception as exc:  # noqa: BLE001 - 采集落盘失败绝不影响回声主流程
            log.warning("transcript 落盘失败（已忽略）：%s", exc)

    def on_message_receive(data: "P2ImMessageReceiveV1") -> None:
        message = data.event.message
        message_id = message.message_id
        if _already_handled(message_id):
            log.info("跳过重复事件 message_id=%s", message_id)
            return
        text = extract_text(message.content, message.message_type)
        if text is None:
            reply = (
                compose_reply(None, message.message_type, prefix=config.prefix)
                if config.mode == "echo"
                else nontext_notice(message.message_type)
            )
            msg_type, content_obj = "text", reply
        elif config.mode == "echo":
            reply = compose_reply(text, message.message_type, prefix=config.prefix)
            msg_type, content_obj = "text", reply
        else:
            msg_type, content_obj, reply = compute_ask_payload(text, config)
        log.info(
            "收到 type=%s id=%s mode=%s fmt=%s -> 回 %d 字",
            message.message_type, message_id, config.mode, config.reply_format, len(reply),
        )
        if message_id:
            _reply(message_id, content_obj, msg_type)
        _record_transcript(message_id, message.chat_id, message.message_type, text, reply)

    def _send_followup(action: str, query: str, theme: str, message_id: Optional[str]) -> None:
        """后台线程里跑按钮动作并把结果卡片 reply 回原消息（重活不阻塞回调秒级响应）。"""
        try:
            payload = compute_action_payload(action, query, theme, config)
        except Exception as exc:  # noqa: BLE001 - 后台动作失败绝不影响 bot 存活
            log.warning("按钮动作处理失败（已忽略）：%s", exc)
            return
        if not payload or not message_id:
            return
        msg_type, content_obj, reply = payload
        _reply(message_id, content_obj, msg_type)
        _record_transcript(message_id, None, "card_action", f"[{action}] {query}", reply)

    def on_card_action(data: "P2CardActionTrigger") -> "P2CardActionTriggerResponse":
        event = data.event
        value = event.action.value if (event and event.action) else None
        action, query, theme = parse_action_value(value)
        message_id = event.context.open_message_id if (event and event.context) else None
        log.info("卡片回调 action=%s query=%r msg=%s", action, query, message_id)
        # 重活（深钻/看证据链需重跑 ask）放后台线程，回调本身只回即时 toast（飞书要求秒级）。
        if action in (ACTION_DRILL, ACTION_THEME, ACTION_EVIDENCE) and query:
            threading.Thread(
                target=_send_followup,
                args=(action, query, theme, message_id),
                daemon=True,
            ).start()
        return P2CardActionTriggerResponse({"toast": action_toast(action)})

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message_receive)
        .register_p2_card_action_trigger(on_card_action)
        .build()
    )

    ws_client = lark.ws.Client(
        config.app_id,
        config.app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    log.info("飞书 chat bot 启动（mode=%s）：长连接接入中（Ctrl+C 退出）……", config.mode)
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
    parser.add_argument(
        "--transcript-log",
        default=None,
        help="dream-loop 采集源：把每轮 Q/A append 到此 jsonl（正文本地保存、已 gitignore；"
        "默认关，也可用 env FEISHU_TRANSCRIPT_LOG 开启）",
    )
    parser.add_argument("--echo", action="store_true", help="退回 B-S0 逐字回声（仅长连接自检；默认调 ask 回六段）")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（含 relations/）；默认 env/auto（ask 只读，不碰 DuckDB）")
    parser.add_argument("--exports-dir", default=None, help="盘面 theme-candidates 快照目录；默认仓内 market_feature_store/exports")
    parser.add_argument("--ask-modules", action="store_true", help="开启 theme-radar 模块 fan-out（子进程较慢；默认关以保证秒级回复）")
    parser.add_argument("--ask-module-timeout", type=int, default=180, help="单模块子进程超时秒数（默认 180）")
    parser.add_argument("--ask-top-companies", type=int, default=12, help="公司暴露召回上限（默认 12）")
    parser.add_argument("--ask-llm", action="store_true", help="用 LLM 精修 结论/交易含义（需 *_API_KEY；无 key 自动降级模板）")
    parser.add_argument("--ask-llm-model", default=None, help="覆盖 LLM 模型 id")
    parser.add_argument("--ask-llm-timeout", type=int, default=60, help="LLM HTTP 超时秒数（默认 60）")
    parser.add_argument("--ask-max-chars", type=int, default=3500, help="回复正文截断预算（卡片/纯文本通用，默认 3500 字）")
    parser.add_argument(
        "--reply-format",
        default="card",
        choices=["card", "text"],
        help="ask 回复格式：card=飞书交互卡片（默认，抬头按召回状态变色）；text=纯文本（B-S2 行为，回退用）",
    )


def build_config(args: argparse.Namespace) -> BotConfig:
    app_id, app_secret = resolve_credentials(args.app_id, args.app_secret)
    transcript_log = args.transcript_log or os.environ.get("FEISHU_TRANSCRIPT_LOG") or None
    return BotConfig(
        app_id=app_id,
        app_secret=app_secret,
        log_level=args.log_level,
        prefix=args.prefix,
        dedup_window=args.dedup_window,
        transcript_log=transcript_log,
        mode="echo" if args.echo else "ask",
        kb_wiki=args.kb_wiki,
        exports_dir=args.exports_dir,
        ask_use_modules=args.ask_modules,
        ask_module_timeout=args.ask_module_timeout,
        ask_top_companies=args.ask_top_companies,
        ask_use_llm=args.ask_llm,
        ask_llm_model=args.ask_llm_model,
        ask_llm_timeout=args.ask_llm_timeout,
        ask_max_chars=args.ask_max_chars,
        reply_format=args.reply_format,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="飞书 chat bot（B-S2，长连接 + ask 六段回复）")
    add_arguments(parser)
    args = parser.parse_args(argv)
    return run(build_config(args))


if __name__ == "__main__":
    raise SystemExit(main())
