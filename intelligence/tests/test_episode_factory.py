from __future__ import annotations

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.task_frame import TaskFrame
from intelligence.runtime.turn_control_core import TurnControlCore


RUNTIME_CAPABILITIES = {
    "finance_query",
    "evidence_search",
    "market_data",
    "financial_data",
    "mainline_context",
    "kb_search",
    "graph_lookup",
    "evidence_lookup",
    "news_search",
    "web_search",
    "l3_lookup",
    "memory_lookup",
}


def test_evidence_grounded_tasks_receive_broad_model_owned_read_tools() -> None:
    control = TurnControlCore().control(
        "目前固态电池产业景气度处于什么阶段，给出数据依据",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="broad-read-tools",
        capabilities=control.capabilities,
    )

    assert {"finance_query", "evidence_search"}.issubset(
        context.contract.allowed_capabilities
    )
    assert "finance_query" not in {
        item.capability for item in context.contract.evidence_plan.requirements
    }
    assert "evidence_search" not in {
        item.capability for item in context.contract.evidence_plan.requirements
    }


@pytest.mark.parametrize(
    ("question", "expected_capabilities", "expected_output"),
    (
        (
            "昨天的反弹能持续多久",
            {"market_data", "mainline_context"},
            "duration_assessment",
        ),
        (
            "科创50你认为反弹空间有多少",
            {"market_data"},
            "technical_levels",
        ),
        (
            "瑞华泰的合理估值",
            {"market_data", "financial_data", "evidence_lookup"},
            "valuation_assessment",
        ),
        (
            "这一周行情下跌的主要原因是什么",
            {"market_data", "news_search"},
            "causal_chain",
        ),
        (
            "目前市场的主线是什么",
            {"market_data", "mainline_context"},
            "direct_assessment",
        ),
    ),
)
def test_acceptance_questions_build_one_bounded_episode_contract(
    question: str,
    expected_capabilities: set[str],
    expected_output: str,
) -> None:
    control = TurnControlCore().control(
        question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="episode-test",
        capabilities=control.capabilities,
        tier="standard",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )

    contract = context.contract
    assert contract.task_frame_hash == control.task_frame.task_frame_hash
    assert contract.question_type == control.task_frame.question_type
    assert expected_output in {item.output_id for item in contract.required_outputs}
    assert expected_capabilities.issubset(contract.allowed_capabilities)
    assert set(contract.allowed_capabilities).issubset(RUNTIME_CAPABILITIES)
    assert set(contract.evidence_plan.mandatory_capabilities).issubset(
        contract.allowed_capabilities
    )
    assert context.policy.tier == "standard"
    assert context.deadline.synthesis_reserve == context.policy.synthesis_reserve
    assert context.today == "2026-07-22"
    assert context.latest_data_date == "2026-07-21"


def test_episode_factory_rejects_unknown_runtime_capability() -> None:
    control = TurnControlCore().control("昨天的反弹能持续多久")

    with pytest.raises(ValueError, match="unknown runtime capability"):
        build_episode_context(
            control.task_frame,
            task_id="episode-test",
            capabilities=(*control.capabilities, "shell"),
        )


def test_market_cause_requires_time_aligned_news_evidence() -> None:
    control = TurnControlCore().control(
        "这一周行情下跌的主要原因是什么",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="market-cause-evidence-plan",
        capabilities=control.capabilities,
    )

    assert context.contract.evidence_plan.profile == "time_aligned_market_causal"
    assert set(context.contract.evidence_plan.mandatory_capabilities) == {
        "market_data",
        "news_search",
    }


def test_stock_frame_with_measure_words_has_no_market_mandates() -> None:
    # R-20260821-05（生产 n=3）：stock_deep_dive + 「涨跌幅/成交额」曾命中盘面
    # 度量词被套上 mainline_current 市场级计划，market_data+mainline_context 进
    # mandatory——结构核验层据此每答必记 missing_mandatory_capability，修复轮
    # 还会把市场总览数字压进个股稿。契约不得再带这两条义务；但能力保持授权
    # （背景放大器可取）。live 路由是 LLM 给的 stock_deep_dive（启发式回退是
    # quick_fact），所以这里直接构造 frame 钉 live 形状。
    frame = TaskFrame(
        raw_question=(
            "皇氏集团最近两周（2026-08-06到2026-08-20）的走势复盘："
            "几个关键转折日各自的涨跌幅和成交额是多少？"
        ),
        user_goal="复盘个股近两周走势与关键转折日",
        question_type="stock_deep_dive",
        subject="皇氏集团",
        subject_kind="company",
        market_scope="A股",
        timeframe="2026-08-06到2026-08-20",
        required_outputs=(
            "direct_assessment",
            "supporting_evidence",
            "counterpoint",
        ),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_multi_layer_evidence",
        confidence=0.95,
    )

    context = build_episode_context(
        frame,
        task_id="episode-r05-stock",
        today="2026-08-21",
        latest_data_date="2026-08-20",
    )

    contract = context.contract
    assert contract.evidence_plan.profile == "company_current_backdrop"
    assert contract.evidence_plan.mandatory_capabilities == ()
    assert "market_data" in contract.allowed_capabilities
    assert "mainline_context" in contract.allowed_capabilities


def test_overnight_hybrid_forecast_episode_authorizes_news_and_web() -> None:
    control = TurnControlCore().control(
        "基于周二的盘面数据，你认为主线是什么。"
        "今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="overnight-hybrid-forecast",
        capabilities=control.capabilities,
    )

    assert control.task_frame.question_type == "market_forecast"
    assert {
        "market_data",
        "mainline_context",
        "news_search",
        "web_search",
    }.issubset(context.contract.allowed_capabilities)


def test_local_forecast_episode_does_not_authorize_news_or_web() -> None:
    control = TurnControlCore().control(
        "昨天的反弹能持续多久",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="local-forecast",
        capabilities=control.capabilities,
    )

    assert "news_search" not in context.contract.allowed_capabilities
    assert "web_search" not in context.contract.allowed_capabilities


def test_market_cause_uses_output_level_grounding_modes() -> None:
    control = TurnControlCore().control(
        "这一周行情下跌的主要原因是什么",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="market-cause-output-grounding",
        capabilities=control.capabilities,
    )

    modes = {
        item.output_id: item.grounding_mode
        for item in context.contract.required_outputs
    }
    assert modes == {
        "direct_assessment": "evidence",
        "causal_chain": "model_reasoning",
        "counterpoint": "evidence",
        "evidence_boundary": "evidence",
        "cause_attribution": "model_reasoning",
    }
    assert {"market_data", "news_search"}.issubset(
        context.contract.allowed_capabilities
    )
    assert context.contract.evidence_plan.profile == "time_aligned_market_causal"


def test_episode_timeout_override_cannot_inflate_policy_budget() -> None:
    control = TurnControlCore().control("昨天的反弹能持续多久")
    context = build_episode_context(
        control.task_frame,
        task_id="episode-test",
        capabilities=control.capabilities,
        tier="quick",
        timeout=300,
    )

    assert context.deadline.remaining() <= context.policy.total_seconds


def test_episode_context_can_reallocate_but_not_inflate_synthesis_reserve() -> None:
    control = TurnControlCore().control("目前市场的主线是什么")
    context = build_episode_context(
        control.task_frame,
        task_id="episode-test",
        capabilities=control.capabilities,
        tier="standard",
        timeout=90.0,
        synthesis_reserve=45.0,
    )

    assert context.policy.total_seconds == 90.0
    assert context.policy.synthesis_reserve == 45.0
    assert context.deadline.synthesis_reserve == 45.0
    assert context.deadline.remaining() <= 90.0
    assert context.deadline.stage_timeout(90.0) <= 45.0


def test_high_synthesis_reserve_keeps_one_third_for_research() -> None:
    control = TurnControlCore().control(
        "这一周行情下跌的主要原因是什么",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    context = build_episode_context(
        control.task_frame,
        task_id="market-cause-budget-balance",
        capabilities=control.capabilities,
        tier="standard",
        timeout=90.0,
        synthesis_reserve=75.0,
    )

    assert context.policy.synthesis_reserve == 60.0
    assert context.deadline.synthesis_reserve == 60.0
    assert context.root_budget is not None
    assert context.root_budget.initial_seconds == 30.0


def test_valuation_contract_has_current_anchor_scenarios_and_invalidation() -> None:
    control = TurnControlCore().control("瑞华泰的合理估值")
    context = build_episode_context(
        control.task_frame,
        task_id="valuation-contract",
        capabilities=("evidence_lookup",),
        timeout=30.0,
    )

    outputs = {
        item.output_id: item.description for item in context.contract.required_outputs
    }
    assert {
        "valuation_assessment",
        "financial_business_anchor",
        "scenario_range",
        "evidence_boundary",
        "invalidation_conditions",
    }.issubset(outputs)
    assert all(
        term in outputs["valuation_assessment"]
        for term in ("当前市场锚点", "方法", "假设")
    )
    assert "market_data" in context.contract.allowed_capabilities
    assert "financial_data" in context.contract.allowed_capabilities
    assert set(context.contract.evidence_plan.mandatory_capabilities) == {
        "market_data",
        "financial_data",
    }
    financial_anchor = next(
        item
        for item in context.contract.required_outputs
        if item.output_id == "financial_business_anchor"
    )
    assert financial_anchor.evidence_types[0] == "financial_data"
    assert "evidence_lookup" in financial_anchor.evidence_types
    assert "market_data" not in financial_anchor.evidence_types
    assert "web_search" not in financial_anchor.evidence_types


@pytest.mark.parametrize(
    ("question", "expected_mode"),
    (
        (
            "一个没有历史胜率的新题材，应该如何判断它是主线候选还是一天噪音",
            "model_reasoning",
        ),
        (
            "如果电力板块涨停家数很多但成交占比和核心股承接下降，还能算主线吗",
            "user_premise",
        ),
        ("目前市场的主线是什么", "evidence"),
    ),
)
def test_episode_factory_projects_task_semantics_into_grounding_modes(
    question: str,
    expected_mode: str,
) -> None:
    control = TurnControlCore().control(
        question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )

    context = build_episode_context(
        control.task_frame,
        task_id="grounding-mode-test",
        capabilities=control.capabilities,
    )

    assert {
        item.grounding_mode for item in context.contract.required_outputs
    } == {expected_mode}
    if expected_mode in {"model_reasoning", "user_premise"}:
        assert context.contract.allowed_capabilities == ()
        assert context.contract.evidence_plan.requirements == ()


def test_outlook_judgment_direct_answer_uses_model_reasoning() -> None:
    """观点题的判断槽走 model_reasoning；边界槽与检索保持 evidence。

    生产 run_20260816_102941 / 103318：同一句「你认为周一的机会在哪」被押进
    evidence 硬边界，judge 按句剥光判断正文后仍 completed。第一刀只改判断槽，
    不把整题标成 evidence-free（那会清掉本次已经取到的行情检索）。
    """

    control = TurnControlCore().control(
        "基于8.15的行情现状，你认为周一的机会在哪",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    context = build_episode_context(
        control.task_frame,
        task_id="outlook-judgment-direct-answer",
        capabilities=control.capabilities,
    )

    modes = {
        item.output_id: item.grounding_mode
        for item in context.contract.required_outputs
    }
    assert control.task_frame.question_type == "general_finance_qa"
    assert modes["direct_answer"] == "model_reasoning"
    assert modes["evidence_boundary"] == "evidence"
    assert context.contract.allowed_capabilities != ()


def test_forecast_condition_slots_use_model_reasoning() -> None:
    """前瞻题的条件槽是向前假设，签 model_reasoning；事实与边界槽保持 evidence。

    2026-08-19 分层审查：情景路径与持续/证伪条件按定义不可能出现在既有证据里
    （证据不含未来），押进 evidence 后数值门禁把「若指数跌破3870点则失效」这类
    可操作阈值整句砍掉，模型学会只输出「相对变化描述」自保。只改条件槽。
    """

    control = TurnControlCore().control(
        "昨天的反弹能持续多久",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    context = build_episode_context(
        control.task_frame,
        task_id="forecast-condition-slots",
        capabilities=control.capabilities,
    )

    modes = {
        item.output_id: item.grounding_mode
        for item in context.contract.required_outputs
    }
    assert control.task_frame.question_type == "market_forecast"
    assert modes["continuation_conditions"] == "model_reasoning"
    assert modes["invalidation_conditions"] == "model_reasoning"
    # 事实槽与边界槽不动：现状基线、持续性评估仍要求行情证据。
    assert modes["current_baseline"] == "evidence"
    assert modes["duration_assessment"] == "evidence"
    assert modes["evidence_boundary"] == "evidence"


def test_technical_invalidation_slot_stays_evidence() -> None:
    """market_technical 的失效位来自行情数据（支撑/均线可查），不吃前瞻豁免。"""

    control = TurnControlCore().control(
        "科创50的支撑点位在哪",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    context = build_episode_context(
        control.task_frame,
        task_id="technical-invalidation-evidence",
        capabilities=control.capabilities,
    )

    modes = {
        item.output_id: item.grounding_mode
        for item in context.contract.required_outputs
    }
    assert control.task_frame.question_type == "market_technical"
    assert modes["invalidation_conditions"] == "evidence"


def test_default_conditional_goal_does_not_flip_fact_or_valuation_slots() -> None:
    """``形成条件化判断`` 是 query_understanding 的默认 decision_goal，不能当路由键。"""

    for task_id, question, judgment_slot in (
        ("outlook-guard-limit-up", "2026-08-14涨停家数多少", "fact_value"),
        ("outlook-guard-valuation", "瑞华泰的合理估值", "valuation_assessment"),
    ):
        control = TurnControlCore().control(
            question,
            llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
        )
        context = build_episode_context(
            control.task_frame,
            task_id=task_id,
            capabilities=control.capabilities,
        )
        assert control.task_frame.user_goal == "形成条件化判断"
        modes = {
            item.output_id: item.grounding_mode
            for item in context.contract.required_outputs
        }
        assert modes[judgment_slot] == "evidence"
        assert "model_reasoning" not in set(modes.values())


def test_outlook_forecast_flips_judgment_and_condition_slots_not_boundaries() -> None:
    """观点措辞翻判断槽，前瞻题型翻条件槽；边界/结构槽两条规则都不碰。

    2026-08-16 第一刀只改判断槽（scenario_paths 当时保持 evidence）；
    2026-08-19 分层审查加了第二刀：前瞻条件槽按题型签 model_reasoning。
    scenario_tree / evidence_boundary 仍是 evidence，证明两条规则都没扩散。
    """

    control = TurnControlCore().control(
        "你觉得a股明天会怎么走",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    context = build_episode_context(
        control.task_frame,
        task_id="outlook-forecast-judgment-slot",
        capabilities=control.capabilities,
    )

    modes = {
        item.output_id: item.grounding_mode
        for item in context.contract.required_outputs
    }
    assert modes["direct_assessment"] == "model_reasoning"
    assert modes["scenario_paths"] == "model_reasoning"
    assert modes["continuation_conditions"] == "model_reasoning"
    assert modes["invalidation_conditions"] == "model_reasoning"
    assert modes["evidence_boundary"] == "evidence"
    assert modes["scenario_tree"] == "evidence"
    assert context.contract.allowed_capabilities != ()


def _prior_recall_context(question: str, task_id: str):
    control = TurnControlCore().control(
        question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    return build_episode_context(
        control.task_frame,
        task_id=task_id,
        capabilities=control.capabilities,
    )


@pytest.fixture
def anchored_wiki(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """密封的实体词典：个股口径的路由依赖 wiki 实体锚定。

    「中际旭创…」那条参数化用例出生即红：题材口径走仓内
    ``config/theme_research_specs.json``，个股口径要靠
    ``relations/entity_exposures.json`` 锚定——而测试会话密封了
    ``KNOWLEDGE_WIKI``，默认路径又不存在，实体锚不上 → 落进
    general_finance_qa（capabilities 为空）→ 槽位永远开不出来。
    红的是环境不是产品：注入词典后生产逻辑原样通过。

    缓存安全：entity_anchor / query_resolution 的词典缓存按
    「解析路径 + 文件指纹」为键，tmp_path 每个用例唯一，不串台。
    """

    import json

    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "中际旭创": {
                        "codes": ["300308.SZ"],
                        "concepts": {"光模块": {}},
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relations / "aliases.json").write_text(
        json.dumps({"aliases": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("KNOWLEDGE_WIKI", str(tmp_path))


@pytest.mark.parametrize(
    "question",
    (
        "液冷题材现在怎么看？我之前的判断还成立吗",
        "我过去对液冷是怎么判断的？先查我自己的历史判断和纠偏原则",
        "液冷题材我之前的看法还成立吗",
        # 个股口径也要覆盖：stock_deep_dive 与 theme_analysis 走的是同一个闸门，
        # 只测题材会漏掉「授权了三条策略但只有一条真能开槽」这种半截实现。
        "中际旭创我之前的判断还成立吗",
    ),
)
def test_prior_reference_opens_a_user_premise_slot_for_the_recall(
    question: str,
    anchored_wiki: None,
) -> None:
    """引用了自己过去看法的问题，必须有一格能装那份先验。

    这条测试存在的理由是两次真实 run（`221010` 泛问、`221845` 明确点名「先查我自己
    的历史判断」）：`memory_lookup` 当时已授权、已注册、召回也验过，模型**一次都没
    调它**。根因不在措辞——那时全部 required output 都是 `grounding=evidence`，而该
    工具的产出按设计标着「不是市场事实、不能当作证据引用」，调回来一格也填不进去。
    在 4 次工具预算下不调它才是理性选择。

    所以断言的是**契约里有落点**，而不是「提示词里提到了记忆」。
    """

    context = _prior_recall_context(question, "prior-recall-inject")

    slot = next(
        (
            item
            for item in context.contract.required_outputs
            if item.output_id == "prior_recall"
        ),
        None,
    )
    assert slot is not None, (
        "引用了历史判断却没有 prior_recall 槽位——memory_lookup 的产出将再次无处可绑，"
        "模型会重复那两次真实 run 里的理性回避。"
    )
    # user_premise 而不是 evidence：这一格装的是用户自己的历史判断，不是当前世界
    # 事实。标成 evidence 会要求它有市场证据支撑（自相矛盾），也会让这份先验可以
    # 反过来去支撑别的结论——那正是工具描述里禁止的事。
    assert slot.grounding_mode == "user_premise"
    # required=False 是有意的：生产 users 根下 24 个 user 的台账全是空的
    # （judgments=0）。设 True 会让每一个题材类问答都因为绑不上这一格而降级
    # partial——把一个增益特性变成全局回归。
    assert slot.required is False
    # 授权与槽位必须同时成立，否则是半截状态：有格子但没工具，或反之。
    assert "memory_lookup" in context.contract.allowed_capabilities


@pytest.mark.parametrize(
    ("question", "why"),
    (
        ("液冷题材现在怎么看", "泛问：没有引用任何历史判断"),
        ("液冷的产业链结构是什么", "结构题：与用户先验无关"),
        ("固态电池现在的强度排名", "取值查询：不该背一个先验槽位"),
    ),
)
def test_questions_without_a_prior_reference_get_no_recall_slot(
    question: str,
    why: str,
) -> None:
    """没引用历史判断就不注入——这一条比上面那条更重要。

    无条件注入会给每道题多加一格必须交付的内容，而绝大多数问题里用户并没有可复述
    的先验；模型要么编一段「你此前认为…」，要么每次多烧一次工具预算去查一个注定
    空手的台账。实测预算只有 4 次（``MAX_BATCH_TOOL_CALLS``），一次空查就是 25%。
    """

    context = _prior_recall_context(question, f"prior-recall-skip-{hash(question)}")

    assert "prior_recall" not in {
        item.output_id for item in context.contract.required_outputs
    }, f"不该注入却注入了（{why}）"


def test_prior_recall_slot_is_scoped_to_subject_bearing_question_types() -> None:
    """题型闸门：只有「用户可能对该主体表达过看法」的题才开 prior_recall。

    与公司深挖 / 题材 / 题材跟踪三条策略上的 memory_lookup 授权配对。
    residual 的 general_finance_evidence 现在也授权 memory_lookup，但开的是
    prime_memory，不是这一格。取值查询和预测题即使句子里出现「我之前」，
    也不注入 prior_recall——前者的契约是 (值/口径日期/证据边界)，后者要的是
    条件化情景，都不该被一段历史先验占掉预算。
    """

    for question_type, question in (
        ("quick_fact", "我之前看的那个收盘价是多少"),
        ("market_forecast", "我之前的判断还成立吗，明天大盘怎么走"),
    ):
        context = _prior_recall_context(question, f"prior-recall-scope-{question_type}")
        assert "prior_recall" not in {
            item.output_id for item in context.contract.required_outputs
        }, f"{question_type} 不该带 prior_recall 槽位"


def test_trade_advice_stance_opens_prior_recall_when_memory_is_authorized() -> None:
    from intelligence.services.evidence_capabilities import runtime_capabilities_for_frame
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.task_frame import TaskFrame

    frame = TaskFrame(
        raw_question="茅台现在该不该买",
        user_goal="给出条件化加减仓判断",
        question_type="trade_advice",
        subject="茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="最新可用日期",
        required_outputs=("conditional_thesis", "invalidation_conditions"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="conditional_thesis_evidence",
        confidence=0.9,
    )
    context = build_episode_context(
        frame,
        task_id="prior-recall-trade-advice",
        capabilities=runtime_capabilities_for_frame(frame),
    )
    assert "memory_lookup" in context.contract.allowed_capabilities
    assert "prior_recall" in {
        item.output_id for item in context.contract.required_outputs
    }


def test_prior_recall_stays_absent_where_the_tool_is_unauthorized() -> None:
    """已知缺口，写成测试而不是留在脑子里。

    「跟我上次说的比，液冷题材变了什么」这句话在语义上百分之百引用了用户先验，
    但 ``TurnControlCore`` 把它路由成 ``comparison_analog``（历史类比题），对应
    ``comparable_multi_source_evidence``——那条策略**没有授权 memory_lookup**。

    所以这里刻意断言「不注入」。为了让语义直觉变绿而把 ``comparison_analog`` 加进
    ``_PRIOR_RECALL_QUESTION_TYPES``，会造出一个有格子却没工具的契约：模型看到
    ``prior_recall`` 这一格，但工具清单里没有能填它的东西，只能编或者留空——
    正是「授权 / 槽位」这对东西只做一半的形状。

    这条测试变红有两种正当原因，都要求成对修改：
      1. 该题型加了 ``memory_lookup`` 授权 → 同时把它加进槽位题型，改这里的期望；
      2. 路由改了，这句话不再落 ``comparison_analog`` → 换一个仍落该题型的句子。
    """

    context = _prior_recall_context(
        "跟我上次说的比，液冷题材变了什么",
        "prior-recall-unauthorized",
    )

    assert context.contract.question_type == "comparison_analog"
    assert "memory_lookup" not in context.contract.allowed_capabilities
    assert "prior_recall" not in {
        item.output_id for item in context.contract.required_outputs
    }, (
        "在没有授权 memory_lookup 的题型上开了 prior_recall 槽位——"
        "模型会看到一格自己无法用工具填充的必需内容。"
    )
