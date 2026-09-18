"""Source-scoped, falsifiable checks, not a general financial fact checker."""
from dataclasses import replace

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural

D10 = '''## 市场情绪环境类比块 [D10]
| 历史相似窗口 | 距离 | 窗口内环境（均值） | 后续5日 | 后续10日 | 后续20日 |
|---|---|---|---|---|---|
| 2025-01-01~2025-01-20 | 0.3 | 涨停62家 · 双红题材12个 | 指数0.89%/日均涨停54家 | 指数0.96%/日均涨停56家 | 指数4.17%/日均涨停57家 |
| 2025-02-01~2025-02-20 | 0.4 | 涨停60家 · 双红题材13个 | 指数0.72%/日均涨停60家 | 指数1.02%/日均涨停59家 | 指数1.29%/日均涨停59家 |
| 2025-03-01~2025-03-20 | 0.5 | 涨停58家 · 双红题材8个 | 指数1.86%/日均涨停67家 | 指数2.71%/日均涨停63家 | 指数5.27%/日均涨停63家 |'''


def cards():
    return (
        AgentEvidence(tool='market_data', title='市场情绪环境类比 [D10]', detail=D10, source='本地 DuckDB · D10', content_hash='regime'),
        AgentEvidence(tool='mainline_context', title='主线', detail='PCB概念(-，涨-1.19%，涨停0)；CPO概念(-，涨-0.69%，涨停0)', source='本地 DuckDB · D4 同日主线结构', content_hash='mainline', source_date='2026-09-17'),
        AgentEvidence(tool='finance_query', title='板块日频', detail='板块代码=990026.FP；板块名称=PCB；涨跌幅=-2.4188；成交额亿=1055.6', source='本地结构化数据 · 板块日频行情', content_hash='sector', source_date='2026-09-17'),
        AgentEvidence(tool='finance_query', title='题材热度', detail='板块名称=PCB概念；涨停家数=3；热度排名=24', source='本地结构化数据 · 题材涨停热度日频', content_hash='heat', source_date='2026-09-17'),
    )


def review(draft, evidence=None, judge=None):
    frame, structural = _structural(draft)
    evidence = cards() if evidence is None else evidence
    binding = replace(structural.outcome.bindings[0], evidence_hashes=tuple(e.content_hash for e in evidence), gap='' if evidence else '没有证据')
    structural = verify_episode_outcome(structural.contract, replace(structural.outcome, evidence=evidence, bindings=(binding,) if evidence else ()))
    return SemanticEpisodeVerifier(judge_fn=judge or _judge(True)).verify(
        frame=frame, structurally_verified=structural, deadline=ResearchDeadline.from_timeout(5),
    )


@pytest.mark.parametrize('draft,code,detail', [
    ('双红题材数从21个收缩（相似窗口最低12个）。', 'historical_window_minimum', '8'),
    ('相似窗口双红题材下限为12个。[E1]', 'historical_window_minimum', '8'),
    ('三个相似窗口没有一段在随后5-20日出现系统性下跌。', 'endpoint_not_path', '区间'),
    ('历史窗口主线环境（涨停/连板/双红数）不收缩。', 'historical_contraction', '62'),
    ('PCB当日-1.19%。[E2]', 'entity_metric_mismatch', 'PCB概念'),
    ('PCB/CPO涨停家数回升（当前0家→需≥3-5家）。', 'source_caliber_conflict', '3'),
    ('升级汽车判断：涨停家数持续≥10家。', 'uncalibrated_watch_threshold', '假设'),
    ('电子链延续，胜率中等。', 'uncalibrated_win_rate', '胜率'),
])
def test_specific_findings_cannot_be_overridden_by_pass_judge(draft, code, detail):
    result = review(draft)
    assert draft in result.public_answer
    assert result.status == 'partial' and result.judge_status == 'rejected'
    findings = result.to_dict()['evidence_claim_findings']
    finding = next(f for f in findings if f['code'] == code)
    assert detail in finding['message']
    assert finding['sentence_index'] in result.rejected_claim_indexes
    assert detail in ' '.join(result.review_notes)
    assert result.verified.outcome.evidence == cards()
    assert all(v['decision'] != 'deleted' for v in result.sentence_verdicts)


@pytest.mark.parametrize('draft', [
    '相似窗口双红题材最低8个。[E1]',
    '相似窗口双红题材最高13个。[E1]',
    '第一段相似窗口双红题材12个，第三段8个。[E1]',
    '前两段相似窗口双红题材最低12个。[E1]',
    '2025-01-01~2025-01-20相似窗口双红题材最低12个。[E1]',
    '相似窗口后续5日双红题材最低13.4个。[E1]',
    '相似窗口随后20日双红题材下限为14个。[E1]',
    '该股历史没有系统性下跌，需要核对单股证据。',
    '三个窗口后续5/10/20日终点收益均为正，但无法据此判断区间回撤。[E1]',
    '不能说三个窗口没有系统性下跌，终点正收益不能证明期间路径。[E1]',
    '历史窗口涨停不收缩的说法不成立。[E1]',
    'PCB概念当日-1.19%，PCB板块当日-2.42%，二者不是同一板块。[E2][E3]',
    'PCB概念D4涨停0家、题材热度口径3家，来源清单不同，不可直接混用。[E2][E4]',
    '观察假设（未校准）：汽车涨停≥10家时再复核，不是已经验证的阈值。',
    '胜率没有校准依据，只能作为主观判断，不能称胜率中等。',
    '如果以后相似窗口出现系统性下跌，应重新核对。',
])
def test_correct_or_explicitly_qualified_claims_are_not_flagged(draft):
    assert not review(draft).to_dict()['evidence_claim_findings']


@pytest.mark.parametrize('draft', [
    '双红题材并未全面失速，但相似窗口双红题材最低12个。',
    '双红题材从21个下降时再复核（相似窗口最低12个）；本文只作研究。',
    '历史窗口没有系统性下跌。但不能当概率。',
    '若双红题材减少则降级（相似窗口双红题材最低12个）。',
])
def test_unrelated_negation_or_later_disclaimer_cannot_hide_a_fact(draft):
    assert review(draft).to_dict()['evidence_claim_findings']


@pytest.mark.parametrize('draft', [
    '该阈值来源于已绑定的验证样本：汽车涨停持续≥10家时再核对。',
    '按样本校准得出的胜率中等，计算口径见[E1]。',
])
def test_explicit_calibration_claim_belongs_to_semantic_review(draft):
    # These checks diagnose missing qualification, not the validity of a
    # calibration claim. A citation or phrase is not an automatic QC pass.
    assert not review(draft).to_dict()['evidence_claim_findings']


def test_entity_check_respects_cited_source_and_explicit_date():
    correct = replace(cards()[2], detail='板块名称=PCB；涨跌幅=-1.19', source_date='2026-09-16', content_hash='previous')
    assert not review('PCB当日-1.19%。[E3]', (*cards()[:2], correct)).to_dict()['evidence_claim_findings']
    assert not review('2026-09-16 PCB当日-1.19%。', (*cards(), correct)).to_dict()['evidence_claim_findings']
    # Correct value in an uncited source must not wash a wrong cited identity.
    assert any(f['code'] == 'entity_metric_mismatch' for f in review('PCB当日-1.19%。[E2]', (*cards(), correct)).to_dict()['evidence_claim_findings'])


def test_changed_values_are_calculated_not_hardcoded_to_old_live():
    source = replace(cards()[0], detail=D10.replace('双红题材8个', '双红题材17个'))
    assert not review('相似窗口双红题材最低12个。[E1]', (source,)).to_dict()['evidence_claim_findings']
    result = review('相似窗口双红题材最低8个。[E1]', (source,))
    assert '12' in result.to_dict()['evidence_claim_findings'][0]['message']


@pytest.mark.parametrize('mutation', ['missing_value', 'duplicate_window', 'other_source', 'missing_header', 'no_cards'])
def test_uninterpretable_or_unrelated_evidence_cannot_certify_a_minimum(mutation):
    source = cards()[0]
    if mutation == 'missing_value':
        source = replace(source, detail=D10.replace('双红题材8个', '双红题材缺失'))
    elif mutation == 'duplicate_window':
        source = replace(source, detail=D10.replace('2025-03-01~2025-03-20', '2025-01-01~2025-01-20'))
    elif mutation == 'other_source':
        source = replace(source, tool='kb_search', source='任意笔记')
    elif mutation == 'missing_header':
        source = replace(source, detail=D10.replace('窗口内环境（均值）', '未来假设'))
    findings = review('相似窗口双红题材最低12个。[E1]', () if mutation == 'no_cards' else (source,)).to_dict()['evidence_claim_findings']
    assert not findings


def test_ambiguous_projection_fields_do_not_authorize_a_metric_check():
    source = replace(cards()[2], detail='板块名称=PCB；板块名称=PCB概念；涨跌幅=-1.19')
    result = review('PCB当日-1.19%。[E1]', (source,))
    assert not result.to_dict()['evidence_claim_findings']


def test_findings_survive_judge_outage_without_claiming_judge_rejected():
    result = review('相似窗口双红题材最低12个。[E1]', judge=lambda _: None)
    assert result.judge_status == 'unavailable' and result.status == 'partial'
    assert result.to_dict()['evidence_claim_findings'] and result.rejected_claim_indexes


def test_adapter_sends_findings_to_existing_same_session_repair():
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services.episode_session import CallbackEpisodeSession
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.tests.test_continuous_turn_adapter import _frame, _control

    frame = _frame(required_outputs=('direct_assessment',))
    control = _control(frame, capabilities=('market_data',))
    context = build_episode_context(frame, task_id='claim-repair', capabilities=control.capabilities, timeout=60)
    source = cards()[0]
    initial = AgentOutcome(
        task_frame_hash=frame.task_frame_hash, status='completed',
        draft='相似窗口双红题材最低12个。[E1]', evidence=(source,), traces=(), gaps=(),
        stop_reason='model_finish', events=(EpisodeEvent(1, 'task', {'task_frame_hash': frame.task_frame_hash}),),
        bindings=(OutputEvidenceBinding('direct_assessment', (source.content_hash,)),), usage=AgentUsage(1, 1),
    )
    goals = []
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                goals.append(goal)
                return replace(previous, draft=previous.draft + '\n更正：表内下限为8个，不是12个；旧判断撤回。[E1]',
                               usage=AgentUsage(2, 1), events=(*previous.events, EpisodeEvent(2, 'model_turn', {'task_frame_hash': frame.task_frame_hash})))
            return CallbackEpisodeSession(episode_id=context.contract.task_id, outcome=initial, resume_callback=resume)
    result = ContinuousTurnAdapter(
        runtime=Runtime(), semantic_verifier=SemanticEpisodeVerifier(judge_fn=_judge(True)),
        runtime_name='continuous_glm', mode='on', context_factory=lambda *_a, **_kw: context,
        registry_factory=lambda *_a, **_kw: 'inert-registry',
    ).handle(frame=frame, control=control)
    assert goals and any('historical_window_minimum' in text and '8' in text for text in goals[0].unsupported_claims)
    assert initial.draft in result.answer
    assert result.status == 'partial'  # preserved erroneous original is not silently certified


def test_repair_feedback_contains_actual_claim_and_reason():
    from intelligence.services.episode_semantic_verifier import semantic_repair_feedback
    result = review('相似窗口双红题材最低12个。[E1]')
    feedback = semantic_repair_feedback(result)
    assert any('最低12' in f and '8' in f and 'historical_window_minimum' in f for f in feedback)
