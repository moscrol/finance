"""market_watch 公开稿未注册阈值删句（R-20260824-04，盘面包 spec §7.4 #10）。

残差/正文分句里出现 MA20、110–120% 带、「旗型蓄能」这类未进本轮证据册的
方法阈值时整句删除、不留质检条；包渲染（grid）里真实在场的同类语言不删。
探针行与锁格来自包渲染、在闸之外，永不受删。
"""

from __future__ import annotations

from pathlib import Path

from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.market_watch_pack import (
    ProbeReceipt,
    render_probe_lines,
)
from intelligence.services.outlook_delivery_gate import (
    apply_market_watch_delivery_gate,
)
from intelligence.tests.test_market_watch_component_first import (
    _prepare_watch_turn,
)
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
)
from intelligence.workbench_skills.registry import SkillRegistry
from intelligence.workbench_skills.router import SkillRouteResult, SkillSelection


CLEAN = "缩量普涨，宽度在电，总量在均额之下。"
MA20_CLAUSE = "按该视角框架，MA20量能远未到位，属于反弹而非主升。"
BAND_CLAUSE = "量能需要回到110-120%区间才升级。"
FLAG_CLAUSE = "形态上更像旗型蓄能，等待方向选择。"


def test_drops_unregistered_method_clauses_for_market_watch() -> None:
    text = CLEAN + MA20_CLAUSE + BAND_CLAUSE + FLAG_CLAUSE
    receipt = apply_market_watch_delivery_gate(
        text,
        question_type="market_watch",
        grid_text="总量袋 served_date=2026-07-23：21949.97 亿。",
    )
    assert receipt.applied
    assert receipt.dropped == 3
    assert receipt.text == CLEAN
    assert "MA20" not in receipt.text
    assert "旗型蓄能" not in receipt.text
    # 删句不留质检条。
    assert "质检" not in receipt.text


def test_keeps_method_language_registered_in_grid() -> None:
    receipt = apply_market_watch_delivery_gate(
        CLEAN + BAND_CLAUSE,
        question_type="market_watch",
        grid_text="证据册：该视角量能带 110-120% 已注册在案。",
    )
    assert receipt.applied
    assert receipt.dropped == 0
    assert BAND_CLAUSE in receipt.text


def test_other_question_types_are_not_expanded() -> None:
    text = CLEAN + FLAG_CLAUSE
    receipt = apply_market_watch_delivery_gate(
        text,
        question_type="theme_analysis",
        grid_text="",
    )
    assert not receipt.applied
    assert receipt.dropped == 0
    assert receipt.text == text


def test_probe_lines_pass_gate_unchanged() -> None:
    rendered = "\n".join(
        render_probe_lines(
            (
                ProbeReceipt(
                    trigger="主线题材「医药」当日无严格双红匹配",
                    requested_date="2026-08-24",
                    served_date="2026-08-24",
                    status="hit",
                    rows=(
                        {
                            "sector_name": "医药医疗",
                            "sector_amount": 1556.85,
                            "stock_name": "药明康德",
                            "stock_code": "603259",
                        },
                    ),
                    role="出清/分歧观察",
                ),
            )
        )
    )
    receipt = apply_market_watch_delivery_gate(
        rendered,
        question_type="market_watch",
        grid_text="",
    )
    assert receipt.text == rendered
    assert receipt.dropped == 0


def test_orchestrator_strips_owner_prose_threshold_clauses(tmp_path: Path) -> None:
    """接线测试：owner 正文里的未注册阈值句在公开稿被删，锁格与干净句保留。"""

    query = "2026-07-23 今天市场怎么样"
    conversation_store, run_store, conversation_id, run_id, assistant_id = (
        _prepare_watch_turn(tmp_path, query)
    )

    class DailyReviewOwner:
        skill_id = "daily-review"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            del context
            modules = [
                {
                    "type": "summary",
                    "summary": (
                        "日报正文：结构以电为主。"
                        "按框架MA20量能远未到位，属于反弹。"
                        "量能回到110-120%区间才升级。"
                        "形态上像旗型蓄能，等待方向。"
                    ),
                    "metrics": [],
                    "items": [],
                }
            ]
            citations = [
                {
                    "source": "2026-07-23-daily-review.md",
                    "title": "指定日日报",
                    "evidence_layer": "canonical",
                    "as_of": "2026-07-23",
                }
            ]
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-23",
                raw_result_ref=None,
                answer_contract=build_module_answer_contract(
                    skill_id=self.skill_id,
                    title="每日复盘",
                    modules=modules,
                    citations=citations,
                    warnings=[],
                    as_of="2026-07-23",
                    retrieval_plan=("读取指定日日报",),
                    output_contract=("输出复盘结构",),
                ),
            )

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="daily-review",
            name="每日复盘",
            description="fixture owner",
            version="1.0.0",
            triggers=("复盘",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
            role="workflow",
            can_own_answer=True,
        ),
        DailyReviewOwner(),
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: (_ for _ in ()).throw(
            AssertionError(f"owner path must not call ask: {options.query}")
        ),
        route_skills_fn=lambda *_args, **_kwargs: SkillRouteResult(
            (SkillSelection("daily-review", "rule", "fixture"),),
            fallback_to_ask=False,
        ),
        skill_registry=registry,
    ).run_turn(
        conversation_id=conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    # 锁格与干净正文仍在。
    assert "21949.97" in result.content
    assert "电力设备" in result.content
    assert "日报正文：结构以电为主" in result.content
    # 未注册阈值句被整句删除，且不留质检条。
    assert "MA20" not in result.content
    assert "110-120%" not in result.content
    assert "旗型蓄能" not in result.content
    assert "质检" not in result.content
    # 删句以 degrade 收据入账，不进正文。
    run = run_store.load_run(run_id)
    assert "market_watch_delivery_gate" in list(run.degrades)
