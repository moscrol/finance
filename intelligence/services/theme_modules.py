"""Source-routing + real subprocess wiring of theme-radar 模式 as `ask` 召回后端.

`ask` does not re-implement the theme-radar report generators; it *fans out* a
query to them and folds their output into the unified six-section answer. Six
modes are wired as recall backends:

产业维（finance-workspace ``skills/theme-radar/scripts/radar.py --mode <m>``）:
- ``brief``      → 题材定锚 / 产业链上下游 / 细分核心个股（浅）
- ``front-map``  → 雷达信号水位 / 公司分层 / 主线公司（中，前瞻信息地图）
- ``deep-dive``  → 共振分层 / 发酵进度与预期差 / 验证清单（深）

时间维 + 横截面（knowledge-base ``skills/theme-radar-reports/scripts/*``）:
- ``replay``     → 模块7 发酵阶段 / 关键时间节点 / 验证清单
- ``scan``       → 模块4 全库工艺/材料级方向横扫（全市场视角）
- ``migrate``    → 模块8 以参照模式为标尺的横向迁移/类比排序

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
# deep-dive renders a much larger report; give it a higher floor regardless of
# the caller-supplied timeout so a long industry chain does not falsely time out.
DEEP_DIVE_TIMEOUT_FLOOR = 300

MODULE_BRIEF = "brief"
MODULE_FRONT_MAP = "front-map"
MODULE_DEEP_DIVE = "deep-dive"
MODULE_REPLAY = "replay"
MODULE_SCAN = "scan"
MODULE_MIGRATE = "migrate"
# canonical ordering used to normalise routed/explicit module lists
ALL_MODULES = (
    MODULE_BRIEF,
    MODULE_FRONT_MAP,
    MODULE_DEEP_DIVE,
    MODULE_REPLAY,
    MODULE_SCAN,
    MODULE_MIGRATE,
)
# 产业维 modes share one depth axis; routing picks the deepest one whose intent
# fired so a query does not redundantly run brief + front-map + deep-dive.
INDUSTRY_MODES = (MODULE_BRIEF, MODULE_FRONT_MAP, MODULE_DEEP_DIVE)

# Deterministic routing: query intent → recall backends.
BRIEF_TRIGGERS = (
    "是什么", "定义", "定锚", "产业链", "上下游", "谁受益", "受益",
    "速览", "速读", "细分", "核心个股", "标的", "分层",
)
FRONT_MAP_TRIGGERS = (
    "信息地图", "信号地图", "前瞻", "信号水位", "雷达速览", "覆盖度",
    "有哪些公司", "公司地图", "主线公司", "全景图",
)
DEEP_DIVE_TRIGGERS = (
    "深拆", "深研", "深度", "彻底", "全面", "上车", "值不值", "能不能买",
    "共识", "个股逻辑", "逻辑卡", "预期差",
)
REPLAY_TRIGGERS = (
    "发酵", "怎么走到今天", "走到今天", "时间线", "时间节点", "复盘",
    "起涨", "补涨", "认同度", "演变", "节点", "怎么发酵", "谁先",
)
SCAN_TRIGGERS = (
    "全市场", "全库", "横扫", "扫一遍", "什么方向", "哪些方向", "共振",
    "扫描", "还有什么题材", "市场上", "全景扫描", "工艺", "材料级",
)
MIGRATE_TRIGGERS = (
    "类比", "横迁", "横向迁移", "还有哪些和它一样", "类似题材", "对标",
    "参照", "像它一样", "相似方向", "迁移", "同阶段",
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


def _order(modules: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for m in ALL_MODULES:
        if m in modules and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def route_modules(query: str, explicit: list[str] | None = None) -> list[str]:
    """Map a query to the set of theme-radar backends to fan out to.

    - explicit ``--modules`` → filtered to known modules, canonical order.
    - 产业维 (brief/front-map/deep-dive) collapses to the single deepest mode
      whose intent fired (deep-dive > front-map > brief).
    - replay / scan / migrate each fire on their own intent keywords.
    - A bare theme word with no intent keyword fans out to brief + replay so a
      query like 「液冷服务器」 still gets the 产业维 + 时间维 views at once.
    """
    if explicit is not None:
        return _order([m for m in explicit if m in ALL_MODULES])
    q = str(query or "")
    routed: list[str] = []
    if any(t in q for t in DEEP_DIVE_TRIGGERS):
        routed.append(MODULE_DEEP_DIVE)
    elif any(t in q for t in FRONT_MAP_TRIGGERS):
        routed.append(MODULE_FRONT_MAP)
    elif any(t in q for t in BRIEF_TRIGGERS):
        routed.append(MODULE_BRIEF)
    if any(t in q for t in REPLAY_TRIGGERS):
        routed.append(MODULE_REPLAY)
    if any(t in q for t in SCAN_TRIGGERS):
        routed.append(MODULE_SCAN)
    if any(t in q for t in MIGRATE_TRIGGERS):
        routed.append(MODULE_MIGRATE)
    if not routed:
        routed = [MODULE_BRIEF, MODULE_REPLAY]
    return _order(routed)


def run_module(name: str, query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    dispatch = {
        MODULE_BRIEF: run_brief,
        MODULE_FRONT_MAP: run_front_map,
        MODULE_DEEP_DIVE: run_deep_dive,
        MODULE_REPLAY: run_replay,
        MODULE_SCAN: run_scan,
        MODULE_MIGRATE: run_migrate,
    }
    fn = dispatch.get(name)
    if fn is None:
        return ModuleResult(name=name, warning=f"未知模块: {name}")
    return fn(query, kb_wiki, timeout)


# --------------------------------------------------------------------------- #
# shared parse helpers
# --------------------------------------------------------------------------- #
def _bold_first(line: str) -> str | None:
    m = re.search(r"\*\*(.+?)\*\*", line)
    return m.group(1).strip() if m else None


def _wikilink(cell: str) -> str:
    m = re.search(r"\[\[(.+?)\]\]", cell)
    return m.group(1).strip() if m else cell.strip().strip("*").strip()


def _section_block(lines: list[str], header_substr: str, stop_prefixes: tuple[str, ...] = ("## ",)) -> list[str]:
    """Lines after the first header/bold line containing ``header_substr``,
    up to the next section header in ``stop_prefixes``."""
    start = None
    for i, ln in enumerate(lines):
        if header_substr in ln and (ln.startswith("#") or ln.lstrip().startswith("**")):
            start = i
            break
    if start is None:
        return []
    out: list[str] = []
    for ln in lines[start + 1:]:
        if any(ln.startswith(p) for p in stop_prefixes):
            break
        out.append(ln)
    return out


def _first_paragraph(block: list[str], limit: int = 80) -> str:
    for ln in block:
        s = ln.strip()
        if not s or s.startswith(("#", "|", "-", ">", "```")):
            continue
        s = re.sub(r"\(\d+\)", "", s).strip()
        return s[:limit] + ("…" if len(s) > limit else "")
    return ""


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} for c in cells):  # separator row
            continue
        rows.append(cells)
    return rows


def _radar_dial(report: str) -> dict[str, str]:
    """Parse the 雷达速览 ``| 维度 | 状态 |`` table into a dim→status dict."""
    dial: dict[str, str] = {}
    block = _section_block(report.splitlines(), "雷达速览")
    for cells in _table_rows(block):
        if len(cells) >= 2 and cells[0] and cells[0] != "维度":
            dial[cells[0]] = cells[1]
    return dial


# --------------------------------------------------------------------------- #
# 产业维 — finance-workspace radar.py (brief / front-map / deep-dive)
# --------------------------------------------------------------------------- #
def _run_radar(name: str, mode: str, query: str, kb_wiki: str | Path | None, timeout: int, citation_source: str, parser) -> ModuleResult:
    res = ModuleResult(name=name)
    if not RADAR_SCRIPT.exists():
        res.warning = f"radar.py 不存在: {RADAR_SCRIPT}"
        return res
    if not kb_wiki:
        res.warning = f"{name} 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        return res
    vault = Path(kb_wiki).expanduser()
    eff_timeout = max(timeout, DEEP_DIVE_TIMEOUT_FLOOR) if mode == "deep-dive" else timeout
    cmd = [sys.executable, str(RADAR_SCRIPT), "--term", str(query), "--vault", str(vault), "--mode", mode]
    res.command = f"radar.py --mode {mode} --term {query} --vault <kb-wiki>"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=eff_timeout, cwd=str(REPO_ROOT))
    except subprocess.TimeoutExpired:
        res.warning = f"{name} 超时(>{eff_timeout}s)，已跳过"
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"{name} 调用失败: {exc}"
        return res
    if proc.returncode != 0:
        res.warning = f"{name} 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        return res
    res.citation_source = citation_source
    res.citation_detail = f"--term {query}"
    parser(proc.stdout, res)
    res.ok = True
    return res


def run_brief(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    return _run_radar(
        MODULE_BRIEF, "brief", query, kb_wiki, timeout,
        "theme-radar · radar.py --mode brief（产业维·速览）", _parse_brief,
    )


def run_front_map(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    return _run_radar(
        MODULE_FRONT_MAP, "front-map", query, kb_wiki, timeout,
        "theme-radar · radar.py --mode front-map（产业维·前瞻信息地图）", _parse_front_map,
    )


def run_deep_dive(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    return _run_radar(
        MODULE_DEEP_DIVE, "deep-dive", query, kb_wiki, timeout,
        "theme-radar · radar.py --mode deep-dive（产业维·题材深拆）", _parse_deep_dive,
    )


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


def _parse_front_map(report: str, res: ModuleResult) -> None:
    lines = report.splitlines()
    title = _first_paragraph(_section_block(lines, "一句话定锚"))
    if title:
        res.title = title
        res.highlights.append(f"产业定锚：{title}")

    dial = _radar_dial(report)
    dims = ["公司分层", "wiki 概念页", "合成研究", "海外对标", "个股逻辑卡"]
    parts = [f"{d.replace('wiki ', 'wiki')}={dial[d]}" for d in dims if d in dial]
    if parts:
        res.highlights.append("信号水位｜" + "；".join(parts))

    # 主线公司 (## 6. 公司地图 → ### 主线公司 table, col[0])
    mains: list[str] = []
    for cells in _table_rows(_section_block(lines, "主线公司", stop_prefixes=("## ", "### "))):
        nm = cells[0]
        if nm and nm != "公司" and nm not in mains:
            mains.append(nm)
        if len(mains) >= 8:
            break
    if mains:
        res.highlights.append("主线公司：" + "、".join(mains))


def _parse_deep_dive(report: str, res: ModuleResult) -> None:
    lines = report.splitlines()
    title = _first_paragraph(_section_block(lines, "一句话定锚"))
    if title:
        res.title = title
        res.highlights.append(f"产业定锚：{title}")

    judge = ""
    for ln in _section_block(lines, "### 判断", stop_prefixes=("## ", "### ")):
        s = ln.strip()
        if s.startswith("- "):
            judge = s[2:].strip()
            break
        if s and not s.startswith(("#", "|", ">", "`")):
            judge = s
            break
    if judge:
        res.highlights.append(f"深研判断：{judge[:80]}{'…' if len(judge) > 80 else ''}")

    # 五、共振分层: Tier 1 三重共振 companies (col[1]); colon-qualified header to
    # avoid matching the earlier ``### 共振分层`` note under 二、为什么现在发酵.
    triple: list[str] = []
    for cells in _table_rows(_section_block(lines, "共振分层：主信源")):
        if len(cells) >= 2 and cells[0].startswith("Tier 1") and cells[1] not in triple:
            triple.append(cells[1])
        if len(triple) >= 8:
            break
    if triple:
        res.highlights.append("三重共振核心层：" + "、".join(triple))

    # 六、发酵进度与预期差: direction / 阶段 / 评分
    prog: list[str] = []
    for cells in _table_rows(_section_block(lines, "发酵进度与预期差")):
        if len(cells) >= 5 and cells[0].isdigit():
            prog.append(f"{cells[1]} {cells[2]}(评分{cells[4]})")
        if len(prog) >= 4:
            break
    if prog:
        res.highlights.append("发酵进度｜" + "；".join(prog))

    for header in ("下一步验证", "风险提示"):
        for ln in _section_block(lines, header, stop_prefixes=("## ", "### ")):
            s = ln.strip()
            if s.startswith("- "):
                item = s[2:].strip()
                if item:
                    res.follow_ups.append((f"风险：{item}" if header == "风险提示" else item))


# --------------------------------------------------------------------------- #
# knowledge-base scripts shared runner (replay / scan / migrate)
# --------------------------------------------------------------------------- #
def _kb_root(kb_wiki: str | Path) -> Path:
    return Path(kb_wiki).expanduser().resolve().parent


def _run_kb_script(res: ModuleResult, kb_wiki: str | Path | None, script_rel: str, extra_args: list[str], command_label: str, timeout: int):
    """Run a KB report generator that writes to ``--out`` and return its text.

    On any failure ``res.warning`` is set and ``None`` is returned.
    """
    if not kb_wiki:
        res.warning = f"{res.name} 需要知识库 wiki 路径 (--kb-wiki / KNOWLEDGE_WIKI)"
        return None
    kb_root = _kb_root(kb_wiki)
    script = kb_root / script_rel
    if not script.exists():
        res.warning = f"{res.name} 脚本不存在: {script}"
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        out_path = tf.name
    cmd = [sys.executable, str(script), "--project-root", str(kb_root), "--out", out_path] + extra_args
    res.command = command_label
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        res.warning = f"{res.name} 超时(>{timeout}s)，已跳过"
        Path(out_path).unlink(missing_ok=True)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"{res.name} 调用失败: {exc}"
        Path(out_path).unlink(missing_ok=True)
        return None
    if proc.returncode != 0:
        res.warning = f"{res.name} 退出码 {proc.returncode}: {(proc.stderr or '').strip()[:160]}"
        Path(out_path).unlink(missing_ok=True)
        return None
    try:
        return Path(out_path).read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        res.warning = f"{res.name} 输出读取失败: {exc}"
        return None
    finally:
        Path(out_path).unlink(missing_ok=True)


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
    kb_root = _kb_root(kb_wiki)
    theme_key = resolve_theme_key(query, kb_root)
    if not theme_key:
        res.warning = "theme_signals.json 无匹配主题，replay 跳过（该题材尚未建发酵信号）"
        return res
    res.theme_key = theme_key
    # generate_fermentation_report.py takes the theme as a positional arg, so it
    # cannot use the generic --project-root/--out runner directly.
    script_rel = "skills/theme-radar-reports/scripts/generate_fermentation_report.py"
    kb_root_path = kb_root
    script = kb_root_path / script_rel
    if not script.exists():
        res.warning = f"replay 脚本不存在: {script}"
        return res
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        out_path = tf.name
    cmd = [sys.executable, str(script), theme_key, "--project-root", str(kb_root_path), "--out", out_path]
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


# --------------------------------------------------------------------------- #
# scan (模块4 全库横扫) — knowledge-base generate_scan_table.py
# --------------------------------------------------------------------------- #
def run_scan(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    res = ModuleResult(name=MODULE_SCAN)
    report = _run_kb_script(
        res, kb_wiki, "skills/theme-radar-reports/scripts/generate_scan_table.py",
        extra_args=[], command_label="generate_scan_table.py（全库工艺/材料级横扫）", timeout=timeout,
    )
    if report is None:
        return res
    theme_key = resolve_theme_key(query, _kb_root(kb_wiki)) if kb_wiki else None
    res.theme_key = theme_key or ""
    res.citation_source = "knowledge-base · generate_scan_table.py（模块4 全库横扫）"
    res.citation_detail = "全库工艺/材料级方向"
    _parse_scan(report, res, query, theme_key)
    res.ok = True
    return res


def _parse_scan(report: str, res: ModuleResult, query: str, theme_key: str | None) -> None:
    lines = report.splitlines()
    stat = re.search(r"(🟡\s*发酵.+个方向）)", report)
    if stat:
        res.title = re.sub(r"\s+", " ", stat.group(1)).strip()
        res.highlights.append("全库扫描：" + res.title)

    nq = _norm(query)
    ntk = _norm(theme_key) if theme_key else ""
    rel: list[str] = []
    hot: list[str] = []
    for cells in _table_rows(lines):
        if len(cells) < 7 or cells[0] in ("工艺/材料",):
            continue
        name = _wikilink(cells[0])
        track = cells[1].strip()
        freq = cells[3].strip()
        hay = _norm(name) + _norm(track)
        is_rel = (ntk and ntk in hay) or (_norm(name) and _norm(name) in nq)
        label = f"{name}" + (f"（属{track}）" if track and track != "—" else "") + f"·{freq}"
        if is_rel:
            if name not in [r.split("（")[0].split("·")[0] for r in rel]:
                rel.append(label)
        elif "🔴 高频" in freq and len(hot) < 6:
            hot.append(name)
    if rel:
        res.highlights.append("题材相关细分方向：" + "；".join(rel[:6]))
    elif hot:
        res.highlights.append("全市场高频发酵方向：" + "、".join(hot))


# --------------------------------------------------------------------------- #
# migrate (模块8 横向迁移/类比) — knowledge-base generate_migration_scan.py
# --------------------------------------------------------------------------- #
def run_migrate(query: str, kb_wiki: str | Path | None, timeout: int = DEFAULT_MODULE_TIMEOUT) -> ModuleResult:
    res = ModuleResult(name=MODULE_MIGRATE)
    report = _run_kb_script(
        res, kb_wiki, "skills/theme-radar-reports/scripts/generate_migration_scan.py",
        extra_args=[], command_label="generate_migration_scan.py（横向迁移·默认 mSAP 标尺）", timeout=timeout,
    )
    if report is None:
        return res
    theme_key = resolve_theme_key(query, _kb_root(kb_wiki)) if kb_wiki else None
    res.theme_key = theme_key or ""
    res.citation_source = "knowledge-base · generate_migration_scan.py（模块8 横向迁移）"
    res.citation_detail = "参照标尺 mSAP"
    _parse_migrate(report, res, query, theme_key)
    res.ok = True
    return res


def _parse_migrate(report: str, res: ModuleResult, query: str, theme_key: str | None) -> None:
    lines = report.splitlines()
    ruler = re.search(r"以\s*\[\[(.+?)\]\]\s*为参照标尺", report)
    if ruler:
        res.title = f"以 {ruler.group(1)} 为参照标尺"

    nq = _norm(query)
    ntk = _norm(theme_key) if theme_key else ""
    cur_tier = ""
    target_tier = ""
    target_line = ""
    target_exact = False
    peers: dict[str, list[str]] = {}
    for ln in lines:
        s = ln.strip()
        if s.startswith("### "):
            cur_tier = re.sub(r"（.*?）", "", s[4:]).strip()
            continue
        if not s.startswith("|") or not cur_tier:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("方向",) or set(cells[0]) <= {"-", ":"}:
            continue
        name = _wikilink(cells[0])
        peers.setdefault(cur_tier, [])
        if name and name not in peers[cur_tier]:
            peers[cur_tier].append(name)
        if not target_exact:
            is_exact = bool(ntk) and ntk == _norm(name)
            is_sub = (bool(ntk) and ntk in _norm(name)) or (bool(_norm(name)) and _norm(name) in nq)
            if is_exact or (is_sub and not target_line):
                target_tier = cur_tier
                target_line = f"「{name}」位于『{cur_tier}』阶段（框架评分{cells[4]}，覆盖{cells[2]}）"
                target_exact = is_exact

    if target_line:
        res.highlights.append("类比定位：" + target_line)
        sib = [n for n in peers.get(target_tier, []) if not ((ntk and ntk in _norm(n)) or (_norm(n) and _norm(n) in nq))][:6]
        if sib:
            res.highlights.append("同阶段类比方向：" + "、".join(sib))
    # 重点跟踪建议（认知跃迁窗口）
    windows: list[str] = []
    for ln in _section_block(lines, "重点跟踪建议"):
        s = ln.strip()
        if s.startswith("- [["):
            windows.append(_wikilink(s))
        if len(windows) >= 6:
            break
    if windows:
        res.highlights.append("认知跃迁窗口（催化共振阶段）：" + "、".join(windows))
