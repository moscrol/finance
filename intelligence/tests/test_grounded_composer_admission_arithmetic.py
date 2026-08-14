"""合成尾段（composer+judge）的准入是**算术**，不是竞速。

为什么值得单独一个文件：run_20260805_204224_708450 的现场读起来像「预算被吃光」——
composer 入场时只剩 59.9s，trace 记 ``insufficient_budget``，像是研究跑慢了。但把数摆开
之后没有任何竞速成分：

    generic owner 的检索窗口 = min(root 180, for_tier("standard").total 90) = 90s
    两段式准入地板       = composer_grant 40 + judge_reserve 57      = 97s
    90 < 97

于是 standard tier 的 composer **恒**进不去，研究耗时为 0 也一样。真正的错位是范畴错误：
composer/judge 是 turn 的合成尾段，本该由根 turn 的 synthesis_reserve 供给，却被记在了
owner 的检索窗口里，而地板是按根 180s 标定的——发钱的和收钱的不是同一个信封。

这里钉的是不变量而不是某次跑通。断言全部落在「两个数之间的关系」上，所以将来谁再动
``composer_grant_seconds`` / ``judge_reserve_seconds`` / 供给信封，红的是断言而不是线上：

1. 地板必须恰好等于两段之和（不是另拍的常量）；
2. owner 检索窗口单独供给时，quick/standard 必然装不下——这是回归见证，同时说明
   「把 for_tier 的 90 抬上去」是错的杠杆（那把尺子正被 benchmark 用作 A/B 基线）；
3. 根信封供给时，三个 tier 全部可准入；
4. ``for_tier`` 那张表和 benchmark 的 profile 保持原值——反向锁。
"""

from __future__ import annotations

import pytest

from intelligence.services import ask, ask_synthesis, llm_refine
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchPolicy,
)
from intelligence.services.research_policy import grounded_deep
from intelligence.tests.test_synthesis_phase_observability import (
    _fake_chain,
    _result,
)

_TIERS = ("quick", "standard", "deep")

# 观测到的研究段耗时（run_20260805_204224_708450：generic owner 29,996ms）。
# 用真实值而不是 0，是为了让「即使研究很快也进不去」这件事以现场数据成立。
_OBSERVED_RESEARCH_SECONDS = 30.0


def _owner_retrieval_window(tier: str) -> float:
    """generic owner 实际拿到的检索窗口。

    与 ``_generic_research_deadline`` 同构：owner 档位预算被钳到根 turn，
    所以 deep 的 240s 实际只有 180s。
    """

    return min(
        ResearchPolicy.for_tier(tier).total_seconds,
        grounded_deep.root_seconds,
    )


def _root_synthesis_window() -> float:
    """合成尾段从根 turn 拿到的窗口上限（``child_seconds`` 封顶单段用量）。"""

    return min(grounded_deep.child_seconds, grounded_deep.root_seconds)


class TestAdmissionFloorArithmetic:
    """地板不是拍出来的第三个数，它必须等于它所保护的两段之和。"""

    def test_floor_is_exactly_grant_plus_judge_reserve(self) -> None:
        assert grounded_deep.minimum_two_phase_entry_seconds == (
            grounded_deep.composer_grant_seconds
            + grounded_deep.judge_reserve_seconds
        )

    @pytest.mark.parametrize("tier", _TIERS)
    def test_owner_retrieval_window_alone_cannot_fund_two_phase(
        self, tier: str
    ) -> None:
        """回归见证：靠 owner 检索窗口供给时，只有 deep 装得下。

        这条断言同时是一道**杠杆锁**：它说明修复不能去抬 ``for_tier`` 的
        total_seconds——那张表正被 benchmark 的 ``HEADLESS_BUDGET_PROFILES``
        与 ``_fresh_context`` 用作「复现生产 30/90」的 A/B 基线，动它等于动尺子。
        """

        window = _owner_retrieval_window(tier)
        floor = grounded_deep.minimum_two_phase_entry_seconds
        if tier == "deep":
            assert window >= floor
        else:
            assert window < floor

    @pytest.mark.parametrize("tier", _TIERS)
    def test_root_envelope_funds_two_phase_for_every_tier(
        self, tier: str
    ) -> None:
        """根信封供给时三个 tier 全部可准入，且扣掉研究耗时后仍成立。"""

        available = min(
            _root_synthesis_window(),
            grounded_deep.root_seconds - _OBSERVED_RESEARCH_SECONDS,
        )
        assert available >= grounded_deep.minimum_two_phase_entry_seconds

    def test_admitted_window_still_leaves_the_measured_judge_reserve(
        self,
    ) -> None:
        """准入后 composer 拿满额，judge 的 57s 不被 composer 侵占。"""

        grant = min(
            grounded_deep.composer_grant_seconds,
            _root_synthesis_window() - grounded_deep.judge_reserve_seconds,
        )
        assert grant == grounded_deep.composer_grant_seconds

    def test_two_phase_tail_fits_inside_the_root_turn(self) -> None:
        """放开准入不得突破根 turn：研究 + 两段合成必须仍在 180s 内。"""

        assert (
            _OBSERVED_RESEARCH_SECONDS
            + grounded_deep.minimum_two_phase_entry_seconds
        ) <= grounded_deep.root_seconds


class TestSynthesisEnvelopeSourcing:
    """``_shadow_deadline`` 该从哪个信封取父截止时间。"""

    @pytest.mark.parametrize("tier", _TIERS)
    def test_synthesis_envelope_supersedes_owner_retrieval_window(
        self, tier: str
    ) -> None:
        options = ask.AskOptions(
            query="占位",
            shadow_grounded_timeout=int(_root_synthesis_window()),
            deadline=ResearchDeadline.from_timeout(
                _owner_retrieval_window(tier) - _OBSERVED_RESEARCH_SECONDS
            ),
            synthesis_deadline=ResearchDeadline.from_timeout(
                grounded_deep.root_seconds - _OBSERVED_RESEARCH_SECONDS
            ),
        )

        remaining = ask_synthesis._shadow_deadline(options).remaining()

        assert remaining >= grounded_deep.minimum_two_phase_entry_seconds

    def test_owner_window_still_clamps_when_no_synthesis_envelope(self) -> None:
        """未注入合成信封的调用方保持旧行为，不被这次改动波及。"""

        options = ask.AskOptions(
            query="占位",
            shadow_grounded_timeout=grounded_deep.child_seconds,
            deadline=ResearchDeadline.from_timeout(20.0),
        )

        assert ask_synthesis._shadow_deadline(options).remaining() <= 20.0

    def test_child_never_outlives_the_synthesis_envelope(self) -> None:
        """child = min(parent, now + stage_slice) 这条规则不能因为换信封而松掉。"""

        options = ask.AskOptions(
            query="占位",
            shadow_grounded_timeout=10_000,
            synthesis_deadline=ResearchDeadline.from_timeout(12.0),
        )

        assert ask_synthesis._shadow_deadline(options).remaining() <= 12.0


class TestAdmissionBehaviourPerTier:
    """把算术接到真实准入路径上——断言的是 skip/admit，不是某次 provider 跑通。"""

    @pytest.mark.parametrize("tier", _TIERS)
    def test_composer_is_admitted_for_every_tier_with_root_envelope(
        self, tier: str, monkeypatch
    ) -> None:
        result = _result()
        spec = result.answer_spec
        assert spec is not None
        fake = _fake_chain(spec)
        timeouts: list[float] = []

        def captured(messages, **kwargs):
            timeouts.append(kwargs["timeout"])
            return fake(messages, **kwargs)

        monkeypatch.setattr(llm_refine, "synthesize_messages", captured)
        monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

        ask_synthesis.synthesize_shadow_grounded_answer(
            ask.PreparedAnswer(
                options=ask.AskOptions(
                    query=result.query,
                    shadow_grounded_composer=True,
                    shadow_grounded_timeout=int(_root_synthesis_window()),
                    deadline=ResearchDeadline.from_timeout(
                        _owner_retrieval_window(tier)
                        - _OBSERVED_RESEARCH_SECONDS
                    ),
                    synthesis_deadline=ResearchDeadline.from_timeout(
                        grounded_deep.root_seconds - _OBSERVED_RESEARCH_SECONDS
                    ),
                    grounded_budget_profile=grounded_deep,
                ),
                result=result,
            ),
            repair_drop_invalid=True,
        )

        phases = {phase.name: phase for phase in result.synthesis_phases}
        assert "composer" in phases
        assert phases["composer"].status == "ok"
        assert phases["composer"].reason_code == ""
        assert timeouts[0] == grounded_deep.composer_grant_seconds

    @pytest.mark.parametrize("tier", ("quick", "standard"))
    def test_composer_skipped_when_only_the_owner_window_funds_it(
        self, tier: str, monkeypatch
    ) -> None:
        """同一套代码、同一个 tier，只换供给信封就从 skip 变 admit。

        这条把病因钉在「信封」而不是「研究太慢」上：两个用例的研究耗时完全相同。
        """

        result = _result()
        assert result.answer_spec is not None

        def must_not_call(messages, **kwargs):
            raise AssertionError("预算不足时不应发起 provider 调用")

        monkeypatch.setattr(llm_refine, "synthesize_messages", must_not_call)

        ask_synthesis.synthesize_shadow_grounded_answer(
            ask.PreparedAnswer(
                options=ask.AskOptions(
                    query=result.query,
                    shadow_grounded_composer=True,
                    shadow_grounded_timeout=int(_root_synthesis_window()),
                    deadline=ResearchDeadline.from_timeout(
                        _owner_retrieval_window(tier)
                        - _OBSERVED_RESEARCH_SECONDS
                    ),
                    grounded_budget_profile=grounded_deep,
                ),
                result=result,
            ),
        )

        phases = {phase.name: phase for phase in result.synthesis_phases}
        assert phases["composer"].status == "skipped"
        assert phases["composer"].reason_code == "insufficient_budget"

    def test_profile_is_read_from_options_not_module_global(
        self, monkeypatch
    ) -> None:
        """地板与授时读生效 profile；抬高地板必须立刻改变准入判定。

        这是「门槛和发钱的那套绑在一起」的可执行证据：模块级常量说 97 能进，
        而生效 profile 说 200 不能进，最终以生效 profile 为准。
        """

        from dataclasses import replace as dataclass_replace

        strict = dataclass_replace(
            grounded_deep,
            minimum_two_phase_entry_seconds=200,
        )
        result = _result()
        assert result.answer_spec is not None

        def must_not_call(messages, **kwargs):
            raise AssertionError("地板未满足时不应发起 provider 调用")

        monkeypatch.setattr(llm_refine, "synthesize_messages", must_not_call)

        ask_synthesis.synthesize_shadow_grounded_answer(
            ask.PreparedAnswer(
                options=ask.AskOptions(
                    query=result.query,
                    shadow_grounded_composer=True,
                    shadow_grounded_timeout=int(_root_synthesis_window()),
                    synthesis_deadline=ResearchDeadline.from_timeout(
                        grounded_deep.root_seconds - _OBSERVED_RESEARCH_SECONDS
                    ),
                    grounded_budget_profile=strict,
                ),
                result=result,
            ),
        )

        phases = {phase.name: phase for phase in result.synthesis_phases}
        assert phases["composer"].status == "skipped"
        assert phases["composer"].reason_code == "insufficient_budget"


class TestBenchmarkRulerIsUntouched:
    """A/B 那把尺子（复现生产 30/90）不能被这次修复连带改动。"""

    def test_for_tier_table_still_reads_30_90_240(self) -> None:
        assert ResearchPolicy.for_tier("quick").total_seconds == 30.0
        assert ResearchPolicy.for_tier("standard").total_seconds == 90.0
        assert ResearchPolicy.for_tier("deep").total_seconds == 240.0
        assert ResearchPolicy.for_tier("standard").synthesis_reserve == 20.0

    def test_benchmark_else_branch_reserve_is_unchanged(self) -> None:
        """``_fresh_context`` 非 GLM 分支那 30s 是尺子的一部分，别动。"""

        policy = ResearchPolicy.for_tier("standard")
        assert min(
            policy.total_seconds * 0.4,
            max(policy.synthesis_reserve, 30.0),
        ) == 30.0
