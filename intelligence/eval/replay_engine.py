"""历史重放引擎（INDEX #25）：站在 D0 出结构化判断 → 自动判分 → AI 校准读数。

设计稿 ``2026-09-04-methodology-backtest-structured-history-design.md`` §10.3 第 2 步。把仓内三块零件接成
一条链，只量、只出收据，不改任何规则 / 卡 / 画像 / 提示词：

* **PIT 输入**：``strict`` 档从 ``$PIT_SNAPSHOT_DIR/<D0>.snapshot.json.gz``（默认 ``~/fidelity-replay/pit-snapshots``）取
  （manifest 存在且 :func:`intelligence.eval.pit_snapshot.validate_frozen_snapshot` 通过）；
  ``trade_date_only`` 档调 :func:`intelligence.eval.fidelity_replay.build_input_snapshot`
  的 ``strict_updated_at=False``——行值可能被 D0 之后的回填改写，这个风险由 ``pit_grade`` 一等字段
  如实标出，两档分开报，**不出混合平均**。
* **结构化判断 + 自动判分**：答卷复用双盲台账 ``hypotheses[]`` 字段名，但类别只允许
  ``market`` / ``direction``（不允许 ``target`` 个股，BP §3.4 边界）；``direction`` 查旁路库
  ``history_outcomes``（窗口不含 D0），``market`` 复用 ``dual_blind_auto_verdict`` 的纯函数口径
  （本模块是它们的唯一实现，脚本 import 回去）。
* **两条车道分开报**：车道 A 规则复现一致率（零泄漏——不涉及 D0 之后的数据）；车道 B 前瞻命中率
  （两种泄漏：数据泄漏由 ``pit_grade`` 守，模型记忆泄漏由 ``memory_bucket`` 分栏 + 匿名化对照臂守）。
* **匿名化对照臂**：``anonymized`` 臂把板块 / 题材代码与名字换成 ``S01…`` / ``TH01…``、绝对日期换成
  ``T-0…T-19``，数值与 ``market_stage`` 文本保留；两臂用同一模板渲染，diff 只落在映射位。
  臂间命中率差 = 记忆成分的上界（消融，不是声明）。

判分产物落 ``~/.finance-runtime/replay/<run_id>/``（不进仓），报表落
``intelligence/eval/measurements/replay-<date>.{json,md}``（进仓）。**不写**
``docs/learning/forecast-review-ledger/``——那是真向前台账，写进去就污染地面真值。

三条红线（抄工单 §6）：主库 / 旁路库 / 快照目录全程只读；LLM 只走 ``llm_refine.complete`` 并尊重
``_budget_rejection``；任何读数必须带 ``pit_grade / memory_bucket / arm`` 三标签。
"""

from __future__ import annotations

import fnmatch
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from intelligence.eval.fidelity_replay import (
    _canonical_sha,
    _connect,
    _market_rows,
    _max_embedded_date,
    build_input_snapshot,
    select_pilot_dates,
)
from intelligence.eval.pit_snapshot import validate_frozen_snapshot
from intelligence.services.checkpoints import DEFAULT_CALIBRATION_MIN_N, calibrate
from intelligence.services.methodology_backtest.compiler import compile_rule
from intelligence.services.methodology_backtest.labels import (
    HEAT_TIER,
    MARKET_ENTITY_ID,
    MARKET_LABELS,
    SECTOR_LABELS,
    THEME_LABELS,
)
from intelligence.services.methodology_backtest.outcomes import WINDOW_START_OFFSET
from intelligence.services.methodology_backtest.rules import METRICS, Rule, load_rule
from intelligence.services.methodology_backtest.runner import load_conditions
from intelligence.services.methodology_backtest.stats import wilson

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / "methodology" / "rules"
MEASUREMENTS_DIR = REPO_ROOT / "intelligence" / "eval" / "measurements"
MODEL_CUTOFFS_PATH = REPO_ROOT / "intelligence" / "eval" / "model_cutoffs.json"
LEDGER_DIR = REPO_ROOT / "docs" / "learning" / "forecast-review-ledger"
# 与 scripts/freeze_daily_pit_snapshot.sh 同一条解析：环境变量 PIT_SNAPSHOT_DIR 优先，否则 ~/fidelity-replay/pit-snapshots
DEFAULT_SNAPSHOT_ROOT = (
    Path(os.environ["PIT_SNAPSHOT_DIR"]).expanduser()
    if os.environ.get("PIT_SNAPSHOT_DIR")
    else Path.home() / "fidelity-replay" / "pit-snapshots"
)
DEFAULT_RUNTIME_ROOT = Path(os.environ.get("REPLAY_RUNTIME_ROOT", "~/.finance-runtime/replay")).expanduser()

INPUT_SCHEMA = "replay-input/v1"
REPORT_SCHEMA = "replay-report/v1"
PIT_GRADES = ("strict", "trade_date_only")
ARMS = ("named", "anonymized")
LANES = ("A", "B")
REPLAY_CATEGORIES = ("market", "direction")
REPLAY_HORIZONS = ("T+1", "T+3", "T+5")
REPLAY_CONFIDENCE = ("high", "medium", "low")
MEMORY_BUCKETS = ("post_cutoff", "pre_cutoff", "unknown")
MEMORY_CONTAMINATED = ("pre_cutoff", "unknown")
LANE_A_ENTITY_TYPES = ("sector", "theme")  # 本单不跑个股规则，输入里也不放 STOCK_LABELS
MIN_HYPOTHESES = 3
MAX_HYPOTHESES = 8
DEFAULT_COUNT_PER_GRADE = 20
DEFAULT_MAX_CALLS = 200
CALENDAR_LOOKBACK = 20
PROMPT_TABLE_LIMIT = 30
LLM_TEMPERATURE = 0.2  # 本单内冻结；改它属于「程序员泄漏」，要另单
LLM_TIMEOUT_SECONDS = 180.0
ESTIMATED_CHARS_PER_TOKEN = 1.6  # 估算，全程带 estimated 标签

HYPOTHESIS_FIELDS = (
    "id",
    "category",
    "claim",
    "horizon",
    "confidence",
    "confidence_probability",
    "evidence_refs",
    "evidence_as_of",
    "falsify_when",
)
ABSOLUTE_DATE_RE = re.compile(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]")
RELATIVE_DATE_RE = re.compile(r"^T-(\d{1,2})$")
SECTOR_CODE_RE = re.compile(r"^\d{6}\.(?:FP|TI)$")
# 个股代码：6 位数字，可带 .SZ/.SH/.BJ。板块代码 990147.FP / 880001.TI 同样是 6 位开头，靠后缀区分。
STOCK_CODE_RE = re.compile(r"(?<![\d.])(\d{6})(?:\.(SZ|SH|BJ|FP|TI))?(?![\d.])", re.IGNORECASE)
DIRECTION_CLAIM_RE = re.compile(
    r"^\s*(?P<entity>\S+)\s+(?P<metric>fwd_return|max_return|days_to_peak|drawdown_after_peak)"
    r"@(?P<horizon>\d{1,2})\s*(?P<op>>=|<=|>|<)\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*%?\s*$"
)
HORIZON_RE = re.compile(r"^T\+(\d{1,2})$")


# --------------------------------------------------------------------------- #
# market 类机判纯函数（从 scripts/dual_blind_auto_verdict.py 下沉；脚本 import 回去，单一实现）
# --------------------------------------------------------------------------- #
METRIC_ALIASES = {
    "涨家数": "advancers",
    "涨停家数": "limit_up",
    "涨停数": "limit_up",
    "涨停": "limit_up",
    "跌停家数": "limit_down",
    "跌停数": "limit_down",
    "跌停": "limit_down",
    "成交额": "total_amount",
    "量比": "volume_ratio",
    "历史新高数": "high_history",
    "历史新高": "high_history",
}
_METRIC_RE = "|".join(sorted(METRIC_ALIASES, key=len, reverse=True))
_NUM = r"([0-9]+(?:\.[0-9]+)?)"
_UNIT = r"(万亿|亿)?"
COND_RE = re.compile(rf"({_METRIC_RE})[^0-9<>≥≤=区间\-]{{0,6}}(>=|<=|≥|≤|>|<)\s*{_NUM}{_UNIT}")
RANGE_RE = re.compile(rf"({_METRIC_RE})[^0-9<>≥≤=]{{0,6}}{_NUM}{_UNIT}\s*[-~—]\s*{_NUM}{_UNIT}")
CLAUSE_SPLIT = re.compile(r"[；;。\n]")
OR_SPLIT = re.compile(r"或(?:者)?")
MARKET_VALUE_KEYS = ("advancers", "limit_up", "limit_down", "total_amount", "volume_ratio", "high_history")


def _to_number(raw: str, unit: str | None) -> float:
    value = float(raw)
    if unit == "万亿":
        value *= 10000.0
    return value


def extract_conditions(text: str) -> list[tuple[str, str, float, float | None]]:
    """返回 (metric, op, lo, hi)；op 为比较符或 'range'。"""
    out: list[tuple[str, str, float, float | None]] = []
    for m in RANGE_RE.finditer(text):
        metric = METRIC_ALIASES[m.group(1)]
        lo = _to_number(m.group(2), m.group(3))
        hi = _to_number(m.group(4), m.group(5))
        out.append((metric, "range", lo, hi))
    stripped = RANGE_RE.sub(" ", text)
    for m in COND_RE.finditer(stripped):
        metric = METRIC_ALIASES[m.group(1)]
        op = {"≥": ">=", "≤": "<="}.get(m.group(2), m.group(2))
        out.append((metric, op, _to_number(m.group(3), m.group(4)), None))
    return out


def eval_conditions(conds: list[tuple[str, str, float, float | None]], vals: dict[str, float | None]) -> bool | None:
    """全部条件 AND；有条件的 metric 缺实际值返回 None（不可判）。空列表返回 None。"""
    if not conds:
        return None
    for metric, op, lo, hi in conds:
        actual = vals.get(metric)
        if actual is None:
            return None
        if op == "range":
            ok = lo <= actual <= (hi if hi is not None else lo)
        elif op == ">=":
            ok = actual >= lo
        elif op == "<=":
            ok = actual <= lo
        elif op == ">":
            ok = actual > lo
        else:
            ok = actual < lo
        if not ok:
            return False
    return True


def any_clause_true(text: str, vals: dict[str, float | None]) -> bool | None:
    """按 ；/。切子句、子句内按 或 切分支；任一分支条件全真即 True。全不可判返回 None。"""
    saw = False
    for clause in CLAUSE_SPLIT.split(text or ""):
        for branch in OR_SPLIT.split(clause):
            result = eval_conditions(extract_conditions(branch), vals)
            if result is True:
                return True
            if result is False:
                saw = True
    return False if saw else None


def all_t1_conditions_true(text: str, vals: dict[str, float | None]) -> bool | None:
    """取包含 T+1 的子句（无则取首个可抽条件子句），其条件全真才 True。"""
    clauses = [c for c in CLAUSE_SPLIT.split(text or "") if extract_conditions(c)]
    if not clauses:
        return None
    preferred = [c for c in clauses if "T+1" in c or "t1" in c]
    clause = preferred[0] if preferred else clauses[0]
    return eval_conditions(extract_conditions(clause), vals)


def market_actuals(con: Any, date: str) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT advancers, limit_up, limit_down, total_amount, volume_ratio, "
        "stock_high_count_history, sh_index_pct_chg, market_stage FROM fact_market_daily WHERE trade_date = ?",
        [date],
    ).fetchone()
    if not row:
        return None
    keys = ("advancers", "limit_up", "limit_down", "total_amount", "volume_ratio", "high_history", "sh_pct", "stage")
    return dict(zip(keys, (float(v) if isinstance(v, (int, float)) else v for v in row)))


def judge_market_claim(claim: str, falsify_when: str, vals: dict[str, float | None]) -> str:
    """market 类四分口径（照 dual_blind_auto_verdict.build_verdicts_for_date 的 market 分支）：
    证伪条件触发 → miss；预期条件全真 → hit；两者都抽不出条件 → unverifiable；其余 partial。"""
    triggered = any_clause_true(falsify_when, vals)
    expected = eval_conditions(extract_conditions(claim), vals)
    if triggered is True:
        return "miss"
    if expected is True:
        return "hit"
    if triggered is None and expected is None:
        return "unverifiable"
    return "partial"


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _git(args: list[str], cwd: Path = REPO_ROOT) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def environment_block(*, snapshot_root: Path, db_path: Path, labels_db: Path) -> dict[str, Any]:
    """成立条件里的环境部分：树 / 解释器 / revision / dirty。"""
    dirty = bool(_git(["status", "--porcelain"]))
    return {
        "worktree": str(REPO_ROOT),
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]) or None,
        "revision": _git(["rev-parse", "HEAD"]) or None,
        "dirty": dirty,
        "interpreter": sys.executable,
        "python": sys.version.split()[0],
        "snapshot_root": str(snapshot_root),
        "db_path": str(db_path),
        "labels_db": str(labels_db),
    }


# --------------------------------------------------------------------------- #
# 1. 节点选择与 PIT 分档
# --------------------------------------------------------------------------- #
def pit_grade_for(as_of: str, snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT) -> tuple[str, dict[str, Any]]:
    """``strict`` 当且仅当 ``<D0>.manifest.json`` 存在且 ``validate_frozen_snapshot`` 通过（checksum、
    hash chain、逐行 known_at / source_time）；否则 ``trade_date_only``，并写明原因。"""
    root = Path(snapshot_root).expanduser()
    manifest_path = root / f"{as_of}.manifest.json"
    if not manifest_path.exists():
        return "trade_date_only", {"reason": "no_manifest"}
    try:
        manifest = validate_frozen_snapshot(root, as_of)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return "trade_date_only", {"reason": f"snapshot_validation_failed: {exc}"}
    return "strict", {
        "manifest_file": manifest_path.name,
        "manifest_sha": manifest.get("manifest_sha"),
        "snapshot_sha256": manifest.get("snapshot_sha256"),
        "compressed_sha256": manifest.get("compressed_sha256"),
        "replay_eligible": manifest.get("replay_eligible"),
        "evidence_cutoff": manifest.get("evidence_cutoff"),
        "generator_commit": manifest.get("generator_commit"),
    }


def trade_dates(db_path: str | Path) -> list[str]:
    con = _connect(db_path)
    try:
        return [
            str(row[0])[:10]
            for row in con.execute(
                "SELECT DISTINCT trade_date FROM fact_market_daily ORDER BY trade_date"
            ).fetchall()
        ]
    finally:
        con.close()


def judgeable_end(db_path: str | Path, *, horizon: int = 5) -> str | None:
    """默认 ``end``：主库最后一个交易日往前 ``horizon`` 个交易日——再往后的节点 T+5 一定 pending。"""
    dates = trade_dates(db_path)
    if len(dates) <= horizon:
        return None
    return dates[-1 - horizon]


def select_nodes(
    db_path: str | Path,
    start: str,
    end: str,
    *,
    count_per_grade: int = DEFAULT_COUNT_PER_GRADE,
    snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT,
    forced_dates: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """两档各抽 ``count_per_grade`` 个节点。分层复用 ``fidelity_replay.select_pilot_dates``（月 × market_stage），
    但两档分开抽（``only_dates``）。``forced_dates``（对账日期）先占位，再补足。"""
    rows = _market_rows(db_path, start, end)
    if not rows:
        return []
    stage_by_date = {row["as_of"]: row["market_stage"] for row in rows}
    grade_by_date: dict[str, tuple[str, dict[str, Any]]] = {
        row["as_of"]: pit_grade_for(row["as_of"], snapshot_root) for row in rows
    }
    forced = {str(d)[:10] for d in forced_dates}
    nodes: list[dict[str, Any]] = []
    for grade in PIT_GRADES:
        dates = [d for d, (g, _meta) in grade_by_date.items() if g == grade]
        if not dates:
            continue
        # 对账日期只在 strict 档占位：它们的意义是「有快照也有真答卷」，掉到 trade_date_only 就没有对账价值
        picked = sorted(d for d in dates if d in forced)[:count_per_grade] if grade == "strict" else []
        remaining = count_per_grade - len(picked)
        if remaining > 0:
            pool = set(dates) - set(picked)
            if pool:
                picked += [
                    item["as_of"]
                    for item in select_pilot_dates(
                        db_path, start, end, count=remaining, only_dates=pool
                    )
                ]
        for as_of in sorted(set(picked)):
            grade_name, meta = grade_by_date[as_of]
            nodes.append(
                {
                    "as_of": as_of,
                    "market_stage": stage_by_date[as_of],
                    "pit_grade": grade_name,
                    "grade_meta": meta,
                    "forced": grade_name == "strict" and as_of in forced,
                }
            )
    nodes.sort(key=lambda n: (n["pit_grade"], n["as_of"]))
    return nodes


# --------------------------------------------------------------------------- #
# 2. 输入构建
# --------------------------------------------------------------------------- #
def load_lane_a_rules(rules_dir: str | Path = RULES_DIR) -> list[Rule]:
    """``scope.entity_type ∈ {sector, theme}`` 的规则；个股规则（PR #585 后合法）本单不跑。"""
    rules: list[Rule] = []
    for path in sorted(Path(rules_dir).expanduser().glob("*.v*.json")):
        rule = load_rule(path)
        if rule.entity_type in LANE_A_ENTITY_TYPES:
            rules.append(rule)
    return rules


def rule_prompt_view(rule: Rule) -> dict[str, Any]:
    """给提示词看的规则视图：去掉 notes / provenance（里面可能有绝对日期与来源文本），保留判定所需字段。"""
    return {
        "rule_id": rule.rule_id,
        "version": rule.version,
        "title": rule.title,
        "scope": rule.raw.get("scope"),
        "condition": rule.raw.get("condition"),
        "outcome_success": (rule.raw.get("outcome") or {}).get("success"),
    }


def _labels_for_day(labels_con: Any, as_of: str) -> dict[str, Any]:
    rows = labels_con.execute(
        """
        SELECT entity_type, entity_id, label, value_num, value_text
        FROM history_labels
        WHERE trade_date = CAST(? AS DATE) AND entity_type IN ('sector', 'theme', 'market')
        ORDER BY entity_type, entity_id, label
        """,
        [as_of],
    ).fetchall()
    by_entity: dict[str, dict[str, dict[str, Any]]] = {"sector": {}, "theme": {}, "market": {}}
    for entity_type, entity_id, label, value_num, value_text in rows:
        value: Any
        if value_text is not None:
            value = value_text
        elif value_num is None:
            value = None
        elif float(value_num).is_integer():
            value = int(value_num)
        else:
            value = float(value_num)
        by_entity[str(entity_type)].setdefault(str(entity_id), {})[str(label)] = value
    sector = [
        {"entity_id": eid, "trade_date": as_of, **{lab: vals.get(lab) for lab in SECTOR_LABELS}}
        for eid, vals in sorted(by_entity["sector"].items())
    ]
    theme = [
        {"entity_id": eid, "trade_date": as_of, **{lab: vals.get(lab) for lab in THEME_LABELS}}
        for eid, vals in sorted(by_entity["theme"].items())
    ]
    market_vals = by_entity["market"].get(MARKET_ENTITY_ID, {})
    market = {"trade_date": as_of, **{lab: market_vals.get(lab) for lab in MARKET_LABELS}}
    return {"sector": sector, "theme": theme, "market": market}


def _calendar_before(labels_con: Any, as_of: str, lookback: int = CALENDAR_LOOKBACK) -> list[dict[str, Any]]:
    rows = labels_con.execute(
        "SELECT trade_date FROM history_calendar WHERE trade_date <= CAST(? AS DATE) ORDER BY trade_date DESC LIMIT ?",
        [as_of, lookback],
    ).fetchall()
    return [{"trade_date": str(row[0])[:10], "offset": f"T-{i}"} for i, row in enumerate(rows)]


MARKET_HISTORY_FIELDS = (
    "trade_date",
    "market_stage",
    "advancers",
    "limit_up",
    "limit_down",
    "total_amount",
    "amount_vs_yesterday_pct",
    "volume_ratio",
    "sh_index_close",
    "sh_index_pct_chg",
    "stock_high_count_history",
)
SECTOR_DAY_FIELDS = ("trade_date", "sector_ts_code", "sector_name", "pct_chg", "diff_ratio", "amount", "strength")
THEME_HEAT_FIELDS = ("trade_date", "sector_ts_code", "sector_name", "rank", "limit_up_count", "limit_up_ratio")


def _project(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in fields:
        value = row.get(key)
        if key == "trade_date" and value is not None:
            value = str(value)[:10]
        elif isinstance(value, (date, datetime)):
            value = value.isoformat()
        out[key] = value
    return out


def _heat_tier_match(row: dict[str, Any]) -> bool:
    return all(
        (row.get(key) == value) or (key == "is_realtime" and not row.get(key) and value is False)
        for key, value in HEAT_TIER.items()
    )


def _name_map_from_db(db_path: str | Path, as_of: str) -> dict[str, str]:
    con = _connect(db_path)
    try:
        names: dict[str, str] = {}
        tables = [
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        ]
        if "dim_sector" in tables:
            for code, name in con.execute("SELECT sector_ts_code, sector_name FROM dim_sector").fetchall():
                if code and name:
                    names[str(code)] = str(name)
        for code, name in con.execute(
            "SELECT DISTINCT sector_ts_code, sector_name FROM fact_sector_daily WHERE trade_date = CAST(? AS DATE)",
            [as_of],
        ).fetchall():
            if code and name:
                names[str(code)] = str(name)
        return names
    finally:
        con.close()


def _load_frozen_snapshot(snapshot_root: Path, as_of: str, grade_meta: dict[str, Any]) -> dict[str, Any]:
    path = snapshot_root / f"{as_of}.snapshot.json.gz"
    compressed = path.read_bytes()
    digest = hashlib.sha256(compressed).hexdigest()
    if grade_meta.get("compressed_sha256") and digest != grade_meta["compressed_sha256"]:
        raise ValueError(f"frozen snapshot checksum mismatch for {as_of}")
    return json.loads(gzip.decompress(compressed))


def build_replay_input(
    node: dict[str, Any],
    *,
    db_path: str | Path,
    labels_db: str | Path,
    snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT,
    rules: list[Rule] | None = None,
    labels_con: Any | None = None,
) -> dict[str, Any]:
    """按 ``pit_grade`` 取输入：strict 从冻结快照，trade_date_only 从主库（``strict_updated_at=False``）。
    两档都追加 D0 当日 sector / theme / market 标签（旁路库只读）、规则全文、D0 之前 20 个交易日历。
    返回体带 ``input_sha256`` 与 ``max_embedded_date``；任何 > D0 的日期直接抛 ValueError，不落盘。"""
    as_of = str(node["as_of"])
    grade = str(node["pit_grade"])
    if grade not in PIT_GRADES:
        raise ValueError(f"unknown pit_grade {grade!r}")
    rules = rules if rules is not None else load_lane_a_rules()
    root = Path(snapshot_root).expanduser()

    if grade == "strict":
        snapshot = _load_frozen_snapshot(root, as_of, node.get("grade_meta") or {})
        data = snapshot.get("data") or {}
        market_rows = sorted(
            (dict(r) for r in data.get("fact_market_daily") or []),
            key=lambda r: str(r.get("trade_date")),
            reverse=True,
        )[:CALENDAR_LOOKBACK]
        sector_rows = [r for r in data.get("fact_sector_daily") or [] if str(r.get("trade_date"))[:10] == as_of]
        heat_rows = [
            r
            for r in data.get("fact_theme_limit_heat_daily") or []
            if str(r.get("trade_date"))[:10] == as_of and _heat_tier_match(r)
        ]
        source = {
            "kind": "frozen_snapshot",
            "snapshot_file": f"{as_of}.snapshot.json.gz",
            **{k: (node.get("grade_meta") or {}).get(k) for k in ("manifest_sha", "snapshot_sha256", "compressed_sha256", "replay_eligible")},
        }
        names = {str(r.get("sector_ts_code")): str(r.get("sector_name")) for r in sector_rows if r.get("sector_ts_code") and r.get("sector_name")}
        for r in heat_rows:
            if r.get("sector_ts_code") and r.get("sector_name"):
                names.setdefault(str(r["sector_ts_code"]), str(r["sector_name"]))
        # D0 可见实体 = 冻结快照里出现过的板块 / 题材代码。旁路库是从**当前**主库重建的：2026-07-27 dim_sector
        # 扩到 630 个板块并回填了 07-10→08-19 的历史行，所以 07-22 的 history_labels 有 630 个实体，而当晚快照
        # 只有 224 个——多出来的 406 个在 D0 根本不存在。「后补数据不冒充 PIT」：strict 档只给 D0 可见实体。
        visible: set[str] | None = {
            str(r.get("sector_ts_code"))
            for r in (data.get("fact_sector_daily") or [])
            if r.get("sector_ts_code")
        } | {str(r.get("sector_ts_code")) for r in heat_rows if r.get("sector_ts_code")}
        del snapshot, data
    else:
        case = {"case_id": f"RP-{as_of}", "as_of": as_of, "status": "ready"}
        built = build_input_snapshot(
            db_path, case, sector_limit=PROMPT_TABLE_LIMIT, stock_limit=1, strict_updated_at=False
        )
        market_rows = list(built["data"].get("market_history") or [])
        sector_rows = list(built["data"].get("fact_sector_daily") or [])
        heat_rows = [r for r in built["data"].get("fact_theme_limit_heat_daily") or [] if _heat_tier_match(r)]
        source = {
            "kind": "build_input_snapshot",
            "strict_updated_at": False,
            "snapshot_sha256": built.get("snapshot_sha256"),
            "db_pit": (built.get("boundary") or {}).get("db_pit"),
        }
        names = _name_map_from_db(db_path, as_of)
        visible = None

    own_con = labels_con is None
    con = labels_con if labels_con is not None else _open_labels(labels_db)
    try:
        labels = _labels_for_day(con, as_of)
        calendar = _calendar_before(con, as_of)
        conditions = load_conditions(con)
    finally:
        if own_con:
            con.close()
    pit_caveats: dict[str, Any] = {
        "label_values_source": "history_labels（从当前主库重建，值本身不可证明 PIT；两档同源）",
        "labels_entities_total": {"sector": len(labels["sector"]), "theme": len(labels["theme"])},
    }
    if visible is not None:
        kept_sector = [e for e in labels["sector"] if e["entity_id"] in visible]
        kept_theme = [e for e in labels["theme"] if e["entity_id"] in visible]
        pit_caveats["labels_entities_visible_at_d0"] = {"sector": len(kept_sector), "theme": len(kept_theme)}
        pit_caveats["labels_entities_excluded_not_visible_at_d0"] = {
            "sector": len(labels["sector"]) - len(kept_sector),
            "theme": len(labels["theme"]) - len(kept_theme),
        }
        pit_caveats["entity_filter"] = "strict 档标签表与车道 A 对照集都只取冻结快照里可见的实体（后补实体不冒充 PIT）"
        labels["sector"], labels["theme"] = kept_sector, kept_theme
    for entity in (*labels["sector"], *labels["theme"]):
        entity["name"] = names.get(entity["entity_id"])

    def _sort_key(row: dict[str, Any], key: str) -> float:
        value = _num(row.get(key))
        return value if value is not None else float("-inf")

    # strength 为空的日子（早期快照）退回按 amount 排，避免落到源表的文本序
    sector_day = [
        _project(r, SECTOR_DAY_FIELDS)
        for r in sorted(
            sector_rows,
            key=lambda r: (_sort_key(r, "strength"), _sort_key(r, "amount")),
            reverse=True,
        )[:PROMPT_TABLE_LIMIT]
    ]
    heat_day = [
        _project(r, THEME_HEAT_FIELDS)
        for r in sorted(heat_rows, key=lambda r: (_num(r.get("rank")) if _num(r.get("rank")) is not None else 1e9))[:PROMPT_TABLE_LIMIT]
    ]
    market_history = [_project(r, MARKET_HISTORY_FIELDS) for r in market_rows]
    market_history.sort(key=lambda r: str(r.get("trade_date")), reverse=True)

    body: dict[str, Any] = {
        "schema_version": INPUT_SCHEMA,
        "as_of": as_of,
        "pit_grade": grade,
        "market_stage": node.get("market_stage"),
        "source": source,
        "market_history": market_history,
        "sector_day": sector_day,
        "theme_heat_day": heat_day,
        "labels": labels,
        "label_version": conditions.get("label_version"),
        "labels_source_max_trade_date": conditions.get("source_max_trade_date"),
        "rules": [rule_prompt_view(rule) for rule in rules],
        "calendar": calendar,
        "visible_entity_ids": sorted(visible) if visible is not None else None,
        "pit_caveats": pit_caveats,
        "boundary": {"max_allowed_date": as_of, "outcome_data_included": False},
    }
    return finalize_replay_input(body, as_of)


def finalize_replay_input(body: dict[str, Any], as_of: str, *, out_path: str | Path | None = None) -> dict[str, Any]:
    """前视门：任何嵌入日期 > D0 → 抛错、不落盘（照 fidelity_replay.build_input_snapshot :1028–1030）。"""
    max_date = _max_embedded_date({k: v for k, v in body.items() if k != "boundary"})
    if max_date and max_date > as_of:
        raise ValueError(f"replay input contains future date {max_date} > {as_of}")
    body.setdefault("boundary", {})["max_embedded_date"] = max_date
    body.pop("input_sha256", None)
    body["input_sha256"] = _canonical_sha(body)
    if out_path is not None:
        _write_json(Path(out_path), body)
    return body


def _open_labels(labels_db: str | Path) -> Any:
    import duckdb

    path = Path(labels_db).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"旁路库不存在: {path}（先跑 build-labels / outcomes）")
    return duckdb.connect(str(path), read_only=True)


# --------------------------------------------------------------------------- #
# 3. 匿名化映射与两臂提示词
# --------------------------------------------------------------------------- #
def build_anon_map(replay_input: dict[str, Any]) -> dict[str, Any]:
    """代码 → S01… / TH01…，日期 → T-n。sector 与 theme 共用 ``sector_ts_code`` 空间：先出现在 sector 表的
    得 ``S``，只在 theme 表出现的得 ``TH``；同一代码只有一个别名。映射随节点落盘，判分前反解。"""
    codes: dict[str, str] = {}
    display: dict[str, str] = {}
    names: dict[str, str] = {}
    sector_ids = [e["entity_id"] for e in replay_input["labels"]["sector"]]
    theme_ids = [e["entity_id"] for e in replay_input["labels"]["theme"]]
    extra = [r.get("sector_ts_code") for r in (*replay_input.get("sector_day", []), *replay_input.get("theme_heat_day", []))]
    width_s = max(2, len(str(len(sector_ids) + len(extra))))
    width_t = max(2, len(str(len(theme_ids) + len(extra))))
    for code in sector_ids:
        codes[code] = f"S{len(codes) + 1:0{width_s}d}"
    n_theme = 0
    for code in theme_ids:
        if code not in codes:
            n_theme += 1
            codes[code] = f"TH{n_theme:0{width_t}d}"
    n_extra = 0
    for code in extra:
        if code and code not in codes:
            n_extra += 1
            codes[str(code)] = f"X{n_extra:02d}"
    name_by_code: dict[str, str] = {}
    for entity in (*replay_input["labels"]["sector"], *replay_input["labels"]["theme"]):
        if entity.get("name"):
            name_by_code[entity["entity_id"]] = str(entity["name"])
    for row in (*replay_input.get("sector_day", []), *replay_input.get("theme_heat_day", [])):
        if row.get("sector_ts_code") and row.get("sector_name"):
            name_by_code.setdefault(str(row["sector_ts_code"]), str(row["sector_name"]))
    for code, alias in codes.items():
        name = name_by_code.get(code)
        if name:
            display[f"{code}({name})"] = alias
            names[name] = alias
    dates = {item["trade_date"]: item["offset"] for item in replay_input["calendar"]}
    for row in replay_input["market_history"]:
        d = str(row.get("trade_date"))[:10]
        if d and d not in dates:
            # 日历之外的历史日（不该出现）也给相对偏移，保证匿名臂零绝对日期
            dates[d] = f"T-{len(dates)}"
    return {
        "schema_version": "replay-anon-map/v1",
        "as_of": replay_input["as_of"],
        "codes": codes,
        "display": display,
        "names": names,
        "dates": dates,
        "kept": ["market_stage text", "all numeric values"],
    }


def reverse_alias(anon_map: dict[str, Any] | None, token: str) -> str:
    """别名 → 真代码；不是别名就原样返回。``code(name)`` 形态也接受。"""
    token = str(token or "").strip()
    if "(" in token and token.endswith(")"):
        token = token.split("(", 1)[0]
    if not anon_map:
        return token
    reverse = {alias: code for code, alias in anon_map.get("codes", {}).items()}
    return reverse.get(token, token)


def apply_anon_map(text: str, anon_map: dict[str, Any]) -> str:
    """把命名臂文本按映射表替换成匿名臂文本（长键先替换）。测试用它断言两臂 diff 只落在映射位。"""
    pairs: list[tuple[str, str]] = []
    for key in ("display", "codes", "names", "dates"):
        pairs.extend((k, v) for k, v in (anon_map.get(key) or {}).items())
    for source, target in sorted(pairs, key=lambda kv: len(kv[0]), reverse=True):
        text = text.replace(source, target)
    return text


class _Namer:
    def __init__(self, replay_input: dict[str, Any], arm: str, anon_map: dict[str, Any] | None):
        self.arm = arm
        self.anon = anon_map or {}
        self.name_by_code: dict[str, str] = {}
        for entity in (*replay_input["labels"]["sector"], *replay_input["labels"]["theme"]):
            if entity.get("name"):
                self.name_by_code[entity["entity_id"]] = str(entity["name"])
        for row in (*replay_input.get("sector_day", []), *replay_input.get("theme_heat_day", [])):
            if row.get("sector_ts_code") and row.get("sector_name"):
                self.name_by_code.setdefault(str(row["sector_ts_code"]), str(row["sector_name"]))

    def entity(self, code: str) -> str:
        code = str(code)
        if self.arm == "anonymized":
            return self.anon["codes"].get(code, code)
        name = self.name_by_code.get(code)
        return f"{code}({name})" if name else code

    def code(self, code: str) -> str:
        code = str(code)
        if self.arm == "anonymized":
            return self.anon["codes"].get(code, code)
        return code

    def day(self, value: Any) -> str:
        raw = str(value or "")[:10]
        if self.arm == "anonymized":
            return self.anon["dates"].get(raw, raw)
        return raw


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e12:
            return str(int(value))
        return f"{value:.{digits}f}"
    return str(value)


def _lane_a_task(rules: list[dict[str, Any]], entity_word: str) -> str:
    lines = [
        "## 任务 A：规则复现（只用上面的标签表，逐条核对谓词；不要用表外信息，不要猜）",
        "",
        "下面每条规则是声明式 JSON：`condition.all` 里全部谓词同时成立才算触发；`lag: 0` 指 T-0 当日；",
        "`entity: market` 的谓词看「大盘标签」；`op: in` 表示值在列表内；标签值 `-` 表示缺失，缺失不成立。",
        f"请列出 T-0 当日每条规则触发的全部{entity_word}（用表里的实体代码），未触发给空列表。",
        "",
        "```json",
        json.dumps(rules, ensure_ascii=False, indent=1),
        "```",
        "",
        "输出格式（只输出 JSON，不要解释）：",
        '{"rule_triggers": {"<rule_id>": ["<实体代码>", "..."], "...": []}}',
    ]
    return "\n".join(lines)


def _lane_b_task(example_code: str, as_of_label: str, rule_ids: list[str]) -> str:
    lines = [
        f"## 任务 B：前瞻判断（站在 {as_of_label} 收盘后，对之后 1 / 3 / 5 个交易日给出可证伪假设）",
        "",
        f"给出 {MIN_HYPOTHESES}–{MAX_HYPOTHESES} 条假设，只输出 JSON：",
        '{"hypotheses": [{"id": "h1", "category": "direction|market", "claim": "...", "horizon": "T+1|T+3|T+5",',
        ' "confidence": "high|medium|low", "confidence_probability": 0.6, "evidence_refs": ["..."],',
        f' "evidence_as_of": "{as_of_label}", "falsify_when": "...", "rule_id": "<可选，你在应用哪条规则>"}}]}}',
        "",
        "硬性格式（不满足会被整条拒绝）：",
        "- `category` 只能是 `direction`（板块 / 题材层）或 `market`（大盘层）；不允许个股，不要写任何 6 位股票代码。",
        "- `direction` 的 `claim` 必须严格写成 `<实体代码> <度量>@<h> <比较符> <数值>`，度量 ∈ "
        f"{list(METRICS)}，h 只能是 3 或 5 且与 `horizon` 一致（T+3 ↔ @3，T+5 ↔ @5）；"
        f"例：`{example_code} fwd_return@5 > 0`（fwd_return / max_return / drawdown_after_peak 单位是 %，days_to_peak 是天数）。",
        "- `market` 的 `claim` 与 `falsify_when` 用数值条件，指标名只能用：涨家数 / 涨停家数 / 跌停家数 / 成交额（单位亿）/ 量比 / 历史新高数；"
        "形如 `T+1 涨家数 > 2500` 或 `成交额 15000-18000 亿`；`horizon` 可取 T+1 / T+3 / T+5。",
        f"- `evidence_as_of` 只能是 {as_of_label} 或更早的日期标签；`evidence_refs` 指向上面的表（如 `market_history[T-0].advancers`）。",
        f"- `rule_id` 若填，只能是：{rule_ids}。",
    ]
    return "\n".join(lines)


def render_prompt(
    replay_input: dict[str, Any],
    arm: str,
    *,
    lane: str,
    anon_map: dict[str, Any] | None = None,
) -> str:
    """同一模板渲染两臂：named 用真码 + 名字 + 绝对日期，anonymized 用别名 + 相对日期；数值与 market_stage 保留。
    匿名臂渲染完做零绝对日期断言（fail closed）。"""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}")
    if arm == "anonymized" and anon_map is None:
        anon_map = build_anon_map(replay_input)
    namer = _Namer(replay_input, arm, anon_map)
    as_of = replay_input["as_of"]
    as_of_label = namer.day(as_of)
    labels = replay_input["labels"]

    lines: list[str] = [
        "你是一名 A 股复盘分析师。下面是截至 T-0 收盘可见的结构化数据（本次 T-0 的日期标签："
        f"{as_of_label}；T-1 是它前一个交易日，依此类推）。只能使用这些数据，不要引用任何表外信息。",
        "",
        f"## 大盘（最近 {len(replay_input['market_history'])} 个交易日；成交额单位亿）",
        "",
        "| 日 | 阶段 | 涨家数 | 涨停家数 | 跌停家数 | 成交额 | 量能环比% | 量比 | 上证收盘 | 上证涨跌% | 历史新高数 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in replay_input["market_history"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    namer.day(row.get("trade_date")),
                    _fmt(row.get("market_stage")),
                    _fmt(row.get("advancers")),
                    _fmt(row.get("limit_up")),
                    _fmt(row.get("limit_down")),
                    _fmt(row.get("total_amount"), 0),
                    _fmt(row.get("amount_vs_yesterday_pct")),
                    _fmt(row.get("volume_ratio")),
                    _fmt(row.get("sh_index_close")),
                    _fmt(row.get("sh_index_pct_chg")),
                    _fmt(row.get("stock_high_count_history")),
                ]
            )
            + " |"
        )
    market = labels["market"]
    lines += [
        "",
        "## 大盘标签（T-0）",
        "",
        "| " + " | ".join(MARKET_LABELS) + " |",
        "|" + "---|" * len(MARKET_LABELS),
        "| " + " | ".join(_fmt(market.get(lab)) for lab in MARKET_LABELS) + " |",
        "",
        f"## 板块日线（T-0，按 strength 取前 {len(replay_input['sector_day'])}；amount 单位亿）",
        "",
        "| 实体 | pct_chg | diff_ratio | amount | strength |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in replay_input["sector_day"]:
        lines.append(
            f"| {namer.entity(row.get('sector_ts_code'))} | {_fmt(row.get('pct_chg'))} | {_fmt(row.get('diff_ratio'))} | "
            f"{_fmt(row.get('amount'), 0)} | {_fmt(row.get('strength'))} |"
        )
    lines += [
        "",
        f"## 题材涨停热度（T-0，按 rank 取前 {len(replay_input['theme_heat_day'])}）",
        "",
        "| 实体 | rank | limit_up_count | limit_up_ratio |",
        "|---|---:|---:|---:|",
    ]
    for row in replay_input["theme_heat_day"]:
        lines.append(
            f"| {namer.entity(row.get('sector_ts_code'))} | {_fmt(row.get('rank'))} | {_fmt(row.get('limit_up_count'))} | "
            f"{_fmt(row.get('limit_up_ratio'))} |"
        )
    lines += [
        "",
        f"## 板块标签（T-0，{len(labels['sector'])} 个实体；列顺序：{' / '.join(SECTOR_LABELS)}；`-` = 缺失）",
        "",
    ]
    for entity in labels["sector"]:
        lines.append(namer.entity(entity["entity_id"]) + " | " + " ".join(_fmt(entity.get(lab)) for lab in SECTOR_LABELS))
    lines += [
        "",
        f"## 题材标签（T-0，{len(labels['theme'])} 个实体；列顺序：{' / '.join(THEME_LABELS)}；`-` = 缺失）",
        "",
    ]
    for entity in labels["theme"]:
        lines.append(namer.entity(entity["entity_id"]) + " | " + " ".join(_fmt(entity.get(lab)) for lab in THEME_LABELS))
    lines += ["", "## 交易日历（T-0 及之前）", ""]
    lines.append(", ".join(f"{item['offset']}={namer.day(item['trade_date'])}" for item in replay_input["calendar"]))
    lines.append("")

    rule_ids = [r["rule_id"] for r in replay_input["rules"]]
    if lane == "A":
        lines.append(_lane_a_task(replay_input["rules"], "板块 / 题材实体"))
    else:
        example_code = namer.code(
            labels["sector"][0]["entity_id"] if labels["sector"] else "990001.FP"
        )
        lines.append(_lane_b_task(example_code, as_of_label, rule_ids))
    prompt = "\n".join(lines) + "\n"
    if arm == "anonymized":
        leaked = ABSOLUTE_DATE_RE.findall(prompt)
        if leaked:
            raise ValueError(f"anonymized prompt leaks absolute dates: {sorted(set(leaked))[:5]}")
    return prompt


def estimate_tokens(prompt: str) -> int:
    """输入 token 估算：len(prompt)/1.6（estimated，不是计费值）。"""
    return int(len(prompt) / ESTIMATED_CHARS_PER_TOKEN)


# --------------------------------------------------------------------------- #
# 4. 答卷校验
# --------------------------------------------------------------------------- #
def parse_json_block(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _resolve_date_label(value: Any, *, as_of: str, anon_map: dict[str, Any] | None) -> str | None:
    """把 evidence_as_of 解析成绝对日期：命名臂直接是 YYYY-MM-DD；匿名臂是 T-n（反解为日历日）。"""
    raw = str(value or "").strip()
    if ABSOLUTE_DATE_RE.fullmatch(raw[:10] or ""):
        return raw[:10]
    m = RELATIVE_DATE_RE.match(raw)
    if m and anon_map:
        reverse = {offset: d for d, offset in anon_map.get("dates", {}).items()}
        return reverse.get(raw)
    if m and not anon_map:
        return as_of if raw == "T-0" else None
    return None


def stock_codes_in(text: str, *, known_codes: Iterable[str] = ()) -> list[str]:
    """文本里的个股代码。带 .SZ/.SH/.BJ 一定是个股；裸 6 位数字只有当它不是已知板块代码前缀时才算个股。"""
    known_prefixes = {str(c).split(".", 1)[0] for c in known_codes}
    found: list[str] = []
    for m in STOCK_CODE_RE.finditer(text or ""):
        digits, suffix = m.group(1), (m.group(2) or "").upper()
        if suffix in {"FP", "TI"}:
            continue
        if suffix in {"SZ", "SH", "BJ"} or digits not in known_prefixes:
            found.append(m.group(0))
    return found


def validate_replay_answer(
    answer: Any,
    *,
    as_of: str,
    arm: str = "named",
    anon_map: dict[str, Any] | None = None,
    entity_codes: Iterable[str] = (),
    rule_ids: Iterable[str] = (),
) -> tuple[dict[str, Any] | None, list[str]]:
    """返回 (规整后的答卷, errors)。hypotheses 部分口径照抄双盲 ``_validate_v11_answer``，再加本单的三道拒绝：
    ``category=target`` / 个股代码 / ``evidence_as_of > D0``；``picks`` 必须为空；direction claim 必须落到
    一个已知实体与一个 ``history_outcomes`` 度量；market claim 必须能被 ``extract_conditions`` 解析。"""
    errors: list[str] = []
    if not isinstance(answer, dict):
        return None, ["答卷必须是 JSON 对象"]
    if answer.get("picks"):
        errors.append("picks 必须为空（本单不允许个股层判断）")
    hypotheses = answer.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        return None, errors + ["hypotheses 应为非空列表"]
    if not MIN_HYPOTHESES <= len(hypotheses) <= MAX_HYPOTHESES:
        errors.append(f"hypotheses 数量应在 {MIN_HYPOTHESES}..{MAX_HYPOTHESES}，实际 {len(hypotheses)}")
    known_codes = set(str(c) for c in entity_codes)
    alias_codes = set((anon_map or {}).get("codes", {}).values())
    accepted_tokens = known_codes | alias_codes
    allowed_rules = set(rule_ids)
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for i, hyp in enumerate(hypotheses):
        if not isinstance(hyp, dict):
            errors.append(f"hypotheses[{i}] 应为对象")
            continue
        for field in HYPOTHESIS_FIELDS:
            if field == "confidence_probability":
                if hyp.get(field) is None:
                    errors.append(f"hypotheses[{i}] 缺字段 {field}")
            elif not hyp.get(field):
                errors.append(f"hypotheses[{i}] 缺字段 {field}")
        hid = str(hyp.get("id") or "")
        if hid in seen_ids:
            errors.append(f"hypotheses[{i}].id 重复：{hid}")
        seen_ids.add(hid)
        category = str(hyp.get("category") or "")
        if category == "target":
            errors.append(f"hypotheses[{i}].category=target 不允许（个股层，BP §3.4）")
        elif category not in REPLAY_CATEGORIES:
            errors.append(f"hypotheses[{i}].category 应为 {sorted(REPLAY_CATEGORIES)} 之一，实际 {category!r}")
        if str(hyp.get("confidence") or "") not in REPLAY_CONFIDENCE:
            errors.append(f"hypotheses[{i}].confidence 应为 {sorted(REPLAY_CONFIDENCE)} 之一")
        probability = hyp.get("confidence_probability")
        if not isinstance(probability, (int, float)) or isinstance(probability, bool):
            errors.append(f"hypotheses[{i}].confidence_probability 应为 0~1 数字")
        elif not 0 <= float(probability) <= 1:
            errors.append(f"hypotheses[{i}].confidence_probability 应在 0~1 之间")
        horizon = str(hyp.get("horizon") or "")
        if horizon not in REPLAY_HORIZONS:
            errors.append(f"hypotheses[{i}].horizon 应为 {list(REPLAY_HORIZONS)} 之一，实际 {horizon!r}")
        refs = hyp.get("evidence_refs")
        if not isinstance(refs, list) or not [x for x in refs if str(x).strip()]:
            errors.append(f"hypotheses[{i}].evidence_refs 应为非空列表")
        claim = str(hyp.get("claim") or "")
        falsify = str(hyp.get("falsify_when") or "")
        stocks = stock_codes_in(claim + " " + falsify, known_codes=known_codes)
        if stocks:
            errors.append(f"hypotheses[{i}] 含个股代码 {stocks[:3]}，个股层不允许")
        resolved_as_of = _resolve_date_label(hyp.get("evidence_as_of"), as_of=as_of, anon_map=anon_map)
        if hyp.get("evidence_as_of") and resolved_as_of is None:
            errors.append(f"hypotheses[{i}].evidence_as_of={hyp.get('evidence_as_of')!r} 无法解析为 D0 或更早的日期")
        elif resolved_as_of and resolved_as_of > as_of:
            errors.append(f"hypotheses[{i}].evidence_as_of={resolved_as_of} 晚于 D0 {as_of}")
        parsed_claim: dict[str, Any] | None = None
        if category == "direction":
            m = DIRECTION_CLAIM_RE.match(claim)
            if not m:
                errors.append(f"hypotheses[{i}].claim 不是 `<实体> <度量>@<h> <op> <值>` 形式：{claim[:60]!r}")
            else:
                token = m.group("entity")
                real = reverse_alias(anon_map, token) if arm == "anonymized" else reverse_alias(None, token)
                if token not in accepted_tokens and real not in known_codes:
                    errors.append(f"hypotheses[{i}].claim 的实体 {token!r} 不在输入的实体表里")
                if arm == "named" and token in alias_codes:
                    errors.append(f"hypotheses[{i}].claim 命名臂不得使用别名 {token!r}")
                h_claim = int(m.group("horizon"))
                hm = HORIZON_RE.match(horizon)
                if hm and int(hm.group(1)) != h_claim:
                    errors.append(f"hypotheses[{i}] claim 的 @{h_claim} 与 horizon {horizon} 不一致")
                parsed_claim = {
                    "entity": real,
                    "entity_token": token,
                    "metric": m.group("metric"),
                    "horizon": h_claim,
                    "op": m.group("op"),
                    "value": float(m.group("value")),
                }
        elif category == "market":
            conds = extract_conditions(claim)
            if not conds:
                errors.append(f"hypotheses[{i}].claim（market）抽不出数值条件：{claim[:60]!r}")
            parsed_claim = {"conditions": [list(c) for c in conds]}
        rule_id = hyp.get("rule_id")
        if rule_id and allowed_rules and str(rule_id) not in allowed_rules:
            errors.append(f"hypotheses[{i}].rule_id={rule_id!r} 不在规则表里")
        normalized.append(
            {
                **{field: hyp.get(field) for field in HYPOTHESIS_FIELDS},
                "rule_id": str(rule_id) if rule_id else None,
                "evidence_as_of_resolved": resolved_as_of,
                "parsed": parsed_claim,
            }
        )
    if errors:
        return None, errors
    return {"hypotheses": normalized, "picks": []}, []


# --------------------------------------------------------------------------- #
# 5. 车道 A：规则复现一致率
# --------------------------------------------------------------------------- #
def expected_triggers(
    labels_con: Any,
    rules: list[Rule],
    as_of: str,
    *,
    restrict_to: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    """确定性对照：``compile_rule`` 以窗口 [D0, D0] 编译，执行事件集查询（与 ``runner.execute_compiled``
    第一句相同的 SQL），取全部 entity_id——不看 outcomes 状态，车道 A 不涉及 D0 之后的数据。
    ``restrict_to``（strict 档）= D0 可见实体，与提示词里的标签表同一集合。"""
    allowed = {str(x) for x in restrict_to} if restrict_to is not None else None
    out: dict[str, list[str]] = {}
    for rule in rules:
        compiled = compile_rule(rule, start=as_of, end=as_of)
        rows = labels_con.execute(compiled.events.sql, list(compiled.events.params)).fetchall()
        ids = {str(r[0]) for r in rows}
        if allowed is not None:
            ids &= allowed
        out[rule.rule_id] = sorted(ids)
    return out


def parse_lane_a_answer(
    payload: dict[str, Any] | None, *, rule_ids: Iterable[str], anon_map: dict[str, Any] | None
) -> tuple[dict[str, list[str]] | None, list[str]]:
    if not isinstance(payload, dict):
        return None, ["答卷不是 JSON 对象"]
    triggers = payload.get("rule_triggers")
    if not isinstance(triggers, dict):
        return None, ["缺 rule_triggers 对象"]
    out: dict[str, list[str]] = {}
    errors: list[str] = []
    for rule_id in rule_ids:
        raw = triggers.get(rule_id)
        if raw is None:
            errors.append(f"rule_triggers 缺 {rule_id}")
            raw = []
        if not isinstance(raw, list):
            errors.append(f"rule_triggers[{rule_id}] 应为列表")
            raw = []
        out[rule_id] = sorted({reverse_alias(anon_map, str(t)) for t in raw if str(t).strip()})
    return out, errors


def compare_triggers(expected: list[str], predicted: list[str]) -> dict[str, Any]:
    e, p = set(expected), set(predicted)
    tp = len(e & p)
    return {
        "expected_n": len(e),
        "predicted_n": len(p),
        "tp": tp,
        "fp": len(p - e),
        "fn": len(e - p),
        "precision": (tp / len(p)) if p else (1.0 if not e else 0.0),
        "recall": (tp / len(e)) if e else (1.0 if not p else 0.0),
        "exact": e == p,
        "missed": sorted(e - p)[:12],
        "spurious": sorted(p - e)[:12],
    }


# --------------------------------------------------------------------------- #
# 6. 自动判分
# --------------------------------------------------------------------------- #
def _eval_date(calendar: list[str], as_of: str, horizon: int) -> str | None:
    """T+h = D0 之后第 h 个交易日（WINDOW_START_OFFSET=1 → 窗口不含 D0）。日历没走到就 None。"""
    if as_of not in calendar:
        return None
    idx = calendar.index(as_of) + WINDOW_START_OFFSET + horizon - 1
    return calendar[idx] if 0 <= idx < len(calendar) else None


def _compare(actual: float, op: str, value: float) -> bool:
    return {">": actual > value, ">=": actual >= value, "<": actual < value, "<=": actual <= value}[op]


def judge(
    node: dict[str, Any],
    answer: dict[str, Any],
    *,
    labels_con: Any,
    db_con: Any,
    entity_types: dict[str, str],
    calendar: list[str] | None = None,
) -> list[dict[str, Any]]:
    """逐条假设判分。direction 查 ``history_outcomes``（``status != ok`` → unverifiable；无行 → unverifiable）；
    market 用 ``market_actuals`` + 条件口径。只读主库 / 旁路库。"""
    as_of = str(node["as_of"])
    if calendar is None:
        calendar = [
            str(r[0])[:10]
            for r in labels_con.execute("SELECT trade_date FROM history_calendar ORDER BY trade_date").fetchall()
        ]
    out: list[dict[str, Any]] = []
    market_cache: dict[str, dict[str, Any] | None] = {}
    for hyp in answer.get("hypotheses") or []:
        category = str(hyp.get("category"))
        horizon_label = str(hyp.get("horizon") or "")
        hm = HORIZON_RE.match(horizon_label)
        h = int(hm.group(1)) if hm else None
        verdict, actual = "unverifiable", ""
        parsed = hyp.get("parsed") or {}
        if category == "direction" and parsed.get("entity") and h is not None:
            entity = str(parsed["entity"])
            etype = entity_types.get(entity, "sector")
            row = labels_con.execute(
                """
                SELECT status, fwd_return, max_return, days_to_peak, drawdown_after_peak
                FROM history_outcomes
                WHERE entity_type = ? AND entity_id = ? AND trade_date = CAST(? AS DATE) AND horizon = ?
                """,
                [etype, entity, as_of, int(parsed["horizon"])],
            ).fetchone()
            if row is None:
                actual = f"history_outcomes 无 ({etype}, {entity}, {as_of}, h={parsed['horizon']}) 行（该窗口未构建或实体不在 universe）"
            elif row[0] != "ok":
                actual = f"outcome status={row[0]}"
            else:
                metrics = dict(zip(("fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"), row[1:]))
                value = metrics.get(parsed["metric"])
                if value is None:
                    actual = f"{parsed['metric']} 为空"
                else:
                    ok = _compare(float(value), parsed["op"], float(parsed["value"]))
                    verdict = "hit" if ok else "miss"
                    actual = f"{parsed['metric']}@{parsed['horizon']} = {float(value):.4f}"
        elif category == "market" and h is not None:
            eval_date = _eval_date(calendar, as_of, h)
            if eval_date is None:
                actual = f"回检日 T+{h} 未到（日历止于 {calendar[-1] if calendar else None}）"
            else:
                if eval_date not in market_cache:
                    market_cache[eval_date] = market_actuals(db_con, eval_date)
                market = market_cache[eval_date]
                if market is None:
                    actual = f"{eval_date} 无 fact_market_daily 行"
                else:
                    vals = {k: market.get(k) for k in MARKET_VALUE_KEYS}
                    verdict = judge_market_claim(str(hyp.get("claim") or ""), str(hyp.get("falsify_when") or ""), vals)
                    actual = (
                        f"{eval_date}: 涨家数{market.get('advancers')} 涨停{market.get('limit_up')} 跌停{market.get('limit_down')} "
                        f"成交额{market.get('total_amount')} 量比{market.get('volume_ratio')} 历史新高{market.get('high_history')}"
                    )
        out.append(
            {
                "id": hyp.get("id"),
                "category": category,
                "horizon": horizon_label,
                "claim": hyp.get("claim"),
                "rule_id": hyp.get("rule_id"),
                "confidence_probability": hyp.get("confidence_probability"),
                "verdict": verdict,
                "actual": actual,
                "evidence_ref": f"auto:replay_engine history_outcomes/fact_market_daily {as_of}",
            }
        )
    return out


# --------------------------------------------------------------------------- #
# 7. 模型截止日与 memory_bucket
# --------------------------------------------------------------------------- #
def load_model_cutoffs(path: str | Path = MODEL_CUTOFFS_PATH) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.is_file():
        return []
    body = _read_json(p)
    entries = body.get("models") if isinstance(body, dict) else body
    return [e for e in (entries or []) if isinstance(e, dict) and e.get("model_pattern")]


def cutoff_for_model(model: str | None, cutoffs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not model:
        return None
    name = str(model).lower()
    for entry in cutoffs:
        pattern = str(entry["model_pattern"]).lower()
        if fnmatch.fnmatchcase(name, pattern) or name == pattern:
            return entry
    return None


def memory_bucket(model: str | None, as_of: str, cutoffs: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """D0 > cutoff → post_cutoff；D0 ≤ cutoff → pre_cutoff；cutoff 为 null 或模型不在表里 → unknown。
    报表把 pre_cutoff 与 unknown 都标 memory_contaminated，不与 post_cutoff 合并出任何数字。"""
    entry = cutoff_for_model(model, cutoffs)
    if entry is None:
        return "unknown", {"model": model, "training_cutoff": None, "note": "model not in model_cutoffs.json"}
    cutoff = entry.get("training_cutoff")
    meta = {
        "model": model,
        "model_pattern": entry.get("model_pattern"),
        "training_cutoff": cutoff,
        "source_url": entry.get("source_url"),
        "checked_at": entry.get("checked_at"),
        "note": entry.get("note"),
    }
    if not cutoff:
        return "unknown", meta
    return ("post_cutoff" if str(as_of) > str(cutoff) else "pre_cutoff"), meta


# --------------------------------------------------------------------------- #
# 8. 聚合（车道 B 复用 checkpoints.calibrate）
# --------------------------------------------------------------------------- #
def cell_key(pit_grade: str, bucket: str, arm: str, category: str, horizon: str) -> str:
    return "|".join((pit_grade, bucket, arm, category, horizon))


def aggregate_lane_b(
    records: list[dict[str, Any]], *, min_n: int = DEFAULT_CALIBRATION_MIN_N
) -> dict[str, Any]:
    """把每条假设整形为 checkpoints 记录 + verdicts 记录，直接调 ``calibrate``（``CategoryStat`` 不重写）；
    ``category`` 位放格子键 ``pit_grade|memory_bucket|arm|category|horizon``，``source`` 位放实际模型名。
    格子 N < min_n 只给 N；N ≥ min_n 给命中率与 Wilson 95%。"""
    checkpoints: list[dict[str, Any]] = []
    verdicts: list[dict[str, Any]] = []
    unverifiable: dict[str, int] = defaultdict(int)
    for rec in records:
        key = cell_key(rec["pit_grade"], rec["memory_bucket"], rec["arm"], rec["category"], rec["horizon"])
        cid = f"{rec['as_of']}|{rec['arm']}|{rec['id']}"
        checkpoints.append({"id": cid, "category": key, "source": rec.get("model") or "unknown", "claim": rec.get("claim")})
        verdicts.append({"id": cid, "verdict": rec["verdict"], "score": None})
        if rec["verdict"] == "unverifiable":
            unverifiable[key] += 1
    cal = calibrate(checkpoints, verdicts)
    cells: list[dict[str, Any]] = []
    for st in cal.by_category:
        grade, bucket, arm, category, horizon = st.category.split("|")
        cell: dict[str, Any] = {
            "pit_grade": grade,
            "memory_bucket": bucket,
            "memory_contaminated": bucket in MEMORY_CONTAMINATED,
            "arm": arm,
            "category": category,
            "horizon": horizon,
            "n": st.n,
            "unverifiable": unverifiable.get(st.category, 0),
        }
        if st.n >= min_n:
            lo, hi = wilson(st.hits, st.n)
            cell.update(
                {
                    "hits": st.hits,
                    "partial": st.partial,
                    "miss": st.miss,
                    "hit_rate": _round(st.hit_rate),
                    "strict_hit_rate": _round(st.hits / st.n),
                    "wilson_95": [_round(lo), _round(hi)],
                    "reliability": st.reliability,
                }
            )
        else:
            cell["note"] = f"N<{min_n}，只给 N"
        cells.append(cell)
    # 全 unverifiable 的格子 calibrate 不会产出（无终态），补一行只报 N=0 + unverifiable 数
    covered = {cell_key(c["pit_grade"], c["memory_bucket"], c["arm"], c["category"], c["horizon"]) for c in cells}
    for key, count in sorted(unverifiable.items()):
        if key in covered:
            continue
        grade, bucket, arm, category, horizon = key.split("|")
        cells.append(
            {
                "pit_grade": grade,
                "memory_bucket": bucket,
                "memory_contaminated": bucket in MEMORY_CONTAMINATED,
                "arm": arm,
                "category": category,
                "horizon": horizon,
                "n": 0,
                "unverifiable": count,
                "note": "全部 unverifiable，无终态样本",
            }
        )
    cells.sort(key=lambda c: (c["pit_grade"], c["memory_bucket"], c["category"], c["horizon"], c["arm"]))
    by_source = [
        {"model": st.category, "n": st.n, "hits": st.hits, "partial": st.partial, "miss": st.miss}
        for st in cal.by_source
    ]
    return {
        "min_n": min_n,
        "scored": cal.scored,
        "unverifiable": cal.unverifiable,
        "cells": cells,
        "by_model": by_source,
        "arm_gap": arm_gap(records, min_n=min_n),
    }


def _pooled_rate(records: list[dict[str, Any]]) -> tuple[int, float | None]:
    terminal = [r for r in records if r["verdict"] in ("hit", "miss", "partial")]
    if not terminal:
        return 0, None
    score = sum({"hit": 1.0, "partial": 0.5, "miss": 0.0}[r["verdict"]] for r in terminal)
    return len(terminal), score / len(terminal)


def arm_gap(records: list[dict[str, Any]], *, min_n: int = DEFAULT_CALIBRATION_MIN_N) -> list[dict[str, Any]]:
    """臂间差 = named 命中率 − anonymized 命中率，按 pit_grade × memory_bucket（类别 × 窗口合并池，但**不**跨档 / 跨桶）。
    两臂 N 都 ≥ min_n 才给差值；差值就是记忆成分的上界，字段标 ``memory_signal``。"""
    groups: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        groups[(rec["pit_grade"], rec["memory_bucket"])][rec["arm"]].append(rec)
    out: list[dict[str, Any]] = []
    for (grade, bucket), arms in sorted(groups.items()):
        n_named, rate_named = _pooled_rate(arms.get("named", []))
        n_anon, rate_anon = _pooled_rate(arms.get("anonymized", []))
        row: dict[str, Any] = {
            "pit_grade": grade,
            "memory_bucket": bucket,
            "memory_contaminated": bucket in MEMORY_CONTAMINATED,
            "pooled_over": "category × horizon（同档同桶内）",
            "named": {"n": n_named, "hit_rate": _round(rate_named) if n_named >= min_n else None},
            "anonymized": {"n": n_anon, "hit_rate": _round(rate_anon) if n_anon >= min_n else None},
        }
        if n_named >= min_n and n_anon >= min_n and rate_named is not None and rate_anon is not None:
            gap = rate_named - rate_anon
            row["gap_named_minus_anonymized"] = _round(gap)
            row["memory_signal"] = "臂间差是记忆成分上界（消融）：named 高于 anonymized 的部分最多是记忆，不能归为能力"
        else:
            row["gap_named_minus_anonymized"] = None
            row["memory_signal"] = f"任一臂 N<{min_n}，不给差值"
        out.append(row)
    return out


def aggregate_lane_a(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 pit_grade × arm × rule_id：微平均精确率 / 召回率 + 集合完全一致比例。"""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        groups[(rec["pit_grade"], rec["arm"], rec["rule_id"])].append(rec)
    out: list[dict[str, Any]] = []
    for (grade, arm, rule_id), items in sorted(groups.items()):
        tp = sum(i["tp"] for i in items)
        fp = sum(i["fp"] for i in items)
        fn = sum(i["fn"] for i in items)
        out.append(
            {
                "pit_grade": grade,
                "arm": arm,
                "rule_id": rule_id,
                "nodes": len(items),
                "expected_total": sum(i["expected_n"] for i in items),
                "predicted_total": sum(i["predicted_n"] for i in items),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision_micro": _round(tp / (tp + fp)) if (tp + fp) else None,
                "recall_micro": _round(tp / (tp + fn)) if (tp + fn) else None,
                "exact_match_rate": _round(sum(1 for i in items if i["exact"]) / len(items)),
                "nodes_with_expected_events": sum(1 for i in items if i["expected_n"]),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# 9. LLM 适配（唯一入口 llm_refine.complete；预算闸由 call_ledger_scope 承担）
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "你是严谨的 A 股结构化复盘助手。只根据用户给出的表格作答，输出必须是一个 JSON 对象，不加任何解释文字。"
)
LLMCallable = Callable[[str, dict[str, Any]], dict[str, Any]]


def llm_via_refine(prompt: str, meta: dict[str, Any]) -> dict[str, Any]:
    """真跑适配：``complete`` 返回 ``(content, provider, reason)``；实际模型名取 ``provider.model``。"""
    import time

    from intelligence.services.llm_refine import complete

    started = time.monotonic()
    content, provider, reason = complete(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        timeout=LLM_TIMEOUT_SECONDS,
        temperature=LLM_TEMPERATURE,
    )
    return {
        "content": content,
        "model": provider.model if provider else None,
        "provider": provider.name if provider else None,
        "reason": reason or "",
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }


def _budget_exhausted(result: dict[str, Any]) -> bool:
    return result.get("content") is None and "预算" in str(result.get("reason") or "")


# --------------------------------------------------------------------------- #
# 10. 跑一遍：节点 → 输入 → 两臂两车道 → 判分 → 聚合 → 报表
# --------------------------------------------------------------------------- #
def new_run_id(now: datetime | None = None) -> str:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    rev = (_git(["rev-parse", "--short=8", "HEAD"]) or "norev")[:8]
    return f"replay-{ts}-{rev}"


def reconciliation_dates(ledger_dir: str | Path, snapshot_root: str | Path) -> list[str]:
    """同时有快照 manifest 与真答卷（``<date>.answer.*.json``）的日期。"""
    ledger = Path(ledger_dir).expanduser()
    root = Path(snapshot_root).expanduser()
    if not ledger.is_dir() or not root.is_dir():
        return []
    answers = {p.name[:10] for p in ledger.glob("*.answer.*.json")}
    manifests = {p.name[:10] for p in root.glob("*.manifest.json")}
    return sorted(answers & manifests)


def _load_dual_blind_module() -> Any:
    """按文件加载 scripts/dual_blind_forecast.py（对账段复用它的 aggregate，不复制实现）。"""
    import importlib.util

    path = REPO_ROOT / "scripts" / "dual_blind_forecast.py"
    spec = importlib.util.spec_from_file_location("dual_blind_forecast_for_replay", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("dual_blind_forecast_for_replay", module)
    spec.loader.exec_module(module)
    return module


def _strict_rate(bucket: dict[str, int]) -> tuple[int, float | None]:
    terminal = int(bucket.get("hit", 0)) + int(bucket.get("miss", 0)) + int(bucket.get("partial", 0))
    return terminal, (int(bucket.get("hit", 0)) / terminal) if terminal else None


def build_reconciliation(
    lane_b_records: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    *,
    ledger_dir: str | Path,
    snapshot_root: str | Path,
    subset_dir: Path,
    min_dates: int = 5,
) -> dict[str, Any]:
    """对账段：重放 strict 档 market 类（T+1，两臂）命中率 vs 双盲台账真人 agent 同类别同期命中率并排。
    台账侧把同期日期的答卷 / 裁定复制到 run 目录下的子集再调 ``aggregate``（台账目录本身一个字节都不写）。
    差值只记录，不做结论。"""
    import shutil

    overlap = reconciliation_dates(ledger_dir, snapshot_root)
    strict_dates = {n["as_of"] for n in nodes if n["pit_grade"] == "strict"}
    included = [d for d in overlap if d in strict_dates]
    excluded = {d: "不在本次 strict 节点集（超出 judgeable end 或未入选）" for d in overlap if d not in strict_dates}
    section: dict[str, Any] = {
        "overlap_dates": overlap,
        "included_dates": included,
        "excluded_dates": excluded,
        "min_dates": min_dates,
        "comparability_note": "重放 market 类取 horizon=T+1 与台账「盘面 / T+1」对齐；命中率 = hit / (hit+miss+partial)，两侧同口径；差值只记录不做结论",
    }
    if len(included) < min_dates:
        section["status"] = "insufficient"
        section["note"] = f"不足对账最小样本：同时有快照与真答卷且进入 strict 节点集的日期只有 {len(included)} 个（< {min_dates}）"
        return section
    ledger = Path(ledger_dir).expanduser()
    subset_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for d in included:
        for path in sorted(ledger.glob(f"{d}.answer.*.json")) + sorted(ledger.glob(f"{d}.verdict.json")):
            shutil.copyfile(path, subset_dir / path.name)
            copied += 1
    module = _load_dual_blind_module()
    agg = module.aggregate(subset_dir)
    human_rows: list[dict[str, Any]] = []
    pooled = {"hit": 0, "miss": 0, "partial": 0, "unverifiable": 0}
    for key, stat in sorted(agg.get("agents", {}).items()):
        bucket = (stat.get("verdicts_by_category") or {}).get("market") or {}
        n, rate = _strict_rate(bucket)
        for k in pooled:
            pooled[k] += int(bucket.get(k, 0))
        human_rows.append(
            {
                "agent": stat.get("agent"),
                "source": stat.get("source"),
                "category": "market",
                "n": n,
                "unverifiable": int(bucket.get("unverifiable", 0)),
                "hit_rate": _round(rate),
                "answers": stat.get("answers"),
            }
        )
    human_n, human_rate = _strict_rate(pooled)
    replay_rows: list[dict[str, Any]] = []
    for arm in ARMS:
        recs = [
            r
            for r in lane_b_records
            if r["as_of"] in included and r["pit_grade"] == "strict" and r["category"] == "market" and r["horizon"] == "T+1" and r["arm"] == arm
        ]
        counts = {"hit": 0, "miss": 0, "partial": 0, "unverifiable": 0}
        for r in recs:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        n, rate = _strict_rate(counts)
        buckets = sorted({r["memory_bucket"] for r in recs})
        replay_rows.append(
            {
                "arm": arm,
                "pit_grade": "strict",
                "memory_bucket": buckets[0] if len(buckets) == 1 else (buckets or ["n/a"]),
                "category": "market",
                "horizon": "T+1",
                "n": n,
                "unverifiable": counts["unverifiable"],
                "hit_rate": _round(rate),
                "diff_vs_human_pooled": _round(rate - human_rate) if (rate is not None and human_rate is not None) else None,
            }
        )
    section.update(
        {
            "status": "ok",
            "ledger_subset_dir": str(subset_dir),
            "ledger_files_copied": copied,
            "human": {"pooled": {"category": "market", "n": human_n, "hit_rate": _round(human_rate), "unverifiable": pooled["unverifiable"]}, "by_agent": human_rows},
            "replay": replay_rows,
        }
    )
    return section


def _memory_bucket_distribution(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for rec in records:
        counts[(rec["pit_grade"], rec["memory_bucket"], rec["arm"])] += 1
    return [
        {"pit_grade": g, "memory_bucket": b, "arm": a, "hypotheses": n, "memory_contaminated": b in MEMORY_CONTAMINATED}
        for (g, b, a), n in sorted(counts.items())
    ]


def build_report(
    *,
    run_id: str,
    run_dir: Path,
    nodes: list[dict[str, Any]],
    lane_a_records: list[dict[str, Any]],
    lane_b_records: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    conditions: dict[str, Any],
    environment: dict[str, Any],
    cutoffs: list[dict[str, Any]],
    reconciliation: dict[str, Any] | None,
    config: dict[str, Any],
    stopped_reason: str | None = None,
) -> dict[str, Any]:
    models = sorted({str(c.get("model")) for c in calls if c.get("model")})
    cutoff_rows = [
        {**memory_bucket(m, "1900-01-01", cutoffs)[1]} for m in models
    ]
    by_grade: dict[str, int] = defaultdict(int)
    for n in nodes:
        by_grade[n["pit_grade"]] += 1
    report = {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "decision_eligible": False,
        "stopped_reason": stopped_reason,
        "conditions": {
            "models": models,
            "model_cutoffs": cutoff_rows,
            "cutoffs_file": str(MODEL_CUTOFFS_PATH),
            "nodes_by_grade": dict(by_grade),
            "manifest_shas": sorted(
                {str((n.get("grade_meta") or {}).get("manifest_sha")) for n in nodes if n["pit_grade"] == "strict" and (n.get("grade_meta") or {}).get("manifest_sha")}
            ),
            "label_version": conditions.get("label_version"),
            "source_max_trade_date": conditions.get("source_max_trade_date"),
            "labels_computed_at": conditions.get("labels_computed_at"),
            "outcomes_computed_at": conditions.get("outcomes_computed_at"),
            "outcomes_horizons": conditions.get("outcomes_horizons"),
            "window_start_offset": WINDOW_START_OFFSET,
            "llm": {
                "entry": "intelligence.services.llm_refine.complete",
                "temperature": LLM_TEMPERATURE,
                "timeout_seconds": LLM_TIMEOUT_SECONDS,
                "system_prompt_sha256": _sha256_text(SYSTEM_PROMPT),
                "calls": len(calls),
                "failures": sum(1 for c in calls if not c.get("ok")),
                "invalid_answers": sum(1 for c in calls if c.get("ok") and not c.get("valid")),
                "estimated_input_tokens": sum(int(c.get("estimated_input_tokens") or 0) for c in calls),
                "estimated": True,
            },
            "environment": environment,
            "config": config,
        },
        "nodes": [
            {k: n.get(k) for k in ("as_of", "market_stage", "pit_grade", "forced")}
            | {
                "manifest_sha": (n.get("grade_meta") or {}).get("manifest_sha"),
                "grade_reason": (n.get("grade_meta") or {}).get("reason"),
                "labels_total": (n.get("pit_caveats") or {}).get("labels_entities_total"),
                "labels_visible_at_d0": (n.get("pit_caveats") or {}).get("labels_entities_visible_at_d0"),
            }
            for n in nodes
        ],
        "pit_caveat": (
            "strict 档的严格性只覆盖冻结快照里的行情表；标签值来自旁路库（从当前主库重建），两档同源、不可证明 PIT。"
            "strict 档标签表与车道 A 对照集只取 D0 可见实体（快照里出现过的代码），后补实体不冒充 PIT。"
        ),
        "lane_a": {"note": "规则复现一致率：不涉及 D0 之后的数据，无泄漏读数；微平均 P/R + 集合完全一致比例", "cells": aggregate_lane_a(lane_a_records)},
        "lane_b": aggregate_lane_b(lane_b_records),
        "memory_bucket_distribution": _memory_bucket_distribution(lane_b_records),
        "reconciliation": reconciliation,
        "rules": ["pre_cutoff 与 unknown 都是 memory_contaminated，报表任何一格都不与 post_cutoff 相加", "格子 N<10 只给 N", "两档 PIT 不出混合平均", "只量不调：提示词 / 温度 / 模型本单内冻结"],
    }
    return report


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_report_markdown(report: dict[str, Any]) -> str:
    c = report["conditions"]
    lines = [
        f"# 历史重放读数 · {report['run_id']}",
        "",
        f"> 生成于 {report['generated_at']}；decision_eligible=false（只量不调）。"
        + (f" **提前停止：{report['stopped_reason']}**" if report.get("stopped_reason") else ""),
        "",
        "## 成立条件",
        "",
        f"- 模型（实际 `provider.model`）：{', '.join(c['models']) or '（无成功调用）'}",
    ]
    for row in c["model_cutoffs"]:
        lines.append(
            f"- 截止日：`{row.get('model')}` → training_cutoff={row.get('training_cutoff')}，来源 {row.get('source_url')}，"
            f"checked_at {row.get('checked_at')}；{row.get('note')}"
        )
    env = c["environment"]
    lines += [
        f"- 节点数按档：{json.dumps(c['nodes_by_grade'], ensure_ascii=False)}",
        f"- 快照 manifest sha（strict 档，{len(c['manifest_shas'])} 份）：{', '.join(s[:12] for s in c['manifest_shas']) or '—'}",
        f"- 旁路库：label_version=`{c['label_version']}`，source_max_trade_date={c['source_max_trade_date']}，outcomes_horizons={c['outcomes_horizons']}，WINDOW_START_OFFSET={c['window_start_offset']}",
        f"- 树 {env.get('worktree')} @ {env.get('branch')} · revision `{env.get('revision')}` · dirty={str(env.get('dirty')).lower()} · 解释器 {env.get('interpreter')}",
        f"- LLM：入口 {c['llm']['entry']}，temperature={c['llm']['temperature']}，调用 {c['llm']['calls']} 次 / 失败 {c['llm']['failures']} 次 / 答卷无效 {c['llm']['invalid_answers']} 次，"
        f"输入 token 估算 {c['llm']['estimated_input_tokens']}（estimated）",
        f"- 配置：{json.dumps(c['config'], ensure_ascii=False)}",
        "",
        "## 节点",
        "",
        f"> {report.get('pit_caveat', '')}",
        "",
        "| D0 | pit_grade | market_stage | forced | 标签实体（板块/题材） | D0 可见 | manifest_sha / 原因 |",
        "|---|---|---|---|---|---|---|",
    ]
    for n in report["nodes"]:
        tag = (n.get("manifest_sha") or "")[:12] or (n.get("grade_reason") or "")
        total = n.get("labels_total") or {}
        vis = n.get("labels_visible_at_d0")
        vis_txt = f"{vis.get('sector')}/{vis.get('theme')}" if vis else "（不过滤）"
        lines.append(
            f"| {n['as_of']} | {n['pit_grade']} | {n.get('market_stage')} | {'✓' if n.get('forced') else ''} | "
            f"{total.get('sector', '—')}/{total.get('theme', '—')} | {vis_txt} | {tag} |"
        )
    lines += [
        "",
        "## 车道 A · 规则复现一致率（无泄漏：不涉及 D0 之后的数据）",
        "",
        "| pit_grade | arm | rule_id | 节点数 | 有事件节点 | 期望实体 | 预测实体 | 精确率(微) | 召回率(微) | 完全一致率 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in report["lane_a"]["cells"]:
        lines.append(
            f"| {cell['pit_grade']} | {cell['arm']} | `{cell['rule_id']}` | {cell['nodes']} | {cell['nodes_with_expected_events']} | "
            f"{cell['expected_total']} | {cell['predicted_total']} | {_pct(cell['precision_micro'])} | {_pct(cell['recall_micro'])} | {_pct(cell['exact_match_rate'])} |"
        )
    if not report["lane_a"]["cells"]:
        lines.append("| — | — | — | 0 | 0 | 0 | 0 | — | — | — |")
    b = report["lane_b"]
    lines += [
        "",
        f"## 车道 B · 前瞻判断分格（pit_grade × memory_bucket × arm × category × horizon；N<{b['min_n']} 只给 N）",
        "",
        f"> 终态样本 {b['scored']} 条，unverifiable {b['unverifiable']} 条。`memory_contaminated=true` 的格子（pre_cutoff / unknown）不与 post_cutoff 相加。",
        "",
        "| pit_grade | memory_bucket | 污染 | arm | category | horizon | N | unverifiable | hit | partial | miss | 命中率(分制) | 严格命中率 | Wilson 95% |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cell in b["cells"]:
        if "hit_rate" in cell:
            wl = cell["wilson_95"]
            tail = f"{cell['hits']} | {cell['partial']} | {cell['miss']} | {_pct(cell['hit_rate'])} | {_pct(cell['strict_hit_rate'])} | [{_pct(wl[0])}, {_pct(wl[1])}]"
        else:
            tail = f"— | — | — | — | — | {cell.get('note', '')}"
        lines.append(
            f"| {cell['pit_grade']} | {cell['memory_bucket']} | {'是' if cell['memory_contaminated'] else '否'} | {cell['arm']} | {cell['category']} | "
            f"{cell['horizon']} | {cell['n']} | {cell['unverifiable']} | {tail} |"
        )
    if not b["cells"]:
        lines.append("| — | — | — | — | — | — | 0 | 0 | — | — | — | — | — | — |")
    lines += [
        "",
        "## 臂间差（memory_signal：named − anonymized，同档同桶内合并类别 × 窗口；差值 = 记忆成分上界）",
        "",
        "| pit_grade | memory_bucket | 污染 | named N | named 命中率 | anonymized N | anonymized 命中率 | 臂间差 | memory_signal |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in b["arm_gap"]:
        lines.append(
            f"| {row['pit_grade']} | {row['memory_bucket']} | {'是' if row['memory_contaminated'] else '否'} | {row['named']['n']} | {_pct(row['named']['hit_rate'])} | "
            f"{row['anonymized']['n']} | {_pct(row['anonymized']['hit_rate'])} | "
            f"{_pct(row['gap_named_minus_anonymized']) if row['gap_named_minus_anonymized'] is not None else '—'} | {row['memory_signal']} |"
        )
    lines += ["", "## memory_bucket 分布（每条假设一票）", "", "| pit_grade | memory_bucket | arm | 假设数 | 污染 |", "|---|---|---|---:|---|"]
    for row in report["memory_bucket_distribution"]:
        lines.append(f"| {row['pit_grade']} | {row['memory_bucket']} | {row['arm']} | {row['hypotheses']} | {'是' if row['memory_contaminated'] else '否'} |")
    rec = report.get("reconciliation")
    lines += ["", "## 对账 · 重放 vs 双盲台账（同期、market 类、T+1）", ""]
    if not rec:
        lines.append("未跑对账（--no-reconcile 或 dry-run）。")
    elif rec.get("status") != "ok":
        lines.append(f"{rec.get('note')}；同时有快照与答卷的日期：{', '.join(rec.get('overlap_dates') or []) or '无'}")
    else:
        lines.append(f"> 同期日期 {len(rec['included_dates'])} 个：{', '.join(rec['included_dates'])}。{rec['comparability_note']}。")
        lines.append("")
        lines.append("| 侧 | agent / arm | pit_grade | memory_bucket | N | unverifiable | 命中率 | 与真人合计差 |")
        lines.append("|---|---|---|---|---:|---:|---:|---:|")
        h = rec["human"]["pooled"]
        lines.append(f"| 台账（真人合计） | all | — | — | {h['n']} | {h['unverifiable']} | {_pct(h['hit_rate'])} | — |")
        for row in rec["human"]["by_agent"]:
            lines.append(f"| 台账 | {row['agent']}/{row['source']} | — | — | {row['n']} | {row['unverifiable']} | {_pct(row['hit_rate'])} | — |")
        for row in rec["replay"]:
            diff = row["diff_vs_human_pooled"]
            lines.append(
                f"| 重放 | {row['arm']} | {row['pit_grade']} | {row['memory_bucket']} | {row['n']} | {row['unverifiable']} | {_pct(row['hit_rate'])} | "
                f"{_pct(diff) if diff is not None else '—'} |"
            )
        if rec.get("excluded_dates"):
            lines.append("")
            lines.append("未进入对账的重叠日期：" + "；".join(f"{d}（{why}）" for d, why in rec["excluded_dates"].items()))
    lines += ["", "## 规则", ""] + [f"- {r}" for r in report["rules"]] + [""]
    return "\n".join(lines)


def write_report(report: dict[str, Any], out_dir: Path, *, stem: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    _write_json(json_path, report)
    md_path.write_text(render_report_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def _entity_types_for(replay_input: dict[str, Any]) -> dict[str, str]:
    types = {e["entity_id"]: "sector" for e in replay_input["labels"]["sector"]}
    for e in replay_input["labels"]["theme"]:
        types.setdefault(e["entity_id"], "theme")
    return types


def run_replay(
    *,
    db_path: str | Path,
    labels_db: str | Path,
    snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    start: str | None = None,
    end: str | None = None,
    count_per_grade: int = DEFAULT_COUNT_PER_GRADE,
    arms: Iterable[str] = ARMS,
    lanes: Iterable[str] = LANES,
    max_calls: int = DEFAULT_MAX_CALLS,
    dry_run: bool = False,
    llm: LLMCallable | None = None,
    ledger_dir: str | Path | None = LEDGER_DIR,
    reconcile: bool = True,
    cutoffs_path: str | Path = MODEL_CUTOFFS_PATH,
    rules_dir: str | Path = RULES_DIR,
    measurements_dir: str | Path | None = MEASUREMENTS_DIR,
    run_id: str | None = None,
    abort_failure_rate: float | None = 0.2,
    nodes_override: list[dict[str, Any]] | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """主流程。``dry_run`` 只建输入与提示词、打印节点数 / 调用数 / 估算 token，不碰 LLM。
    ``llm`` 可注入（selftest 用 stub）；缺省走 ``llm_via_refine``。整个真跑包在 ``call_ledger_scope(max_calls)``
    里——``complete`` 的 ``_budget_rejection`` 就是硬帽，被拒即停，不重试、不绕。"""
    from intelligence.services.llm_refine import call_ledger_scope

    arms = tuple(a for a in ARMS if a in set(arms))
    lanes = tuple(lane for lane in LANES if lane in set(lanes))
    db_path = Path(db_path).expanduser()
    labels_db = Path(labels_db).expanduser()
    snapshot_root = Path(snapshot_root).expanduser()
    run_id = run_id or new_run_id()
    run_dir = Path(runtime_root).expanduser() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    rules = load_lane_a_rules(rules_dir)
    rule_ids = [r.rule_id for r in rules]
    cutoffs = load_model_cutoffs(cutoffs_path)
    llm = llm or llm_via_refine

    labels_con = _open_labels(labels_db)
    db_con = _connect(db_path)
    try:
        conditions = load_conditions(labels_con)
        calendar = [str(r[0])[:10] for r in labels_con.execute("SELECT trade_date FROM history_calendar ORDER BY trade_date").fetchall()]
        start = start or conditions["calendar"]["start"]
        end = end or judgeable_end(db_path) or conditions["calendar"]["end"]
        forced = reconciliation_dates(ledger_dir, snapshot_root) if (reconcile and ledger_dir) else []
        nodes = nodes_override if nodes_override is not None else select_nodes(
            db_path, start, end, count_per_grade=count_per_grade, snapshot_root=snapshot_root, forced_dates=forced
        )
        log(f"[replay] run_id={run_id} nodes={len(nodes)} " + json.dumps({g: sum(1 for n in nodes if n['pit_grade'] == g) for g in PIT_GRADES}, ensure_ascii=False))
        environment = environment_block(snapshot_root=snapshot_root, db_path=db_path, labels_db=labels_db)
        config = {
            "start": start,
            "end": end,
            "count_per_grade": count_per_grade,
            "arms": list(arms),
            "lanes": list(lanes),
            "max_calls": max_calls,
            "dry_run": dry_run,
            "reconcile": bool(reconcile and ledger_dir),
            "forced_dates": forced,
            "rules": rule_ids,
        }
        _write_json(run_dir / "run.json", {"run_id": run_id, "config": config, "environment": environment, "nodes": nodes, "started_at": _utc_now_iso()})

        calls: list[dict[str, Any]] = []
        lane_a_records: list[dict[str, Any]] = []
        lane_b_records: list[dict[str, Any]] = []
        planned = len(nodes) * len(arms) * len(lanes)
        estimated_tokens = 0
        stopped_reason: str | None = None

        with call_ledger_scope(max_calls=max_calls) as ledger:
            for node in nodes:
                as_of = node["as_of"]
                node_dir = run_dir / "nodes" / as_of
                replay_input = build_replay_input(
                    node, db_path=db_path, labels_db=labels_db, snapshot_root=snapshot_root, rules=rules, labels_con=labels_con
                )
                finalize_replay_input(replay_input, as_of, out_path=node_dir / "input.json")
                anon_map = build_anon_map(replay_input)
                _write_json(node_dir / "anon_map.json", anon_map)
                node["pit_caveats"] = replay_input.get("pit_caveats")
                entity_types = _entity_types_for(replay_input)
                known_codes = list(entity_types)
                expected = (
                    expected_triggers(labels_con, rules, as_of, restrict_to=replay_input.get("visible_entity_ids"))
                    if "A" in lanes
                    else {}
                )
                verdict_doc: dict[str, Any] = {
                    "as_of": as_of,
                    "pit_grade": node["pit_grade"],
                    "market_stage": node.get("market_stage"),
                    "expected_triggers": expected,
                    "pit_caveats": replay_input.get("pit_caveats"),
                    "lane_a": {},
                    "lane_b": {},
                    "memory_bucket": {},
                }
                answers: dict[str, dict[str, Any]] = {arm: {} for arm in arms}
                for arm in arms:
                    for lane in lanes:
                        prompt = render_prompt(replay_input, arm, lane=lane, anon_map=anon_map)
                        (node_dir / f"prompt.{lane}.{arm}.txt").write_text(prompt, encoding="utf-8")
                        est = estimate_tokens(prompt)
                        estimated_tokens += est
                        if dry_run or stopped_reason:
                            continue
                        if ledger.over_budget():
                            stopped_reason = f"预算闸：已达 max_calls={max_calls}"
                            continue
                        result = llm(prompt, {"as_of": as_of, "arm": arm, "lane": lane, "pit_grade": node["pit_grade"]})
                        model = result.get("model")
                        bucket, bucket_meta = memory_bucket(model, as_of, cutoffs)
                        verdict_doc["memory_bucket"].setdefault(arm, {})[f"lane_{lane}"] = {"bucket": bucket, **bucket_meta}
                        call_rec = {
                            "as_of": as_of,
                            "pit_grade": node["pit_grade"],
                            "arm": arm,
                            "lane": lane,
                            "model": model,
                            "provider": result.get("provider"),
                            "ok": result.get("content") is not None,
                            "reason": result.get("reason") or "",
                            "elapsed_ms": result.get("elapsed_ms"),
                            "estimated_input_tokens": est,
                            "prompt_sha256": _sha256_text(prompt),
                            "valid": False,
                        }
                        payload = parse_json_block(result.get("content"))
                        entry: dict[str, Any] = {
                            "model": model,
                            "provider": result.get("provider"),
                            "reason": result.get("reason") or "",
                            "raw": result.get("content"),
                            "memory_bucket": bucket,
                            "errors": [],
                        }
                        if _budget_exhausted(result):
                            stopped_reason = f"预算闸拒发：{result.get('reason')}"
                            entry["errors"].append("budget_rejected")
                        elif result.get("content") is None:
                            entry["errors"].append(f"llm_failed: {result.get('reason')}")
                        elif payload is None:
                            entry["errors"].append("答卷不是可解析的 JSON 对象")
                        elif lane == "A":
                            parsed, errs = parse_lane_a_answer(payload, rule_ids=rule_ids, anon_map=anon_map if arm == "anonymized" else None)
                            entry["errors"] = errs
                            if parsed is not None:
                                entry["parsed"] = parsed
                                call_rec["valid"] = not errs
                                lane_a_cells: dict[str, Any] = {}
                                for rule_id in rule_ids:
                                    cmp = compare_triggers(expected.get(rule_id, []), parsed.get(rule_id, []))
                                    lane_a_cells[rule_id] = cmp
                                    lane_a_records.append({"as_of": as_of, "pit_grade": node["pit_grade"], "arm": arm, "rule_id": rule_id, "model": model, **cmp})
                                verdict_doc["lane_a"][arm] = lane_a_cells
                        else:
                            normalized, errs = validate_replay_answer(
                                payload, as_of=as_of, arm=arm, anon_map=anon_map if arm == "anonymized" else None, entity_codes=known_codes, rule_ids=rule_ids
                            )
                            entry["errors"] = errs
                            if normalized is not None:
                                entry["parsed"] = normalized
                                call_rec["valid"] = True
                                verdicts = judge(node, normalized, labels_con=labels_con, db_con=db_con, entity_types=entity_types, calendar=calendar)
                                verdict_doc["lane_b"][arm] = verdicts
                                for v in verdicts:
                                    lane_b_records.append({**v, "as_of": as_of, "pit_grade": node["pit_grade"], "arm": arm, "model": model, "memory_bucket": bucket})
                        answers[arm][lane] = entry
                        calls.append(call_rec)
                        if abort_failure_rate is not None and len(calls) >= 10:
                            failures = sum(1 for c in calls if not c["ok"])
                            if failures / len(calls) > abort_failure_rate:
                                stopped_reason = f"失败率 {failures}/{len(calls)} > {abort_failure_rate:.0%}，停止（缩 --count-per-grade 再试一次）"
                if not dry_run:
                    for arm in arms:
                        _write_json(node_dir / f"answer.{arm}.json", answers[arm])
                    _write_json(node_dir / "verdict.json", verdict_doc)
                log(f"[replay] node {as_of} {node['pit_grade']} done" + (f" (stopped: {stopped_reason})" if stopped_reason else ""))
                if stopped_reason:
                    break
            ledger_summary = ledger.summary()
        reconciliation = None
        if not dry_run and reconcile and ledger_dir and "B" in lanes:
            reconciliation = build_reconciliation(
                lane_b_records, nodes, ledger_dir=ledger_dir, snapshot_root=snapshot_root, subset_dir=run_dir / "ledger-subset"
            )
        report = build_report(
            run_id=run_id,
            run_dir=run_dir,
            nodes=nodes,
            lane_a_records=lane_a_records,
            lane_b_records=lane_b_records,
            calls=calls,
            conditions=conditions,
            environment=environment,
            cutoffs=cutoffs,
            reconciliation=reconciliation,
            config=config,
            stopped_reason=stopped_reason,
        )
        report["conditions"]["llm"]["ledger"] = {k: ledger_summary.get(k) for k in ("call_count", "reserved_count", "failure_count", "rejected_count", "max_calls", "failure_reasons")}
        report["dry_run"] = {
            "nodes": len(nodes),
            "planned_calls": planned,
            "estimated_input_tokens": estimated_tokens,
            "estimated": True,
            "chars_per_token": ESTIMATED_CHARS_PER_TOKEN,
        }
        _write_json(run_dir / "report.json", report)
        (run_dir / "report.md").write_text(render_report_markdown(report), encoding="utf-8")
        if not dry_run and measurements_dir is not None:
            stem = f"replay-{datetime.now().date().isoformat()}"
            paths = write_report(report, Path(measurements_dir).expanduser(), stem=stem)
            report["measurement_paths"] = {k: str(v) for k, v in paths.items()}
        log(
            f"[replay] done: nodes={len(nodes)} planned_calls={planned} calls={len(calls)} "
            f"failures={sum(1 for c in calls if not c['ok'])} est_tokens={estimated_tokens} (estimated) run_dir={run_dir}"
        )
        return report
    finally:
        db_con.close()
        labels_con.close()


def rebuild_report(
    run_dir: str | Path,
    *,
    db_path: str | Path,
    labels_db: str | Path,
    snapshot_root: str | Path = DEFAULT_SNAPSHOT_ROOT,
    ledger_dir: str | Path | None = LEDGER_DIR,
    cutoffs_path: str | Path = MODEL_CUTOFFS_PATH,
    rules_dir: str | Path = RULES_DIR,
    measurements_dir: str | Path | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """``report`` 子命令：从已落盘的 run 目录（input / anon_map / answer.*.json 的 raw）重新校验、判分、聚合，
    不碰 LLM。判分逻辑修了可以在这里重出报表而不再花钱。"""
    run_dir = Path(run_dir).expanduser()
    meta = _read_json(run_dir / "run.json")
    nodes = meta["nodes"]
    config = dict(meta.get("config") or {})
    config["rebuilt_from"] = str(run_dir)
    arms = tuple(config.get("arms") or ARMS)
    lanes = tuple(config.get("lanes") or LANES)
    rules = load_lane_a_rules(rules_dir)
    rule_ids = [r.rule_id for r in rules]
    cutoffs = load_model_cutoffs(cutoffs_path)
    labels_con = _open_labels(labels_db)
    db_con = _connect(db_path)
    calls: list[dict[str, Any]] = []
    lane_a_records: list[dict[str, Any]] = []
    lane_b_records: list[dict[str, Any]] = []
    try:
        conditions = load_conditions(labels_con)
        calendar = [str(r[0])[:10] for r in labels_con.execute("SELECT trade_date FROM history_calendar ORDER BY trade_date").fetchall()]
        seen_nodes: list[dict[str, Any]] = []
        for node in nodes:
            as_of = node["as_of"]
            node_dir = run_dir / "nodes" / as_of
            if not (node_dir / "input.json").exists():
                continue
            seen_nodes.append(node)
            replay_input = _read_json(node_dir / "input.json")
            anon_map = _read_json(node_dir / "anon_map.json")
            node["pit_caveats"] = replay_input.get("pit_caveats")
            entity_types = _entity_types_for(replay_input)
            expected = expected_triggers(labels_con, rules, as_of, restrict_to=replay_input.get("visible_entity_ids"))
            for arm in arms:
                answer_path = node_dir / f"answer.{arm}.json"
                if not answer_path.exists():
                    continue
                answers = _read_json(answer_path)
                for lane in lanes:
                    entry = answers.get(lane)
                    if not entry:
                        continue
                    model = entry.get("model")
                    bucket, _meta = memory_bucket(model, as_of, cutoffs)
                    prompt_path = node_dir / f"prompt.{lane}.{arm}.txt"
                    est = estimate_tokens(prompt_path.read_text(encoding="utf-8")) if prompt_path.exists() else 0
                    call_rec = {"as_of": as_of, "pit_grade": node["pit_grade"], "arm": arm, "lane": lane, "model": model, "ok": entry.get("raw") is not None, "reason": entry.get("reason"), "estimated_input_tokens": est, "valid": False}
                    payload = parse_json_block(entry.get("raw"))
                    if payload is not None and lane == "A":
                        parsed, errs = parse_lane_a_answer(payload, rule_ids=rule_ids, anon_map=anon_map if arm == "anonymized" else None)
                        if parsed is not None:
                            call_rec["valid"] = not errs
                            for rule_id in rule_ids:
                                cmp = compare_triggers(expected.get(rule_id, []), parsed.get(rule_id, []))
                                lane_a_records.append({"as_of": as_of, "pit_grade": node["pit_grade"], "arm": arm, "rule_id": rule_id, "model": model, **cmp})
                    elif payload is not None:
                        normalized, errs = validate_replay_answer(
                            payload, as_of=as_of, arm=arm, anon_map=anon_map if arm == "anonymized" else None, entity_codes=list(entity_types), rule_ids=rule_ids
                        )
                        if normalized is not None:
                            call_rec["valid"] = True
                            for v in judge(node, normalized, labels_con=labels_con, db_con=db_con, entity_types=entity_types, calendar=calendar):
                                lane_b_records.append({**v, "as_of": as_of, "pit_grade": node["pit_grade"], "arm": arm, "model": model, "memory_bucket": bucket})
                    calls.append(call_rec)
        reconciliation = None
        if ledger_dir and "B" in lanes and config.get("reconcile", True):
            reconciliation = build_reconciliation(
                lane_b_records, seen_nodes, ledger_dir=ledger_dir, snapshot_root=snapshot_root, subset_dir=run_dir / "ledger-subset"
            )
        report = build_report(
            run_id=str(meta.get("run_id")),
            run_dir=run_dir,
            nodes=seen_nodes,
            lane_a_records=lane_a_records,
            lane_b_records=lane_b_records,
            calls=calls,
            conditions=conditions,
            environment=environment_block(snapshot_root=Path(snapshot_root), db_path=Path(db_path), labels_db=Path(labels_db)),
            cutoffs=cutoffs,
            reconciliation=reconciliation,
            config=config,
        )
        report["rebuilt_at"] = _utc_now_iso()
        _write_json(run_dir / "report.json", report)
        (run_dir / "report.md").write_text(render_report_markdown(report), encoding="utf-8")
        if measurements_dir is not None:
            stem = f"replay-{datetime.now().date().isoformat()}"
            paths = write_report(report, Path(measurements_dir).expanduser(), stem=stem)
            report["measurement_paths"] = {k: str(v) for k, v in paths.items()}
        log(f"[replay] report rebuilt: nodes={len(seen_nodes)} calls={len(calls)} run_dir={run_dir}")
        return report
    finally:
        db_con.close()
        labels_con.close()
