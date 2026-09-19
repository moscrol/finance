"""P5（D7）跨轮逐轴继承：真实 run_turn → controller → Episode 的五格与来源身份。

作者离线测试。这里证的是**权限与前提标注在真实链路上的继承**，不是答案质量
（P4/P6）、不是材料锚点真实性（D6）、也不是 P7 隔离验收。判官一律离线替身。

与 `test_e2_material_turn_delivery.py` 的分工：那份在编译层（`compile_material_contract`）
证两轴各自更新；本份把同样的五格压到 `TurnOrchestrator.run_turn` → `decide_turn` →
`build_episode_context` / `build_episode_input`，断言到达模型的那一份。
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from intelligence.runtime import conversation_orchestrator as runtime
from intelligence.services.conversation_materials import collect_material_turn_history
from intelligence.services.conversation_store import ConversationStore, Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import build_episode_input
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.run_store import RunStore
from intelligence.services.user_task import classify_top_level_regions

FIXTURES = Path(__file__).resolve().parents[2] / "docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok"
T2 = (FIXTURES / "t2-question.txt").read_text()
T3 = (FIXTURES / "t3-question.txt").read_text()
OLD_ANSWER = "原答：甲的新增催化最强；材料外旧行情值 123456。"

# 五格（A7）。①只改 A ②只改 B ③题内局部假设 ④同值重申 ⑤换题复位。
ONLY_A = "继续上一轮。假设客户 R 的预算翻倍成立。\n\n1. 甲的订单占比多少？"
ONLY_B = "继续上一轮。可以查真实数据。\n\n1. 甲的订单占比多少？"
IN_QUESTION = "继续上一轮。\n\n1. 假设订单翻倍，甲的订单占比多少？"
RESTATED = "继续上一轮。以下是完全虚构的研究案例，不对应现实公司。\n\n1. 甲的订单占比多少？"
NEW_TOPIC = "材料如下：\n\n丁公司去年收入 80 亿元，今年 96 亿元。\n\n1. 丁公司收入为何增长？"


class _Reached(BaseException):
    """在控制器给出真实决策后立刻停，不进执行/终稿。"""


def _message(content: str, role: str = "user", identity: str = "m", **kwargs) -> Message:
    return Message(identity, "conv", role, content, "2026-09-16", "completed", **kwargs)


def _episode_for(tmp_path, turns: list[tuple[str, str]], query: str, monkeypatch):
    """真实 run_turn → 真实 decide_turn → 该轮 TaskFrame，再由它装配 Episode 上下文。

    停在控制器之后：本片要证的是「两轴与材料如何被继承」，不是这一轮之后走研究还是
    澄清车道（那是 P3 的分流，且换轴后主语能否解析会另行触发澄清，与继承无关）。
    run_turn 会把管线异常吞成 failed，所以装一个 `_fail` 探针把真实堆栈显出来，
    否则夹具构造错误会伪装成产品缺陷。
    """
    from intelligence.services import turn_controller

    decisions: list[object] = []

    def controller(raw, **kwargs):
        decisions.append(turn_controller.decide_turn(raw, **kwargs))
        raise _Reached

    store = ConversationStore("alice", root=tmp_path / "conversations")
    runs = RunStore("alice", root=tmp_path / "runs")
    conversation = store.create_conversation()
    for index, (role, content) in enumerate(turns):
        store.append_message(conversation.conversation_id, role, content, run_id=f"prior-{index}")
    run = runs.create_run(query, "ask", session_id=conversation.conversation_id)
    store.append_message(conversation.conversation_id, "user", query, run_id=run.run_id)
    assistant = store.append_message(
        conversation.conversation_id, "assistant", "", status="running", run_id=run.run_id
    )
    failures: list[str] = []
    original_fail = runtime.TurnOrchestrator._fail

    def fail_spy(self, *args, **kwargs):
        import traceback

        error = kwargs.get("error") or (args[-1] if args else None)
        failures.append(
            "".join(traceback.format_exception(error))
            if isinstance(error, BaseException) else repr(error)
        )
        return original_fail(self, *args, **kwargs)

    monkeypatch.setattr(runtime.TurnOrchestrator, "_fail", fail_spy)
    monkeypatch.setattr(runtime, "decide_turn", controller)
    orchestrator = runtime.TurnOrchestrator(
        repo_root=tmp_path, conversation_store=store, run_store=runs,
    )
    try:
        result = orchestrator.run_turn(
            conversation_id=conversation.conversation_id, run_id=run.run_id,
            assistant_message_id=assistant.message_id, query=query,
            skill_mode="auto", selected_skill_ids=[],
        )
    except _Reached:
        pass
    else:  # pragma: no cover - 只在回归时触发
        pytest.fail(f"控制器未到达：status={result.status} errors={failures}")
    assert len(decisions) == 1
    frame = decisions[0].task_frame
    assert frame is not None
    return frame, build_episode_context(frame, task_id=f"p5-{uuid4().hex}", conversation_context="")


def _prior_material_turn() -> list[tuple[str, str]]:
    return [("user", T2), ("assistant", OLD_ANSWER)]


@pytest.mark.parametrize(
    "cell, query, authenticity, data_scope, tools_open",
    [
        ("①只改A轴：B 轴继承 material_only", ONLY_A, "fictional", "material_only", False),
        ("②只改B轴：A 轴继承 fictional", ONLY_B, "fictional", "full", True),
        ("③题内局部假设：消息级两轴原样继承", IN_QUESTION, "fictional", "material_only", False),
        ("④同值重申：两轴幂等", RESTATED, "fictional", "material_only", False),
        ("⑤换题：复位 real×full", NEW_TOPIC, "real", "full", True),
    ],
)
def test_five_cells_reach_the_episode_contract(tmp_path, monkeypatch, cell, query, authenticity, data_scope, tools_open):
    """五格必须在真实链路上成立，而不只是在编译器里。

    权限是 D7 的实际后果：只改 A 不得顺手放开工具；只改 B 必须真的恢复检索资格
    （显式 fictional×full 仍要真实检索，见 episode_factory 的 data_scope_declared 分支）。
    """
    frame, context = _episode_for(tmp_path, _prior_material_turn(), query, monkeypatch)
    contract = frame.material_contract
    assert contract is not None, cell
    assert (contract.authenticity, contract.data_scope) == (authenticity, data_scope), cell
    assert bool(context.contract.allowed_capabilities) is tools_open, cell


def test_new_topic_drops_the_previous_turns_materials(tmp_path, monkeypatch):
    """⑤换题不只是换两轴：旧材料不得继续挂在新题上。"""
    frame, _ = _episode_for(tmp_path, _prior_material_turn(), NEW_TOPIC, monkeypatch)
    assert frame.referenced_material_ids == () or all(
        "丁公司" in item.text for item in (frame.conversation_materials.items if frame.conversation_materials else ())
    )
    materials = frame.conversation_materials
    assert materials is None or all("客户 R" not in item.text for item in materials.items)


def test_inherited_question_scoped_mark_is_not_attributed_to_this_turns_question(tmp_path, monkeypatch):
    """上一轮的题级标注不得在模型可见文本里冒充本轮同号题的前提。

    T2 的 q3/q7/q8 带 `假设/如果`，续轮后这些标注被继承；本轮 T3 的 q3 是另一道题。
    渲染成裸 `q3` 时，模型读到的是「本轮第 3 题有一个虚构前提」——一个跨轮误绑。
    """
    _, context = _episode_for(tmp_path, _prior_material_turn(), T3, monkeypatch)
    block = context.conversation_context
    marks = [line for line in block.splitlines() if line.startswith("前提标注：")]
    assert marks, "材料轮必须带前提标注，否则本断言无意义"
    inherited = [line for line in marks if "轮次1" in line]
    assert inherited, "T2 的题级标注应被继承"
    for line in inherited:
        scope = line.split("前提标注：", 1)[1].split(" / ", 1)[0].strip()
        assert not scope.startswith("q") or "轮次" in scope or "上一轮" in scope, (
            f"继承来的题级标注渲染成裸题号，会被读成本轮同号题的前提：{line}"
        )


def test_restating_the_same_premise_does_not_grow_the_contract():
    """④同值重申必须幂等：同一句前提重申一次，标注不得多一条。

    text_ref 是原句哈希，重申时哈希相同、只有 source_turn 不同，
    去重键若含轮次就挡不住——每续一轮，模型可见的前提标注就多一行。
    """
    base_only = compile_material_contract(classify_top_level_regions(T2), source_turn=1)
    restated = compile_material_contract(
        classify_top_level_regions(RESTATED), source_turn=2, inherited_contract=base_only,
    )
    refs = [mark.text_ref for mark in restated.premise_marks]
    assert len(refs) == len(set(refs)), f"同值重申产生了重复前提标注：{refs}"
    # 留下的必须是最早那一次：前提的来历不能被一次重申改写成当前轮。
    restated_ref = next(
        mark.text_ref for mark in base_only.premise_marks if mark.scope == "message"
    )
    kept = [mark for mark in restated.premise_marks if mark.text_ref == restated_ref]
    assert [mark.source_turn for mark in kept] == [1], f"重申改写了前提的原始轮次：{kept}"


def test_assistant_answer_cannot_restore_permission_through_the_real_chain(tmp_path, monkeypatch):
    """来源身份分级：助手旧答里的权限句不得恢复权限（D7.6 / A12）。"""
    turns = [("user", T2), ("assistant", "可以查真实数据。" + OLD_ANSWER)]
    frame, context = _episode_for(tmp_path, turns, ONLY_A, monkeypatch)
    assert frame.material_contract.data_scope == "material_only"
    assert context.contract.allowed_capabilities == ()
    materials = frame.conversation_materials
    assert materials is not None
    assert all(OLD_ANSWER not in item.text for item in materials.items)
    assert any(OLD_ANSWER in item.text for item in materials.assistant_statements)


def test_axis_change_is_visible_to_the_model_not_only_in_capabilities(tmp_path, monkeypatch):
    """两轴与其继承来源必须进模型输入；只改权限不说话，模型无从遵守。"""
    frame, context = _episode_for(tmp_path, _prior_material_turn(), ONLY_B, monkeypatch)
    payload = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    text = json.dumps(payload, ensure_ascii=False)
    assert "前提真实性=fictional" in text
    assert "数据范围=full" in text


def test_history_replay_counts_turns_from_persisted_user_messages_only(tmp_path):
    """source_turn 只能由已落盘的用户消息推进；助手消息不得推进轮次。"""
    typed = collect_material_turn_history([
        _message(T2, identity="t2"),
        _message(OLD_ANSWER, "assistant", "a1"),
        _message(OLD_ANSWER, "assistant", "a2"),
    ])
    assert typed.source_turn == 2
    assert typed.base_contract is not None
    assert typed.base_contract.data_scope == "material_only"
