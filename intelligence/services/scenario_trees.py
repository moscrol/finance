"""情景树 v0（工单 #37 / roadmap G-15；契约正文 09-06 统一 spec §3.3）。

观察剧本只推一步（T+1 看什么）。**情景树**把它接成多步：每个节点是一条观察剧本，节点之间的边是
**六轨注册标签上的确定性条件**——「明天缩量且题材阶段不推进，走分枝 A；放量且涨停热度排名跃迁，走
分枝 B；其余走 otherwise」。世界每过一个交易日，河的切片自动判定走了哪条边，树长出一条 ``realized_path``。

它回答的是「按这个框架，接下来几步各自该看什么、什么条件算升级 / 降级 / 放弃」，**不回答涨跌、时点、
目标价**——与观察剧本同一道硬门、同一个 ``scope``。用户口语里的「推演」在产品语言里就是它。

三条硬门（§3.3，在观察剧本的门之上）：

1. 每条 ``condition`` 只能引用注册标签，且 v0 只收**单日切片可判**的那些
   （``river_derive.SLICE_EVALUABLE_LABELS``）；编译不过的条件整棵树拒绝登记。
2. 节点与边上不得出现概率数字、百分比、方向词、时点词、个股；``analog_ref`` v0 必须为空（等 #35 区间派生）。
3. ``realized_path`` 只能由 ``river.slice(T+k, knowledge_cutoff=T+k)`` 的对象写入；任一步所需标签为 gap →
   该步 ``unresolvable``，树停在那里，不猜、不跳、不用别的轨补。

同一父节点的子条件必须**互斥且穷尽**：机械判法是在每个标签的取值域上枚举（bool 两值、text 提到的值 ∪ 其它、
num 取 1..``NUM_DOMAIN_MAX`` 的整数），任意两个兄弟能同真即拒绝；恰有一个 ``otherwise`` 兜底。
没有 ``otherwise``，世界不落进任何分枝时树就没话说；不互斥，两个分枝同真时「走了哪条」需要一个隐藏的优先级。

回检不按「走了哪条枝」判对错——那是世界的选择，不是框架的对错。回检三件事：(a) 覆盖：世界落进声明过的
分枝还是 ``otherwise``（占比高说明框架对这个环境没有语言）；(b) 沿路剧本：到达节点的观察剧本变量是否按条件
触发（与 G-03 同口径，走 checkpoints）；(c) 规则样本：每条被走过的 ``(condition → 下一步切片事实)`` 存在
step 记录里，供 §5.4 飞轮（G-16 提议器）消费——v0 只存不提议。

⚠ 与 ``intelligence/services/scenario_tree.py``（问答路由的 ``ScenarioTreeArtifact``）同名不同物：那个是回答
里的「推演契约」产物，本模块是判断轨上的可回检对象。模块名用复数以示区别，旧模块一行不动。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import compliance_gate, observation_script, river_projection
from intelligence.services.methodology_backtest.rules import LABEL_KINDS, OPS_BY_KIND
from intelligence.services.river_derive import SLICE_EVALUABLE_LABELS, LabelNotSliceEvaluable, bind

OBJECT_TYPE = "scenario_tree"
STATUSES = ("drafted", "confirmed", "resolving", "resolved", "unresolvable", "expired")
STEP_KINDS = ("T+1", "T+3", "T+5")
STEP_DAYS = {"T+1": 1, "T+3": 3, "T+5": 5}
MAX_DEPTH_V0 = 3
OTHERWISE = "otherwise"
NUM_DOMAIN_MAX = 200  # limit_heat_rank 之类计数 / 名次标签的枚举上界；够覆盖 400 个板块的名次不需要——名次 > 200 与 > 199 对分枝没有区别
CN_TZ = timezone(timedelta(hours=8))
PROJECTION_TASK = "scenario_tree"

# 错误码（在 observation_script / compliance_gate 之上）
E_DEPTH = "E_DEPTH"
E_NO_OTHERWISE = "E_NO_OTHERWISE"
E_MULTIPLE_OTHERWISE = "E_MULTIPLE_OTHERWISE"
E_SIBLINGS_OVERLAP = "E_SIBLINGS_OVERLAP"
E_LABEL_NOT_SLICE_EVALUABLE = "E_LABEL_NOT_SLICE_EVALUABLE"
E_CONDITION_INVALID = "E_CONDITION_INVALID"
E_ANALOG_REF_NOT_AVAILABLE = "E_ANALOG_REF_NOT_AVAILABLE"
E_NODE_SCRIPT = "E_NODE_SCRIPT"
E_STRUCTURE = "E_STRUCTURE"
E_MISSING_ATTRIBUTION = "E_MISSING_ATTRIBUTION"
E_TEXT = "E_TEXT"


@dataclass(frozen=True)
class Rejection:
    code: str
    where: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "where": self.where, "detail": self.detail}


class ScenarioTreeRejected(ValueError):
    def __init__(self, rejections: list[Rejection]) -> None:
        self.rejections = rejections
        super().__init__("; ".join(f"{r.code}@{r.where}: {r.detail}" for r in rejections))


# --------------------------------------------------------------------------- #
# 对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Predicate:
    label: str
    op: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "op": self.op, "value": list(self.value) if isinstance(self.value, tuple) else self.value}


@dataclass(frozen=True)
class Node:
    node_id: str
    depth: int
    parent: str | None
    condition: tuple[Predicate, ...] | str | None  # 谓词合取 | "otherwise" | None（根）
    step_kind: str | None
    script: observation_script.ObservationScript
    analog_ref: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.condition is None or isinstance(self.condition, str):
            cond: Any = self.condition
        else:
            cond = {"all": [p.to_dict() for p in self.condition]}
        return {
            "node_id": self.node_id,
            "depth": self.depth,
            "parent": self.parent,
            "condition": cond,
            "step_kind": self.step_kind,
            "script": self.script.to_dict(),
            "analog_ref": self.analog_ref,
        }


@dataclass(frozen=True)
class ScenarioTree:
    as_of: str
    knowledge_cutoff: str
    scope: str
    entity_ids: tuple[str, ...]
    max_depth: int
    nodes: tuple[Node, ...]
    projection_hash: str | None
    framework_version: str | None
    model_id: str | None
    user_id: str = "default"
    visibility: str = "private"
    status: str = "drafted"
    recorded_at: str | None = None
    id: str | None = None

    @property
    def root(self) -> Node:
        return next(n for n in self.nodes if n.parent is None)

    def children(self, node_id: str) -> list[Node]:
        return [n for n in self.nodes if n.parent == node_id]

    def node(self, node_id: str) -> Node:
        return next(n for n in self.nodes if n.node_id == node_id)

    @property
    def text_fields(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for n in self.nodes:
            for name, values in n.script.text_fields.items():
                for v in values:
                    out.append((f"{n.node_id}.{name}", v))
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "object_type": OBJECT_TYPE,
            "as_of": self.as_of,
            "knowledge_cutoff": self.knowledge_cutoff,
            "scope": self.scope,
            "entity_ids": list(self.entity_ids),
            "max_depth": self.max_depth,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [{"parent": n.parent, "child": n.node_id} for n in self.nodes if n.parent is not None],
            "projection_hash": self.projection_hash,
            "framework_version": self.framework_version,
            "model_id": self.model_id,
            "user_id": self.user_id,
            "visibility": self.visibility,
            "status": self.status,
            "recorded_at": self.recorded_at,
        }


# --------------------------------------------------------------------------- #
# 条件编译
# --------------------------------------------------------------------------- #
def compile_condition(raw: Any, *, where: str) -> tuple[tuple[Predicate, ...] | str | None, list[Rejection]]:
    """``{"all": [{"label","op","value"}...]}`` | ``"otherwise"`` | None → 谓词合取。只收单日切片可判的注册标签。"""
    if raw is None:
        return None, []
    if isinstance(raw, str):
        if raw.strip() == OTHERWISE:
            return OTHERWISE, []
        return None, [Rejection(E_CONDITION_INVALID, where, f"条件字符串只能是 {OTHERWISE!r}，收到 {raw!r}")]
    if not isinstance(raw, dict) or not isinstance(raw.get("all"), list) or not raw["all"]:
        return None, [Rejection(E_CONDITION_INVALID, where, "条件形状是 {\"all\": [谓词...]}（v0 只支持 AND；OR 用两个兄弟节点表达）")]
    if set(raw) - {"all"}:
        return None, [Rejection(E_CONDITION_INVALID, where, f"条件只认 all，多余键 {sorted(set(raw) - {'all'})}")]
    preds: list[Predicate] = []
    errs: list[Rejection] = []
    for i, p in enumerate(raw["all"]):
        w = f"{where}.all[{i}]"
        if not isinstance(p, dict):
            errs.append(Rejection(E_CONDITION_INVALID, w, "谓词必须是对象"))
            continue
        label, op, value = p.get("label"), p.get("op"), p.get("value")
        if label not in LABEL_KINDS:
            errs.append(Rejection(E_CONDITION_INVALID, w, f"label {label!r} 不是注册标签（ALL_LABELS）"))
            continue
        if label not in SLICE_EVALUABLE_LABELS:
            errs.append(Rejection(E_LABEL_NOT_SLICE_EVALUABLE, w, f"label {label!r} 需要历史或个股级原料，单日切片判不了；v0 拒绝（等 #35 派生对象）"))
            continue
        _entity, kind = LABEL_KINDS[label]
        if op not in OPS_BY_KIND[kind]:
            errs.append(Rejection(E_CONDITION_INVALID, w, f"op {op!r} 对 {kind} 标签不合法（允许 {OPS_BY_KIND[kind]}）"))
            continue
        if op in ("in", "not_in"):
            if not isinstance(value, (list, tuple)) or not value:
                errs.append(Rejection(E_CONDITION_INVALID, w, f"{op} 的 value 要非空列表"))
                continue
            value = tuple(value)
        elif kind == "bool" and not isinstance(value, bool):
            errs.append(Rejection(E_CONDITION_INVALID, w, "bool 标签的 value 必须是 true / false"))
            continue
        elif kind == "num" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            errs.append(Rejection(E_CONDITION_INVALID, w, "num 标签的 value 必须是数字"))
            continue
        elif kind == "text" and not isinstance(value, str):
            errs.append(Rejection(E_CONDITION_INVALID, w, "text 标签的 value 必须是字符串"))
            continue
        preds.append(Predicate(str(label), str(op), value))
    if errs:
        return None, errs
    return tuple(preds), []


def _domain(label: str, siblings: list[tuple[Predicate, ...]]) -> list[Any]:
    kind = LABEL_KINDS[label][1]
    if kind == "bool":
        return [True, False]
    if kind == "num":
        return list(range(0, NUM_DOMAIN_MAX + 1))
    mentioned: set[str] = set()
    for conj in siblings:
        for p in conj:
            if p.label == label:
                if isinstance(p.value, tuple):
                    mentioned |= {str(v) for v in p.value}
                else:
                    mentioned.add(str(p.value))
    return sorted(mentioned) + ["__other__"]


def eval_predicate(pred: Predicate, value: Any) -> bool | None:
    """标签值 → 谓词真假；值 None → None（缺原料）。"""
    if value is None:
        return None
    op, v = pred.op, pred.value
    if op == "==":
        return value == v
    if op == "!=":
        return value != v
    if op == "in":
        return value in v
    if op == "not_in":
        return value not in v
    try:
        x = float(value)
        y = float(v)
    except (TypeError, ValueError):
        return None
    return {">": x > y, ">=": x >= y, "<": x < y, "<=": x <= y}[op]


def siblings_overlap(a: tuple[Predicate, ...], b: tuple[Predicate, ...], all_siblings: list[tuple[Predicate, ...]]) -> bool:
    """两个兄弟条件能否同真：逐标签在取值域上枚举；只出现在一边的标签不约束另一边。"""
    labels = {p.label for p in a} | {p.label for p in b}
    for label in labels:
        domain = _domain(label, all_siblings)
        pa = [p for p in a if p.label == label]
        pb = [p for p in b if p.label == label]
        joint = [
            v for v in domain
            if all(eval_predicate(p, v) for p in pa) and all(eval_predicate(p, v) for p in pb)
        ]
        if not joint:
            return False  # 这个标签上就已经互斥
    return True


# --------------------------------------------------------------------------- #
# 构造与校验
# --------------------------------------------------------------------------- #
def make(spec: dict[str, Any]) -> tuple[ScenarioTree | None, list[Rejection]]:
    """作者给的 JSON → 树对象 + 拒绝清单（空即通过）。不登记、不读盘。"""
    rej: list[Rejection] = []
    nodes_raw = spec.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return None, [Rejection(E_STRUCTURE, "nodes", "至少要有根节点")]
    max_depth = int(spec.get("max_depth") or 0)
    if max_depth < 1 or max_depth > MAX_DEPTH_V0:
        rej.append(Rejection(E_DEPTH, "max_depth", f"v0 深度 1..{MAX_DEPTH_V0}，收到 {max_depth}"))
    scope = str(spec.get("scope") or "")
    entity_ids = tuple(str(x) for x in (spec.get("entity_ids") or []))
    as_of = str(spec.get("as_of") or "")[:10]
    cutoff = str(spec.get("knowledge_cutoff") or as_of)[:10]
    if cutoff != as_of:
        rej.append(Rejection(E_STRUCTURE, "knowledge_cutoff", "起草时 C 必须等于 as_of：树是站在当天写的"))

    nodes: list[Node] = []
    ids: set[str] = set()
    roots = 0
    for i, n in enumerate(nodes_raw):
        w = f"nodes[{i}]"
        if not isinstance(n, dict) or not n.get("node_id"):
            rej.append(Rejection(E_STRUCTURE, w, "节点要有 node_id"))
            continue
        nid = str(n["node_id"])
        if nid in ids:
            rej.append(Rejection(E_STRUCTURE, w, f"node_id 重复：{nid}"))
        ids.add(nid)
        parent = n.get("parent")
        depth = int(n.get("depth") or 0)
        if parent is None:
            roots += 1
            if depth != 0:
                rej.append(Rejection(E_STRUCTURE, w, "根节点 depth 必须为 0"))
        if depth > max_depth:
            rej.append(Rejection(E_DEPTH, w, f"depth {depth} > max_depth {max_depth}"))
        cond, errs = compile_condition(n.get("condition"), where=f"{w}.condition")
        rej.extend(errs)
        if parent is not None and cond is None and not errs:
            rej.append(Rejection(E_CONDITION_INVALID, w, "非根节点必须有条件或 otherwise"))
        if parent is None and cond is not None:
            rej.append(Rejection(E_CONDITION_INVALID, w, "根节点不带条件"))
        step_kind = n.get("step_kind")
        if parent is not None and step_kind not in STEP_KINDS:
            rej.append(Rejection(E_STRUCTURE, w, f"step_kind 只能是 {STEP_KINDS}"))
        if n.get("analog_ref") not in (None, {}, []):
            rej.append(Rejection(E_ANALOG_REF_NOT_AVAILABLE, w, "analog_ref v0 必须为空：区间相似窗口读数等 #35 派生对象"))
        script_raw = n.get("script") or {}
        try:
            script = observation_script.make(
                as_of=as_of,
                scope=scope,
                entity_ids=entity_ids,
                variables=script_raw.get("variables") or [],
                downgrade_or_abandon_conditions=script_raw.get("downgrade_or_abandon_conditions") or [],
                upgrade_conditions=script_raw.get("upgrade_conditions") or [],
                machine_conditions=script_raw.get("machine_conditions") or [],
                scope_note=str(script_raw.get("scope_note") or ""),
                framework_version=spec.get("framework_version"),
                knowledge_cutoff=cutoff,
                user_id=str(spec.get("user_id") or "default"),
                status="drafted",
                projection_hash=spec.get("projection_hash"),
                model_id=spec.get("model_id"),
            )
        except Exception as exc:  # noqa: BLE001 — 构造失败按结构错报
            rej.append(Rejection(E_NODE_SCRIPT, f"{w}.script", f"{type(exc).__name__}: {exc}"))
            continue
        for r in observation_script.validate(script):
            rej.append(Rejection(E_NODE_SCRIPT, f"{w}.script.{r.field}", f"{r.code}: {r.detail}"))
        nodes.append(Node(nid, depth, None if parent is None else str(parent), cond, step_kind if parent is not None else None, script))

    if roots != 1:
        rej.append(Rejection(E_STRUCTURE, "nodes", f"恰好一个根节点，收到 {roots}"))
    # 父指针存在、depth = 父 + 1
    by_id = {n.node_id: n for n in nodes}
    for n in nodes:
        if n.parent is not None:
            p = by_id.get(n.parent)
            if p is None:
                rej.append(Rejection(E_STRUCTURE, n.node_id, f"parent {n.parent!r} 不存在"))
            elif n.depth != p.depth + 1:
                rej.append(Rejection(E_STRUCTURE, n.node_id, f"depth 应为父 {p.depth}+1"))
    # 兄弟：恰一个 otherwise + 两两互斥
    for parent_id in {n.parent for n in nodes if n.parent is not None}:
        sibs = [n for n in nodes if n.parent == parent_id]
        others = [n for n in sibs if n.condition == OTHERWISE]
        if len(others) == 0:
            rej.append(Rejection(E_NO_OTHERWISE, parent_id, "同一父节点下必须恰有一个 otherwise 分枝——没有它，世界不落进任何分枝时树就没话说"))
        elif len(others) > 1:
            rej.append(Rejection(E_MULTIPLE_OTHERWISE, parent_id, f"{len(others)} 个 otherwise"))
        conds = [n for n in sibs if isinstance(n.condition, tuple)]
        all_conj = [n.condition for n in conds]  # type: ignore[misc]
        for i in range(len(conds)):
            for j in range(i + 1, len(conds)):
                if siblings_overlap(conds[i].condition, conds[j].condition, all_conj):  # type: ignore[arg-type]
                    rej.append(Rejection(E_SIBLINGS_OVERLAP, parent_id, f"{conds[i].node_id} 与 {conds[j].node_id} 可同真：改写成在同一标签上不相交的条件，或合并"))
    # 文本硬门（§3.3 第 2 条 + G-12a）：所有自由文本过 compliance_gate，含策略词与概率数字
    tree_tmp = ScenarioTree(
        as_of=as_of, knowledge_cutoff=cutoff, scope=scope, entity_ids=entity_ids, max_depth=max_depth,
        nodes=tuple(nodes), projection_hash=spec.get("projection_hash"), framework_version=spec.get("framework_version"),
        model_id=spec.get("model_id"), user_id=str(spec.get("user_id") or "default"),
        visibility=str(spec.get("visibility") or "private"),
    )
    codes = compliance_gate.OBSERVATION_SCRIPT_CODES + (compliance_gate.E_STRATEGY_WORD,)
    for where, text in [("title", str(spec.get("title") or "")), ("note", str(spec.get("note") or ""))] + tree_tmp.text_fields:
        if not text:
            continue
        for hit in compliance_gate.scan(text, codes=codes):
            rej.append(Rejection(E_TEXT, where, f"{hit.code}: {hit.term}（{hit.context}）"))
    if rej:
        return None, rej
    return tree_tmp, []


def ensure_valid(spec: dict[str, Any]) -> ScenarioTree:
    tree, rej = make(spec)
    if rej or tree is None:
        raise ScenarioTreeRejected(rej)
    return tree


def _make_id(tree: ScenarioTree, recorded_at: str) -> str:
    body = json.dumps({"as_of": tree.as_of, "scope": tree.scope, "entities": tree.entity_ids, "nodes": [n.to_dict() for n in tree.nodes], "ts": recorded_at}, ensure_ascii=False, sort_keys=True, default=str)
    return "st-" + hashlib.sha256(body.encode()).hexdigest()[:16]


def root_claim(tree: ScenarioTree) -> str:
    return f"情景树[{tree.scope}:{'/'.join(tree.entity_ids)}] 根剧本：{observation_script.to_claim(tree.root.script)}"


def deepest_due(tree: ScenarioTree) -> str:
    days = 0
    for n in tree.nodes:
        if n.step_kind:
            days = max(days, STEP_DAYS[n.step_kind] * n.depth)
    base = datetime.fromisoformat(tree.as_of)
    return (base + timedelta(days=max(days, 1))).date().isoformat()


# --------------------------------------------------------------------------- #
# 登记（append-only）
# --------------------------------------------------------------------------- #
def trees_path(us: Any) -> Path:
    return Path(us.root) / "scenario_trees.jsonl"


def register(
    path: str | Path,
    tree: ScenarioTree,
    *,
    checkpoints_path: str | Path,
    recorded_at: str | None = None,
    status: str = "confirmed",
) -> tuple[Path, dict[str, Any]]:
    """登记一棵树：缺 projection_hash / model_id / framework_version 拒收（§4.2）；同时在 checkpoints 落一条 scenario_tree 可证伪点。"""
    missing = [k for k in ("projection_hash", "model_id", "framework_version") if not getattr(tree, k)]
    if missing:
        raise ScenarioTreeRejected([Rejection(E_MISSING_ATTRIBUTION, "tree", f"缺 {'/'.join(missing)}：agent 产物必须带生成时的投影哈希、模型号与框架版本（09-06 spec §4.2）")])
    if status not in STATUSES:
        raise ScenarioTreeRejected([Rejection(E_STRUCTURE, "status", f"status 只能是 {STATUSES}")])
    stamp = recorded_at or datetime.now(CN_TZ).isoformat(timespec="seconds")
    tree_id = _make_id(tree, stamp)
    _, ck = checkpoints_svc.register_checkpoint(
        Path(checkpoints_path),
        claim=root_claim(tree),
        due=deepest_due(tree),
        category=OBJECT_TYPE,
        source=OBJECT_TYPE,
        themes=list(tree.entity_ids),
        framework_version=tree.framework_version,
        object_type=OBJECT_TYPE,
        projection_hash=tree.projection_hash,
        model_id=tree.model_id,
    )
    record = {
        **tree.to_dict(),
        "record": "tree",
        "id": tree_id,
        "status": status,
        "recorded_at": stamp,
        "checkpoint_id": ck["id"],
        "realized_path": [{"node_id": tree.root.node_id, "resolved_as_of": tree.as_of, "evidence_refs": []}],
    }
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return p, record


def load(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def current_state(records: list[dict[str, Any]], tree_id: str) -> dict[str, Any] | None:
    """树本体 + 追加的 step 记录折成当前状态（append-only 台账的读法）。"""
    tree = next((r for r in records if r.get("record") == "tree" and r.get("id") == tree_id), None)
    if tree is None:
        return None
    path = list(tree.get("realized_path") or [])
    status = tree.get("status")
    for r in records:
        if r.get("record") == "step" and r.get("tree_id") == tree_id:
            if r.get("node_id"):
                path.append({"node_id": r["node_id"], "resolved_as_of": r["as_of"], "evidence_refs": r.get("evidence_refs") or []})
            status = r.get("status", status)
    return {**tree, "realized_path": path, "status": status}


# --------------------------------------------------------------------------- #
# 逐日解析
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ResolutionStep:
    tree_id: str
    as_of: str
    from_node: str
    node_id: str | None  # None = unresolvable / resolved（没有新节点）
    status: str
    evidence_refs: tuple[str, ...]
    projection_hash: str | None
    condition_hit: dict[str, Any] | None
    reason: str
    sample: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": "step",
            "tree_id": self.tree_id,
            "as_of": self.as_of,
            "from_node": self.from_node,
            "node_id": self.node_id,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "projection_hash": self.projection_hash,
            "condition_hit": self.condition_hit,
            "reason": self.reason,
            "sample": self.sample,
        }


def _node_from_record(nrec: dict[str, Any], as_of: str) -> Node:
    cond, errs = compile_condition(nrec.get("condition"), where=nrec.get("node_id", "?"))
    if errs:
        raise ScenarioTreeRejected(errs)
    s = nrec["script"]
    script = observation_script.make(**{k: v for k, v in s.items() if k in observation_script.ObservationScript.__dataclass_fields__ and k not in {"id", "checkpoint_id"}})
    return Node(str(nrec["node_id"]), int(nrec["depth"]), nrec.get("parent"), cond, nrec.get("step_kind"), script, nrec.get("analog_ref"))


def resolve(
    state: dict[str, Any],
    as_of: str,
    *,
    slice_fn: Callable[..., Any],
    checkpoints_path: str | Path | None = None,
    framework_version: str | None = None,
) -> ResolutionStep:
    """走一步：读 ``slice(as_of, knowledge_cutoff=as_of)``，判当前节点的哪个子条件为真。

    ``slice_fn(as_of, entity, knowledge_cutoff=...)`` 返回 ``RiverSlice``；这里**强制** C = as_of（§3.3 硬门 3）。
    到达的节点其观察剧本按 G-03 口径登记（带当日投影哈希）。
    """
    tree_id = str(state["id"])
    path = state.get("realized_path") or []
    if not path:
        raise ValueError("树没有 realized_path 根节点")
    if state.get("status") in ("resolved", "unresolvable", "expired"):
        return ResolutionStep(tree_id, as_of, path[-1]["node_id"], None, str(state["status"]), (), None, None, f"树已是终态 {state['status']}，不再解析")
    if as_of <= str(path[-1]["resolved_as_of"]):
        raise ValueError(f"as_of={as_of} 不晚于上一步 {path[-1]['resolved_as_of']}：解析只能往前走")
    nodes = [_node_from_record(n, state["as_of"]) for n in state["nodes"]]
    by_id = {n.node_id: n for n in nodes}
    current = by_id[path[-1]["node_id"]]
    children = [n for n in nodes if n.parent == current.node_id]
    if not children:
        return ResolutionStep(tree_id, as_of, current.node_id, None, "resolved", (), None, None, "叶节点已到达")

    entity = state["entity_ids"][0] if state.get("entity_ids") else ""
    sl = slice_fn(as_of, entity, knowledge_cutoff=as_of)
    if str(getattr(sl, "knowledge_cutoff", as_of)) != as_of:
        raise ValueError("解析用的切片 knowledge_cutoff 必须等于 as_of（不得站在 now 回看）")
    cp = river_projection.project(sl.to_dict(), framework_version=framework_version or state.get("framework_version"), task=PROJECTION_TASK)

    hits: list[tuple[Node, list[str]]] = []
    for child in children:
        if child.condition == OTHERWISE:
            continue
        refs: list[str] = []
        truth: bool | None = True
        for pred in child.condition:  # type: ignore[union-attr]
            try:
                value, used = bind(pred.label, sl)
            except LabelNotSliceEvaluable as exc:
                raise ScenarioTreeRejected([Rejection(E_LABEL_NOT_SLICE_EVALUABLE, child.node_id, str(exc))]) from exc
            refs.extend(used)
            v = eval_predicate(pred, value)
            if v is None:
                truth = None
                break
            if not v:
                truth = False
        if truth is None:
            return ResolutionStep(
                tree_id, as_of, current.node_id, None, "unresolvable", tuple(refs), cp.projection_hash, None,
                f"节点 {child.node_id} 的条件所需标签在 {as_of} 的切片里缺原料：停在这里，不猜、不跳",
            )
        if truth:
            hits.append((child, refs))
    if len(hits) > 1:  # 互斥门漏了——按设计不可能，真出现就是编译门 bug
        raise ScenarioTreeRejected([Rejection(E_SIBLINGS_OVERLAP, current.node_id, f"{[h[0].node_id for h in hits]} 同真")])
    if hits:
        node, refs = hits[0]
        cond_hit = {"all": [p.to_dict() for p in node.condition]}  # type: ignore[union-attr]
    else:
        node = next(n for n in children if n.condition == OTHERWISE)
        refs = []
        cond_hit = {"otherwise": True}
    status = "resolved" if not [n for n in nodes if n.parent == node.node_id] else "resolving"
    # 到达节点的剧本进回检队列（G-03 同口径）：带当日投影哈希
    if checkpoints_path is not None:
        due_days = STEP_DAYS.get(node.step_kind or "T+1", 1)
        due = (datetime.fromisoformat(as_of) + timedelta(days=due_days)).date().isoformat()
        checkpoints_svc.register_checkpoint(
            Path(checkpoints_path),
            claim=observation_script.to_claim(node.script),
            due=due,
            category=observation_script.CHECKPOINT_CATEGORY,
            source=f"{OBJECT_TYPE}:{tree_id}",
            themes=list(state.get("entity_ids") or []),
            framework_version=state.get("framework_version"),
            object_type=observation_script.OBJECT_TYPE,
            projection_hash=cp.projection_hash,
            model_id=state.get("model_id"),
        )
    sample = {
        "condition": cond_hit,
        "from_node": current.node_id,
        "to_node": node.node_id,
        "next_facts_refs": list(cp.selected_refs),
        "as_of": as_of,
    }
    return ResolutionStep(tree_id, as_of, current.node_id, node.node_id, status, tuple(refs), cp.projection_hash, cond_hit, "命中" if hits else "无声明分枝命中，走 otherwise", sample)


def append_step(path: str | Path, step: ResolutionStep) -> None:
    p = Path(path).expanduser()
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(step.to_dict(), ensure_ascii=False, default=str) + "\n")


# --------------------------------------------------------------------------- #
# 每日复盘钩子（默认关；关着时返回同一个对象）
# --------------------------------------------------------------------------- #
ENV_RESOLVE_FLAG = "FORESIGHT_SCENARIO_TREE_RESOLVE"
DAILY_SECTION_TITLE = "## 情景树逐日解析"


def daily_review_hook(text: str, us: Any, as_of: str, *, db_path: str | Path | None = None) -> str:
    """``FORESIGHT_SCENARIO_TREE_RESOLVE`` 为 on/1/true 才解析用户全部 confirmed / resolving 的树并附一段；否则**原样返回同一个对象**。"""
    import os

    flag = str(os.environ.get(ENV_RESOLVE_FLAG) or "").strip().lower()
    if flag not in {"on", "1", "true", "yes"}:
        return text
    path = trees_path(us)
    records = load(path)
    if not records:
        return text
    from intelligence.services import river

    def slice_fn(day: str, entity: str, **kw: Any) -> Any:
        return river.slice_river(day, entity, knowledge_cutoff=kw.get("knowledge_cutoff") or day, db_path=db_path, checkpoints_path=us.checkpoints_path)

    lines = [DAILY_SECTION_TITLE]
    for tree in [r for r in records if r.get("record") == "tree"]:
        state = current_state(records, tree["id"])
        if state is None or state.get("status") not in ("confirmed", "resolving"):
            continue
        if as_of <= str(state["realized_path"][-1]["resolved_as_of"]):
            continue
        try:
            step = resolve(state, as_of, slice_fn=slice_fn, checkpoints_path=us.checkpoints_path)
        except (ScenarioTreeRejected, ValueError) as exc:
            lines.append(f"- {tree['id']}：解析失败 {type(exc).__name__}: {exc}")
            continue
        append_step(path, step)
        lines.append(f"- {tree['id']}：{step.from_node} → {step.node_id or '—'}［{step.status}］{step.reason}（projection={step.projection_hash}）")
    if len(lines) == 1:
        return text
    section = "\n".join(lines)
    body = text or ""
    return (body.rstrip("\n") + "\n\n" + section + "\n") if body else section + "\n"


# --------------------------------------------------------------------------- #
# 回检（三件事，不按走了哪条枝判对错）
# --------------------------------------------------------------------------- #
@dataclass
class Recheck:
    trees: int = 0
    steps: int = 0
    steps_declared: int = 0
    steps_otherwise: int = 0
    steps_unresolvable: int = 0
    samples: int = 0
    reached_scripts: int = 0
    min_n: int = checkpoints_svc.DEFAULT_CALIBRATION_MIN_N
    by_tree: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def otherwise_share(self) -> float | None:
        if self.trees < self.min_n:
            return None  # 样本不足不出率
        denom = self.steps_declared + self.steps_otherwise
        return round(self.steps_otherwise / denom, 4) if denom else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trees": self.trees, "steps": self.steps, "steps_declared": self.steps_declared,
            "steps_otherwise": self.steps_otherwise, "steps_unresolvable": self.steps_unresolvable,
            "otherwise_share": self.otherwise_share if self.otherwise_share is not None else f"样本不足（<{self.min_n} 棵树）",
            "samples": self.samples, "reached_scripts": self.reached_scripts, "by_tree": self.by_tree,
            "discipline": "不按走了哪条枝判对错；沿路剧本的对错见 checkpoints.calibrate(by_object_type=observation_script)",
        }


def recheck(records: list[dict[str, Any]]) -> Recheck:
    out = Recheck()
    tree_ids = [r["id"] for r in records if r.get("record") == "tree"]
    out.trees = len(tree_ids)
    for r in records:
        if r.get("record") != "step":
            continue
        out.steps += 1
        t = out.by_tree.setdefault(str(r.get("tree_id")), {"declared": 0, "otherwise": 0, "unresolvable": 0})
        if r.get("status") == "unresolvable":
            out.steps_unresolvable += 1
            t["unresolvable"] += 1
            continue
        if r.get("node_id") is None:
            continue
        out.reached_scripts += 1
        if (r.get("condition_hit") or {}).get("otherwise"):
            out.steps_otherwise += 1
            t["otherwise"] += 1
        else:
            out.steps_declared += 1
            t["declared"] += 1
        if r.get("sample"):
            out.samples += 1
    return out
