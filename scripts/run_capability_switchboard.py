#!/usr/bin/env python3
"""开关板 runner：默认盒 ± 一颗，一次只拧一颗。

与梯子（``run_episode_seam_ladder.py``）分家的理由：梯子的唯一变量是能力面**且必须
包含**（S0⊂S1⊂S2⊂S3），它回答「这题最低开到哪」；开关板要的是并列零件各自 on/off，
回答「这一颗拧不拧得动」。两个目标函数不同，混进同一份 artifact 会互相污染读数。
所以本文件复用梯子的装配零件（题面、路由、夹具 runner、scripted 模型），但**不复用
它的包含关系**，也不写进它的输出。

第 1 步的过关判据是三条，不是一条：

    正控   ``offered_schemas`` 关前关后差集**恰好**这一颗
    负控   另起一个 script 硬点名调那颗关掉的工具，必须落 unknown_or_unauthorized_tool
    底盘   有收据、不崩

只做第三条等于只证明了「没崩」——而 scripted 模型只调递给它的 schema，关掉一颗后它
压根不会去碰，「没崩」在离线臂**恒真**，那不是读数。

用法：
    python3 scripts/run_capability_switchboard.py --switch market_data --state off
    python3 scripts/run_capability_switchboard.py --all-arms          # 每颗关一次
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter  # noqa: E402
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime  # noqa: E402
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn  # noqa: E402
from intelligence.services.capability_switchboard import (  # noqa: E402
    SwitchRow,
    load_switchboard,
)
from intelligence.services.episode_factory import build_episode_context  # noqa: E402
from intelligence.services.research_contract import (  # noqa: E402
    ResearchContractError,
    release_root_budget,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry  # noqa: E402
from intelligence.services.episode_tools import build_episode_registry  # noqa: E402
from scripts.run_episode_seam_ladder import (  # noqa: E402
    OFFLINE_PROVIDER,
    OfflineSemanticVerifier,
    ScriptedEpisodeModel,
    SeamLadderCase,
    _arguments_for_schema,
    _classify_failure,
    _final_json,
    _observed_hashes,
    _source_revision,
    load_cases,
    resolve_control,
    stage_registry_with_fixture_runners,
)

DEFAULT_CASES = REPO / "intelligence" / "tests" / "fixtures" / "episode_seam_ladder_cases.json"
DEFAULT_OUTPUT_DIR = REPO / "intelligence" / "eval" / "runs" / "switchboard"

# 授权面的派生入口。收据写它的名字，因为本仓的授权面是**逐 frame 解算**的
# （`episode_factory.py` 的 `_authorized_capabilities` → `runtime_capabilities_for_frame`，
# evidence_plan 的 mandatory 还会往里追加），根本不存在一排可冻结的「生产开哪些」。
CAPABILITY_SOURCE = "intelligence.services.episode_factory.build_episode_context"


class TwoDeltasError(ValueError):
    """一次只准拧一颗。两个差量的 run 无法归因，拒跑而不是写一份假收据。"""


@dataclass(frozen=True)
class Delta:
    switch_id: str
    state: str  # "on" | "off"

    def label(self) -> str:
        return f"{self.switch_id}={self.state}"


@dataclass
class Derivation:
    resolved_capabilities: tuple[str, ...] = ()
    enabled_capabilities: tuple[str, ...] = ()
    context: object | None = None
    registry: ResearchToolRegistry | None = None
    designed_unsatisfiable: str = ""
    detail: str = ""


class AdversarialEpisodeModel:
    """负控：不管递没递给它，硬点名调 ``target``。

    存在的理由是 ``ScriptedEpisodeModel`` 只调 ``tools`` 里出现过的名字——关掉一颗
    之后它永远不会去碰那一颗，于是 ``unauthorized_invocations=[]`` 恒真。要证明
    「关得住」而不是「schema 变短了」，必须有人真的去敲那扇门。
    """

    def __init__(self, contract: object, target: str) -> None:
        self._contract = contract
        self._target = target
        self._tried = False
        self.offered_schemas: list[tuple[str, ...]] = []

    def complete(self, *, messages, tools, timeout):
        del timeout
        offered = tuple(
            str(fn.get("name") or "")
            for item in tools
            if isinstance(item, dict) and isinstance(fn := item.get("function"), dict)
        )
        self.offered_schemas.append(offered)
        if not self._tried:
            self._tried = True
            return ModelTurn(
                "",
                (
                    ModelToolCall(
                        call_id="switchboard-adversarial-0",
                        name=self._target,
                        arguments=_arguments_for_schema(None),
                    ),
                ),
                OFFLINE_PROVIDER,
                "",
            )
        return ModelTurn(
            _final_json(self._contract, _observed_hashes(messages)),
            (),
            OFFLINE_PROVIDER,
            "",
        )


@contextmanager
def switch_derivation(
    case: SeamLadderCase,
    control: object,
    row: SwitchRow | None,
    delta: Delta | None,
) -> Iterator[Derivation]:
    """建生产 context，再按差量收窄——收窄的是**合同**，不只是工具 schema。

    只过滤 schema 会留下「合同授权得比这一臂暴露得多」的特权路径，那是个更小的
    展示面、不是更小的装配体。与梯子 ``narrow_context_to_stage`` 同一条理由。
    """

    episode_id = f"switchboard:{case.case_id}:{delta.label() if delta else 'default'}"
    source = build_episode_context(
        control.task_frame,
        task_id=episode_id,
        capabilities=control.capabilities,
        tier=case.tier,
        timeout=case.timeout,
        today=case.as_of,
        latest_data_date=case.as_of,
        synthesis_reserve=GLMAgentRuntime.synthesis_reserve_for_task(
            tier=case.tier,
            question_type=control.task_frame.question_type,
        ),
        conversation_context="\n".join(
            f"{item['role']}: {item['content']}" for item in case.conversation_context
        ),
    )
    try:
        contract = source.contract
        resolved = tuple(contract.allowed_capabilities)
        enabled = resolved
        if delta is not None and row is not None and row.kind == "capability":
            if delta.state == "off":
                enabled = tuple(item for item in resolved if item != row.id)
            elif row.id not in resolved:
                enabled = resolved + (row.id,)

        mandatory = tuple(contract.evidence_plan.mandatory_capabilities)
        missing = tuple(item for item in mandatory if item not in set(enabled))
        if missing:
            # 「地板以下不跑」的同形：这是**设计上的不可满足**，不是被测组件的失败。
            # 归因字段叫 switch_id 而不是 stage，两份 artifact 不互相冒充。
            yield Derivation(
                resolved_capabilities=resolved,
                enabled_capabilities=enabled,
                designed_unsatisfiable="mandatory_capability_unauthorized",
                detail="evidence plan requires " + ",".join(missing),
            )
            return
        try:
            narrowed = replace(source, contract=replace(contract, allowed_capabilities=enabled))
        except ResearchContractError as exc:
            yield Derivation(
                resolved_capabilities=resolved,
                enabled_capabilities=enabled,
                designed_unsatisfiable="mandatory_capability_unauthorized",
                detail=str(exc),
            )
            return
        full = build_episode_registry(control.task_frame, narrowed)
        yield Derivation(
            resolved_capabilities=resolved,
            enabled_capabilities=enabled,
            context=narrowed,
            registry=ResearchToolRegistry(full.authorized_specs(enabled)),
        )
    finally:
        # registry 是 WeakValueDictionary：以抛出结束的一集会通过 traceback 留住
        # 它的 ledger，下一次同名 run 会撞上一个死注册。
        release_root_budget(episode_id)


def _build_adapter(case: SeamLadderCase, derived: Derivation, model, row, delta):
    """在 composition root 上拧非工具那一族，loop 里不加任何产品 if。"""

    verifier = OfflineSemanticVerifier()
    if (
        delta is not None
        and row is not None
        and row.id == "semantic-verifier"
        and delta.state == "off"
    ):
        verifier = _NullSemanticVerifier()
    registry = stage_registry_with_fixture_runners(derived.registry, case.as_of)
    client = model
    if delta is not None and row is not None and row.id == "noop-prompt" and delta.state == "on":
        client = NoopPromptClient(model)
    adapter = ContinuousTurnAdapter(
        runtime=GLMAgentRuntime(client=client),
        semantic_verifier=verifier,
        mode="on",
        context_factory=lambda _frame, **_kw: derived.context,
        registry_factory=lambda _frame, _ctx: registry,
        tier=case.tier,
        timeout=case.timeout,
        today=case.as_of,
        latest_data_date=case.as_of,
        deadline_expires_at=time.monotonic() + case.timeout,
    )
    return adapter, registry, client


class NoopPromptClient:
    """第 3 步的零行为零件：往递给模型的 messages 里加一段固定说明书。

    **挂在哪很重要。** 它包在 ``GLMAgentRuntime(client=...)`` 这个**已有的**注入缝
    外面，所以 ``agent_episode`` / 梯子 / ``ResearchProfile`` 一行不动——这正是第 3 步
    要证的「挂得上一颗零件，而 loop 图不变」。往 loop 里加一个产品 `if` 也能让它
    「生效」，但那证明的是反面。

    零行为：不改工具面、不改核验、不改合同。它唯一的可观测后果就是那段文字出现在
    模型看到的消息流里——所以正控只能是 ``prompt_segment_delivered``，不能是「没崩」。
    """

    SEGMENT = "【开关板·零行为零件】本段不改变工具面、不改变核验、不改变合同，仅用于验证提示词缝可挂载。"

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.delivered = False

    def complete(self, *, messages, tools, timeout):
        injected = [{"role": "system", "content": self.SEGMENT}, *messages]
        # 记的是**内层模型真的收到了**，不是「我打算注入」。后者恒真，等于没测。
        self.delivered = any(
            self.SEGMENT in str(item.get("content") or "")
            for item in injected
            if isinstance(item, dict)
        )
        return self._inner.complete(messages=injected, tools=tools, timeout=timeout)


class _NullSemanticVerifier:
    """把核验这一颗关掉的正确方式：构造注入。

    **不是**让 root deadline 过期——那条路是 `continuous_turn_adapter.py:731-732`
    的 ``raise TimeoutError`` → ``model_unavailable``，拿到的是降级/中止的一集，
    会把这颗误判成焊点。
    """

    def verify(self, *, frame, structurally_verified, deadline):
        from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome

        del frame, deadline
        return SemanticEpisodeOutcome(
            verified=structurally_verified,
            judge_status="skipped_by_switch",
        )


def _run_arm(case, control, board, row, delta, adversarial_target: str = "") -> dict:
    """跑一臂，返回该臂的观测。"""

    with switch_derivation(case, control, row, delta) as derived:
        arm: dict[str, object] = {
            "delta": delta.label() if delta else "",
            "resolved_capabilities": list(derived.resolved_capabilities),
            "enabled_capabilities": list(derived.enabled_capabilities),
            "designed_unsatisfiable": derived.designed_unsatisfiable,
            "designed_unsatisfiable_detail": derived.detail,
            "offered_schemas": [],
            "refused_calls": [],
            "chassis_survived": False,
            "failure_class": "",
        }
        if derived.context is None:
            return arm
        contract = derived.context.contract
        model = (
            AdversarialEpisodeModel(contract, adversarial_target)
            if adversarial_target
            else ScriptedEpisodeModel(contract)
        )
        adapter, registry, client = _build_adapter(case, derived, model, row, delta)
        arm["prompt_segment_delivered"] = False
        disabled = (
            frozenset({row.id})
            if delta is not None and row is not None and row.kind == "predicate" and delta.state == "off"
            else frozenset()
        )
        from intelligence.services.predicate_faces import using

        try:
            with using(disabled):
                result = adapter.handle(frame=control.task_frame, control=control)
        except Exception as exc:  # noqa: BLE001 — 分类，不吞
            failure_class, detail = _classify_failure(exc)
            arm["failure_class"] = failure_class
            arm["failure_detail"] = detail
            return arm
        # 递给模型的那份 schema，不是 registry.names()——中间再滤一层，正控会假绿。
        offered = getattr(model, "offered_schemas", ())
        arm["offered_schemas"] = list(offered[0]) if offered else []
        arm["chassis_survived"] = True
        arm["prompt_segment_delivered"] = bool(getattr(client, "delivered", False))
        artifact = result.private_artifact or {}
        arm["judge_status"] = str(
            (artifact.get("semantic_verifier") or {}).get("judge_status") or ""
        )
        arm["refused_calls"] = _refused_calls(artifact)
        return arm


def _reading_pack_face_changed(switch_id: str) -> bool:
    """判读包那一面：验真注入文本，不拿宪法行冒充。"""

    if switch_id != "predicate.reading-baseline":
        return False
    from intelligence.services import reading_baseline
    from intelligence.services.predicate_faces import using

    on_text = reading_baseline.baseline_guidance()
    on_block = reading_baseline.block_rule_lines("D0")
    with using({switch_id}):
        off_text = reading_baseline.baseline_guidance()
        off_block = reading_baseline.block_rule_lines("D0")
    return bool(on_text) and off_text == "" and bool(on_block) and off_block == []


def _predicate_declared_faces_changed(switch_id: str) -> bool:
    """谓词的正控：**它声明的每一面都要变**，少一面就不算关掉。

    不是「三面都要变」——只有 `double-red` 三面俱全，`capacity-top3` / `sqrt-weighted`
    只有算数+说明书两面，`single-red` 只有算数一面。硬要三面会把两面的判成失败，
    那是判据错不是开关坏。
    """

    from pathlib import Path as _Path

    from intelligence.services import predicate_faces
    from intelligence.services.predicate_faces import (
        FACE_ARITHMETIC,
        FACE_PACK,
        FACE_PROSE,
        FACE_ROUTE,
    )

    on = predicate_faces.faces()
    off = predicate_faces.faces({switch_id})
    declared = on.declared_faces(switch_id)
    if not declared:
        return False

    # 说明书那一面拿**真的宪法正文**来验，不在本文件另造样例：造样例只能证明
    # 过滤函数会过滤，证明不了它过滤得到真正被注入模型的那几行。
    methodology = (
        _Path(__file__).resolve().parents[1] / "intelligence" / "foresight_methodology.md"
    ).read_text(encoding="utf-8")
    lines = tuple(methodology.splitlines())

    checks = {
        FACE_ARITHMETIC: on.arithmetic_enabled(switch_id) != off.arithmetic_enabled(switch_id),
        FACE_ROUTE: on.route_alternation() != off.route_alternation(),
        FACE_PROSE: on.prose_lines(lines) != off.prose_lines(lines),
        FACE_PACK: _reading_pack_face_changed(switch_id),
    }
    return all(checks[face] for face in declared)


def _refused_calls(artifact) -> list[str]:
    """从这一集的 ProviderTrace 里捞被拒的工具调用。

    拒绝路径是现成的，不新写第二套：``agent_episode.py:395-411`` 收到
    ``result.error == "unknown_or_unauthorized_tool"`` 时，追加一条
    ``ProviderTrace(provider="episode:tool_gate", capability=<工具名>,
    status="disabled")``，最终落在 artifact 的 ``traces``
    （``continuous_turn_adapter.py:1083``）。

    ⚠ 起初这里去翻 ``trace_steps``，捞不到任何东西——于是负控全绿地报「未拒绝」，
    看起来像「关不住」。**观测点找错，读数长得和真失败一模一样**，这正是正控/负控
    自己也需要被验证一次的理由（见 tests 里的合成负控）。
    """

    refused: list[str] = []
    for trace in (artifact.get("traces") or ()):
        if not isinstance(trace, dict):
            continue
        if trace.get("provider") != "episode:tool_gate":
            continue
        if trace.get("detail") != "unknown_or_unauthorized_tool":
            continue
        refused.append(str(trace.get("capability") or ""))
    return refused


# 本 runner 真正拧得动的开关面。
#
# 不在这里面的，跑出来只会是「默认臂跑了两遍」——底盘当然不崩、schema 当然不变，
# 于是全绿。那是**空过**：证明的是 runner 没坏，不是开关能关。宁可报
# not_implemented，也不让一颗没接线的开关顶着 ✅ 混进读数。
#
#   followup-composer  追问在 conversation_orchestrator 里合成，不经 episode adapter，
#                      本 runner 够不着。
#   predicate.*        声明的每一面都要变（三面是上限不是定额），见 predicate_faces。
_RUNNER_APPLIES_KINDS = frozenset({"capability"})
_RUNNER_APPLIES_IDS = frozenset({"semantic-verifier", "noop-prompt"})
def _wired_predicates() -> frozenset[str]:
    """已经在 `predicate_faces` 里登记了面的谓词。没登记的报 not_implemented，不空过。"""

    from intelligence.services.predicate_faces import wired_predicate_ids

    return wired_predicate_ids()


def run_switch(case, board, row: SwitchRow, delta: Delta) -> dict:
    """一颗开关的完整一轮：对照臂 + 差量臂 + 负控臂。"""

    if (
        row.kind not in _RUNNER_APPLIES_KINDS
        and row.id not in _RUNNER_APPLIES_IDS
        and row.id not in _wired_predicates()
    ):
        return {
            "switch_set": board.switch_set,
            "capability_source": CAPABILITY_SOURCE,
            "case_id": case.case_id,
            "as_of": case.as_of,
            "revision": _source_revision(),
            "switch_id": row.id,
            "kind": row.kind,
            "delta": delta.label(),
            "positive_control": {"field": row.positive_control, "schema_delta": None, "passed": None},
            "negative_control": {"ran": False, "refused_calls": [], "passed": None},
            "chassis_survived": None,
            "designed_unsatisfiable": "",
            "outcome": "not_implemented",
            "not_implemented_reason": (
                "本 runner 只拧 capability（收窄合同）、semantic-verifier（构造注入）与 noop-prompt（client 装饰）；"
                "这一颗的关法不在 episode composition root 上"
            ),
        }

    control = resolve_control(case)
    baseline = _run_arm(case, control, board, None, None)

    # 这一颗在本题的**解算面**里根本没被授权 → 关它是空操作，读数没有意义。
    #
    # 这是「本来就没开」那个坑的镜像：不拦住的话，schema 差集恒为 []，正控恒不过，
    # 收据上就是一个 ❌，会把下一个 agent 派去修一颗其实没毛病的开关。授权面逐
    # frame 解算（见 CAPABILITY_SOURCE），一颗开关在 A 题可测、在 B 题不可测是常态，
    # 不是缺陷。
    if (
        row.kind == "capability"
        and delta.state == "off"
        and row.id not in set(baseline["resolved_capabilities"])
    ):
        return {
            "switch_set": board.switch_set,
            "capability_source": CAPABILITY_SOURCE,
            "case_id": case.case_id,
            "as_of": case.as_of,
            "revision": _source_revision(),
            "switch_id": row.id,
            "kind": row.kind,
            "delta": delta.label(),
            "resolved_capabilities": list(baseline["resolved_capabilities"]),
            "positive_control": {"field": row.positive_control, "schema_delta": None, "passed": None},
            "negative_control": {"ran": False, "refused_calls": [], "passed": None},
            "chassis_survived": None,
            "designed_unsatisfiable": "",
            "outcome": "inactive_on_case",
        }

    treated = _run_arm(case, control, board, row, delta)

    # 差量臂根本没建起来 = 这道题的证据计划把这一颗列为 mandatory，关了合同就不合法。
    # 这是**设计上的不可满足**，不是被测组件的失败，也不是「关得动」的证据——
    # 此时 schema 差集会等于「全部工具」（因为那一臂一个都没有），拿它当正控读数
    # 会得出「关掉一颗却少了七颗」的假象。所以这里直接短路，三种结局分开记。
    if treated["designed_unsatisfiable"]:
        outcome = "designed_unsatisfiable"
        schema_delta = None
        negative: dict[str, object] = {"ran": False}
        positive_ok = None
        negative_ok = None
    else:
        before = set(baseline["offered_schemas"])
        after = set(treated["offered_schemas"])
        schema_delta = (
            sorted(before - after) if delta.state == "off" else sorted(after - before)
        )
        negative = {"ran": False}
        if row.kind == "capability" and delta.state == "off":
            negative = _run_arm(case, control, board, row, delta, adversarial_target=row.id)
            negative["ran"] = True

        if row.kind == "capability":
            positive_ok = schema_delta == [row.id]
        else:
            # 非工具那一族的正控不是 schema，是它自己声明的那个字段。
            # 写成无条件 True 就是空过——一颗没接线的开关会顶着 ✅ 混进读数。
            if row.id in _wired_predicates():
                positive_ok = _predicate_declared_faces_changed(row.id)
            elif row.id == "noop-prompt":
                # 那段说明书必须真的进了模型看到的消息流，且对照臂里没有。
                positive_ok = bool(treated.get("prompt_segment_delivered")) and not baseline.get(
                    "prompt_segment_delivered"
                )
            else:
                # semantic-verifier 关掉后 judge_status 必须变——不变说明注入没生效。
                positive_ok = baseline.get("judge_status") != treated.get("judge_status")
        negative_ok = (
            (
                row.id in negative.get("refused_calls", [])
                or negative.get("failure_class") == "unauthorized_tool"
            )
            if negative.get("ran")
            else True
        )
        outcome = (
            "passed"
            if positive_ok and negative_ok and treated["chassis_survived"]
            else "failed"
        )
    return {
        "switch_set": board.switch_set,
        "capability_source": CAPABILITY_SOURCE,
        "case_id": case.case_id,
        "as_of": case.as_of,
        "revision": _source_revision(),
        "dirty": _source_revision().endswith("-dirty"),
        "switch_id": row.id,
        "kind": row.kind,
        "delta": delta.label(),
        "positive_control": {
            "field": row.positive_control,
            "schema_delta": schema_delta,
            "passed": positive_ok,
        },
        "negative_control": {
            "ran": bool(negative.get("ran")),
            "refused_calls": negative.get("refused_calls", []),
            "failure_class": negative.get("failure_class", ""),
            "passed": negative_ok,
        },
        "baseline_arm": baseline,
        "treated_arm": treated,
        "chassis_survived": bool(treated["chassis_survived"]),
        "designed_unsatisfiable": treated["designed_unsatisfiable"],
        "outcome": outcome,
    }


def parse_deltas(pairs: Sequence[str]) -> Delta:
    if len(pairs) != 1:
        raise TwoDeltasError(f"一次只准拧一颗，收到 {len(pairs)} 个：{list(pairs)}")
    raw = pairs[0]
    switch_id, _, state = raw.partition("=")
    state = state or "off"
    if state not in {"on", "off"}:
        raise TwoDeltasError(f"差量状态只能是 on/off：{raw}")
    return Delta(switch_id.strip(), state)


def main(argv: tuple[str, ...] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--switch",
        action="append",
        default=[],
        help="形如 market_data=off；给两个会被拒跑",
    )
    parser.add_argument("--all-arms", action="store_true", help="表里够格的每颗关一次")
    parser.add_argument("--case", default="", help="只跑某道题")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    board = load_switchboard()
    cases = load_cases(args.questions)
    if args.case:
        cases = tuple(c for c in cases if c.case_id == args.case)
    if not cases:
        print("没有匹配的题面")
        return 2

    if args.all_arms:
        # 每颗按**背离默认**的方向拧，不是无脑发 off。
        # `noop-prompt` 默认就是 off，「关一个已经关着的」两臂完全相同，正控必不过——
        # 那读数是 runner 的缺陷，不是开关的缺陷。ambient（跟合同走）按 off 处理。
        deltas = [
            Delta(switch_id, "off" if board.resolve(switch_id).default != "off" else "on")
            for switch_id in board.arm_ids()
        ]
    else:
        try:
            deltas = [parse_deltas(args.switch)]
        except TwoDeltasError as exc:
            print(f"拒跑：{exc}")
            return 2

    records = []
    for case in cases:
        for delta in deltas:
            row = board.resolve(delta.switch_id)  # 未知 id 在这里抛，不静默忽略
            if not row.eligible_for_arm:
                print(f"跳过 {row.id}：不够格进实验臂（status={row.status}）")
                continue
            records.append(run_switch(case, board, row, delta))

    artifact = {
        "kind": "capability_switchboard",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "switch_set": board.switch_set,
        "records": records,
    }
    output = args.output or (
        DEFAULT_OUTPUT_DIR
        / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-switchboard.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    marks = {
        "passed": "✅",
        "designed_unsatisfiable": "⊘",
        "inactive_on_case": "–",
        "not_implemented": "·",
        "failed": "❌",
    }
    for record in records:
        pos = record["positive_control"]
        neg = record["negative_control"]
        if record["outcome"] == "inactive_on_case":
            tail = "这颗不在本题解算面里，关它是空操作（授权面逐 frame 解算，换道题可能可测）"
        elif record["outcome"] == "not_implemented":
            tail = record.get("not_implemented_reason", "")
        elif record["outcome"] == "designed_unsatisfiable":
            tail = "该题证据计划把这颗列为 mandatory，关了合同不合法（非失败，也非「关得动」的证据）"
        else:
            tail = (
                f"schema差集={pos['schema_delta']}"
                f" 负控={'拒绝' if neg['ran'] and neg['passed'] else ('未跑' if not neg['ran'] else '未拒绝')}"
                f" 底盘={'跑完' if record['chassis_survived'] else '崩'}"
            )
        print(f"{marks[record['outcome']]} {record['case_id']} {record['delta']:<26} {tail}")

    tally = {key: sum(1 for r in records if r["outcome"] == key) for key in marks}
    print(
        f"\n通过 {tally['passed']}"
        f" ｜ 设计不可满足 {tally['designed_unsatisfiable']}"
        f" ｜ 本题不适用 {tally['inactive_on_case']}"
        f" ｜ 未接线 {tally['not_implemented']}"
        f" ｜ 失败 {tally['failed']} → {output}"
    )
    return 1 if tally["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
