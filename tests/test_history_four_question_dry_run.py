"""Can a model that does everything right actually deliver the answer?

真验收失败时看到的是 `report partial`，但「模型没做对」和「系统不让它交」在报告上
长得一样。既有的脚本化用例都以 status="partial"、bindings 里 evidence_hashes 为空
收尾——它们证明了管线不崩，没证明过一份**绑着真实历史原件的完整答案**能出门。

这里让脚本化模型按真实四题的形状把事做对，断言落在「系统允许交付」上：

1. 市场阶段与类比检索——阶段有自己的出处，相似不冒充预测（真验收失败①：漏传市场类型）
2. 同窗内的板块排名、成员股票排名与代表板块启动路径（失败②：两种排名各用各的窗口）
3. 接力判不了就报未成熟，不写成「没接上」（失败③：把观察天数不足当成没有接力）
4. 同一条启动规则量过全体，未启动样本留在分母（失败④：拿近期表现代替启动时特征）

这不是模型质量评测（模型是脚本，数据是合成的），是交付通路的存在性证明：用来把
「模型没做对」和「系统不让它交」分开。真模型复验是另一回事，见 docs/handoffs。
"""

import json

import pytest

from intelligence.services.conversation_store import ConversationStore
from intelligence.services.episode_issues import ReleaseAction, release_action
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.historical_research.anatomy import LAUNCH_RULE
from intelligence.services.historical_research.episode import HistorySession
from intelligence.services.run_store import RunStore
from tests.test_history_live_seams import FIRST, FOLLOWUPS, _decide
from tests.test_history_market_anatomy import anatomy_db as _anatomy_db
from tests.test_history_window_binding import (
    _args,
    _context,
    _execute,
    _read,
    _scenario,
    _tools,
)


@pytest.fixture
def anatomy_db(tmp_path):
    return _anatomy_db.__wrapped__(tmp_path)


def _observations(messages):
    return [json.loads(m["content"]) for m in messages if m.get("role") == "tool"]


def _cited(observed, plan):
    """模型视角可见的证据序号（E1、E2…）→ 它出自哪个算子。

    协议要求绑定填序号而非 content_hash——模型上下文里根本没有哈希
    （``episode_protocol`` 会摘掉）。算子则是模型自己点的那一手，它当然知道。
    脚本只用模型手上真有的信息，测的才是模型真能做到的事。
    """

    return {
        eid: operation
        for observation, (_call_id, _tool, _args, operation) in zip(observed, plan)
        if observation.get("ok")
        for eid in observation.get("evidence_ids", ())
    }


def _final(context, observed, plan, draft, *, status, envelope=None):
    operations = _cited(observed, plan)

    def cite(output):
        if output.grounding_mode != "evidence":
            # 假设槽不得伪装成证据。
            return []
        if not output.allowed_history_operations:
            return list(operations)
        # 按槽位允许的算子分别绑定：契约里的 allowed_history_operations
        # 随 契约 一起发给模型，做对的模型不会把类比列表塞进只收排名的格子。
        return [
            eid
            for eid, operation in operations.items()
            if operation in output.allowed_history_operations
        ]

    def binding(output):
        cited = cite(output)
        item = {
            "output_id": output.output_id,
            "evidence_hashes": cited,
            "basis": output.grounding_mode,
        }
        if output.grounding_mode == "evidence" and not cited:
            # 本轮拿不到该格认可的原件就照实说，不为了填格去跑一次无关查询。
            item["gap"] = f"本轮没有 {output.output_id} 认可的历史原件"
        return item

    payload = {
        "status": status,
        "draft": draft,
        "gaps": [],
        "bindings": [binding(o) for o in context.contract.required_outputs],
    }
    if envelope is not None:
        payload["history_research"] = envelope
    return payload


def _run(loop_name, model, decision, context, tools):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop

    loop = ContinuousAgentEpisode if loop_name == "episode" else HarnessReferenceLoop
    return loop(model).run(task_frame=decision.task_frame, context=context, registry=tools)


def _no_blocking(contract, outcome):
    verified = verify_episode_outcome(contract, outcome)
    blocking = [
        item for item in verified.issue_items if release_action(item.code) is ReleaseAction.BLOCK
    ]
    assert not blocking, [item.serialize() for item in blocking]
    return verified


@pytest.mark.parametrize("loop_name", ["episode", "harness"])
def test_same_window_ranking_and_launch_path_reach_the_answer(tmp_path, anatomy_db, loop_name):
    """第二题的形状：同窗内两种排名 + 代表板块启动路径，全部绑进正文。"""

    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn

    tools, context, session, original, ref, _conversations, _conversation, decision = _scenario(
        tmp_path, anatomy_db
    )
    row = original["rows"][0]
    plan = [
        ("read-original", "read_history_result", {"result_ref": ref}, "find_analogues"),
        # 全市场板块排名：空 codes = 窗口内全部已观测代码，不预筛。
        ("rank-sectors", "history_query", _args(original, ref), "rank_history"),
        # 成员股票排名：同一窗口、同一参照，换实体类型，才谈得上「区分两种排名」。
        ("rank-stocks", "history_query", _args(original, ref, entity_kind="stock"), "rank_history"),
        # 代表板块从启动到窗口内峰值的路径：仍绑同一窗口。
        (
            "trace-leader",
            "history_query",
            _args(original, ref, operation="trace_history", entity_codes=["A.FP"]),
            "trace_history",
        ),
    ]

    class PerfectModel:
        def complete(self, *, messages, tools, timeout):
            observed = _observations(messages)
            if len(observed) < len(plan):
                call_id, name, args, _operation = plan[len(observed)]
                return ModelTurn("", (ModelToolCall(call_id, name, args),), "dry-run", "")
            assert all(o.get("ok") for o in observed), observed
            draft = (
                "在同一参照窗口内：板块层面的全市场排名与A.FP成员股票排名分列，"
                "代表板块A.FP的启动信号与其后的价格路径见原件；未触发与缺数样本保留。"
            )
            return ModelTurn(
                json.dumps(
                    _final(context, observed, plan, draft, status="completed"),
                    ensure_ascii=False,
                ),
                (),
                "dry-run",
                "",
            )

    outcome = _run(loop_name, PerfectModel(), decision, context, tools)

    assert outcome.stop_reason == "model_finish"
    _no_blocking(context.contract, outcome)

    # 正文引用的确实是这三份原件产出的证据卡。
    bound = {
        item.history_provenance.operation
        for item in outcome.evidence
        if item.history_provenance is not None
    }
    assert {"rank_history", "trace_history"} <= bound

    # 同窗：三次查询落在同一起止日期，排名与追踪不是各看各的窗口。
    saved = [session.read(r) for r in session.refs if r.startswith(session.run_id + "/")]
    assert [doc["spec"]["operation"] for doc in saved] == [
        "rank_history",
        "rank_history",
        "trace_history",
    ]
    assert {(doc["spec"]["start"], doc["spec"]["end"]) for doc in saved} == {
        (row["start"], row["end"])
    }
    assert {doc["window_binding"]["source_query_id"] for doc in saved} == {original["query_id"]}
    # 两种排名分列：板块与成员股票各自成原件，不混为一张榜。
    assert [doc["spec"]["entity_kind"] for doc in saved] == ["sector", "stock", "sector"]

    assert "A.FP" in outcome.draft
    # 这一轮用户问的是「当时谁走强、从启动到见顶经过了什么」，不是「有没有规律」，
    # 所以做完就该是 completed：不能因为第一轮问过类比，就把描述性回合一直挂在
    # 「尚未完成条件全集比较」上。要求样本全集的那一轮见下一条用例。
    assert outcome.status == "completed", outcome.gaps
    assert not any("条件全集" in gap for gap in outcome.gaps), outcome.gaps


def _prior_analysis(tmp_path, db, *, followup=2, sample=0):
    """按真实顺序把对话走到第 followup+2 题，交出该轮的工具、上下文与参照分析件。

    前两轮只负责产出后续轮要引用的原件，不跑 episode——这几条用例要证的是
    「某一轮能不能交付」，不是把前面的轮次再验一遍。轮次意图逐轮继承，
    与线上同一条路径（decide_turn）走出来，不另抄一份。
    """

    conversations = ConversationStore("dryrun", root=tmp_path / "conversations")
    conversation = conversations.create_conversation()
    first = _decide(conversations, conversation, FIRST)
    runs = RunStore("dryrun", root=tmp_path / "runs")
    run = runs.create_run(FIRST, "ask", session_id=conversation.conversation_id)
    session = HistorySession(runs, run.run_id, run.session_id)
    context = _context(first.task_frame)
    tools = _tools(first.task_frame, context, db, session)
    found = _execute(
        tools, context, operation="find_analogues", entity_kind="market",
        entity_codes=["000001.SH"], start="2026-01-24", end="2026-01-29",
        search_start="2026-01-05", search_end="2026-01-23", window_days=6,
        step_days=6, features=["return_pct", "advancers_mean"], preview_limit=1,
    )
    ref = found.telemetry["result_ref"]
    original = session.read(ref)

    second = _decide(conversations, conversation, FOLLOWUPS[0], first.turn_intent, 1)
    run2 = runs.create_run(FOLLOWUPS[0], "ask", session_id=run.session_id)
    session2 = HistorySession(runs, run2.run_id, run.session_id)
    context2 = _context(second.task_frame)
    tools2 = _tools(second.task_frame, context2, db, session2)
    _read(tools2, context2, ref)
    # sample 选的是第一轮类比返回的哪一个候选窗口；不同候选覆盖不同的行情段，
    # 后面几轮的参照窗就是它。挑窗口是研究选择，不是测试凑数据。
    row = original["rows"][sample]
    ranked = _execute(
        tools2, context2,
        **_args(original, ref, start=row["start"], end=row["end"],
                window_ref={"result_ref": ref, "sample_id": row["sample_id"]}),
    )
    analysis_ref = ranked.telemetry["result_ref"]

    previous, question = second.turn_intent, FOLLOWUPS[followup]
    if followup > 1:
        # 第三题在中间：它的意图要真的走一遍，第四题才是接在它后面而不是接在第二题后面。
        previous = _decide(
            conversations, conversation, FOLLOWUPS[1], second.turn_intent, 2
        ).turn_intent
    later = _decide(conversations, conversation, question, previous, followup + 1)
    run_later = runs.create_run(question, "ask", session_id=run.session_id)
    session_later = HistorySession(runs, run_later.run_id, run.session_id)
    context_later = _context(later.task_frame)
    tools_later = _tools(later.task_frame, context_later, db, session_later)
    return (
        tools_later, context_later, session_later, later, analysis_ref,
        session2.read(analysis_ref),
    )


@pytest.mark.parametrize("loop_name", ["episode", "harness"])
def test_launch_comparison_with_controls_completes_the_turn(tmp_path, anatomy_db, loop_name):
    """第四题的形状：同一条启动规则量过全体，未启动样本留在分母，结论可标 completed。"""

    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn

    tools, context, session, decision, analysis_ref, analysis = _prior_analysis(
        tmp_path, anatomy_db
    )
    # window_ref 的 sample_id 是可选项：分析件的行没有候选样本号，只给 result_ref。
    window_ref = {"result_ref": analysis_ref}
    if analysis["rows"][0].get("sample_id"):
        window_ref["sample_id"] = analysis["rows"][0]["sample_id"]
    plan = [
        ("read-analysis", "read_history_result", {"result_ref": analysis_ref}, "rank_history"),
        # 每轮的回答要靠本轮账本自己站住：类比相似点这一格只认 find_analogues，
        # 上一轮的检索不在本轮账本里，所以重做一次同口径检索，而不是拿排名充数。
        (
            "analogues-again",
            "history_query",
            dict(
                operation="find_analogues", entity_kind="market", entity_codes=["000001.SH"],
                start="2026-01-24", end="2026-01-29", search_start="2026-01-05",
                search_end="2026-01-23", window_days=6, step_days=6,
                features=["return_pct", "advancers_mean"], preview_limit=1,
            ),
            "find_analogues",
        ),
        # 沿用上一轮分析件的窗口，重算启动路径特征。
        (
            "trace-on-bound-window",
            "history_query",
            dict(
                operation="trace_history", entity_kind="sector", entity_codes=["A.FP", "B.FP"],
                start=analysis["spec"]["start"], end=analysis["spec"]["end"], preview_limit=5,
                window_ref=window_ref,
            ),
            "trace_history",
        ),
        # 条件全集比较：X 用同一条启动规则判定，未启动的进控制组、缺数的进不可判定。
        (
            "compare-launch",
            "history_query",
            dict(
                operation="compare_cases", entity_kind="sector", entity_codes=["A.FP", "B.FP"],
                start="2026-01-05", end="2026-01-11",
                search_start="2026-01-05", search_end="2026-01-29",
                window_days=7, step_days=7,
                features=["return_pct", "amount_vs_prior_mean"],
                condition={"rule": LAUNCH_RULE},
                outcome={"horizon_days": 3, "threshold_pct": 0},
                preview_limit=25,
            ),
            "compare_cases",
        ),
    ]

    class PerfectModel:
        def complete(self, *, messages, tools, timeout):
            observed = _observations(messages)
            if len(observed) < len(plan):
                call_id, name, args, _operation = plan[len(observed)]
                return ModelTurn("", (ModelToolCall(call_id, name, args),), "dry-run", "")
            assert all(o.get("ok") for o in observed), observed
            refs = [
                r for r in session.refs if r.startswith(session.run_id + "/")
            ]
            draft = (
                "同一条启动规则量过全体样本：启动组与未启动的控制组分列，"
                "缺数与历史不足的样本按不可判定保留在分母，未验证的部分仍是研究假设。"
            )
            envelope = {
                "purpose": decision.task_frame.history_intent.purpose,
                "result_refs": refs,
                "claim_level": "historical_comparison",
                "research_only": True,
                "decision_eligible": False,
                "promotion_eligible": False,
            }
            return ModelTurn(
                json.dumps(
                    _final(context, observed, plan, draft, status="completed", envelope=envelope),
                    ensure_ascii=False,
                ),
                (),
                "dry-run",
                "",
            )

    outcome = _run(loop_name, PerfectModel(), decision, context, tools)

    assert outcome.stop_reason == "model_finish"
    _no_blocking(context.contract, outcome)
    assert outcome.status == "completed", outcome.gaps

    saved = {
        doc["spec"]["operation"]: doc
        for doc in (session.read(r) for r in session.refs if r.startswith(session.run_id + "/"))
    }
    assert {"trace_history", "compare_cases"} <= set(saved)

    comparison = saved["compare_cases"]["comparison"]
    # 控制组真的在分母里：未启动样本既没被剔除，也没被当成不可判定。
    assert comparison["launch_states"]["not_observed"] > 0
    assert comparison["enumerated"] == sum(comparison["launch_states"].values())
    assert LAUNCH_RULE in comparison["x_definition"]
    # x=null 不可判定：不进四格，但留在 enumerated 分母里，别被当成控制组。
    assert "kept in enumerated" in comparison["x_definition"]
    # 打标签的规则随原件走，后来的读者改不了「启动」当初的含义。
    assert any(
        LAUNCH_RULE in str(ref) for ref in saved["compare_cases"].get("definition_refs", ())
    )


@pytest.mark.parametrize("loop_name", ["episode", "harness"])
def test_immature_succession_is_delivered_as_immature_not_as_absence(
    tmp_path, anatomy_db, loop_name
):
    """第三题的形状：接力判不了就说判不了，不能写成「没接上」。

    真验收这一题的错法是把「峰后观察天数不足」当成「没有接力」——一个是还没到期，
    一个是已观察到不成立，前者被写成后者就是凭空多出一条结论。这一轮用户授权了
    延长观察终点（起点不动），所以正确做法是先用满授权的终点观察，再照实报状态。
    """

    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn

    tools, context, session, decision, analysis_ref, analysis = _prior_analysis(
        tmp_path, anatomy_db, followup=1, sample=2
    )
    intent = decision.task_frame.history_intent
    assert intent.analysis_window_source == "prior_analysis"
    assert intent.allow_window_extension is True
    assert intent.requires_full_comparison is False

    plan = [
        ("read-analysis", "read_history_result", {"result_ref": analysis_ref}, "rank_history"),
        # 来源与候选目标必须在同一次 trace 的 entity_codes 里、同一窗口：
        # 只查单码得到 0 条接力记录是没配对，不是没接力。
        (
            "trace-succession",
            "history_query",
            dict(
                operation="trace_history", entity_kind="sector",
                entity_codes=["A.FP", "B.FP"],
                start=analysis["spec"]["start"], end="2026-01-16",
                preview_limit=25, window_ref={"result_ref": analysis_ref},
            ),
            "trace_history",
        ),
        (
            "analogues-again",
            "history_query",
            dict(
                operation="find_analogues", entity_kind="market", entity_codes=["000001.SH"],
                start="2026-01-24", end="2026-01-29", search_start="2026-01-05",
                search_end="2026-01-23", window_days=6, step_days=6,
                features=["return_pct", "advancers_mean"], preview_limit=1,
            ),
            "find_analogues",
        ),
    ]

    class PerfectModel:
        def complete(self, *, messages, tools, timeout):
            observed = _observations(messages)
            if len(observed) < len(plan):
                call_id, name, args, _operation = plan[len(observed)]
                return ModelTurn("", (ModelToolCall(call_id, name, args),), "dry-run", "")
            assert all(o.get("ok") for o in observed), observed
            refs = [r for r in session.refs if r.startswith(session.run_id + "/")]
            draft = (
                "沿用上一轮参照窗的起点，按授权把观察终点延到2026-01-16：A.FP与B.FP的接力"
                "判定都还没到期（峰后可观察日不足5个交易日），因此既不能说接上了，也不能说"
                "没接上；日线先后也不证明资金转移。"
            )
            envelope = {
                "purpose": decision.task_frame.history_intent.purpose,
                "result_refs": refs,
                # 本轮没做条件全集比较，就不能自称规律；单案例如实标注。
                "claim_level": "single_case",
                "research_only": True,
                "decision_eligible": False,
                "promotion_eligible": False,
            }
            return ModelTurn(
                json.dumps(
                    _final(context, observed, plan, draft, status="completed", envelope=envelope),
                    ensure_ascii=False,
                ),
                (),
                "dry-run",
                "",
            )

    outcome = _run(loop_name, PerfectModel(), decision, context, tools)

    assert outcome.stop_reason == "model_finish"
    _no_blocking(context.contract, outcome)
    assert outcome.status == "completed", outcome.gaps

    traced = next(
        session.read(r)
        for r in session.refs
        if r.startswith(session.run_id + "/") and session.read(r)["spec"]["operation"] == "trace_history"
    )
    succession = {
        row["entity_code"]: row["succession_status"]
        for row in traced["rows"]
        if row["record_kind"] == "sector_succession"
    }
    # 「还没到期」与「已观察到不成立」在原件里就是两个状态，不靠正文措辞区分。
    assert succession == {"A.FP": "immature", "B.FP": "immature"}
    assert "not_supported" not in succession.values()

    binding = traced["window_binding"]
    # 授权只允许延长观察终点：起点与排名窗原样留痕，延长这件事本身记在原件里。
    assert binding["relation"] == "extended_observation"
    assert (binding["ranking_start"], binding["ranking_end"]) == (
        analysis["spec"]["start"],
        analysis["spec"]["end"],
    )
    assert binding["end"] == "2026-01-16"

    # 这条「未成熟」必须是正文引得动的原件行，而不是只写在草稿里的说法。
    bound_ids = {
        eid for item in outcome.bindings for eid in item.evidence_hashes
    }
    immature = [
        item
        for item in outcome.evidence
        if item.history_provenance is not None
        and item.history_provenance.operation == "trace_history"
        and "immature" in (item.detail or "")
    ]
    assert immature, [item.detail for item in outcome.evidence][:3]
    assert {item.content_hash for item in immature} & bound_ids


@pytest.mark.parametrize("loop_name", ["episode", "harness"])
def test_market_stage_and_analogues_carry_their_own_basis(tmp_path, anatomy_db, loop_name):
    """第一题的形状：先按市场类型看阶段，再找相似窗口，口径与缺失随原件走。

    真验收这一题的错法是查询没带市场类型，于是拿不到市场行的阶段与来源，
    只好凭板块数据讲市场。这里把实体类型真的传成 market，并要求「阶段是谁说的」
    与「相似不是预测」这两件事都能在正文里引到。
    """

    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
    from intelligence.services.conversation_store import ConversationStore as _Store
    from intelligence.services.run_store import RunStore as _Runs

    conversations = _Store("dryrun", root=tmp_path / "conversations")
    conversation = conversations.create_conversation()
    decision = _decide(conversations, conversation, FIRST)
    runs = _Runs("dryrun", root=tmp_path / "runs")
    run = runs.create_run(FIRST, "ask", session_id=conversation.conversation_id)
    session = HistorySession(runs, run.run_id, run.session_id)
    context = _context(decision.task_frame)
    tools = _tools(decision.task_frame, context, anatomy_db, session)
    # 第一轮没有参照原件可绑，窗口来源为 none：这时不该被要求先读原件。
    assert decision.task_frame.history_intent.analysis_window_source == "none"

    plan = [
        (
            "market-stage",
            "history_query",
            dict(
                operation="inspect_history", entity_kind="market",
                entity_codes=["000001.SH"], start="2026-01-24", end="2026-01-29",
                preview_limit=5,
            ),
            "inspect_history",
        ),
        (
            "analogues",
            "history_query",
            dict(
                operation="find_analogues", entity_kind="market",
                entity_codes=["000001.SH"], start="2026-01-24", end="2026-01-29",
                search_start="2026-01-05", search_end="2026-01-23",
                window_days=6, step_days=6,
                features=["return_pct", "advancers_mean"], preview_limit=3,
            ),
            "find_analogues",
        ),
    ]

    class PerfectModel:
        def complete(self, *, messages, tools, timeout):
            observed = _observations(messages)
            if len(observed) < len(plan):
                call_id, name, args, _operation = plan[len(observed)]
                return ModelTurn("", (ModelToolCall(call_id, name, args),), "dry-run", "")
            assert all(o.get("ok") for o in observed), observed
            draft = (
                "市场阶段取自market行自带的market_stage与其来源字段，供应商内层cycle_stage另标；"
                "相似窗口按声明的距离口径给出，重叠候选属同一簇、不是独立样本，相似程度不当预测胜率。"
            )
            return ModelTurn(
                json.dumps(
                    _final(context, observed, plan, draft, status="completed"),
                    ensure_ascii=False,
                ),
                (),
                "dry-run",
                "",
            )

    outcome = _run(loop_name, PerfectModel(), decision, context, tools)

    assert outcome.stop_reason == "model_finish"
    _no_blocking(context.contract, outcome)
    assert outcome.status == "completed", outcome.gaps

    saved = [session.read(r) for r in session.refs if r.startswith(session.run_id + "/")]
    inspected, analogues = saved[0], saved[1]
    assert inspected["spec"]["entity_kind"] == "market"
    market = inspected["rows"][0]["market"]
    # 阶段有自己的出处字段：授课口径与供应商内层阶段各归各的，不混着讲。
    assert "market_stage" in market and "market_stage_source" in market
    assert market["cycle_stage_source"] and market["cycle_stage"] != market["market_stage"]

    # 相似不是预测：距离口径、重叠不独立这两条随原件走，不靠模型自觉。
    assert "no fitted transform or forward outcomes" in analogues["distance_definition"]
    assert "not independent evidence or predictive odds" in analogues["independence_policy"]
    assert analogues["decision_eligible"] is False and analogues["promotion_eligible"] is False

    bound = {
        item.history_provenance.operation
        for item in outcome.evidence
        if item.history_provenance is not None
    }
    assert {"inspect_history", "find_analogues"} <= bound
