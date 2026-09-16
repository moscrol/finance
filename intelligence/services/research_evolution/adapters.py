"""只读资源适配：受控证据目录、旧台账、02 来源记录。

06 的职责是**取数与授权**，业务判定全部交回 01/02/04（spec 06 §3「facade 只组装，不重写领域算法」）。
本模块提供两个端口与它们的生产实现：

- ``EvidenceSource``：给定实体与交易日，列出**受控**的证据版本目录与条件观测。
  生产实现 ``RiverEvidenceSource`` 走 ``river.slice_river`` + ``river_derive.bind``——
  引用只能从目录里选（spec §4.1「引用只能通过受控 id 解析，不能收任意绝对路径/URL 后直接读取」）。
- ``LegacyLedgers``：按 owner 的用户态路径加载旧读取器的原始 dict（``checkpoints`` / ``judgments`` /
  ``scenario_trees`` / ``observation_scripts`` / ``verdicts``），只读，不改一个字节。

「从现在开始跟踪」的语义在这里落地：绑定时把**当时解析到的真实版本**存进绑定记录，
view 时把它与**今天的版本**一起喂给 01 的 ``assess``。我们从不声称知道原判断当天的版本——
那正是 01 的 ``baseline_unknown`` gap 要挡住的东西。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import judgments as judgments_svc
from intelligence.services import research_queue as research_queue_svc
from intelligence.services import scenario_trees as scenario_trees_svc
from intelligence.services.research_evolution.contracts import (
    ERR_REF_UNRESOLVABLE,
    ApiError,
    gap,
)

# 01 只能编译这四个标签（``conditions.compile_binding_condition``）；UI 不该让用户选到别的。
SLICE_EVALUABLE_LABELS: tuple[str, ...] = ("dual_red_strict", "volume_surge", "market_stage", "limit_heat_rank")


# --------------------------------------------------------------------------- #
# 端口
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EvidenceCatalog:
    """一次取数的结果：可绑定的版本、可判的观测、以及为什么某些轨是空的。"""

    entity: str
    as_of: str
    knowledge_cutoff: str
    versions: tuple[dict[str, Any], ...] = ()
    observations: tuple[dict[str, Any], ...] = ()
    gaps: tuple[dict[str, Any], ...] = ()
    pit_grade: str = "unverifiable"
    available: bool = False
    reason: str | None = None

    def by_ref(self) -> dict[str, dict[str, Any]]:
        """每个引用取**截止前记录时刻最晚**的那一版。

        同一个 ref 在目录里可以有多版（原始值 + 后来的修订）。按插入顺序取最后一条是
        隐式依赖列表顺序——换个取数顺序，绑定基线就换成另一版，而且没有任何地方会报错。
        """
        out: dict[str, dict[str, Any]] = {}
        for version in self.versions:
            ref = str(version["ref"])
            current = out.get(ref)
            if current is None or str(version.get("recorded_at") or "") > str(current.get("recorded_at") or ""):
                out[ref] = dict(version)
        return out


class EvidenceSource(Protocol):
    """受控证据目录端口。实现必须只读，且不得接受任意路径 / URL。

    ``owner_user_id`` 是必填的：切片的判断轨会读该用户的 checkpoint 台账，
    取数时不带 owner 就会读到**部署默认用户**的台账（跨用户读取）。
    """

    def catalog(self, *, owner_user_id: str, entity: str, as_of: str, knowledge_cutoff: str) -> EvidenceCatalog: ...


@dataclass
class StaticEvidenceSource:
    """固定市场输入用：按 ``(entity, as_of)`` 给全量目录，再按 ``knowledge_cutoff`` 过滤。

    过滤这一步不是装饰：河的 ``_enforce_cutoff`` 就是这么做的（``recorded_at > C`` 或为 NULL 的对象
    进不了切片）。少了它，「今天才被记录的版本」会出现在历史 cutoff 的目录里，测试就会在一个
    比生产宽松的世界里通过。
    """

    catalogs: dict[tuple[str, str], EvidenceCatalog] = field(default_factory=dict)

    def catalog(self, *, owner_user_id: str, entity: str, as_of: str, knowledge_cutoff: str) -> EvidenceCatalog:
        found = self.catalogs.get((entity, as_of))
        if found is None:
            return EvidenceCatalog(
                entity=entity,
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
                available=False,
                reason="entity_unresolved",
                gaps=({"reason": "entity_unresolved", "ref": None, "checked_at": knowledge_cutoff, "retryable": True, "detail": f"{as_of} 无「{entity}」的切片"},),
            )
        versions = tuple(v for v in found.versions if _known_by(v.get("recorded_at"), knowledge_cutoff))
        observations = tuple(o for o in found.observations if _known_by(o.get("recorded_at"), knowledge_cutoff))
        return EvidenceCatalog(
            entity=found.entity,
            as_of=found.as_of,
            knowledge_cutoff=knowledge_cutoff,
            versions=versions,
            observations=observations,
            gaps=found.gaps,
            pit_grade=found.pit_grade,
            available=bool(versions),
            reason=found.reason if versions else "no_objects_before_cutoff",
        )


def _known_by(recorded_at: Any, knowledge_cutoff: str) -> bool:
    """``recorded_at`` 缺失一律判「不可知」——与河同口径：缺记录时刻不能当作当时已知。"""
    if not recorded_at:
        return False
    return str(recorded_at)[:10] <= str(knowledge_cutoff)[:10]


@dataclass
class RiverEvidenceSource:
    """生产实现：六轨切片 → ``EvidenceVersion`` 目录；四个可编译标签 → ``ConditionObservation``。

    ``db_path`` 由 06 在 create_app 处注入（不从 cwd 推断）。``river.slice_river`` 自己 fail closed：
    库不存在抛 ``FileNotFoundError``、实体解析不出返回全缺口切片，两种都如实转成 ``available=False``。
    """

    db_path: str | Path | None = None
    frozen_snapshot_root: str | Path | None = None

    def catalog(self, *, owner_user_id: str, entity: str, as_of: str, knowledge_cutoff: str) -> EvidenceCatalog:
        from intelligence import userspace
        from intelligence.services import river, river_derive

        # 判断轨读的是**该 owner** 的 checkpoint 台账；不显式给就会读部署默认用户的。
        checkpoints_path = userspace.user_space(owner_user_id).checkpoints_path
        # 06 的核心动作就是「以今天的 cutoff 重读绑定日的旧 as_of」——这在河的口径里是
        # 事后复核档（cutoff > as_of），必须显式 allow_hindsight，否则在读库前就被拒。
        # 这一档的切片 hindsight=True 且 pit_grade 永不为 strict；下面把 hindsight 如实
        # 映射成 unverifiable，绝不抬成 strict 冒充当时已知。
        hindsight_read = str(knowledge_cutoff)[:10] > str(as_of)[:10]
        try:
            sl = river.slice_river(
                as_of,
                entity,
                knowledge_cutoff=knowledge_cutoff,
                allow_hindsight=hindsight_read,
                db_path=self.db_path,
                checkpoints_path=checkpoints_path,
                frozen_snapshot_root=self.frozen_snapshot_root,
            )
        except FileNotFoundError:
            return EvidenceCatalog(
                entity=entity,
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
                available=False,
                reason="market_db_unavailable",
                gaps=({"reason": "market_db_unavailable", "ref": None, "checked_at": knowledge_cutoff, "retryable": True, "detail": "市场库当前不可用，读不到证据版本"},),
            )
        except ValueError as exc:
            return EvidenceCatalog(
                entity=entity,
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
                available=False,
                reason="invalid_slice_request",
                gaps=({"reason": "invalid_slice_request", "ref": None, "checked_at": knowledge_cutoff, "retryable": False, "detail": str(exc)},),
            )

        versions: list[dict[str, Any]] = []
        for obj in sl.objects:
            # 判断轨的对象是用户自己的台账行，不作为「外部依据」进目录（它们是被维护的对象本身）。
            if obj.track == "judgment":
                continue
            versions.append(
                {
                    "ref": obj.ref,
                    "source_hash": obj.source_hash,
                    "valid_from": obj.valid_from,
                    "valid_to": obj.valid_to,
                    "recorded_at": obj.recorded_at,
                    "derivation": obj.derivation or "deterministic",
                    "namespace": "market_feature_store",
                    # 目录展示用，不进 01 的 EvidenceVersion。
                    "_track": obj.track,
                    "_object_type": obj.object_type,
                    "_entity_id": obj.entity_id,
                }
            )

        observations: list[dict[str, Any]] = []
        for label in SLICE_EVALUABLE_LABELS:
            try:
                value, refs = river_derive.bind(label, sl)
            except river_derive.LabelNotSliceEvaluable:
                continue
            if value is None:
                continue
            observations.append(
                {
                    "label": label,
                    "entity_id": sl.entity_id,
                    "as_of": as_of,
                    "value": value,
                    # 观测的记录时刻取该标签实际读到的对象里最晚的一个；缺则 None（01 会据此判「还不知道」）。
                    "recorded_at": _latest_recorded_at(sl, refs),
                    "label_version": None,
                    "source_ref": refs[0] if refs else None,
                }
            )

        gaps = tuple(
            {
                "reason": f"track_{g.track}_{g.reason}",
                "ref": None,
                "checked_at": knowledge_cutoff,
                "retryable": True,
                "detail": g.detail,
            }
            for g in sl.gaps
        )
        entity_unresolved = all(str(g["reason"]).endswith("entity_unresolved") for g in gaps) if gaps else False
        return EvidenceCatalog(
            entity=entity,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
            versions=tuple(versions),
            observations=tuple(observations),
            gaps=gaps,
            pit_grade=sl.pit_grade if not sl.hindsight else "unverifiable",
            available=bool(versions) and not entity_unresolved,
            reason=None if versions else "no_objects_in_slice",
        )


def _latest_recorded_at(sl: Any, refs: Sequence[str]) -> str | None:
    stamps = [o.recorded_at for o in sl.objects if o.ref in set(refs) and o.recorded_at]
    return max(stamps) if stamps else None


# --------------------------------------------------------------------------- #
# 旧台账（只读）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LegacyLedgers:
    """一个 owner 的旧台账原始行。读不出来的文件如实留空 + 一条 gap，不抛。"""

    checkpoints: tuple[dict[str, Any], ...] = ()
    verdicts: tuple[dict[str, Any], ...] = ()
    judgments: tuple[dict[str, Any], ...] = ()
    trees: tuple[dict[str, Any], ...] = ()
    scripts: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    paths: dict[str, str] = field(default_factory=dict)


def load_legacy_ledgers(user_root: str | Path, *, judgment_window: int = 0) -> LegacyLedgers:
    """用现役读取器加载五本台账。``judgment_window=0`` = 全部（``load_judgments`` 的口径）。"""
    root = Path(user_root)
    checkpoints_path = root / "checkpoints.jsonl"
    verdicts_path = root / "verdicts.jsonl"
    judgments_path = root / "judgments.jsonl"
    trees_path = root / "scenario_trees.jsonl"
    scripts_path = root / "observation_scripts.jsonl"

    warnings: list[str] = []
    checkpoints, warn = checkpoints_svc.load_checkpoints(checkpoints_path)
    if warn:
        warnings.append(warn)
    verdicts, warn = checkpoints_svc.load_verdicts(verdicts_path)
    if warn:
        warnings.append(warn)
    judgments, warn = judgments_svc.load_judgments(judgments_path, judgment_window)
    if warn:
        warnings.append(warn)
    try:
        trees = scenario_trees_svc.load(trees_path)
    except (OSError, ValueError) as exc:
        trees, _ = [], warnings.append(f"情景树台账读取失败：{exc}")
    try:
        scripts = _load_jsonl(scripts_path)
    except (OSError, ValueError) as exc:
        scripts, _ = [], warnings.append(f"观察剧本台账读取失败：{exc}")

    return LegacyLedgers(
        checkpoints=tuple(checkpoints),
        verdicts=tuple(verdicts),
        judgments=tuple(judgments),
        trees=tuple(trees),
        scripts=tuple(scripts),
        warnings=tuple(warnings),
        paths={
            "checkpoints": str(checkpoints_path),
            "verdicts": str(verdicts_path),
            "judgments": str(judgments_path),
            "scenario_trees": str(trees_path),
            "observation_scripts": str(scripts_path),
        },
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    import json

    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
    return out


# --------------------------------------------------------------------------- #
# 可跟踪对象（spec §4.1「原记录没有完整依据，尚不能比较变化」+「从现在开始跟踪」）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TrackableObject:
    """面板里一条「可以开始跟踪」的旧对象。``bound`` 为真表示已有绑定。"""

    object_ref: dict[str, Any]
    kind: str
    title: str
    recorded_at: str | None
    bound: bool
    binding_id: str | None
    gaps: tuple[dict[str, Any], ...]
    candidate_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_ref": dict(self.object_ref),
            "kind": self.kind,
            "title": self.title,
            "recorded_at": self.recorded_at,
            "bound": self.bound,
            "binding_id": self.binding_id,
            "gaps": [dict(g) for g in self.gaps],
            "candidate_refs": list(self.candidate_refs),
        }


def trackable_objects(
    ledgers: LegacyLedgers,
    *,
    owner_user_id: str,
    baseline_cutoff: str,
    bound_refs: Mapping[str, str],
    conversation_id: str | None = None,
    limit: int = 40,
) -> list[TrackableObject]:
    """旧 checkpoint / judgment / 情景树 → 可跟踪对象清单（用 01 的适配器造 ObjectRef 与 gap）。

    ``bound_refs``：``object_ref.ref`` → ``binding_id``（已建立绑定的对象）。
    ``conversation_id`` 给了就只保留该会话范围的对象（``session_id`` 相符），否则给全量最近若干条。
    """
    from intelligence.services.judgment_maintenance import adapters as jm_adapters

    out: list[TrackableObject] = []
    scope = {"conversation_id": conversation_id} if conversation_id else None

    def _in_scope(record: Mapping[str, Any]) -> bool:
        if conversation_id is None:
            return True
        return str(record.get("session_id") or "") == conversation_id

    for record in ledgers.checkpoints:
        if not _in_scope(record):
            continue
        ref = jm_adapters.object_ref_from_checkpoint(record, owner_user_id=owner_user_id, scope=scope)
        _, gaps = jm_adapters.candidate_binding_from_checkpoint(record, owner_user_id=owner_user_id, baseline_cutoff=baseline_cutoff, scope=scope)
        out.append(
            TrackableObject(
                object_ref=ref.to_dict(),
                kind="checkpoint",
                title=str(record.get("claim") or ""),
                recorded_at=_opt(record.get("ts")),
                bound=ref.ref in bound_refs,
                binding_id=bound_refs.get(ref.ref),
                gaps=tuple(g.to_dict() for g in gaps),
            )
        )

    for record in ledgers.judgments:
        if not _in_scope(record):
            continue
        ref = jm_adapters.object_ref_from_judgment(record, owner_user_id=owner_user_id, scope=scope)
        candidate, gaps = jm_adapters.candidate_binding_from_judgment(
            record,
            owner_user_id=owner_user_id,
            binding_id="draft",
            created_at=_opt(record.get("ts")) or f"{baseline_cutoff}T00:00:00+00:00",
            baseline_cutoff=baseline_cutoff,
            scope=scope,
        )
        out.append(
            TrackableObject(
                object_ref=ref.to_dict(),
                kind="judgment",
                title=str(record.get("memo") or ""),
                recorded_at=_opt(record.get("ts")),
                bound=ref.ref in bound_refs,
                binding_id=bound_refs.get(ref.ref),
                gaps=tuple(g.to_dict() for g in gaps),
                candidate_refs=tuple(candidate.baseline_evidence_refs) if candidate else (),
            )
        )

    tree_ids = {str(r.get("id")) for r in ledgers.trees if r.get("record") == "tree" and r.get("id")}
    for tree_id in sorted(tree_ids):
        state = scenario_trees_svc.current_state(list(ledgers.trees), tree_id)
        if state is None or not _in_scope(state):
            continue
        ref = jm_adapters.object_ref_from_scenario_tree(state, owner_user_id=owner_user_id, scope=scope)
        candidate, gaps = jm_adapters.candidate_binding_from_scenario_tree(
            state,
            owner_user_id=owner_user_id,
            binding_id="draft",
            created_at=_opt(state.get("recorded_at")) or f"{baseline_cutoff}T00:00:00+00:00",
            baseline_cutoff=baseline_cutoff,
        )
        out.append(
            TrackableObject(
                object_ref=ref.to_dict(),
                kind="scenario_tree",
                title=str(state.get("question") or state.get("title") or tree_id),
                recorded_at=_opt(state.get("recorded_at")),
                bound=ref.ref in bound_refs,
                binding_id=bound_refs.get(ref.ref),
                gaps=tuple(g.to_dict() for g in gaps),
                candidate_refs=tuple(candidate.baseline_evidence_refs) if candidate else (),
            )
        )

    out.sort(key=lambda t: (t.recorded_at or "", t.object_ref.get("ref") or ""), reverse=True)
    return out[:limit]


def _opt(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def find_trackable(objects: Sequence[TrackableObject], object_ref: Mapping[str, Any]) -> TrackableObject:
    """按 ``ref`` 在受控清单里定位对象；找不到 → ``ref_unresolvable``（不接受任意 ref）。"""
    wanted = str(object_ref.get("ref") or "").strip()
    for item in objects:
        if str(item.object_ref.get("ref")) == wanted:
            return item
    raise ApiError(ERR_REF_UNRESOLVABLE, "该对象不在可跟踪清单中", detail={"ref": wanted})


# --------------------------------------------------------------------------- #
# 02 来源记录
# --------------------------------------------------------------------------- #
def priority_source_records(
    *,
    maintenance_report: Mapping[str, Any] | None,
    project_state: Mapping[str, Any] | None,
    research_queue: Mapping[str, Any] | None,
    data_requests: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """把 06 读到的来源对象包成 02 的 ``source_records``（``{"kind", "payload"}``）。"""
    records: list[dict[str, Any]] = []
    if maintenance_report is not None:
        records.append({"kind": "maintenance_report", "payload": dict(maintenance_report)})
    if project_state is not None:
        records.append({"kind": "research_project", "payload": dict(project_state)})
    if research_queue:
        queue = research_queue_svc.extract_queue(dict(research_queue))
        if queue:
            records.append({"kind": "research_queue", "payload": queue})
    for request in data_requests:
        records.append({"kind": "data_request", "payload": dict(request)})
    return records


def load_research_queue_for(finance_root: str | Path | None, *, as_of: str | None) -> tuple[str | None, dict[str, Any]]:
    """按 ≤ as_of 找最新一份日更研究队列。找不到返回 ``(None, {})``——缺队列是如实状态，不是错误。"""
    if not finance_root:
        return None, {}
    exports = Path(finance_root) / "复盘" / "exports"
    if not exports.is_dir():
        return None, {}
    try:
        path, payload = research_queue_svc.load_research_queue(exports, as_of=as_of)
    except (OSError, ValueError):
        return None, {}
    return (str(path) if path else None), payload


__all__ = [
    "SLICE_EVALUABLE_LABELS",
    "EvidenceCatalog",
    "EvidenceSource",
    "LegacyLedgers",
    "RiverEvidenceSource",
    "StaticEvidenceSource",
    "TrackableObject",
    "find_trackable",
    "gap",
    "load_legacy_ledgers",
    "load_research_queue_for",
    "priority_source_records",
    "trackable_objects",
]
