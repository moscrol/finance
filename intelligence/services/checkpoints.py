"""可证伪点台账 + 判断打分 + 二阶推演校准 (checkpoints / verdicts / calibration)。

B 方案（``judgments.jsonl``）让 foresight 站在你旧判断上往前推；C 方案再往前一步：
把判断里**可证伪的那一刀**单独登记成带「到期日 + 类别 + 机检规格」的检查点，到期拉
盘面/知识库数据核对当初判断的对错，给判断打分，再**反过来校准「你哪类二阶推演靠谱」**，
把这份胜率回注 foresight 发问——让它信任你历史靠谱的推演类、主动质疑你常落空的那类。

两个 append-only 台账（每行一条 JSON，均 gitignore、按用户隔离）：

- ``checkpoints.jsonl``  登记的可证伪点：
    - ``id``                 稳定 id（注册日 + 短哈希），verdict 凭它回链；
    - ``claim``              可证伪陈述（必填）；
    - ``due``                到期回检日 YYYY-MM-DD（必填）；
    - ``category``           二阶推演类型（校准聚合维度，如「估值切换」「产能时点」）；
    - ``themes`` / ``stocks``关联题材 / 个股；
    - ``metric``             可选机检规格（无则人工判定）：
        - ``stock_return``   个股区间涨幅，对比 ``op``/``target``（``window_days`` 窗口）→ 盘面 resolver；
        - ``kb_evidence``    注册后是否出现新证据（``target`` 主题/公司，``target`` 条数阈值）→ 知识库 resolver；
        - ``manual``         人工判定；
    - ``source_judgment_ts`` 反链 B 的核心判断（可选）；
    - ``session_id``         来源会话（可选）。
- ``verdicts.jsonl``    回检打分：``id`` / ``verdict``(hit|miss|partial|unverifiable) /
    ``score``(1|0|0.5|None) / ``observed`` / ``data_source`` / ``reason`` / ``auto`` / ``checked_at``。

``unverifiable``（如本机无 DuckDB、数据未到）是**非终态**：不计入胜率、下次仍进到期队列，
等数据齐了再判。终态（hit/miss/partial）才进 ``calibrate`` 聚合。

本模块只用标准库，不依赖 duckdb / 联网，可离线运行、可独立单测；真正拉数的 resolver
在 ``checkpoint_resolvers`` 里且**优雅降级**（缺数→unverifiable，绝不编造）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timezone
from pathlib import Path
from typing import Any

# verdict → 分数。unverifiable 记 None（不计入胜率）。
VERDICTS = ("hit", "partial", "miss", "unverifiable")
TERMINAL_VERDICTS = ("hit", "partial", "miss")
SCORE_MAP: dict[str, float | None] = {"hit": 1.0, "partial": 0.5, "miss": 0.0, "unverifiable": None}

METRIC_TYPES = ("stock_return", "kb_evidence", "market_daily", "manual")
NUMERIC_METRIC_TYPES = ("stock_return", "kb_evidence")
VALID_OPS = (">=", ">", "<=", "<", "==")

# 判断轨对象分三类（时间长河 roadmap §13.2 F2 / 终局 spec §2.2「判断轨」）：
# 用户自己下的判断、agent 下的判断、系统生成经用户确认的观察剧本。
# 三类混进同一个胜率分母，会让「用户决策」的读数被另外两类稀释——G-09 的胜率面板
# 要按这个维度分列，所以字段必须在**登记时**就写下，事后从 category 反推是猜。
OBJECT_TYPES = ("judgment", "agent_judgment", "observation_script")
DEFAULT_OBJECT_TYPE = "judgment"
OBJECT_TYPE_CN = {
    "judgment": "用户判断",
    "agent_judgment": "agent 判断",
    "observation_script": "观察剧本",
    "unknown_legacy": "存量未标类型",
}

# market_daily 条件字段名：只允许安全标识符（真实列名在查询时再校验，查不到→unverifiable）。
_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")

DEFAULT_WINDOW_DAYS = 60
# 一个类别至少要有多少条终态判定，才给它贴「靠谱 / 参半 / 偏差大」并注入提示词。
# 2026-09-04 前是 2——两个样本就给可靠性标签，正是「一次错误否定一套方法」的机制来源
# （设计稿 docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md §3.4）。
# 只读消融（83 个可证伪点、69 条终态、2 个类别）：min_n=2 → 2 类有标签；10 或 20 → 1 类
# （掉的是 n=2 的「duckdb_flow/市场路径」）。取 10：与 20 结果相同，但给未来新类别留出
# 更早进入校准的余地；四个消费者（render_calibration_for_prompt / prime / red_team.weak_categories /
# user_memory.peer_hit_line）共用这一闸。
DEFAULT_CALIBRATION_MIN_N = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return date_cls.today().isoformat()


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _clean_terms(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        key = _norm(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _parse_date(value: Any) -> str:
    """把 ``value`` 规整成 ``YYYY-MM-DD``；非法日期抛 ``ValueError``。"""
    s = str(value or "").strip()
    if not s:
        raise ValueError("到期日 due 不能为空")
    try:
        return date_cls.fromisoformat(s[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"非法到期日 due={value!r}（需 YYYY-MM-DD）") from exc


def normalize_metric(metric: dict[str, Any] | None) -> dict[str, Any] | None:
    """校验并规整机检规格；``None`` / 空 → ``None``（走人工判定）。"""
    if not metric:
        return None
    if not isinstance(metric, dict):
        raise ValueError("metric 必须是对象")
    mtype = str(metric.get("type") or "").strip()
    if mtype not in METRIC_TYPES:
        raise ValueError(f"非法 metric.type={mtype!r}（允许 {METRIC_TYPES}）")
    if mtype == "manual":
        return {"type": "manual"}
    if mtype == "market_daily":
        return _normalize_market_daily_metric(metric)
    out: dict[str, Any] = {"type": mtype}
    op = str(metric.get("op") or ">=").strip()
    if op not in VALID_OPS:
        raise ValueError(f"非法 metric.op={op!r}（允许 {VALID_OPS}）")
    out["op"] = op
    target = metric.get("target")
    if target is None:
        raise ValueError(f"metric.type={mtype} 需要数值阈值 target")
    try:
        out["target"] = float(target)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"非法 metric.target={target!r}（需数值）") from exc
    if mtype == "stock_return":
        out["window_days"] = int(metric.get("window_days") or DEFAULT_WINDOW_DAYS)
    if metric.get("target_name"):
        out["target_name"] = str(metric["target_name"]).strip()
    return out


def _normalize_market_daily_metric(metric: dict[str, Any]) -> dict[str, Any]:
    """规整 ``market_daily`` 机检规格：到期日拉 ``fact_market_daily`` 当日行，逐条比较。

    ``conditions`` 为条件列表，全部达标=hit、任一不达标=miss、查无当日行=unverifiable：
    ``[{"field": "advancers", "op": ">=", "target": 3000}, ...]``
    也接受字符串简写 ``"advancers>=3000"``。可选 ``trade_date`` 覆盖取数日（默认 due）。
    """
    raw = metric.get("conditions")
    if not raw or not isinstance(raw, list):
        raise ValueError("market_daily 需要非空 conditions 列表")
    conditions: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            m = re.match(r"^\s*([a-z][a-z0-9_]*)\s*(>=|<=|==|>|<)\s*(-?[\d.]+)\s*$", item)
            if not m:
                raise ValueError(f"非法 market_daily 条件 {item!r}（形如 advancers>=3000）")
            item = {"field": m.group(1), "op": m.group(2), "target": m.group(3)}
        if not isinstance(item, dict):
            raise ValueError(f"非法 market_daily 条件 {item!r}")
        field_name = str(item.get("field") or "").strip()
        if not _FIELD_RE.match(field_name):
            raise ValueError(f"非法 market_daily 字段名 {field_name!r}")
        op = str(item.get("op") or ">=").strip()
        if op not in VALID_OPS:
            raise ValueError(f"非法 market_daily op={op!r}（允许 {VALID_OPS}）")
        try:
            target = float(item.get("target"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"非法 market_daily target={item.get('target')!r}（需数值）") from exc
        conditions.append({"field": field_name, "op": op, "target": target})
    out: dict[str, Any] = {"type": "market_daily", "conditions": conditions}
    if metric.get("trade_date"):
        out["trade_date"] = _parse_date(metric["trade_date"])
    return out


def _make_id(claim: str, ts: str, due: str = "") -> str:
    """内容派生 id。``due`` 进哈希：**同一陈述 + 不同到期日 = 两个检查点**。

    2026-09-06 实测：观察剧本因 due 落在非交易日而改点时，新旧两条 claim 相同、
    又在同一秒登记（``ts`` 只到秒），算出的 id 完全一样——那条「旧点判不了」的
    verdict 会同时打在新点上，新点一登记就被判过了。
    ``framework_interpretation`` 早就按 ``(claim, due)`` 做幂等，本函数只是补齐同一口径。
    存量 id 已落盘不受影响（内容派生只在写入时算一次）。
    """
    digest = hashlib.sha1(f"{ts}|{claim}|{due}".encode("utf-8")).hexdigest()[:6]
    return f"ck-{ts[:10]}-{digest}"


def register_checkpoint(
    path: str | Path,
    *,
    claim: str,
    due: str,
    category: str | None = None,
    source: str | None = None,
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    metric: dict[str, Any] | None = None,
    source_judgment_ts: str | None = None,
    session_id: str | None = None,
    framework_version: str | None = None,
    object_type: str = DEFAULT_OBJECT_TYPE,
    hindsight: bool = False,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """登记一个可证伪点到 ``checkpoints.jsonl``，返回 ``(path, record)``。

    ``claim`` 为空或 ``due`` 非法日期时抛 ``ValueError``——可证伪点至少要有陈述与到期日。
    ``object_type`` 非法同样抛错：认不出类型就 fail closed，不默默按「用户判断」记。
    """
    text = str(claim or "").strip()
    if not text:
        raise ValueError("claim 不能为空：可证伪点至少要有陈述")
    if object_type not in OBJECT_TYPES:
        raise ValueError(f"非法 object_type={object_type!r}（允许 {OBJECT_TYPES}）")
    due_norm = _parse_date(due)
    metric_norm = normalize_metric(metric)
    ts_norm = ts or _now().isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "id": _make_id(text, ts_norm, due_norm),
        "ts": ts_norm,
        "claim": text,
        "due": due_norm,
        "category": str(category).strip() if category and str(category).strip() else None,
        "source": str(source).strip() if source and str(source).strip() else None,
        "themes": _clean_terms(themes),
        "stocks": _clean_terms(stocks),
        "object_type": object_type,
        # 这条判断是不是站在**事后视角**建立的（上游切片 knowledge_cutoff > as_of）。
        # 终局 spec §4.1：hindsight 只用于人工复核，**不得进入任何校准或方法有效性统计**。
        # 必须落进记录：标记若只活在上游那一跳，到 calibrate 这里就没人知道了。
        "hindsight": bool(hindsight),
    }
    if metric_norm:
        record["metric"] = metric_norm
    if framework_version and str(framework_version).strip():
        record["framework_version"] = str(framework_version).strip()
    if source_judgment_ts and str(source_judgment_ts).strip():
        record["source_judgment_ts"] = str(source_judgment_ts).strip()
    if session_id and str(session_id).strip():
        record["session_id"] = str(session_id).strip()
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def _load_jsonl(path: str | Path, label: str) -> tuple[list[dict[str, Any]], str | None]:
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"{label}读取失败：{exc}"
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out, None


def load_checkpoints(path: str | Path) -> tuple[list[dict[str, Any]], str | None]:
    """读取全部可证伪点（保留出现顺序）。文件不存在时返回空列表。"""
    records, warn = _load_jsonl(path, "可证伪点台账")
    return [r for r in records if str(r.get("claim") or "").strip() and r.get("id")], warn


LEGACY_OBJECT_TYPE = "unknown_legacy"
# 存量记录（``object_type`` 字段上线前登记的）只能从 ``source`` 反推，而且只反推**确定**的那部分。
# 这三个 source 是 agent 侧产出：框架解读步、逻辑生命周期、下期关注。
# ``foresight_judgment`` 是用户 accept 后入账的用户判断，其余无 source 的手工登记同样多为用户判断——
# 但「多为」不是「是」，所以剩下的一律进 ``unknown_legacy`` 单独一格。
# 把它们折进 ``judgment``，等于用一个默认值把三种来源合成一种，胜率面板就再也分不开了。
_AGENT_SOURCES = ("framework_interpretation", "logic_lifecycle", "track_next_watch")
_USER_SOURCES = ("foresight_judgment",)


def object_type_of(record: dict[str, Any]) -> str:
    """读一条 checkpoint 的对象类型；存量记录返回 ``unknown_legacy`` 而不是瞎猜。"""
    declared = str(record.get("object_type") or "").strip()
    if declared in OBJECT_TYPES:
        return declared
    source = str(record.get("source") or "").strip()
    if source in _AGENT_SOURCES:
        return "agent_judgment"
    if source in _USER_SOURCES:
        return "judgment"
    return LEGACY_OBJECT_TYPE


def load_verdicts(path: str | Path) -> tuple[list[dict[str, Any]], str | None]:
    """读取全部回检打分（保留出现顺序）。文件不存在时返回空列表。"""
    records, warn = _load_jsonl(path, "回检打分台账")
    return [r for r in records if r.get("id") and r.get("verdict") in VERDICTS], warn


def _latest_terminal_verdicts(verdicts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """每个 id 取最后一条**终态**打分（后写覆盖先写）。"""
    out: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        if v.get("verdict") in TERMINAL_VERDICTS:
            out[str(v["id"])] = v
    return out


def due_checkpoints(
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    today: str | None = None,
) -> list[dict[str, Any]]:
    """到期且尚未拿到终态打分的检查点（``due <= today``）。

    ISO 日期可直接字典序比较。``unverifiable`` 非终态，仍会再次进队列等数据齐了重判。
    """
    today = today or _today()
    scored = _latest_terminal_verdicts(verdicts)
    out: list[dict[str, Any]] = []
    for c in checkpoints:
        due = str(c.get("due") or "")
        if not due or due > today:
            continue
        if str(c.get("id")) in scored:
            continue
        out.append(c)
    return out


def record_verdict(
    path: str | Path,
    *,
    id: str,
    verdict: str,
    score: float | None = None,
    observed: dict[str, Any] | None = None,
    data_source: str = "manual",
    reason: str = "",
    degradation: dict[str, Any] | None = None,
    auto: bool = False,
    checked_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """把一条回检打分 append 到 ``verdicts.jsonl``，返回 ``(path, record)``。

    ``degradation`` 只在 ``unverifiable`` 时有值（见 checkpoint_resolvers）：
    落盘保留它，是为了半年后还能回答"当时为什么判不了、补什么才能判"。
    """
    cid = str(id or "").strip()
    if not cid:
        raise ValueError("verdict 必须带 checkpoint id")
    if verdict not in VERDICTS:
        raise ValueError(f"非法 verdict={verdict!r}（允许 {VERDICTS}）")
    if score is None:
        score = SCORE_MAP[verdict]
    record: dict[str, Any] = {
        "id": cid,
        "checked_at": checked_at or _now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "score": score,
        "data_source": data_source,
        "auto": bool(auto),
    }
    if observed:
        record["observed"] = observed
    if reason and str(reason).strip():
        record["reason"] = str(reason).strip()
    if degradation:
        record["degradation"] = degradation
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


# --------------------------------------------------------------------------- #
# 校准：把已回检的判断按「二阶推演类别」聚合成胜率，定位你哪类推演靠谱/偏差。
# --------------------------------------------------------------------------- #
@dataclass
class CategoryStat:
    category: str
    n: int = 0
    hits: int = 0
    partial: int = 0
    miss: int = 0
    score_sum: float = 0.0
    samples: list[str] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        return (self.score_sum / self.n) if self.n else 0.0

    @property
    def reliability(self) -> str:
        if self.n == 0:
            return "无样本"
        r = self.hit_rate
        if r >= 0.7:
            return "靠谱"
        if r >= 0.4:
            return "参半"
        return "偏差大"


@dataclass
class Calibration:
    by_category: list[CategoryStat] = field(default_factory=list)
    by_source: list[CategoryStat] = field(default_factory=list)
    # 判断轨对象分三类（用户决策 / agent 判断 / 观察剧本）。不分列的话，
    # 「观察剧本这类判断准不准」这个问题**问不出来**：系统生成经确认的剧本
    # 会和用户自己下的判断混在同一个分母里，互相稀释。
    # 存量记录进 unknown_legacy 单独一格，不折进 judgment（见 object_type_of）。
    by_object_type: list[CategoryStat] = field(default_factory=list)
    scored: int = 0
    pending: int = 0
    unverifiable: int = 0
    # 因 hindsight 被挡在校准之外的条数。**必须报出来**：静默剔除会让样本
    # 莫名其妙变少，而「样本少」和「样本被规则挡了」是两件事，后者是产品在守纪律。
    hindsight_excluded: int = 0

    @property
    def overall_rate(self) -> float:
        total = sum(c.score_sum for c in self.by_category)
        n = sum(c.n for c in self.by_category)
        return (total / n) if n else 0.0


def calibrate(
    checkpoints: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    today: str | None = None,
) -> Calibration:
    """按 ``category``（二阶推演类型）与 ``source``（判断产出模块）两个维度聚合终态打分→胜率。

    category 回答「哪类推演靠谱」；source 回答「哪个模块在产真信号」——命中率长期不达标的模块应降级为资料工具。
    两个列表均按命中率升序（最该质疑的在前）。"""
    by_id = {str(c.get("id")): c for c in checkpoints if c.get("id")}
    terminal = _latest_terminal_verdicts(verdicts)
    stats: dict[str, CategoryStat] = {}
    src_stats: dict[str, CategoryStat] = {}
    obj_stats: dict[str, CategoryStat] = {}
    hindsight_excluded = 0
    for cid, v in terminal.items():
        ck = by_id.get(cid)
        if ck is None:
            continue
        if ck.get("hindsight"):
            # 事后视角建立的判断进校准 = 拿「后来才知道的事」去证明「当时判得准」。
            # 这里是**机器保证**，不是提醒：spec §4.1 那句「不得进入任何校准」，
            # 靠消费方自觉看 pit_grade 是保不住的——今天它就一处没人读。
            hindsight_excluded += 1
            continue
        cat = str(ck.get("category") or "未分类").strip() or "未分类"
        src = str(ck.get("source") or "未标来源").strip() or "未标来源"
        # 对象类型从 checkpoint 记录回连取，**不在 verdict 里再存一份**：
        # 同一事实存两处必漂，而漂的时候胜率面板会按过期那份分列。
        obj = object_type_of(ck)
        verdict = str(v.get("verdict"))
        score = v.get("score")
        score = SCORE_MAP.get(verdict, 0.0) if score is None else float(score)
        for key, bucket in ((cat, stats), (src, src_stats), (obj, obj_stats)):
            st = bucket.setdefault(key, CategoryStat(category=key))
            st.n += 1
            st.score_sum += score
            if verdict == "hit":
                st.hits += 1
            elif verdict == "partial":
                st.partial += 1
            else:
                st.miss += 1
            if len(st.samples) < 3:
                st.samples.append(str(ck.get("claim") or "")[:60])
    pending = len(due_checkpoints(checkpoints, verdicts, today=today))
    unverifiable = sum(1 for v in verdicts if v.get("verdict") == "unverifiable")
    return Calibration(
        by_category=sorted(stats.values(), key=lambda s: (s.hit_rate, -s.n)),
        by_source=sorted(src_stats.values(), key=lambda s: (s.hit_rate, -s.n)),
        by_object_type=sorted(obj_stats.values(), key=lambda s: (s.hit_rate, -s.n)),
        scored=sum(s.n for s in stats.values()),
        pending=pending,
        unverifiable=unverifiable,
        hindsight_excluded=hindsight_excluded,
    )


def render_calibration_for_prompt(cal: Calibration, min_n: int = DEFAULT_CALIBRATION_MIN_N) -> str:
    """渲染成注入 foresight 系统提示词的「胜率加权」要点（只列样本足够的类别）。"""
    lines: list[str] = []
    for st in cal.by_category:
        if st.n < min_n:
            continue
        pct = round(st.hit_rate * 100)
        if st.reliability == "靠谱":
            tail = "→ 这类判断历史靠谱，可继续信任、承接它往前推"
        elif st.reliability == "偏差大":
            tail = "→ 这类判断历史常落空，发问时主动质疑、要我拿反证"
        else:
            tail = "→ 这类判断半对半错，发问时让我同时给正反两面"
        lines.append(
            f"- {st.category}：{st.n} 中 {st.hits} 命中"
            f"（命中率 {pct}%，{st.reliability}）{tail}"
        )
    return "\n".join(lines)


def render_report(cal: Calibration) -> str:
    """CLI 人读的校准报告。"""
    lines = ["# 二阶推演校准（哪类判断靠谱）"]
    lines.append(
        f"> 已回检 {cal.scored} 条 · 待回检 {cal.pending} 条 · "
        f"暂无法判定 {cal.unverifiable} 条 · 总命中率 {round(cal.overall_rate * 100)}%"
        + (
            f"\n> ⚠ 另有 {cal.hindsight_excluded} 条因**事后视角**被挡在校准之外"
            "（knowledge_cutoff 晚于 as_of，只可人工复核）"
            if cal.hindsight_excluded
            else ""
        )
    )
    if not cal.by_category:
        lines.append("")
        lines.append("（还没有已回检的判断。先 `checkpoint register` 登记可证伪点，到期 `checkpoint recheck`。）")
        return "\n".join(lines) + "\n"
    for st in cal.by_category:
        lines.append("")
        lines.append(
            f"## {st.category} · 命中率 {round(st.hit_rate * 100)}%（{st.reliability}）"
        )
        lines.append(f"- 样本 {st.n}：命中 {st.hits} / 半对 {st.partial} / 落空 {st.miss}")
        for s in st.samples:
            lines.append(f"- 例：{s}")
    if cal.by_source:
        lines.append("")
        lines.append("# 按产出模块（哪个模块在产真信号）")
        for st in cal.by_source:
            lines.append(
                f"- {st.category}：命中率 {round(st.hit_rate * 100)}%（{st.reliability}）"
                f"，样本 {st.n}：命中 {st.hits} / 半对 {st.partial} / 落空 {st.miss}"
            )
    if cal.by_object_type:
        lines.append("")
        lines.append("# 按对象类型（用户决策 / agent 判断 / 观察剧本，分开算不互相稀释）")
        for st in cal.by_object_type:
            lines.append(
                f"- {OBJECT_TYPE_CN.get(st.category, st.category)}："
                f"命中率 {round(st.hit_rate * 100)}%（{st.reliability}）"
                f"，样本 {st.n}：命中 {st.hits} / 半对 {st.partial} / 落空 {st.miss}"
            )
    return "\n".join(lines) + "\n"


def load_calibration(
    checkpoints_path: str | Path,
    verdicts_path: str | Path,
    *,
    today: str | None = None,
) -> tuple[Calibration, list[str]]:
    """从两个台账文件直接算出校准（给 foresight 注入与 CLI 复用）。"""
    warnings: list[str] = []
    cks, cwarn = load_checkpoints(checkpoints_path)
    if cwarn:
        warnings.append(cwarn)
    vds, vwarn = load_verdicts(verdicts_path)
    if vwarn:
        warnings.append(vwarn)
    return calibrate(cks, vds, today=today), warnings


# --------------------------------------------------------------------------- #
# 人类层回检日志 (Obsidian vault digest)：让夜间 recheck 不黑盒，可读可审
# --------------------------------------------------------------------------- #
# 复用潜意识沉淀 vault（同一本 Obsidian），回检日志放其下子目录，跟 judgments 双层落盘同理。
ENV_VAULT = "SUBCONSCIOUS_VAULT"
ENV_AGENT_MEMORY_VAULT = "AGENT_MEMORY_VAULT"
RECHECK_VAULT_SUBDIR = "可证伪点回检"
_VERDICT_CN = {"hit": "命中", "partial": "半对", "miss": "落空", "unverifiable": "暂无法判定"}


def resolve_recheck_vault(
    fallback_root: str | Path, *, explicit: str | None = None
) -> tuple[Path, bool]:
    """回检日志 vault 路径：显式 > env > ``~/agent-memory`` > 回退。

    返回 ``(vault_path, is_fallback)``；回退路径在 ``fallback_root/_vault``（已 gitignore），
    仍是真实可读的 md，只是不在你的 Obsidian 里。真实落地请指 ``--vault`` / ``SUBCONSCIOUS_VAULT``。
    """
    cand = explicit or os.environ.get(ENV_VAULT) or os.environ.get(ENV_AGENT_MEMORY_VAULT)
    if cand:
        return Path(str(cand)).expanduser(), False
    shared_memory = Path.home() / "agent-memory"
    if shared_memory.exists():
        return shared_memory, False
    return Path(fallback_root) / "_vault", True


def build_recheck_digest_section(
    results: list[dict[str, Any]], *, now: datetime | None = None, applied: bool = True
) -> str:
    """把一轮回检结果渲染成人类可读的 markdown 节：本轮命中率 + 逐条判定理由/证据。

    ``results`` 复用 CLI 的条目结构（id/claim/verdict/data_source/reason/observed，
    可带 category）。判定明细（终态/分数）以 ``verdicts.jsonl`` 为准，这里是人读快照。
    """
    now = now or _now()
    terminal = [r for r in results if str(r.get("verdict")) in TERMINAL_VERDICTS]
    hits = sum(1 for r in results if r.get("verdict") == "hit")
    partial = sum(1 for r in results if r.get("verdict") == "partial")
    miss = sum(1 for r in results if r.get("verdict") == "miss")
    unv = sum(1 for r in results if r.get("verdict") == "unverifiable")
    head = now.strftime("%H:%M") if hasattr(now, "strftime") else str(now)
    verb = "落盘" if applied else "预览"
    lines = [f"## {head} 回检 · {verb} {len(results)} 条"]
    if terminal:
        rate = round(hits / len(terminal) * 100)
        lines.append(
            f"> 本轮命中率 {rate}%（终态 {len(terminal)} 中 {hits} 命中）"
            f"｜命中 {hits} · 半对 {partial} · 落空 {miss} · 暂无法判定 {unv}"
        )
    else:
        lines.append(
            f"> 本轮无终态判定｜暂无法判定 {unv}（缺数据/未到，下次重跑再判，不计入胜率）"
        )
    lines.append("")
    for r in results:
        cn = _VERDICT_CN.get(str(r.get("verdict")), str(r.get("verdict")))
        cat = str(r.get("category") or "未分类").strip() or "未分类"
        claim = str(r.get("claim") or "").strip()
        lines.append(f"- **{cn}**｜{cat}｜{claim}")
        src = str(r.get("data_source") or "").strip()
        reason = str(r.get("reason") or "").strip()
        detail = f"{src}：{reason}" if (src and reason) else (reason or src)
        if detail:
            lines.append(f"  - {detail}")
        # 降级条目多写三行：试过什么、影响、下一步。只写"数据不可用"等于没写。
        deg = r.get("degradation") if isinstance(r.get("degradation"), dict) else None
        if deg:
            tried = deg.get("attempted") or []
            if tried:
                shown = "；".join(
                    f"{t.get('source')}→{t.get('status')}" for t in tried if isinstance(t, dict)
                )
                lines.append(f"  - 试过：{shown}")
            else:
                lines.append("  - 试过：未发起查询（规格不全/无机检规格）")
            owed = str(deg.get("owed_source") or "").strip()
            impact = str(deg.get("impact") or "").strip()
            if impact:
                lines.append(f"  - 影响：{impact}" + (f"（本该由 {owed} 判）" if owed else ""))
            todo = [str(t).strip() for t in (deg.get("todo") or []) if str(t).strip()]
            for t in todo:
                lines.append(f"  - 待补：{t}")
        rid = str(r.get("id") or "").strip()
        if rid:
            lines.append(f"  - `{rid}`")
    return "\n".join(lines)


def write_recheck_digest(vault_path: str | Path, section: str, *, date: str) -> Path:
    """把一轮回检 section 写进 vault 当日日志：首轮建文件带标题，同日多次回检按时间追加各占一节。"""
    note = Path(vault_path) / RECHECK_VAULT_SUBDIR / f"{date}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    if note.exists():
        with note.open("a", encoding="utf-8") as fh:
            fh.write("\n" + section + "\n")
    else:
        header = (
            f"# 可证伪点夜间回检 · {date}\n\n"
            "> 每晚到期点自动核对的人类可读快照；判定明细（终态/分数）以 "
            "`verdicts.jsonl` 为准。同日多次回检按运行时间各占一节。\n\n"
        )
        note.write_text(header + section + "\n", encoding="utf-8")
    return note
