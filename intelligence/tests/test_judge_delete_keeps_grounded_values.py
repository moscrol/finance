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
