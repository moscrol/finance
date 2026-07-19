from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar

from intelligence.services.answer_orchestrator import (
    QUESTION_NEWS_IMPACT,
    QUESTION_STOCK_DEEP_DIVE,
    QuestionPlan,
)

DEFAULT_COMPANY_CMD = "{python_sh} -m disclosure_lookup.cli company {company_sh} --days {days} --source {sources}"


@dataclass(frozen=True)
class L3LookupConfig:
    """Runtime config for official-disclosure lookup tools.

    The orchestration layer deliberately depends on CLI templates instead of a
    concrete module path. This keeps finance-workspace decoupled from whichever
    repo owns the disclosure implementation today, and lets the same interface
    be replaced by HTTP API / MCP later.
    """

    enabled: bool = False
    company_cmd: str | None = DEFAULT_COMPANY_CMD
    cninfo_cmd: str | None = None
    sse_einteract_cmd: str | None = None
    timeout: int = 480
    limit: int = 5
    days: int = 30
    python: str = sys.executable
    pythonpath: str | None = None
    cwd: str | None = None
    cache_dir: str | None = None
    cache_ttl_seconds: int = 0

    # 默认结果缓存：公告/互动易在 15 分钟内基本不会变，缓存避免同一会话内
    # 重复拉 SSE uid 映射（首建 6-7 分钟）导致超时。设 FINANCE_L3_CACHE_TTL_SECONDS=0 可关。
    DEFAULT_CACHE_DIR: ClassVar[str] = str(Path.home() / ".cache" / "finance-l3")
    DEFAULT_CACHE_TTL_SECONDS: ClassVar[int] = 900

    @classmethod
    def from_env(
        cls,
        *,
        enabled: bool = False,
        timeout: int | None = None,
        limit: int | None = None,
    ) -> "L3LookupConfig":
        env_enabled = _env_bool("FINANCE_L3_LOOKUP_ENABLED")
        return cls(
            enabled=enabled or env_enabled,
            company_cmd=os.environ.get("FINANCE_L3_COMPANY_CMD")
            or DEFAULT_COMPANY_CMD,
            cninfo_cmd=os.environ.get("FINANCE_L3_CNINFO_CMD") or None,
            sse_einteract_cmd=os.environ.get("FINANCE_L3_SSE_EINTERACT_CMD") or None,
            timeout=timeout if timeout is not None else _env_int("FINANCE_L3_LOOKUP_TIMEOUT", 480),
            limit=limit if limit is not None else _env_int("FINANCE_L3_LOOKUP_LIMIT", 5),
            days=_env_int("FINANCE_L3_LOOKUP_DAYS", 30),
            python=os.environ.get("FINANCE_L3_PYTHON") or sys.executable,
            pythonpath=os.environ.get("FINANCE_L3_PYTHONPATH") or None,
            cwd=os.environ.get("FINANCE_L3_CWD") or None,
            cache_dir=os.environ.get("FINANCE_L3_CACHE_DIR") or cls.DEFAULT_CACHE_DIR,
            cache_ttl_seconds=_env_int("FINANCE_L3_CACHE_TTL_SECONDS", cls.DEFAULT_CACHE_TTL_SECONDS),
        )


@dataclass(frozen=True)
class L3EvidenceGap:
    kind: str
    priority: str
    reason: str
    source_types: tuple[str, ...] = ("cninfo",)


@dataclass(frozen=True)
class L3EvidenceItem:
    source_type: str
    title: str
    summary: str
    citation: str = ""
    raw: str = ""


@dataclass
class L3EvidenceBundle:
    query: str
    gaps: list[L3EvidenceGap] = field(default_factory=list)
    items: list[L3EvidenceItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)

    @property
    def looked_up(self) -> bool:
        return bool(self.commands)

    def to_prompt_block(self) -> str:
        lines = [
            "## L3 官方证据工具补查（运行时工具证据，不等同于已沉淀知识库）",
            "- 口径：L3 测的是「公司端兑现度」而非「题材合法性」；题材可由产业端催化独立驱动，无公告 ≠ 无驱动，不得据此降级。",
            "- 结论固定写成两行：「驱动=产业端何事件（见催化归因/叙事源）；公司端兑现=有/无+口径」。",
            "- 使用原则：公告/问询函/互动易用于约束事实边界；若只查到澄清、风险提示或无订单口径，不能把预期当兑现。",
        ]
        if self.gaps:
            lines.append("- 触发缺口：")
            for gap in self.gaps:
                sources = "/".join(gap.source_types)
                lines.append(f"  - {gap.priority}·{gap.kind}：{gap.reason}；建议源={sources}")
        if self.items:
            lines.append("- 工具返回：")
            for idx, item in enumerate(self.items, start=1):
                cite = f"；来源={item.citation}" if item.citation else ""
                lines.append(f"  - [L{idx}] {item.source_type}｜{item.title}：{item.summary}{cite}")
        else:
            lines.append(
                "- 工具返回：未取得可注入的 L3 证据；读作「公司端尚未兑现」，"
                "驱动是否成立另看产业端催化；不得据此否定题材或降级，但也不得把预期写成已兑现。"
            )
        if self.warnings:
            lines.append("- 工具警告：")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


def lookup_l3_evidence(
    query: str,
    plan: QuestionPlan,
    local_evidence_text: str,
    *,
    config: L3LookupConfig | None = None,
    company_hint: str | None = None,
) -> L3EvidenceBundle:
    cfg = config or L3LookupConfig.from_env()
    bundle = L3EvidenceBundle(query=query)
    gaps = detect_l3_gaps(query, plan, local_evidence_text)
    bundle.gaps.extend(gaps)

    if not _should_consider_l3_lookup(plan):
        bundle.warnings.append(f"本问题类型不需要 L3 官方补查：{plan.question_type}")
        return bundle
    if not gaps:
        bundle.warnings.append("本轮本地证据未识别到 P0/P1 L3 缺口，跳过外接公告工具。")
        return bundle
    if not cfg.enabled:
        bundle.warnings.append("L3 lookup 未启用；可通过 ask --l3-lookup 或 FINANCE_L3_LOOKUP_ENABLED=1 打开。")
        return bundle

    stock = _extract_stock_hint(query)
    if company_hint:
        stock["stock_name"] = str(company_hint).strip()
    wanted = _wanted_sources(gaps)
    if cfg.company_cmd:
        _run_source("company", cfg.company_cmd, query, stock, cfg, bundle, wanted_sources=wanted)
        return bundle
    if "cninfo" in wanted:
        _run_source("cninfo", cfg.cninfo_cmd, query, stock, cfg, bundle)
    if "sse_einteract" in wanted:
        _run_source("sse_einteract", cfg.sse_einteract_cmd, query, stock, cfg, bundle)
    if not bundle.commands:
        bundle.warnings.append(
            "L3 lookup 已启用，但未配置命令模板；请设置 FINANCE_L3_CNINFO_CMD / FINANCE_L3_SSE_EINTERACT_CMD。"
        )
    return bundle


def lookup_l3_company(
    company: str,
    *,
    sources: tuple[str, ...] = ("cninfo",),
    config: L3LookupConfig | None = None,
) -> L3EvidenceBundle:
    cfg = config or L3LookupConfig.from_env(enabled=True)
    bundle = L3EvidenceBundle(query=company)
    if not cfg.enabled:
        bundle.warnings.append("L3 lookup 未启用；l3-ingest 需要启用运行时公告/互动易工具。")
        return bundle

    stock = _extract_stock_hint(company)
    if not stock.get("stock_name"):
        stock["stock_name"] = company
    wanted = {source.strip() for source in sources if source.strip()}
    if not wanted:
        wanted = {"cninfo"}
    if cfg.company_cmd:
        _run_source("company", cfg.company_cmd, company, stock, cfg, bundle, wanted_sources=wanted)
        return bundle
    if "cninfo" in wanted:
        _run_source("cninfo", cfg.cninfo_cmd, company, stock, cfg, bundle)
    if "sse_einteract" in wanted:
        _run_source("sse_einteract", cfg.sse_einteract_cmd, company, stock, cfg, bundle)
    if not bundle.commands:
        bundle.warnings.append(
            "L3 lookup 已启用，但未配置命令模板；请设置 FINANCE_L3_COMPANY_CMD 或单源命令模板。"
        )
    return bundle


def detect_l3_gaps(query: str, plan: QuestionPlan, local_evidence_text: str) -> list[L3EvidenceGap]:
    if not _should_consider_l3_lookup(plan):
        return []
    text = _normalize(f"{query}\n{local_evidence_text}")
    gaps: list[L3EvidenceGap] = []

    hard_terms = ("客户", "订单", "合同", "中标", "量产", "产能", "扩产", "投产", "出货", "验证", "认证", "供应")
    weak_or_missing_terms = (
        "未命中",
        "缺口",
        "不足",
        "待验证",
        "证据不足",
        "没有",
        "需验证",
        "仍需跟踪",
        "待复核",
    )
    if any(t in text for t in hard_terms) and any(t in text for t in weak_or_missing_terms):
        gaps.append(
            L3EvidenceGap(
                kind="hard_evidence_gap",
                priority="P0",
                reason="客户/订单/量产/产能等硬证据不足，必须用公告、问询函或互动易约束事实边界。",
                source_types=("cninfo", "sse_einteract"),
            )
        )
    if any(t in text for t in ("公告", "问询函", "风险提示", "澄清", "异动")):
        gaps.append(
            L3EvidenceGap(
                kind="regulatory_disclosure_check",
                priority="P0",
                reason="问题显式涉及公告/问询函/风险提示，应优先查官方披露而不是只靠研报或盘面。",
                source_types=("cninfo",),
            )
        )
    if plan.question_type == QUESTION_NEWS_IMPACT and not gaps:
        gaps.append(
            L3EvidenceGap(
                kind="source_text_boundary",
                priority="P1",
                reason="新闻/公告影响题需要确认原始披露或公司口径，避免根据标题扩写。",
                source_types=("cninfo", "sse_einteract"),
            )
        )
    return _dedupe_gaps(gaps)


def _run_source(
    source_type: str,
    command_template: str | None,
    query: str,
    stock: dict[str, str],
    cfg: L3LookupConfig,
    bundle: L3EvidenceBundle,
    wanted_sources: set[str] | None = None,
) -> None:
    if not command_template:
        bundle.warnings.append(f"{source_type} 命令模板未配置，跳过。")
        return
    command = _render_command(command_template, query, stock, cfg.limit, cfg.days, cfg.python, wanted_sources)
    bundle.commands.append(" ".join(command))
    env = _subprocess_env(cfg)
    cwd = os.path.expanduser(cfg.cwd) if cfg.cwd else None
    cached_stdout = _read_cached_stdout(cfg, source_type, command, cwd)
    if cached_stdout is not None:
        items = _parse_lookup_output(source_type, cached_stdout)
        if not items:
            bundle.warnings.append(f"{source_type} 缓存命中但没有解析到可用证据。")
        bundle.items.extend(items[: cfg.limit])
        return
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=cfg.timeout,
            check=False,
            env=env,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        bundle.warnings.append(f"{source_type} 查询超时（{cfg.timeout}s），回答需标记 L3 未完成。")
        return
    except OSError as exc:
        bundle.warnings.append(f"{source_type} 查询无法启动：{exc}")
        return

    if completed.returncode != 0:
        stderr = _squash(completed.stderr, 180)
        bundle.warnings.append(f"{source_type} 查询失败 rc={completed.returncode}：{stderr or '无 stderr'}")
        return
    _write_cached_stdout(cfg, source_type, command, cwd, completed.stdout)
    items = _parse_lookup_output(source_type, completed.stdout)
    if not items:
        bundle.warnings.append(f"{source_type} 查询成功但没有解析到可用证据。")
    bundle.items.extend(items[: cfg.limit])


def _render_command(
    template: str,
    query: str,
    stock: dict[str, str],
    limit: int,
    days: int,
    python: str,
    wanted_sources: set[str] | None = None,
) -> list[str]:
    company = stock.get("stock_name") or query
    sources = ",".join(s for s in ("cninfo", "sse_einteract", "irm_szse") if not wanted_sources or s in wanted_sources)
    values = {
        "query": query,
        "query_sh": shlex.quote(query),
        "python": python,
        "python_sh": shlex.quote(python),
        "company": company,
        "company_sh": shlex.quote(company),
        "stock_code": stock.get("stock_code", ""),
        "stock_code_sh": shlex.quote(stock.get("stock_code", "")),
        "stock_name": stock.get("stock_name", ""),
        "stock_name_sh": shlex.quote(stock.get("stock_name", "")),
        "sources": sources or "cninfo",
        "sources_sh": shlex.quote(sources or "cninfo"),
        "limit": str(limit),
        "days": str(days),
    }
    rendered = template.format_map(values)
    return shlex.split(rendered)


def _parse_lookup_output(source_type: str, stdout: str) -> list[L3EvidenceItem]:
    text = str(stdout or "").strip()
    if not text:
        return []
    parsed = _try_parse_json_items(source_type, text)
    if parsed:
        return parsed
    lines = [_squash(line, 220) for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    parsed_lines = _parse_plaintext_lookup_lines(source_type, lines)
    if parsed_lines:
        return parsed_lines
    if all(_is_non_evidence_cli_line(line) for line in lines):
        return []
    title = lines[0]
    summary = "；".join(lines[:4])
    return [L3EvidenceItem(source_type=source_type, title=title, summary=summary, citation="runtime cli")]


def _try_parse_json_items(source_type: str, text: str) -> list[L3EvidenceItem]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    rows: list[Any]
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("items") or data.get("results") or data.get("data") or []
    else:
        rows = []
    out: list[L3EvidenceItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        actual_source = str(
            row.get("source_type")
            or row.get("provider")
            or row.get("source")
            or source_type
        )
        if actual_source.startswith(("http://", "https://")):
            actual_source = source_type
        title = str(row.get("title") or row.get("name") or row.get("question") or source_type)
        body = str(row.get("summary") or row.get("content") or row.get("answer") or row.get("text") or "")
        if not body:
            continue
        date = row.get("date") or row.get("publish_date") or row.get("source_date") or ""
        url = row.get("url") or row.get("source") or row.get("id") or "runtime cli"
        prefix = f"{date} " if date else ""
        out.append(
            L3EvidenceItem(
                source_type=actual_source,
                title=_squash(title, 120),
                summary=_squash(prefix + body, 260),
                citation=str(url),
                raw=json.dumps(row, ensure_ascii=False)[:2000],
            )
        )
    return out


def _is_non_evidence_cli_line(line: str) -> bool:
    text = str(line or "").strip().lower()
    return bool(
        not text
        or text.startswith(("[warn]", "[warning]", "[error]", "warning:", "error:"))
        or text in {"(无结果)", "无结果", "(no results)", "no results"}
        or "无法解析公司" in text
    )


def _parse_plaintext_lookup_lines(source_type: str, lines: list[str]) -> list[L3EvidenceItem]:
    out: list[L3EvidenceItem] = []
    date_line = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?\s+")
    source_line = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?\s+(\S+)\s+")
    for idx, line in enumerate(lines):
        if not date_line.search(line):
            continue
        source_match = source_line.search(line)
        actual_source = source_match.group(1) if source_match else source_type
        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        citation = _first_url(line) or (_first_url(next_line) if not date_line.search(next_line) else "") or "runtime cli"
        out.append(
            L3EvidenceItem(
                source_type=actual_source,
                title=_squash(line, 160),
                summary=_squash(line, 260),
                citation=citation,
                raw=line,
            )
        )
    return out


def _first_url(text: str) -> str:
    match = re.search(r"https?://\S+", str(text or ""))
    return match.group(0).rstrip("；;,.，。") if match else ""


def _should_consider_l3_lookup(plan: QuestionPlan) -> bool:
    return plan.question_type in {QUESTION_STOCK_DEEP_DIVE, QUESTION_NEWS_IMPACT}


def _wanted_sources(gaps: list[L3EvidenceGap]) -> set[str]:
    out: set[str] = set()
    for gap in gaps:
        out.update(gap.source_types)
    return out


def _extract_stock_hint(query: str) -> dict[str, str]:
    q = str(query or "")
    code = ""
    name = ""
    m = re.search(r"\b(\d{6})(?:\.(?:SH|SZ|BJ))?\b", q, re.I)
    if m:
        code = m.group(1)
    chunks = re.findall(r"[\u4e00-\u9fff]{2,8}", q)
    stop = {"深挖", "重点看", "查公告", "验证订单", "怎么看", "还有空间", "互动易"}
    for chunk in chunks:
        clean = re.sub(r"^(深挖|看看|看下|分析|查询|查|重点看)", "", chunk.strip())
        clean = re.sub(r"(公告|互动易|问询函|订单|客户|验证|重点|情况|怎么看).*$", "", clean)
        if clean and clean not in stop and len(clean) >= 2:
            name = clean
            break
    return {"stock_code": code, "stock_name": name}


def _dedupe_gaps(gaps: list[L3EvidenceGap]) -> list[L3EvidenceGap]:
    seen: set[tuple[str, str]] = set()
    out: list[L3EvidenceGap] = []
    for gap in gaps:
        key = (gap.kind, gap.priority)
        if key not in seen:
            seen.add(key)
            out.append(gap)
    return out


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def _squash(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def _env_bool(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name) or "").strip() or default)
    except ValueError:
        return default


def _subprocess_env(cfg: L3LookupConfig) -> dict[str, str]:
    env = os.environ.copy()
    if not cfg.pythonpath:
        return env
    raw_parts = [part for part in str(cfg.pythonpath).split(os.pathsep) if part]
    parts = [os.path.expanduser(part) for part in raw_parts]
    existing = env.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _cache_path(cfg: L3LookupConfig, source_type: str, command: list[str], cwd: str | None) -> Path | None:
    if not cfg.cache_dir or cfg.cache_ttl_seconds <= 0:
        return None
    cache_dir = Path(os.path.expanduser(cfg.cache_dir))
    key_payload = {
        "source_type": source_type,
        "command": command,
        "cwd": cwd or "",
        "pythonpath": cfg.pythonpath or "",
    }
    digest = sha256(json.dumps(key_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def _read_cached_stdout(
    cfg: L3LookupConfig,
    source_type: str,
    command: list[str],
    cwd: str | None,
) -> str | None:
    path = _cache_path(cfg, source_type, command, cwd)
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    cached_at = float(payload.get("cached_at") or 0)
    if time.time() - cached_at > cfg.cache_ttl_seconds:
        return None
    stdout = payload.get("stdout")
    return stdout if isinstance(stdout, str) else None


def _write_cached_stdout(
    cfg: L3LookupConfig,
    source_type: str,
    command: list[str],
    cwd: str | None,
    stdout: str,
) -> None:
    path = _cache_path(cfg, source_type, command, cwd)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cached_at": time.time(),
            "source_type": source_type,
            "command": command,
            "cwd": cwd or "",
            "stdout": stdout,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return
