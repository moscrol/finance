"""Source-routing + real subprocess wiring of theme-radar 模式 as `ask` 召回后端.

`ask` does not re-implement the theme-radar report generators; it *fans out* a
query to them and folds their output into the unified six-section answer:

- ``brief``  → finance-workspace ``skills/theme-radar/scripts/radar.py --mode brief``
  (产业维：题材定锚 / 产业链上下游 / 细分核心个股)
- ``replay`` → knowledge-base ``skills/theme-radar-reports/scripts/generate_fermentation_report.py``
  (模块7 时间维：发酵阶段 / 关键时间节点 / 验证清单)

Each backend is invoked defensively (timeout + return-code check + graceful
degrade). A backend that cannot run in the current environment (missing script,
unmatched theme, timeout, non-zero exit) records a ``warning`` and is skipped
without affecting the other sources — the wiring stays real even when a given
backend is unavailable.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RADAR_SCRIPT = REPO_ROOT / "skills" / "theme-radar" / "scripts" / "radar.py"

DEFAULT_MODULE_TIMEOUT = 180

MODULE_BRIEF = "brief"
MODULE_REPLAY = "replay"
ALL_MODULES = (MODULE_BRIEF, MODULE_REPLAY)

# Deterministic routing: query intent → recall backends.
BRIEF_TRIGGERS = (
    "是什么", "定义", "定锚", "产业链", "上下游", "谁受益", "受益",
    "速览", "速读", "细分", "核心个股", "标的", "分层", "全景", "上车", "值不值",
)
REPLAY_TRIGGERS = (
    "发酵", "怎么走到今天", "走到今天", "时间线", "时间节点", "复盘",
    "起涨", "补涨", "认同度", "演变", "节点", "怎么发酵", "谁先",
)


@dataclass
class ModuleResult:
    name: str
    ok: bool = False
    command: str = ""
    title: str = ""
    theme_key: str = ""
    highlights: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    citation_source: str = ""
    citation_detail: str = ""
    warning: str = ""


def _norm(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def route_modules(query: str, explicit: list[str] | None = None) -> list[str]:
    """Map a query to the set of theme-radar backends to fan out to.

    A bare theme word (no intent keyword) fans out to *both* brief + replay so a
    query like 「液冷服务器」 gets the 产业维 and 时间维 views at once.
    """
    if explicit is not None:
        return [m for m in explicit if m in ALL_MODULES]
    q = str(query or "")
    routed: list[str] = []
    if any(t in q for t in BRIEF_TRIGGERS):
        routed.append(MODULE_BRIEF)
    if any(t in q for t in REPLAY_TRIGGERS):
        routed.append(MODULE_REPLAY)
    if not routed:
        routed = list(ALL_MODULES)
    return routed


def run_module(name: str, query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    if name == MODULE_BRIEF:
        return run_brief(query, kb_wiki, timeout)
    if name == MODULE_REPLAY:
        return run_replay(query, kb_wiki, timeout)
    return ModuleResult(name=name, warning=f"未知模块: {name}")


# --------------------------------------------------------------------------- #
# brief (产业维) — finance-workspace radar.py --mode brief
# --------------------------------------------------------------------------- #
def run_brief(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    res = ModuleResult(name=MODULE_BRIEF)
    if not RADAR_SCRIPT.exists():
        res.warning = f"radar.py 不存在: {RADAR_SCRIPT}"
        return res
    if not kb_wiki:
        res.warning = "brief 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        return res
    vault = Path(kb_wiki).expanduser()
    cmd = [sys.executable, str(RADAR_SCRIPT), "--term", str(query), "--vault", str(vault), "--mode", "brief"]
    res.command = f"radar.py --mode brief --term {query} --vault <kb-wiki>"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO_ROOT))
    except subprocess.TimeoutExpired:
        res.warning = f"brief 超时(>{timeout}s)，已跳过"
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"brief 调用失败: {exc}"
        return res
    if proc.returncode != 0:
        res.warning = f"brief 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        return res
    res.citation_source = "theme-radar · radar.py --mode brief（产业维）"
    res.citation_detail = f"--term {query}"
    _parse_brief(proc.stdout, res)
    res.ok = True
    return res


def _bold_first(line: str) -> str | None:
    m = re.search(r"\*\*(.+?)\*\*", line)
    return m.group(1).strip() if m else None


def _section_block(lines: list[str], header_substr: str) -> list[str]:
    """Lines after the first header/bold line containing ``header_substr``,
    up to the next ``## `` section header."""
    start = None
    for i, ln in enumerate(lines):
        if header_substr in ln and (ln.startswith("#") or ln.lstrip().startswith("**")):
            start = i
            break
    if start is None:
        return []
    out: list[str] = []
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        out.append(ln)
    return out


def _parse_brief(report: str, res: ModuleResult) -> None:
    lines = report.splitlines()
    m = re.search(r"\*\*一句话定锚\*\*[：:]\s*(.+)", report)
    if m:
        res.title = m.group(1).strip()
        res.highlights.append(f"产业定锚：{res.title}")

    concepts: list[str] = []
    for ln in _section_block(lines, "相关概念"):
        s = ln.strip()
        if s.startswith("- "):
            nm = _bold_first(s)
            if nm and nm not in concepts:
                concepts.append(nm)
        if len(concepts) >= 6:
            break
    if concepts:
        res.highlights.append("相关概念：" + "、".join(concepts))

    chain = 0
    for ln in _section_block(lines, "产业链上下游"):
        s = ln.strip()
        if s.startswith("- **"):
            txt = re.sub(r"（看点[：:].*?）", "", s[2:]).strip()
            res.highlights.append("产业链｜" + txt)
            chain += 1
        if chain >= 4:
            break

    core: list[str] = []
    in_sec = False
    for ln in lines:
        if ln.startswith("## "):
            in_sec = "核心个股" in ln
            continue
        if in_sec and ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[1] == "核心" and cells[0] and cells[0] not in core:
                core.append(cells[0])
        if len(core) >= 10:
            break
    if core:
        res.highlights.append("各细分核心层个股：" + "、".join(core))


# --------------------------------------------------------------------------- #
# replay (时间维 模块7) — knowledge-base generate_fermentation_report.py
# --------------------------------------------------------------------------- #
def resolve_theme_key(query: str, kb_root: Path) -> str | None:
    """Map a free query to an existing ``theme_signals.json`` theme key.

    Exact match → key contained in query (longest) → query contained in key
    (shortest). Returns ``None`` if no theme has fermentation signals yet.
    """
    path = kb_root / "wiki" / "relations" / "theme_signals.json"
    try:
        themes = json.loads(path.read_text(encoding="utf-8")).get("themes", {})
    except Exception:
        return None
    keys = list(themes.keys())
    nq = _norm(query)
    for k in keys:
        if _norm(k) == nq:
            return k
    subs = [k for k in keys if _norm(k) and _norm(k) in nq]
    if subs:
        return max(subs, key=lambda k: len(_norm(k)))
    sup = [k for k in keys if nq and nq in _norm(k)]
    if sup:
        return min(sup, key=lambda k: len(_norm(k)))
    return None


def run_replay(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    res = ModuleResult(name=MODULE_REPLAY)
    if not kb_wiki:
        res.warning = "replay 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        return res
    wiki = Path(kb_wiki).expanduser().resolve()
    kb_root = wiki.parent
    script = kb_root / "skills" / "theme-radar-reports" / "scripts" / "generate_fermentation_report.py"
    if not script.exists():
        res.warning = f"replay 脚本不存在: {script}"
        return res
    theme_key = resolve_theme_key(query, kb_root)
    if not theme_key:
        res.warning = "theme_signals.json 无匹配主题，replay 跳过（该题材尚未建发酵信号）"
        return res
    res.theme_key = theme_key
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        out_path = tf.name
    cmd = [sys.executable, str(script), theme_key, "--project-root", str(kb_root), "--out", out_path]
    res.command = f"generate_fermentation_report.py {theme_key}"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        res.warning = f"replay 超时(>{timeout}s)，已跳过"
        Path(out_path).unlink(missing_ok=True)
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"replay 调用失败: {exc}"
        Path(out_path).unlink(missing_ok=True)
        return res
    if proc.returncode != 0:
        res.warning = f"replay 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        Path(out_path).unlink(missing_ok=True)
        return res
    try:
        report = Path(out_path).read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"replay 输出读取失败: {exc}"
        return res
    finally:
        Path(out_path).unlink(missing_ok=True)
    res.citation_source = "knowledge-base · generate_fermentation_report.py（模块7 发酵复盘）"
    res.citation_detail = f"theme={theme_key}"
    _parse_replay(report, res, query, theme_key)
    res.ok = True
    return res


def _timeline_rows(report: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for ln in _section_block(report.splitlines(), "关键时间节点"):
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 5 or not re.match(r"\d{4}-\d{2}-\d{2}", cells[1]):
            continue
        rows.append((cells[1], cells[2], cells[4]))
    return rows


def _parse_replay(report: str, res: ModuleResult, query: str, theme_key: str) -> None:
    note = "" if _norm(theme_key) == _norm(query) else f"（按主题键「{theme_key}」回溯）"
    m = re.search(r"当前阶段\s*\*\*(.+?)\*\*", report)
    cover = re.search(r"库内覆盖\s*([^\n]+)", report)
    if m:
        res.title = m.group(1).strip()
        cov = (cover.group(1).strip() if cover else "").rstrip()
        res.highlights.append(f"发酵阶段：{res.title}" + (f"｜库内覆盖 {cov}" if cov else "") + note)

    rows = _timeline_rows(report)
    for t, ev, grade in rows[-3:]:
        ev = ev.strip()
        res.highlights.append(f"节点 {t}：{ev[:48]}{'…' if len(ev) > 48 else ''}（{grade}）")

    for ln in _section_block(report.splitlines(), "验证清单"):
        s = ln.strip()
        if s.startswith(("- [ ]", "- [x]")):
            item = s[5:].strip()
            if item:
                res.follow_ups.append(item)
