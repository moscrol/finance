"""判官删句不得静默连坐真值。离线锁。

Gate 1 实锤（`docs/verification/2026-08-21-gate1-pcb-exact-name.md` §Live 第 3 层）：
判官把「缩量洗盘后主升」整段判未核验删掉，真值 4.74/3432.59 绑在那段里一起没了，
活下来的反而是错口径的句子。

三筛自审（`harness-reference/PLAYBOOK.md` §约束三筛）：
- 本刀**不给含真值的句子发免死金牌**——那会让编造搭真数的便车（变错，必须硬）
- 本刀拦的是**信息丢失**，不是模型的表达 → 拦输入侧，保下限
- 模型变强一倍：误删仍可能发生，但真值不再丢 → 不挡路，反而缓解
"""

from __future__ import annotations

from intelligence.services.agent_research import (
    AgentEvidence,
    StructuredObservation,
    evidence_content_hash,
    grounded_values_in_text,
)
from intelligence.services.episode_semantic_verifier import (
    _gaps_with_lost_observations,
)

TIMELINE = AgentEvidence(
    tool="market_data",
    title="PCB概念 双红时间轴",
    detail="交易日=2026-08-07；涨跌幅=4.74；成交额亿=3432.59；边际量=23.72；双红=是",
    source="本地 DuckDB · 问句日预取",
    source_date="2026-08-07",
    observations=(
        StructuredObservation(
            subject="PCB概念", as_of="2026-08-07", metric="pct_chg", value=4.74
        ),
        StructuredObservation(
            subject="PCB概念", as_of="2026-08-07", metric="amount", value=3432.59
        ),
    ),
)

# Gate 1 的形状：真值和未核验叙述绑在同一段
BEFORE = (
    "08-07 该板块涨 4.74%，成交额 3432.59 亿。"
    "缩量洗盘后主升，主力资金持续净流入三日。"
)
AFTER = "08-07 该板块涨 4.74%，成交额 3432.59 亿。"
AFTER_WIPED = "本题证据不足。"


def test_grounded_values_are_found_by_exact_token() -> None:
    hits = grounded_values_in_text(BEFORE, (TIMELINE,))
    assert {obs.value for obs in hits} == {4.74, 3432.59}


def test_near_miss_number_is_not_counted_as_grounded() -> None:
    """从严：4.7 不算命中 4.74。宁可少报（变笨）也不误报（变错）。

    误报会把没被删的数当成缺口，反过来污染缺口统计。
    """

    assert grounded_values_in_text("涨了 4.7%，成交 3432.6 亿", (TIMELINE,)) == ()


def test_surviving_values_do_not_become_gaps() -> None:
    """只删了未核验那句、真值还在稿子里 → 不记缺口，不制造噪声。"""

    gaps = _gaps_with_lost_observations(
        gaps=(), before=BEFORE, after=AFTER, evidence=(TIMELINE,)
    )
    assert gaps == ()


def test_collateral_truth_becomes_a_gap_not_silence() -> None:
    """真值随整段被删 → 必须落成缺口，且写明真值本身，供下游按槽重呈。"""

    gaps = _gaps_with_lost_observations(
        gaps=(), before=BEFORE, after=AFTER_WIPED, evidence=(TIMELINE,)
    )
    assert len(gaps) == 2
    joined = "\n".join(gaps)
    assert "4.74" in joined and "3432.59" in joined
    assert "PCB概念" in joined and "2026-08-07" in joined
    # 缺口要说清「有据但被连坐」，不能读成「没有数据」
    assert "有据" in joined and "不得当作无数据" in joined


def test_删除决定不受影响_编造不得搭真数便车() -> None:
    """本刀只补记缺口，**不回写 after**——含真值的句子没有免死金牌。

    一旦它能把 after 改回去，绑在同句的编造就跟着复活，
    那正是把「保下限」做成了「封上限」的反面：拦错了对象。
    """

    gaps = _gaps_with_lost_observations(
        gaps=("既有缺口",), before=BEFORE, after=AFTER_WIPED, evidence=(TIMELINE,)
    )
    # 返回的是缺口元组，不是稿件；结构上就没有改写正文的入口
    assert isinstance(gaps, tuple)
    assert all(isinstance(item, str) for item in gaps)
    assert gaps[0] == "既有缺口"


def test_evidence_hash_unchanged_by_observations() -> None:
    """挂上 observations 不得改变既有证据身份（哈希只吃 tool/title/detail/source）。"""

    bare = AgentEvidence(
        tool=TIMELINE.tool,
        title=TIMELINE.title,
        detail=TIMELINE.detail,
        source=TIMELINE.source,
    )
    assert evidence_content_hash(bare) == evidence_content_hash(TIMELINE)


# ── 第 3 刀：槽把连坐掉的真值补回稿件 ───────────────────────────────


def test_slot_line_is_system_written_facts_only() -> None:
    """槽行只有数值，没有任何叙述——被驳回的因果不会借尸还魂。"""

    from intelligence.services.episode_semantic_verifier import (
        slot_line_for_observations,
    )

    line = slot_line_for_observations(TIMELINE.observations)
    assert "PCB概念 2026-08-07" in line
    assert "涨跌幅=4.74" in line and "成交额亿=3432.59" in line
    # 被判官驳回的那句叙述不得随槽回来
    assert "洗盘" not in line and "主升" not in line and "净流入" not in line


def test_collateral_truth_is_restored_into_draft() -> None:
    """Gate 1 的形状：整段被删后，真值必须以槽的形态回到稿子里。

    这条直接对应账本 R-20260821-04 的验证条件。
    """

    from intelligence.services.episode_semantic_verifier import (
        _restore_lost_observations,
    )

    draft, restored = _restore_lost_observations(
        draft=AFTER_WIPED, before=BEFORE, evidence=(TIMELINE,)
    )
    assert {obs.value for obs in restored} == {4.74, 3432.59}
    assert "4.74" in draft and "3432.59" in draft
    # 原有内容不动，只在末尾追加槽行
    assert draft.startswith(AFTER_WIPED)
    assert "洗盘" not in draft and "净流入" not in draft


def test_no_restore_when_values_survived() -> None:
    """真值还在稿里就不补——不制造重复数字。"""

    from intelligence.services.episode_semantic_verifier import (
        _restore_lost_observations,
    )

    draft, restored = _restore_lost_observations(
        draft=AFTER, before=BEFORE, evidence=(TIMELINE,)
    )
    assert restored == ()
    assert draft == AFTER


# ── 第 4 刀：数值门禁认结构化观察值，不因忘绑引用就判真话为编造 ──────


def _outcome_with(evidence, *, bindings=()):
    """``_bound_evidence_quantities`` 只读 ``.evidence`` / ``.bindings`` 两个属性。

    真 ``AgentOutcome`` 对 events 序列有强校验，为这两个属性去造合法 events
    只会把夹具写成噪声；替身在此是**窄接口**，不是绕过契约。
    """

    from types import SimpleNamespace

    return SimpleNamespace(evidence=tuple(evidence), bindings=tuple(bindings))


def test_structured_observation_counts_without_binding() -> None:
    """observations 是 harness 投递上桌的事实，真伪与模型记没记得绑引用无关。

    没有这条，模型写对了 4.74 却忘了绑 E 号，条件句会被判成
    「证据里没有的数量」整句删掉——拿引用卫生当真伪判据。
    """

    from intelligence.services.episode_semantic_verifier import (
        _bound_evidence_quantities,
    )

    quantities = _bound_evidence_quantities(_outcome_with((TIMELINE,)))
    assert "4.74" in quantities and "3432.59" in quantities


def test_unbound_evidence_text_still_needs_binding() -> None:
    """只放宽到结构化值，不放宽到未绑定证据的**文本**。

    后者仍需引用卫生把关；一并放宽等于把门禁拆了（筛 2：变错，必须硬）。
    """

    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.episode_semantic_verifier import (
        _bound_evidence_quantities,
    )

    text_only = AgentEvidence(
        tool="web_search",
        title="某研报",
        detail="预计三季度增长 61.8%",
        source="https://example.com/a",
    )
    assert "61.8" not in _bound_evidence_quantities(_outcome_with((text_only,)))


# ── 第 5 刀：数值核对从判官手里拿走，投递给它 ──────────────────────


def test_verified_quantities_lists_only_exact_matches() -> None:
    """投递给判官的清单只装逐字节相等的数——编造的数进不来。"""

    from intelligence.services.episode_semantic_verifier import (
        _verified_quantities_for_judge,
    )

    outcome = _outcome_with((TIMELINE,))
    outcome.draft = "08-07 涨 4.74%，成交 3432.59 亿；另有传闻称成交 9999.99 亿。"
    rows = _verified_quantities_for_judge(outcome)
    values = {r["value"] for r in rows}
    assert values == {4.74, 3432.59}
    assert 9999.99 not in values, "未投递过的数不得进入已核对清单"


def test_verified_quantities_carry_locator_for_semantic_check() -> None:
    """每条要带 (subject, as_of, metric)，判官才能继续审语义（口径/日期对不对）。"""

    from intelligence.services.episode_semantic_verifier import (
        _verified_quantities_for_judge,
    )

    outcome = _outcome_with((TIMELINE,))
    outcome.draft = "08-07 成交 3432.59 亿。"
    row = _verified_quantities_for_judge(outcome)[0]
    assert row["subject"] == "PCB概念"
    assert row["as_of"] == "2026-08-07"
    assert row["metric"] == "amount"


def test_judge_prompt_forbids_rejecting_verified_quantities() -> None:
    """提示词必须写明这份清单怎么用，否则就是「投递了没人读」。"""

    from intelligence.services import episode_semantic_verifier as v

    prompt = "".join(
        str(getattr(v, name))
        for name in dir(v)
        if name.isupper() and isinstance(getattr(v, name), str)
    )
    assert "verified_quantities" in prompt
    assert "未注册数字" in prompt
