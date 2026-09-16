"""旧台账 → 04 输入（只读适配器）。规格 §2、§7 第 0 步「旧读取器产生临时输入」。

四本 append-only 台账（``checkpoints.jsonl`` / ``verdicts.jsonl`` / ``judgments.jsonl`` /
``observation_scripts.jsonl`` / ``scenario_trees.jsonl``）都没有版本链、曝光日志和覆盖声明，所以适配出的
输入天然带缺口：迟登多半 ``deadline_missing``，到期回检一律 ``coverage_unknown``（除非 06 另给 coverage
收据）。这是**诚实的存量状态**，不是适配器偷懒——补字段的责任在 06 的绑定流程。

作者映射（``actor.author``）只看记录里**写下的字段**，不猜：

| 台账 | 依据 | author / agent_refs |
|---|---|---|
| checkpoint ``object_type_of`` = judgment | 用户判断 | user；``source=foresight_judgment`` 时是 agent 提议后 accept → agent_refs 记 source |
| checkpoint = agent_judgment / scenario_tree / method_observation | agent 产物 | agent |
| checkpoint = observation_script | 系统起草、用户确认 | user + agent_refs（``user_authored`` 的无 agent_refs）|
| checkpoint = unknown_legacy | 存量未标类型 | unknown |
| judgments 行 ``record_type=foresight_judgment`` | agent 提议后 accept | user + agent_refs |
| judgments 行带 ``promotion`` | 门禁晋升的经验，作者未记 | unknown |
| judgments 普通行 | 用户 memo | user |
| observation_scripts 行 | 系统起草、用户确认；``user_authored`` 除外 | user (+ agent_refs) |
| scenario_trees 行 | 带 model_id / projection_hash 的 agent 产物 | agent |

时间：checkpoint ``ts`` 与 verdict ``checked_at`` 是带时区 ISO 秒；剧本 / 树的 ``recorded_at`` 带 +08:00。
只有日期或无时区的按 ``date`` 粒度处理（不猜时区）。

回检责任：checkpoint 无 ``metric`` 或 ``metric.type=manual`` → user；其他机检类 → system。

本模块用现有读取器，不写任何文件；路径由调用方显式传入，不从 cwd / 环境推断用户根。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import judgments as judgments_svc
from intelligence.services import observation_script as script_svc
from intelligence.services import scenario_trees as trees_svc
from intelligence.services.research_diagnostics.clock import classify_time, instant_lt
from intelligence.services.research_diagnostics.contracts import (
    ActorInfo,
    Gap,
    ObjectRef,
    ProcessRecord,
    TimePoint,
    VerdictRecord,
    content_hash,
)

NS_CHECKPOINTS = "checkpoints.jsonl"
NS_VERDICTS = "verdicts.jsonl"
NS_JUDGMENTS = "judgments.jsonl"
NS_SCRIPTS = "observation_scripts.jsonl"
NS_TREES = "scenario_trees.jsonl"
DEADLINE_RULE_REF = "observation_script.default_next_open"

_AGENT_OBJECT_TYPES = ("agent_judgment", "scenario_tree", "method_observation")


@dataclass
class LegacyInputs:
    records: list[ProcessRecord] = field(default_factory=list)
    verdicts: list[VerdictRecord] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": [r.to_dict() for r in self.records],
            "verdicts": [v.to_dict() for v in self.verdicts],
            "gaps": [g.to_dict() for g in self.gaps],
        }


def _pit(recorded: TimePoint, event_time: TimePoint | None = None) -> str:
    """记录的 PIT 档位：带时区时刻 → strict；只到日 → trade_date_only；无登记时刻但市场日已知 → trade_date_only
    （09-06 终局 spec §4.1：历史对象缺 ``recorded_at`` 整片标 trade_date_only，与 strict 分开统计）；两者都没有 → unverifiable。"""
    if recorded.granularity == "datetime":
        return "strict"
    if recorded.granularity == "date" or (event_time is not None and event_time.granularity != "unknown"):
        return "trade_date_only"
    return "unverifiable"


def _row_hash(row: dict[str, Any]) -> str:
    return "content_sha256:" + content_hash(row)[:16]


_SYSTEM_RESOLVED_OBJECT_TYPES = ("observation_script", "scenario_tree", "method_observation")


def _responsibility(metric: Any, object_type: str) -> str:
    """回检责任：剧本 / 树 / 方法观察由系统钩子逐日解析；其余看机检规格，人工判定归用户。"""
    if object_type in _SYSTEM_RESOLVED_OBJECT_TYPES:
        return "system"
    if not metric:
        return "user"
    mtype = str((metric or {}).get("type") or "")
    return "user" if mtype == "manual" else "system"


def checkpoint_to_record(row: dict[str, Any], *, owner_user_id: str, derived_ids: dict[str, str] | None = None) -> ProcessRecord:
    """一行 checkpoint → ProcessRecord。``derived_ids`` 是 checkpoint_id → 原对象身份（剧本 / 树）的映射。"""
    otype = checkpoints_svc.object_type_of(row)
    source = str(row.get("source") or "")
    evidence = [f"object_type={otype}"]
    if source:
        evidence.append(f"source={source}")
    agent_refs: list[str] = []
    if otype in _AGENT_OBJECT_TYPES:
        author = "agent"
    elif otype == "observation_script":
        author = "user"
        if row.get("projection_hash_missing") != checkpoints_svc.USER_AUTHORED:
            agent_refs.append(f"observation_script:drafted:{row.get('projection_hash') or 'projection_unknown'}")
    elif otype == "judgment":
        author = "user"
        if source == "foresight_judgment":
            agent_refs.append(f"foresight_judgment:{row.get('source_judgment_ts') or row.get('id')}")
    else:
        author = "unknown"
    cid = str(row.get("id"))
    derived = derived_ids.get(cid) if derived_ids else None
    recorded = classify_time(str(row.get("ts") or ""))
    return ProcessRecord(
        record_id=f"ck:{cid}",
        owner_user_id=owner_user_id,
        object_ref=ObjectRef(kind="checkpoint", namespace=NS_CHECKPOINTS, id=cid, version_or_hash=_row_hash(row)),
        object_kind="checkpoint",
        actor=ActorInfo(author=author, agent_refs=agent_refs, evidence=evidence),
        recorded_at=recorded,
        event_time=TimePoint.unknown(),
        knowledge_cutoff=None,
        declared_deadline=None,
        deadline_rule_ref=None,
        due=str(row.get("due") or "") or None,
        hindsight=bool(row.get("hindsight")),
        review_responsibility=_responsibility(row.get("metric"), otype),
        version_chain_complete=None,
        pit_grade=_pit(recorded),
        derived_from=derived,
        source_refs=(f"{NS_CHECKPOINTS}#{cid}",),
    )


def verdict_to_record(row: dict[str, Any], *, owner_user_id: str) -> VerdictRecord:
    deg = row.get("degradation") if isinstance(row.get("degradation"), dict) else None
    reason = None
    if deg:
        reason = str(deg.get("impact") or deg.get("owed_source") or "degraded")
    elif row.get("verdict") == "unverifiable":
        reason = str(row.get("reason") or "unverifiable")
    cid = str(row.get("id"))
    return VerdictRecord(
        verdict_id=f"vd:{cid}:{content_hash(row)[:12]}",
        owner_user_id=owner_user_id,
        object_ref=ObjectRef(kind="checkpoint", namespace=NS_CHECKPOINTS, id=cid),
        verdict=str(row.get("verdict")),
        checked_at=str(row.get("checked_at") or "") or None,
        data_source=str(row.get("data_source") or "") or None,
        auto=bool(row.get("auto")),
        degradation_reason=reason,
        source_refs=(f"{NS_VERDICTS}#{cid}",),
    )


def judgment_to_record(row: dict[str, Any], *, owner_user_id: str) -> ProcessRecord:
    rid = str(row.get("id") or row.get("ts"))
    evidence = []
    agent_refs: list[str] = []
    if row.get("record_type") == "foresight_judgment":
        author = "user"
        agent_refs.append(f"foresight_judgment:{rid}")
        evidence.append("record_type=foresight_judgment")
    elif row.get("promotion"):
        author = "unknown"
        evidence.append("promotion=present（晋升经验，作者未记）")
    else:
        author = "user"
        evidence.append("memo（用户核心判断）")
    recorded = classify_time(str(row.get("ts") or ""))
    return ProcessRecord(
        record_id=f"jd:{rid}",
        owner_user_id=owner_user_id,
        object_ref=ObjectRef(kind="judgment", namespace=NS_JUDGMENTS, id=rid, version_or_hash=_row_hash(row)),
        object_kind="judgment",
        actor=ActorInfo(author=author, agent_refs=agent_refs, evidence=evidence),
        recorded_at=recorded,
        event_time=TimePoint.unknown(),
        version_chain_complete=None,
        pit_grade=_pit(recorded),
        source_refs=(f"{NS_JUDGMENTS}#{rid}",),
    )


def script_to_record(
    row: dict[str, Any],
    *,
    owner_user_id: str,
    next_open_fn: Callable[[str], Any] | None = None,
) -> tuple[ProcessRecord, list[Gap]]:
    """剧本行：登记截止按 ``next_open_fn(as_of)``（默认 ``observation_script.default_next_open``）。

    台账里写入者当时算出的 ``late`` 旗标保留在 source_refs；与重算不一致记 gap，不悄悄二选一。
    """
    gaps: list[Gap] = []
    sid = str(row.get("id"))
    as_of = str(row.get("as_of") or "")
    deadline = None
    if as_of:
        try:
            deadline = (next_open_fn or script_svc.default_next_open)(as_of).isoformat()
        except (ValueError, TypeError):
            gaps.append(Gap("deadline_uncomputable", f"{NS_SCRIPTS}#{sid}", detail=f"as_of={as_of!r} 算不出次日开盘"))
    recorded = classify_time(str(row.get("recorded_at") or ""))
    user_authored = row.get("projection_hash_missing") == checkpoints_svc.USER_AUTHORED
    agent_refs = [] if user_authored else [f"observation_script:drafted:{row.get('projection_hash') or 'projection_unknown'}"]
    late_flag = row.get("late")
    if deadline is not None and recorded.granularity == "datetime" and isinstance(late_flag, bool):
        recomputed = instant_lt(deadline, recorded.value)
        if recomputed is not None and recomputed != late_flag:
            gaps.append(Gap("late_flag_disagrees", f"{NS_SCRIPTS}#{sid}", retryable=False, detail=f"台账 late={late_flag}，重算={recomputed}"))
    event_time = classify_time(as_of)
    rec = ProcessRecord(
        record_id=f"os:{sid}",
        owner_user_id=owner_user_id,
        object_ref=ObjectRef(kind="observation_script", namespace=NS_SCRIPTS, id=sid, version_or_hash=_row_hash(row)),
        object_kind="observation_script",
        actor=ActorInfo(
            author="user",
            agent_refs=agent_refs,
            evidence=[f"status={row.get('status')}", "user_authored" if user_authored else "system_drafted"],
        ),
        recorded_at=recorded,
        event_time=event_time,
        knowledge_cutoff=str(row.get("knowledge_cutoff") or "") or None,
        declared_deadline=deadline,
        deadline_rule_ref=DEADLINE_RULE_REF if deadline else None,
        # 回检机会在它登记出的 checkpoint 行上（derived_from 指回这里）；没登记 checkpoint 的剧本
        # （late / drafted / skipped）从未进回检队列，也就没有到期机会。台账里的 due 只是信息。
        due=None,
        hindsight=bool(row.get("hindsight")),
        review_responsibility="system",
        version_chain_complete=None,
        pit_grade=_pit(recorded, event_time),
        source_refs=(f"{NS_SCRIPTS}#{sid}", f"late={late_flag}", f"ledger_due={row.get('due')}"),
    )
    return rec, gaps


def tree_to_record(row: dict[str, Any], *, owner_user_id: str) -> ProcessRecord:
    tid = str(row.get("id"))
    recorded = classify_time(str(row.get("recorded_at") or ""))
    event_time = classify_time(str(row.get("as_of") or ""))
    return ProcessRecord(
        record_id=f"st:{tid}",
        owner_user_id=owner_user_id,
        object_ref=ObjectRef(kind="scenario_tree", namespace=NS_TREES, id=tid, version_or_hash=_row_hash(row)),
        object_kind="scenario_tree",
        actor=ActorInfo(author="agent", evidence=[f"model_id={row.get('model_id')}", f"projection_hash={row.get('projection_hash')}"]),
        recorded_at=recorded,
        event_time=event_time,
        knowledge_cutoff=str(row.get("knowledge_cutoff") or "") or None,
        declared_deadline=None,
        review_responsibility="system",
        version_chain_complete=None,
        pit_grade=_pit(recorded, event_time),
        source_refs=(f"{NS_TREES}#{tid}",),
    )


def records_from_legacy(
    *,
    owner_user_id: str,
    checkpoints: Iterable[dict[str, Any]] = (),
    verdicts: Iterable[dict[str, Any]] = (),
    judgments: Iterable[dict[str, Any]] = (),
    scripts: Iterable[dict[str, Any]] = (),
    trees: Iterable[dict[str, Any]] = (),
    next_open_fn: Callable[[str], Any] | None = None,
) -> LegacyInputs:
    """已加载的台账行 → 04 输入。剧本登记出的 checkpoint 行标 ``derived_from`` 指回剧本。"""
    out = LegacyInputs()
    script_rows = list(scripts)
    tree_rows = [t for t in trees if t.get("record") == "tree"]
    derived_ids: dict[str, str] = {}
    for s in script_rows:
        if s.get("checkpoint_id"):
            derived_ids[str(s["checkpoint_id"])] = f"observation_script|{NS_SCRIPTS}|{s.get('id')}"
    for t in tree_rows:
        if t.get("checkpoint_id"):
            derived_ids[str(t["checkpoint_id"])] = f"scenario_tree|{NS_TREES}|{t.get('id')}"
    for s in script_rows:
        rec, gaps = script_to_record(s, owner_user_id=owner_user_id, next_open_fn=next_open_fn)
        out.records.append(rec)
        out.gaps.extend(gaps)
    for t in tree_rows:
        out.records.append(tree_to_record(t, owner_user_id=owner_user_id))
    for c in checkpoints:
        out.records.append(checkpoint_to_record(c, owner_user_id=owner_user_id, derived_ids=derived_ids))
    for j in judgments:
        out.records.append(judgment_to_record(j, owner_user_id=owner_user_id))
    for v in verdicts:
        out.verdicts.append(verdict_to_record(v, owner_user_id=owner_user_id))
    out.gaps.append(Gap("legacy_no_coverage_declaration", None, detail="存量台账无完整性声明；到期回检只能 unknown，除非 06 另给 coverage 收据"))
    out.gaps.append(Gap("legacy_no_version_chain", None, detail="存量台账无版本链与曝光日志；条件修改 / 过期沿用需 06 绑定后才可判"))
    return out


def load_legacy_inputs(
    *,
    owner_user_id: str,
    checkpoints_path: str | Path,
    verdicts_path: str | Path,
    judgments_path: str | Path | None = None,
    scripts_path: str | Path | None = None,
    trees_path: str | Path | None = None,
    next_open_fn: Callable[[str], Any] | None = None,
) -> LegacyInputs:
    """用现有读取器读显式路径。不解析用户根、不写文件。"""
    cks, cwarn = checkpoints_svc.load_checkpoints(checkpoints_path)
    vds, vwarn = checkpoints_svc.load_verdicts(verdicts_path)
    jds: list[dict[str, Any]] = []
    jwarn = None
    if judgments_path is not None:
        jds, jwarn = judgments_svc.load_judgments(judgments_path, window=0)
    scripts = script_svc.load(scripts_path) if scripts_path is not None else []
    trees = trees_svc.load(trees_path) if trees_path is not None else []
    out = records_from_legacy(
        owner_user_id=owner_user_id,
        checkpoints=cks,
        verdicts=vds,
        judgments=jds,
        scripts=scripts,
        trees=trees,
        next_open_fn=next_open_fn,
    )
    for warn, ns in ((cwarn, NS_CHECKPOINTS), (vwarn, NS_VERDICTS), (jwarn, NS_JUDGMENTS)):
        if warn:
            out.gaps.append(Gap("ledger_read_warning", ns, detail=warn))
    return out
