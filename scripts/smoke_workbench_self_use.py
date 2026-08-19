#!/usr/bin/env python3
"""Run a redacted, end-to-end Workbench conversation smoke check."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import BinaryIO

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from intelligence.services.gate_receipt import (  # noqa: E402
    extract_gate_receipt,
    table_row,
)

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
ANSWER_PHASES = {
    "verified_draft",
    "validated_synthesis",
    "verified_fallback",
    "decision_brief_fallback",
    "evidence_gap_fallback",
}
EVENT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "intelligence"
    / "contracts"
    / "stream_events.json"
)
EVENT_REGISTRY = json.loads(EVENT_REGISTRY_PATH.read_text(encoding="utf-8"))
EVENT_DEFINITIONS = {
    definition["event_type"]: definition
    for definition in EVENT_REGISTRY["events"]
}
PUBLIC_EVENT_TYPES = {
    event_type
    for event_type, definition in EVENT_DEFINITIONS.items()
    if definition["public"]
}
SAFE_LABEL = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_SOURCE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
UNSAFE_MODEL_LABEL = re.compile(
    r"(?:\.\.|error|exception|prompt|authorization|api[_-]?key|secret|header|"
    r"traceback|credential)",
    re.IGNORECASE,
)
PRIVATE_PATH_COMPONENT = re.compile(
    r"(?:^|/)(?:users|home|private|var|tmp|etc)(?:/|$)", re.IGNORECASE
)
CREDENTIAL_FAMILY_CASE_INSENSITIVE = re.compile(
    r"^(?:gh[a-z]_|github_pat_|xox[a-z]-|(?:sk|rk)[-_]|hf_|glpat-|xapp-|bearer)",
    re.IGNORECASE,
)
CREDENTIAL_FAMILY_CASE_SENSITIVE = re.compile(r"^(?:AKIA|ASIA|AIza|ya29\.)")
JWT_SHAPE = re.compile(
    r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$"
)
SUPPORTED_MODEL_FAMILY = re.compile(
    r"^(?:(?:glm|gpt|chatgpt|deepseek|kimi|moonshot|qwen|qwq|tongyi|claude)-"
    r"[A-Za-z0-9][A-Za-z0-9._-]*|o[134](?:$|[-.][A-Za-z0-9][A-Za-z0-9._-]*)|"
    r"fixture[A-Za-z0-9._-]*)$",
    re.IGNORECASE,
)
SAFE_LLM_PROVIDERS = frozenset(
    {
        "zhipu",
        "glm",
        "openai",
        "deepseek",
        "moonshot",
        "kimi",
        "dashscope",
        "qwen",
        "tongyi",
        "fixture",
    }
)
SECRET_PATTERNS = (
    (
        "token_prefix",
        re.compile(
            r"\b(?:gh[a-z]_|github_pat_|xox[a-z]-|(?:sk|rk)[-_]|hf_|glpat-|xapp-)"
            r"[A-Za-z0-9_-]{8,}",
            re.IGNORECASE,
        ),
    ),
    (
        "cloud_token_prefix",
        re.compile(r"\b(?:AKIA|ASIA|AIza|ya29\.)[A-Za-z0-9._-]{8,}"),
    ),
    (
        "bearer_token",
        re.compile(r"\bbearer(?:\s+|[-_:])[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    ),
    (
        "jwt_shape",
        re.compile(
            r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
        ),
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|token|secret|password|authorization)"
            r"\s*[=:]\s*(?!\[REDACTED\](?:\s|$))\S+"
        ),
    ),
)
SAFE_LLM_FALLBACK_REASONS = frozenset(
    {
        "provider_timeout",
        "provider_unavailable",
        "quality_gate_rejected",
        "budget_exhausted",
    }
)
PUBLIC_LEAK_PATTERNS = (
    ("traceback", re.compile(r"\bTraceback\b", re.IGNORECASE)),
    (
        "local_path",
        re.compile(
            r"(?:/Users/|/private/var/|/home/|"
            r"(?<![A-Za-z0-9])[A-Za-z]:[/\\]).+?(?:\s|[\"'])"
        ),
    ),
    (
        "technical_code",
        re.compile(
            r"provider_timeout|untrusted\s+index\s+freshness|"
            r"narrow\s+retrieval\s+empty",
            re.IGNORECASE,
        ),
    ),
)
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
QUANTIFIED_MARKET_OBSERVATION = re.compile(
    r"(?:成交(?:额)?|涨停|跌停|上涨家数|下跌家数|涨跌幅|量比|"
    r"近\s*\d+\s*日)[^。；;\n]{0,48}\d"
)
DIRECT_ASSESSMENT = re.compile(
    r"(?:直接|核心|基准)[^。；;\n]{0,4}(?:回答|判断|结论)"
)
VALUATION_FIELD = (
    r"(?:财报|财务|报表|营收|收入|净利|利润|盈利|毛利|负债|现金流|"
    r"PE|PB|PS|市盈|市净|市销|分位|机构预测|历史估值|行情时效|"
    r"估值|估值证据|估值输入|可比公司|可比样本)"
)
VALUATION_FIELD_RE = re.compile(VALUATION_FIELD)
UNRESOLVED_GAP_ASSERTION = re.compile(
    r"(?:仍|尚|还|目前|当前|依然)?\s*"
    r"(?:缺少|缺乏|缺失|不足|不充分|不完整)|"
    r"(?:尚未|未能|未|无法|不能)\s*"
    r"(?:获取|取得|获得|核验|确认|完成|形成|建立|检索到|返回|覆盖|对齐|归因|回答)|"
    r"(?:仍需|尚待|有待|需|需要)\s*(?:补充|核验|确认|获取)|"
    r"(?:存在|仍有|尚有|留有)[^。；;，,\n]{0,12}(?:缺口|不足)|"
    r"(?:样本|数据|证据)(?:数量)?\s*(?:太少|过少)|"
    r"(?:不含|没有)[^。；;，,\n]{0,36}(?:证据|新闻|政策|信息)|"
    r"无法\s*(?:给出|形成|计算|估算|确定)[^。；;，,\n]{0,10}估值|"
    r"返回空结果"
)
GAP_ASSERTION_NEGATION = re.compile(
    r"(?:并非|并未|并不|没有|不存在|不再)[^。；;，,\n]{0,6}$|"
    r"(?:已|已经|现已|目前已)?\s*"
    r"(?:补齐|补全|填补|弥补|消除|解决|关闭)"
    r"[^。；;，,\n]{0,10}$"
)
GAP_ASSERTION_RESOLUTION = re.compile(
    r"^(?:的)?(?:问题|缺口)?\s*(?:已|已经|现已|目前已)?\s*"
    r"(?:得到)?\s*"
    r"(?:补齐|补全|填补|弥补|消除|解决|关闭|归零|为零)"
)
GAP_CONTRAST_SPLIT = re.compile(r"(?:但|不过|然而|可是|却)")
CAUSE_TIME = re.compile(
    r"同一时间窗口|同窗|同期|同日|时间对齐|与[^。；;\n]{0,20}对齐|"
    r"20\d{2}[-年/.]\d{1,2}(?:[-月/.]\d{1,2})?|\d{1,2}月\d{1,2}日"
)
CAUSE_DEICTIC_TIME = re.compile(r"该(?:时间)?窗口")
CAUSE_SOURCE = re.compile(r"新闻|政策|事件|消息|资讯|外部信息")
CAUSE_OBJECT = re.compile(r"原因|归因|因果|诱因|催化|外部驱动")
CAUSE_UNCERTAINTY = re.compile(
    r"无法|不能|不足以|未能|缺口|缺少|缺失|尚缺|未检索到|未返回|不含|没有"
)
FORECAST_DURATION = re.compile(
    r"(?:\d+(?:\.\d+)?(?:\s*(?:[-~～至到—]|到)\s*\d+(?:\.\d+)?)?|"
    r"[一二两三四五六七八九十百]+(?:到|至)?"
    r"[一二两三四五六七八九十百]*)\s*(?:个)?(?:交易日|天|周|月)"
)
FORECAST_LANGUAGE = re.compile(
    r"预计|预期|还能|将(?:维持|持续)|可持续|大概率(?:持续|维持)|"
    r"(?:可能)?(?:再)?延续|基准判断|"
    r"基准情景|反弹(?:的)?(?:持续)?(?:时间)?窗口|"
    r"倾向于?(?:还能|持续|维持)|"
    r"(?:主观基准|本轮反弹)[^。；;\n]{0,80}"
    r"(?:未来|后续|接下来|短期|仍有|仍可|还能|预计|预期|将|可持续|惯性)"
)
MARKET_TRIGGER = (
    r"(?:成交|量能|指数|涨停|跌停|主线|板块|市场宽度|上涨家数|"
    r"下跌家数|均线|支撑|压力|资金|北向|融资)"
)
MARKET_CHANGE = (
    r"(?:萎缩|缩量|放量|回落|扩散|跌破|失守|站上|走弱|下降|"
    r"减少|增加|收窄|转弱|转强|恶化|修复|低于|高于|不足|超过)"
)
INVALIDATION_TRIGGER = re.compile(
    rf"(?:若|如果|一旦|当)[^。；;\n]{{0,40}}{MARKET_TRIGGER}"
    rf"[^。；;\n]{{0,40}}{MARKET_CHANGE}"
    r"[^。；;\n]{0,60}(?:失效|结束|下调|转弱|转强|改变)"
    rf"|失效条件\s*[:：]\s*(?:若|如果|一旦|当)"
    rf"[^。；;\n]{{0,40}}{MARKET_TRIGGER}"
    rf"[^。；;\n]{{0,40}}{MARKET_CHANGE}[^。；;\n]{{0,60}}"
    rf"|【?(?:失效|降级|失效或降级)条件】?\s*[:：]?\s*[①②③④⑤⑥⑦⑧⑨⑩-]*"
    rf"[^。；;\n]{{0,16}}{MARKET_TRIGGER}[^。；;\n]{{0,40}}{MARKET_CHANGE}"
)


def _is_cause_question(question: str) -> bool:
    has_cause_request = any(
        marker in question
        for marker in ("原因", "为什么", "归因", "诱因", "怎么回事")
    )
    has_market_context = any(
        marker in question for marker in ("下跌", "行情", "市场", "大盘", "指数")
    )
    return has_cause_request and has_market_context


def _task_gap_anchors(question: str, subject: str = "") -> tuple[str, ...]:
    """缺口陈述必须点到的名词。

    ``subject`` 来自 ``report.task_frame.subject``——上游 LLM 已经抽好的研究对象。
    优先用它，不要从原始问句里猜：2026-08-14 实测，问句「液冷服务器现在发酵到什么
    阶段？主线还是补涨？…」只被猜出唯一锚点「主线」，于是

      · 741 字实质回答（三家公司分层 + 17 条证据）因为缺口句里没写「主线」→ 判红
      · 185 字拒答因为**复述了题干**（题干含「主线」）→ 判绿

    判据把「复述问题」奖励成了「说清缺口」。同一形状已在
    ``docs/handoffs/2026-08-05-user-memory-recall-cjk.md`` 记过并作废：
    **实体在上游已经抽好，只是没往下传**——修法是接上游，不是造更好的分词器。
    """

    extra = (subject,) if subject else ()
    if "主线" in question:
        return extra + ("主线",)
    if "估值" in question:
        return extra + (
            "估值",
            "市值",
            "市盈",
            "市净",
            "盈利",
            "收入",
            "PE",
            "PB",
            "PS",
            "失效",
            "降级",
        )
    if "反弹" in question and any(marker in question for marker in ("持续", "多久")):
        return extra + (
            "反弹",
            "持续",
            "时长",
            "交易日",
            "失效",
            "继续成立",
            "量能",
            "成交",
        )
    if _is_cause_question(question):
        return extra + ("下跌", "原因", "归因", "因果", "诱因", "新闻", "事件")
    return extra + ("问题所需", "直接回答")


_QUESTION_ECHO_MIN_CHARS = 15


def _echoes_question(segment: str, question: str) -> bool:
    """段落是否只是把题干抄了一遍。

    复述题干会把题干里的每个词都带进来，于是任何基于「锚点出现在缺口句里」的
    判据都被无条件满足——2026-08-14 实测，一份 185 字的纯拒答就是这样过门的。
    这类段落不构成「说清了缺什么」，必须排除。

    阈值取 15 个字符：短于此的重合（「液冷服务器」这类实体名本身）是正常引用，
    正是我们想奖励的；长逐字片段才是复述。
    """

    if len(question) < _QUESTION_ECHO_MIN_CHARS:
        return False
    return any(
        question[i : i + _QUESTION_ECHO_MIN_CHARS] in segment
        for i in range(len(question) - _QUESTION_ECHO_MIN_CHARS + 1)
    )


def _has_task_specific_gap(question: str, answer: str, subject: str = "") -> bool:
    anchors = _task_gap_anchors(question, subject)
    clauses = re.split(r"[。；;\n]+", answer)
    if "估值" in question:
        return any(
            (
                _segment_asserts_valuation_gap(segment)
                or (
                    _segment_asserts_gap(segment)
                    and (
                        "条件" in segment
                        and any(marker in segment for marker in ("失效", "降级"))
                    )
                )
            )
            and not _echoes_question(segment, question)
            for clause in clauses
            for segment in _gap_segments(clause)
        )
    return any(
        _segment_asserts_gap(segment)
        and any(anchor in segment for anchor in anchors)
        and not _echoes_question(segment, question)
        for clause in clauses
        for segment in _gap_segments(clause)
    )


def _gap_segments(clause: str) -> tuple[str, ...]:
    return tuple(
        segment.strip()
        for segment in GAP_CONTRAST_SPLIT.split(clause)
        if segment.strip()
    )


def _segment_asserts_gap(segment: str) -> bool:
    for match in UNRESOLVED_GAP_ASSERTION.finditer(segment):
        prefix = segment[max(0, match.start() - 10) : match.start()]
        suffix = segment[match.end() : match.end() + 24]
        if GAP_ASSERTION_NEGATION.search(prefix):
            continue
        if GAP_ASSERTION_RESOLUTION.search(suffix):
            continue
        return True
    return False


def _segment_asserts_valuation_gap(segment: str) -> bool:
    return any(
        VALUATION_FIELD_RE.search(phrase) and _segment_asserts_gap(phrase)
        for phrase in re.split(r"[，,]+", segment)
    )


def _has_specific_cause_gap(answer: str) -> bool:
    explicit_time_context = bool(CAUSE_TIME.search(answer))
    return any(
        _segment_asserts_gap(segment)
        and
        (
            CAUSE_TIME.search(segment)
            or (explicit_time_context and CAUSE_DEICTIC_TIME.search(segment))
        )
        and CAUSE_SOURCE.search(segment)
        and CAUSE_OBJECT.search(segment)
        and CAUSE_UNCERTAINTY.search(segment)
        for clause in re.split(r"[。；;\n]+", answer)
        for segment in _gap_segments(clause)
    )


def _has_forward_duration(answer: str) -> bool:
    return any(
        FORECAST_DURATION.search(clause) and FORECAST_LANGUAGE.search(clause)
        for clause in re.split(r"[。；;\n]+", answer)
    )


def _has_invalidation_trigger(answer: str) -> bool:
    markdown_neutral = re.sub(r"[*_`#]", "", answer)
    return bool(INVALIDATION_TRIGGER.search(markdown_neutral))


def _has_specific_invalidation_gap(answer: str) -> bool:
    markdown_neutral = re.sub(r"[*_`#]", "", answer)
    for clause in re.split(r"[。；;\n]+", markdown_neutral):
        for segment in _gap_segments(clause):
            has_gap = bool(
                _segment_asserts_gap(segment)
                or (
                    any(
                        marker in segment
                        for marker in ("未核验", "已删除", "需补充")
                    )
                    and any(
                        marker in segment for marker in ("证据", "数据", "阈值")
                    )
                )
            )
            has_invalidation_slot = "失效条件" in segment or (
                "失效" in segment
                and any(marker in segment for marker in ("条件", "阈值", "触发"))
            ) or ("继续成立" in segment and "条件" in segment)
            if has_gap and has_invalidation_slot:
                return True
    return False


class SmokeProtocolError(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def semantic_answer_issues(
    question: str,
    report: dict[str, object],
    messages: list[object],
) -> list[str]:
    """Return user-facing semantic failures for the small release red bar."""

    issues: list[str] = []
    answer_status = report.get("answer_status")
    assistant_text = ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "assistant":
            assistant_text = str(message.get("content") or "")
            break
    if not assistant_text.strip():
        issues.append("assistant_answer_missing")
        return issues
    # 研究对象由上游 LLM 抽好后随 report 一起下发，别再从问句里猜（见
    # _task_gap_anchors 的说明）。取不到就退回原行为，不 fail closed——
    # 这个门只该拦「说不清缺口」，不该因为 payload 少个字段就误杀。
    task_frame = report.get("task_frame")
    subject = ""
    if isinstance(task_frame, dict):
        subject = str(task_frame.get("subject") or "").strip()
    explicit_gap = (
        _has_specific_cause_gap(assistant_text)
        if _is_cause_question(question)
        else _has_task_specific_gap(question, assistant_text, subject)
    )
    if answer_status == "partial" and not explicit_gap:
        issues.append(f"answer_status={answer_status!r}")
    elif answer_status not in {"complete", "partial"}:
        issues.append(f"answer_status={answer_status!r}")
    if "主线" in question:
        if not (
            any(
                marker in assistant_text
                for marker in (
                    "主线是",
                    "主线偏向",
                    "当前主线",
                    "主线判断",
                )
            )
            or DIRECT_ASSESSMENT.search(assistant_text)
        ):
            issues.append("mainline_direct_assessment_missing")
        if not (
            any(
                marker in assistant_text
                for marker in ("依据", "证据", "数据", "盘面", "缺少")
            )
            or QUANTIFIED_MARKET_OBSERVATION.search(assistant_text)
        ):
            issues.append("mainline_evidence_missing")
    if "明天" in question and any(marker in question for marker in ("反弹", "下跌")):
        for marker, name in (
            ("基准", "forecast_baseline_missing"),
            ("反弹", "forecast_rebound_missing"),
            ("下跌", "forecast_decline_missing"),
            ("失效", "forecast_invalidation_missing"),
        ):
            if marker not in assistant_text:
                issues.append(name)
    if "反弹" in question and any(marker in question for marker in ("持续", "多久")):
        if not _has_forward_duration(assistant_text):
            issues.append("forecast_duration_missing")
        has_specific_invalidation_gap = (
            answer_status == "partial"
            and _has_specific_invalidation_gap(assistant_text)
        )
        if not _has_invalidation_trigger(assistant_text) and not has_specific_invalidation_gap:
            issues.append("forecast_invalidation_missing")
    if "科创50" in question or "支撑点位" in question:
        if "支撑" not in assistant_text:
            issues.append("technical_support_missing")
        if "失效" not in assistant_text:
            issues.append("technical_invalidation_missing")
    return issues


class SecretScanner:
    def __init__(self) -> None:
        self.scanned_string_count = 0
        self.hits: list[dict[str, str]] = []

    def scan(self, value: object, source: str) -> None:
        if isinstance(value, str):
            self.scanned_string_count += 1
            for marker, pattern in SECRET_PATTERNS:
                if pattern.search(value):
                    self.hits.append({"source": source, "marker": marker})
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self.scan(item, f"{source}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                component = (
                    key
                    if isinstance(key, str) and SAFE_SOURCE_COMPONENT.fullmatch(key)
                    else "field"
                )
                self.scan(item, f"{source}.{component}")


class PublicLeakScanner:
    def __init__(self) -> None:
        self.scanned_string_count = 0
        self.hits: list[dict[str, str]] = []

    def scan(
        self,
        value: object,
        source: str,
        *,
        _path: tuple[str, ...] = (),
    ) -> None:
        if isinstance(value, str):
            self.scanned_string_count += 1
            if (
                len(_path) >= 3
                and _path[-3:] == ("report", "llm", "fallback_reason")
                and value in SAFE_LLM_FALLBACK_REASONS
            ):
                return
            for marker, pattern in PUBLIC_LEAK_PATTERNS:
                if pattern.search(value):
                    self.hits.append({"source": source, "marker": marker})
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self.scan(
                    item,
                    f"{source}[{index}]",
                    _path=(*_path, str(index)),
                )
            return
        if isinstance(value, dict):
            for key, item in value.items():
                component = (
                    key
                    if isinstance(key, str) and SAFE_SOURCE_COMPONENT.fullmatch(key)
                    else "field"
                )
                self.scan(
                    item,
                    f"{source}.{component}",
                    _path=(*_path, str(key)),
                )


def _validated_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("base URL must be an HTTP(S) origin")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip(
        "/"
    )


def _url(base_url: str, path: str, query: dict[str, object] | None = None) -> str:
    encoded = urllib.parse.urlencode(query or {})
    return f"{base_url}{path}" + (f"?{encoded}" if encoded else "")


def _open(
    request: urllib.request.Request,
    *,
    timeout: float,
    stage: str,
) -> BinaryIO:
    try:
        hostname = urllib.parse.urlsplit(request.full_url).hostname
        if hostname in LOOPBACK_HOSTS:
            return LOOPBACK_OPENER.open(request, timeout=timeout)
        return urllib.request.urlopen(request, timeout=timeout)
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        raise SmokeProtocolError(stage) from exc


def _request_bytes(
    method: str,
    url: str,
    *,
    timeout: float,
    stage: str,
    payload: dict[str, object] | None = None,
) -> bytes:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with _open(request, timeout=timeout, stage=stage) as response:
        return response.read()


def _request_json(
    method: str,
    url: str,
    *,
    timeout: float,
    stage: str,
    payload: dict[str, object] | None = None,
) -> object:
    body = _request_bytes(
        method,
        url,
        timeout=timeout,
        stage=stage,
        payload=payload,
    )
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SmokeProtocolError(stage) from exc


def _iter_sse(response: BinaryIO):
    event_type = "message"
    event_id: str | None = None
    data_lines: list[str] = []
    for raw_line in response:
        try:
            line = raw_line.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise SmokeProtocolError("sse_decode") from exc
        if not line:
            if data_lines:
                yield event_type, event_id, "\n".join(data_lines)
            event_type = "message"
            event_id = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            continue
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event_type = value
        elif field == "id":
            event_id = value
        elif field == "data":
            data_lines.append(value)
    if data_lines:
        yield event_type, event_id, "\n".join(data_lines)


def _json_object(data: str, stage: str) -> dict[str, object]:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SmokeProtocolError(stage) from exc
    if not isinstance(payload, dict):
        raise SmokeProtocolError(stage)
    return payload


def _stream_until_terminal(
    *,
    base_url: str,
    user: str,
    run_id: str,
    timeout: float,
    scanner: SecretScanner,
    public_scanner: PublicLeakScanner,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    deadline = time.monotonic() + timeout
    cursor = 0
    request_count = 0
    event_count = 0
    terminal_event_count = 0
    text_delta_count = 0
    no_progress_count = 0
    snapshots: dict[int, tuple[str, str, bool]] = {}
    highest_revision = 0
    draft_seen = False
    terminal_phase: str | None = None

    while time.monotonic() < deadline:
        request_count += 1
        previous_cursor = cursor
        remaining = max(0.1, deadline - time.monotonic())
        request = urllib.request.Request(
            _url(
                base_url,
                f"/api/runs/{urllib.parse.quote(run_id, safe='')}/events",
                {"user": user, "after": cursor},
            ),
            headers={"Accept": "text/event-stream"},
            method="GET",
        )
        with _open(
            request,
            timeout=remaining,
            stage="sse_connect",
        ) as response:
            for event_name, _, raw_data in _iter_sse(response):
                if not SAFE_SOURCE_COMPONENT.fullmatch(event_name):
                    raise SmokeProtocolError("sse_event_type")
                event_count += 1
                payload = _json_object(raw_data, "sse_payload")
                scanner.scan(payload, f"sse.{event_name}")
                public_scanner.scan(payload, f"sse.{event_name}")

                if event_name == "timeout":
                    continue
                if event_name == "run":
                    status = payload.get("status")
                    if status not in TERMINAL_RUN_STATUSES:
                        raise SmokeProtocolError("sse_terminal_status")
                    if status == "completed":
                        if not draft_seen:
                            raise SmokeProtocolError("answer_snapshot_draft")
                        latest_snapshot = snapshots.get(highest_revision)
                        if (
                            terminal_phase is None
                            or latest_snapshot is None
                            or latest_snapshot[0] == "verified_draft"
                            or latest_snapshot[2] is not True
                        ):
                            raise SmokeProtocolError("answer_snapshot_terminal")
                    terminal_event_count += 1
                    return (
                        payload,
                        {
                            "request_count": request_count,
                            "event_count": event_count,
                            "terminal_event_count": terminal_event_count,
                            "text_delta_count": text_delta_count,
                            "replayed": request_count > 1,
                        },
                        {
                            "draft_seen": draft_seen,
                            "terminal_phase": terminal_phase,
                            "highest_revision": highest_revision,
                            "snapshot_count": len(snapshots),
                        },
                    )

                seq = payload.get("seq")
                if seq is not None:
                    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
                        raise SmokeProtocolError("sse_sequence")
                    cursor = max(cursor, seq)

                canonical_type = payload.get("event_type")
                if (
                    not isinstance(canonical_type, str)
                    or canonical_type not in PUBLIC_EVENT_TYPES
                    or canonical_type != event_name
                ):
                    raise SmokeProtocolError("sse_public_event")
                event_payload = payload.get("payload")
                required_fields = EVENT_DEFINITIONS[canonical_type][
                    "payload_schema"
                ].get("required", [])
                if (
                    not isinstance(event_payload, dict)
                    or any(
                        field not in event_payload
                        for field in required_fields
                    )
                ):
                    raise SmokeProtocolError("sse_payload_schema")
                if canonical_type in {"message.complete", "message.error"}:
                    terminal_event_count += 1
                if canonical_type == "text.delta":
                    delta = event_payload.get("delta")
                    if not isinstance(delta, str):
                        raise SmokeProtocolError("text_delta")
                    if delta.strip():
                        text_delta_count += 1
                if canonical_type == "answer.snapshot":
                    revision = event_payload.get("revision")
                    phase = event_payload.get("phase")
                    text = event_payload.get("text")
                    final = event_payload.get("final")
                    if (
                        not isinstance(revision, int)
                        or isinstance(revision, bool)
                        or revision < 1
                        or not isinstance(phase, str)
                        or phase not in ANSWER_PHASES
                        or not isinstance(text, str)
                        or not text.strip()
                        or type(final) is not bool
                        or (phase == "verified_draft" and final)
                        or (phase != "verified_draft" and not final)
                    ):
                        raise SmokeProtocolError("answer_snapshot")
                    identity = (phase, text, final)
                    existing = snapshots.get(revision)
                    if revision < highest_revision:
                        raise SmokeProtocolError("answer_snapshot_revision")
                    if existing is not None:
                        if existing != identity:
                            raise SmokeProtocolError("answer_snapshot_conflict")
                        continue
                    if phase == "verified_draft" and snapshots:
                        raise SmokeProtocolError("answer_snapshot_revision")
                    snapshots[revision] = identity
                    highest_revision = revision
                    if phase == "verified_draft":
                        draft_seen = True
                    else:
                        if not draft_seen:
                            raise SmokeProtocolError("answer_snapshot_draft")
                        terminal_phase = phase

        if cursor == previous_cursor:
            no_progress_count += 1
            if no_progress_count >= 3:
                raise SmokeProtocolError("sse_no_progress")
        else:
            no_progress_count = 0

    raise SmokeProtocolError("sse_timeout")


def _safe_optional_label(value: object, stage: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not SAFE_LABEL.fullmatch(value)
        or any(pattern.search(value) for _, pattern in SECRET_PATTERNS)
    ):
        raise SmokeProtocolError(stage)
    return value


def _looks_like_high_entropy_token(value: str) -> bool:
    compact = value.replace("-", "").replace("_", "")
    if len(compact) < 48 or re.fullmatch(r"[A-Za-z0-9]+", compact) is None:
        return False
    character_classes = sum(
        bool(pattern.search(compact))
        for pattern in (
            re.compile(r"[a-z]"),
            re.compile(r"[A-Z]"),
            re.compile(r"[0-9]"),
        )
    )
    return character_classes == 3 and len(set(compact)) >= 16


def _safe_optional_provider_label(value: object, stage: str) -> str | None:
    label = _safe_optional_label(value, stage)
    if label is None:
        return None
    normalized = label.lower()
    return normalized if normalized in SAFE_LLM_PROVIDERS else None


def _safe_optional_model_label(value: object, stage: str) -> str | None:
    label = _safe_optional_label(value, stage)
    if label is None:
        return None
    if (
        CREDENTIAL_FAMILY_CASE_INSENSITIVE.search(label)
        or CREDENTIAL_FAMILY_CASE_SENSITIVE.search(label)
        or JWT_SHAPE.fullmatch(label)
        or _looks_like_high_entropy_token(label)
        or UNSAFE_MODEL_LABEL.search(label)
        or PRIVATE_PATH_COMPONENT.search(label)
        or re.match(r"^[A-Za-z]:/", label)
        or "://" in label
    ):
        raise SmokeProtocolError(stage)
    return label if SUPPORTED_MODEL_FAMILY.fullmatch(label) else None


def _safe_identifier(value: object, stage: str) -> str:
    if (
        not isinstance(value, str)
        or not SAFE_IDENTIFIER.fullmatch(value)
        or any(pattern.search(value) for _, pattern in SECRET_PATTERNS)
    ):
        raise SmokeProtocolError(stage)
    return value


def _retrieval_summary(trace: object) -> dict[str, str | None]:
    if not isinstance(trace, list):
        raise SmokeProtocolError("run_trace")
    summary: dict[str, str | None] = {
        "requested_mode": None,
        "effective_mode": None,
        "fallback_reason": None,
    }
    for step in trace:
        if not isinstance(step, dict):
            raise SmokeProtocolError("run_trace")
        if step.get("name") != "ask_retrieve_compose":
            continue
        output_summary = step.get("output_summary")
        if not isinstance(output_summary, str):
            raise SmokeProtocolError("run_trace")
        try:
            payload = json.loads(output_summary)
        except json.JSONDecodeError as exc:
            raise SmokeProtocolError("run_trace") from exc
        wiki_rag = payload.get("wiki_rag") if isinstance(payload, dict) else None
        if not isinstance(wiki_rag, dict):
            continue
        for key in summary:
            value = wiki_rag.get(key)
            summary[key] = _safe_optional_label(
                value if value else None,
                "run_trace",
            )
        break
    return summary


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def run_smoke(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    started = time.monotonic()
    deadline = started + args.timeout
    scanner = SecretScanner()
    public_scanner = PublicLeakScanner()
    readiness = {"page": False, "skills": False}
    summary: dict[str, object] = {
        "schema_version": 1,
        "readiness": readiness,
        "terminal_outcome": "protocol_error",
    }

    def remaining(stage: str) -> float:
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise SmokeProtocolError(stage)
        return seconds

    try:
        page = _request_bytes(
            "GET",
            _url(args.base_url, "/"),
            timeout=remaining("readiness_page"),
            stage="readiness_page",
        )
        if not page.strip():
            raise SmokeProtocolError("readiness_page")
        readiness["page"] = True

        skills = _request_json(
            "GET",
            _url(args.base_url, "/api/skills"),
            timeout=remaining("readiness_skills"),
            stage="readiness_skills",
        )
        if not isinstance(skills, list):
            raise SmokeProtocolError("readiness_skills")
        readiness["skills"] = True

        conversation = _request_json(
            "POST",
            _url(args.base_url, "/api/conversations"),
            timeout=remaining("create_conversation"),
            stage="create_conversation",
            payload={"title": "Self-use smoke", "user": args.user},
        )
        if not isinstance(conversation, dict):
            raise SmokeProtocolError("create_conversation")
        conversation_id = _safe_identifier(
            conversation.get("conversation_id"),
            "create_conversation",
        )

        turn = _request_json(
            "POST",
            _url(
                args.base_url,
                f"/api/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages",
            ),
            timeout=remaining("create_message"),
            stage="create_message",
            payload={
                "content": args.question,
                "skill_mode": "hybrid",
                "selected_skill_ids": [],
                "user": args.user,
            },
        )
        if not isinstance(turn, dict):
            raise SmokeProtocolError("create_message")
        run_id = _safe_identifier(turn.get("run_id"), "create_message")

        terminal_run, sse_summary, answer_stream = _stream_until_terminal(
            base_url=args.base_url,
            user=args.user,
            run_id=run_id,
            timeout=remaining("sse_timeout"),
            scanner=scanner,
            public_scanner=public_scanner,
        )
        run_status = terminal_run["status"]
        degrades = terminal_run.get("degrades", [])
        if not isinstance(degrades, list) or not all(
            isinstance(item, str) for item in degrades
        ):
            raise SmokeProtocolError("run_degrades")

        report = _request_json(
            "GET",
            _url(
                args.base_url,
                f"/api/runs/{urllib.parse.quote(run_id, safe='')}/report",
                {"user": args.user},
            ),
            timeout=remaining("run_report"),
            stage="run_report",
        )
        trace = _request_json(
            "GET",
            _url(
                args.base_url,
                f"/api/runs/{urllib.parse.quote(run_id, safe='')}/trace",
                {"user": args.user},
            ),
            timeout=remaining("run_trace"),
            stage="run_trace",
        )
        messages = _request_json(
            "GET",
            _url(
                args.base_url,
                f"/api/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages",
                {"user": args.user},
            ),
            timeout=remaining("conversation_messages"),
            stage="conversation_messages",
        )
        if not isinstance(messages, list):
            raise SmokeProtocolError("conversation_messages")
        scanner.scan(terminal_run, "terminal_run")
        scanner.scan(report, "report")
        scanner.scan(trace, "trace")
        scanner.scan(messages, "messages")
        public_scanner.scan(terminal_run, "terminal_run")
        public_scanner.scan(report, "report", _path=("report",))
        public_scanner.scan(trace, "trace")
        public_scanner.scan(messages, "messages")

        report_present = isinstance(report, dict)
        if run_status == "completed" and not report_present:
            raise SmokeProtocolError("run_report")
        report_payload = report if isinstance(report, dict) else {}
        modules = report_payload.get("modules", [])
        if not isinstance(modules, list):
            raise SmokeProtocolError("run_report_modules")
        llm = report_payload.get("llm")
        if run_status == "completed" and not isinstance(llm, dict):
            raise SmokeProtocolError("model_metadata")
        llm_payload = llm if isinstance(llm, dict) else {}
        llm_used = llm_payload.get("used")
        if llm_payload and not isinstance(llm_used, bool):
            raise SmokeProtocolError("model_metadata")

        semantic_issues = (
            semantic_answer_issues(args.question, report_payload, messages)
            if getattr(args, "semantic", False)
            else []
        )
        if semantic_issues:
            summary["semantic"] = {"passed": False, "issues": semantic_issues}
            raise SmokeProtocolError("semantic_answer")
        if getattr(args, "semantic", False):
            summary["semantic"] = {"passed": True, "issues": []}

        outcome = (
            "degraded" if run_status == "completed" and degrades else str(run_status)
        )
        summary.update(
            {
                "run_id": run_id,
                "run_status": run_status,
                "terminal_outcome": outcome,
                "degrade_count": len(degrades),
                "sse": sse_summary,
                "answer_stream": answer_stream,
                "report": {
                    "present": report_present,
                    "status": _safe_optional_label(
                        report_payload.get("status"),
                        "report_status",
                    ),
                    "module_count": len(modules),
                },
                "model": {
                    "metadata_present": isinstance(llm, dict),
                    "used": llm_used if isinstance(llm_used, bool) else None,
                    "provider": _safe_optional_provider_label(
                        llm_payload.get("provider"),
                        "model_metadata",
                    ),
                    "model": _safe_optional_model_label(
                        llm_payload.get("model"),
                        "model_metadata",
                    ),
                },
                "retrieval": _retrieval_summary(trace),
                "gate_receipt": extract_gate_receipt(report_payload),
                "gate_receipt_table": table_row(extract_gate_receipt(report_payload)),
            }
        )
        exit_code = 0 if run_status == "completed" else 1
    except SmokeProtocolError as exc:
        summary["failure_stage"] = exc.stage
        exit_code = 2

    summary["secret_scan"] = {
        "scanned_string_count": scanner.scanned_string_count,
        "hit_count": len(scanner.hits),
        "hits": scanner.hits,
    }
    summary["public_scan"] = {
        "scanned_string_count": public_scanner.scanned_string_count,
        "hit_count": len(public_scanner.hits),
        "hits": public_scanner.hits,
    }
    summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
    if scanner.hits:
        summary["terminal_outcome"] = "secret_scan_failed"
        exit_code = 2
    elif public_scanner.hits:
        summary["terminal_outcome"] = "public_scan_failed"
        exit_code = 2
    return exit_code, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a redacted Workbench self-use smoke check"
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="将最终正文 required outputs 纳入退出码（默认仅协议 smoke）",
    )
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.base_url = _validated_base_url(args.base_url)
        args.user = args.user.strip()
        args.question = args.question.strip()
        if not args.user or not args.question or args.timeout <= 0:
            raise ValueError
        output = Path(args.output).expanduser()
    except ValueError:
        print("invalid smoke arguments", file=sys.stderr)
        return 2

    exit_code, summary = run_smoke(args)
    try:
        _atomic_write_json(output, summary)
    except OSError:
        print("failed to write smoke summary", file=sys.stderr)
        return 2
    print(f"smoke outcome: {summary['terminal_outcome']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
