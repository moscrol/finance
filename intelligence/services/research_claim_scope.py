"""Narrow, advisory checks for the frozen historical/ranking answer failures.

Only canonical D10 endpoint tables and returned sector observations are used.
An endpoint cannot certify the path between dates or a complete candidate pool.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from intelligence.services.answer_claim_scope import ClaimEvidenceContext, ClaimIssue

_WINDOW = re.compile(r'(\d{4}-\d{2}-\d{2})\s*[~～至]\s*((?:\d{4}-)?\d{2}-\d{2})')
_ENDPOINT = re.compile(r'后续\s*(\d+)\s*(?:个)?(?:交易)?日(?:的)?\s*(?:上证)?指数\s*(上涨|下跌|涨|跌)?\s*([+−-]?\d+(?:\.\d+)?)\s*%')
_PATH = re.compile(r'先(?:震荡)?回调|先跌后涨|先涨后跌|中途(?:回调|下跌|上涨)')
_PATH_LIMIT = re.compile(r'不能|无法|不足以|尚未|未取得|缺少|缺乏|并不|不代表|待核验')
_OPEN_CHOICE = re.compile(r'(?:哪个|哪些|哪几).{0,12}(?:板块|方向|题材)|(?:板块|方向|题材).{0,12}(?:最有机会|优先|首选)')
_SELECTION = re.compile(r'最有机会|最值得|优先(?:选择|关注|看)|首选')
_SELECTION_SCOPE = re.compile(r'筛选范围|候选池|(?:本轮|本次|上述|已查到|已查询).{0,12}(?:板块|候选|范围)')
_SELECTION_METHOD = re.compile(r'(?:按|依据|基于|比较维度|排序依据|筛选标准)[^。；\n]{0,100}(?:排序|选取|筛选|比较|持续性|延续性|成交额|边际量|涨幅|流动性)')


def evidence_scope(evidence: list[Any]) -> tuple[tuple[tuple[str, str, int, float], ...], tuple[str, ...]]:
    """Parse the existing producer's exact table; never infer from user priors."""
    endpoints: dict[tuple[str, str, int], set[float]] = {}
    names: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict) or item.get('evidence_tier') in {'user_memory', 'user_memory_gap'}:
            continue
        detail = str(item.get('detail') or '')
        if item.get('tool') == 'finance_query':
            match = re.search(r'(?:^|；)板块名称=([^；\n]+)', detail)
            if match and match[1].strip() not in {'', '未知'}:
                names.add(match[1].strip())
        if item.get('tool') != 'market_data' or '市场情绪环境类比块 [D10]' not in detail:
            continue
        horizons: dict[int, int] = {}
        for line in detail.splitlines():
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if cells and cells[0] == '历史相似窗口':
                horizons = {i: int(m[1]) for i, cell in enumerate(cells)
                            if (m := re.fullmatch(r'后续(\d+)日', cell))}
                continue
            window = _WINDOW.fullmatch(cells[0]) if cells else None
            if not window or len(window[2]) != 10:
                continue
            for column, days in horizons.items():
                match = re.match(r'指数([+−-]?\d+(?:\.\d+)?)%', cells[column]) if column < len(cells) else None
                if match:
                    endpoints.setdefault((window[1], window[2], days), set()).add(float(match[1].replace('−', '-')))
    # Conflicting observations cannot become a deterministic comparison oracle.
    values = tuple((*key, next(iter(numbers))) for key, numbers in sorted(endpoints.items()) if len(numbers) == 1)
    return values, tuple(sorted(names))


def research_claim_issues(answer: str, context: ClaimEvidenceContext) -> list[ClaimIssue]:
    from intelligence.services.answer_claim_scope import ClaimIssue, split_sentences

    issues: list[ClaimIssue] = []
    sentences = split_sentences(answer)
    endpoints = context.historical_endpoint_returns
    for sentence in sentences:
        if endpoints and _PATH.search(sentence) and not _PATH_LIMIT.search(sentence) and re.search(r'历史|相似窗口|类比|\d{4}-\d{2}-\d{2}', sentence):
            issues.append(ClaimIssue(
                'historical_path_unverified', '历史终点不能证明过程', sentence[:80],
                '已取的 D10 只给后续各期限的指数累计涨跌；该过程描述尚未绑定逐日路径，不能由终点正负推出。',
                '逐一写明窗口、期限和累计涨跌；核对逐日路径后再描述先后顺序。',
            ))
        windows = list(_WINDOW.finditer(sentence))
        # A multi-window sentence needs an explicit mapping; do not guess which
        # window a later number belongs to.
        if len(windows) != 1:
            continue
        start, end = windows[0].groups()
        for match in _ENDPOINT.finditer(sentence[windows[0].end():]):
            days, direction, number = match.groups()
            expected = [value for s, e, n, value in endpoints
                        if s == start and (e == end or e[5:] == end) and n == int(days)]
            if len(expected) != 1:
                continue
            claimed = float(number.replace('−', '-'))
            if direction in {'跌', '下跌'}:
                claimed = -abs(claimed)
            elif direction in {'涨', '上涨'}:
                claimed = abs(claimed)
            if (claimed > 0) - (claimed < 0) != (expected[0] > 0) - (expected[0] < 0):
                issues.append(ClaimIssue(
                    'claim_direction_mismatch', '同窗口同期限方向矛盾', sentence[:80],
                    f'D10 的 {start}~{end} 后续{days}日指数累计涨跌为 {expected[0]:+.2f}%，与本句方向不一致。',
                    '核对同一窗口、同一期限和同一指标后修正；不要拿另一期限的收益代替。',
                ))
    names = context.observed_sector_names
    # User-named comparisons have their own bounded universe. Returned rows
    # elsewhere in the episode must not silently enlarge that task.
    user_named = sum(name in context.question for name in names)
    choice = next((sentence for sentence in sentences if _SELECTION.search(sentence)), None)
    if (choice and _OPEN_CHOICE.search(context.question) and len(names) >= 3 and user_named < 2
            and not (_SELECTION_SCOPE.search(answer) and _SELECTION_METHOD.search(answer))):
        issues.append(ClaimIssue(
            'selection_criteria_missing', '择优结论缺筛选口径', choice[:80],
            f'本轮材料涉及{len(names)}个不同板块（不等于完整候选池）；择优结论未同时交代比较范围和筛选方法，完整候选池规模未提供。',
            '说明在本轮实际查询的范围内，按哪些维度比较；全集规模未知就直说，不能用返回行数冒充全集。',
        ))
    return issues
