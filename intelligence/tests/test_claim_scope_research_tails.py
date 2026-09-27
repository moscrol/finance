"""Frozen answer regressions: endpoints are not paths; rankings need a scope."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from intelligence.services.claim_scope_review import review_runtime_claims


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setenv('ASK_CLAIM_SCOPE_REVIEW', 'advisory')
    root = Path(__file__).parent / 'fixtures/live_products/run_20260922_191550_067475'
    ep = json.loads((root / 'continuous-episode.json').read_text())
    ep['outcome']['events'] = copy.deepcopy(ep['events'])
    question = json.loads((root / 'MANIFEST.json').read_text())['question']
    return ep, question, (root / 'answer.md').read_text(), ep['events'][41]['payload']['content']


def review(frozen, answer, *, question=None):
    ep, original_question, *_ = frozen
    return review_runtime_claims(answer=answer, question=question or original_question, episode=ep)


@pytest.mark.parametrize('answer_index', [2, 3])
def test_frozen_answer_discloses_path_and_selection_gaps(frozen, answer_index):
    report = review(frozen, frozen[answer_index])
    assert report['rules_hit'].count('historical_path_unverified') == 1
    assert report['rules_hit'].count('selection_criteria_missing') == 1
    assert 'claim_direction_mismatch' not in report['rules_hit']
    assert '85' not in json.dumps(report, ensure_ascii=False)
    assert all(item['advisory_only'] for item in report['checks'])


@pytest.mark.parametrize('end', ['2025-12-02', '12-02'])
def test_same_window_horizon_and_metric_have_a_direction_contradiction(frozen, end):
    report = review(frozen, f'2025-11-05~{end} 窗口后续10日指数上涨1.87%。')
    assert report['rules_hit'] == ['claim_direction_mismatch']


@pytest.mark.parametrize('answer', [
    '2025-11-05~12-02 窗口后续10日指数下跌1.87%。',
    '2025-11-05~12-02 窗口后续5日指数上涨0.30%。',
    '2025-11-05~12-02 窗口内指数上涨1.87%。',
    '2025-11-05~12-02 窗口后续10日涨停数上涨1.87%。',
    '2025-11-05~12-03 窗口后续10日指数上涨1.87%。',
    '历史窗口终点上涨不能证明途中没有回调，尚未取得逐日路径。',
])
def test_noncontradictions_are_not_direction_errors(frozen, answer):
    assert review(frozen, answer)['rules_hit'] == []


def test_numeric_memory_is_not_a_historical_market_source(frozen):
    ep, question, *_ = frozen
    ep['outcome']['evidence'][0]['tool'] = 'memory_lookup'
    ep['outcome']['evidence'][0]['evidence_tier'] = 'user_memory'
    result = review_runtime_claims(
        answer='2025-11-05~12-02 窗口后续10日指数上涨1.87%。', question=question, episode=ep,
    )
    assert 'claim_direction_mismatch' not in result['rules_hit']


def test_scoped_selection_with_comparison_dimensions_clears_warning(frozen):
    answer = frozen[3] + '\n筛选范围：本轮实际查询到的板块，完整候选池规模未提供；按边际量、成交额与近20日持续性比较后选取这两个方向。'
    assert 'selection_criteria_missing' not in review(frozen, answer)['rules_hit']


@pytest.mark.parametrize('question', ['半导体与CPO概念哪个更有机会？', '解释半导体与CPO概念的量价变化。'])
def test_user_named_comparisons_are_not_an_open_pool_ranking(frozen, question):
    assert 'selection_criteria_missing' not in review(frozen, '最有机会的是半导体。', question=question)['rules_hit']


def test_explicit_scope_without_selection_method_still_warns(frozen):
    answer = '最有机会的是半导体。本轮查询的板块属于部分候选池，完整候选池规模未提供。'
    assert 'selection_criteria_missing' in review(frozen, answer)['rules_hit']
