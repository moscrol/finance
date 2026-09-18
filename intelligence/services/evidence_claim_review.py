"""Narrow source-aware diagnostics; never rewrite prose or certify research.

D10 tables, D4 same-day prose and finance_query key/value rows are existing
local projection contracts. Unknown layouts are not interpreted as facts. This
is not a general NLP entailment engine: findings carry their exact source IDs,
while unrecognized claims still belong to semantic review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import re

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.episode_protocol import cited_evidence_ordinals, evidence_ordinal_table, strip_evidence_ordinals


@dataclass(frozen=True)
class ClaimFinding:
    sentence_index: int
    code: str
    message: str
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_NUMBER = r"[-+]?\d+(?:\.\d+)?"
_WINDOW = re.compile(r"\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2}")
# Scope qualification must be local, not an end-of-answer disclaimer.
_QUALIFIER = re.compile(r"不能|无法|不足以|不代表|不意味着|不成立|未(?:能|经)?(?:验证|核验|校准)|待验证|观察假设|假设|如果|若|尚不|并非|并未|不是")
_MINIMUM = re.compile(rf"(?:最低|下限)(?:为|是)?\s*({_NUMBER})\s*个")
_PATH = re.compile(r"(?:没有一段|均未|都未|未曾|没有|未出现)[^。；;]{0,25}(?:系统性下跌|回撤|下跌)")
_THRESHOLD = re.compile(rf"(?:≥|>=|至少|不低于)\s*{_NUMBER}(?:\s*[-–~至]\s*{_NUMBER})?\s*家")
_WIN_RATE = re.compile(r"胜率\s*(?:中等|较高|很高|偏高|高|低|[0-9.]+\s*%)")


def _regime_rows(card: AgentEvidence) -> list[list[str]]:
    if card.tool != 'market_data' or card.source != '本地 DuckDB · D10':
        return []
    lines = card.detail.splitlines()
    header = '| 历史相似窗口 | 距离 | 窗口内环境（均值） | 后续5日 | 后续10日 | 后续20日 |'
    if header not in lines:
        return []
    rows = []
    seen = set()
    for line in lines[lines.index(header) + 1:]:
        if not line.startswith('|'):
            break
        cells = [c.strip() for c in line.strip('|').split('|')]
        if cells and set(''.join(cells)) <= {'-', ':'}:
            continue
        if len(cells) != 6 or not _WINDOW.fullmatch(cells[0]) or cells[0] in seen:
            return []
        seen.add(cells[0])
        rows.append(cells)
    return rows


def _single_quantity(text: str, label: str, unit: str) -> Decimal | None:
    matches = re.findall(label + rf'\s*({_NUMBER})\s*' + unit, text)
    if len(matches) != 1:
        return None
    try:
        return Decimal(matches[0])
    except InvalidOperation:
        return None


def _history_findings(index: int, text: str, cards: dict[str, AgentEvidence]) -> list[ClaimFinding]:
    sources = [(eid, _regime_rows(card)) for eid, card in cards.items()]
    sources = [(eid, rows) for eid, rows in sources if rows]
    # No silent choice among multiple vintages/tables.
    if len(sources) != 1:
        return []
    eid, rows = sources[0]
    # A named/subset window is not the whole table. Do not invent its scope.
    if re.search(r'\d{4}-\d{2}-\d{2}|第[一二三四五六七八九十\d]+|前[两一二三四五六七八九十\d]+段|部分窗口|其中', text):
        return []
    findings = []
    if '相似窗口' in text and '双红' in text and not re.search(r'后续|随后|未来|之后', text):
        stated = _MINIMUM.search(text)
        values = [_single_quantity(row[2], '双红题材', '个') for row in rows]
        if stated and all(v is not None for v in values):
            minimum = min(v for v in values if v is not None)
            if Decimal(stated[1]) != minimum:
                findings.append(ClaimFinding(index, 'historical_window_minimum',
                    f'该相似窗口表的双红题材均值下限为{minimum}个，不是{stated[1]}个；仅限表内{len(rows)}段窗口，不能外推总体下限。', (eid,)))
    if '窗口' in text and _PATH.search(text):
        # The D10 contract contains forward endpoints, NOT intra-period prices.
        # Other path-bearing observations require semantic review, not this rule.
        has_path = any(any(o.metric in {'max_drawdown', 'drawdown', 'daily_close'} for o in c.observations) for c in cards.values())
        if not has_path:
            findings.append(ClaimFinding(index, 'endpoint_not_path',
                '相似窗口表只给期末收益，未给区间价格路径或最大回撤；不能据此断言期间没有下跌。', (eid,)))
    if '窗口' in text and '涨停' in text and re.search(r'不(?:曾)?收缩|均未减少|没有减少', text):
        for row in rows:
            baseline = _single_quantity(row[2], '涨停', '家')
            future = [_single_quantity(cell, '日均涨停', '家') for cell in row[3:]]
            smaller = next((v for v in future if v is not None and baseline is not None and v < baseline), None)
            if smaller is not None:
                findings.append(ClaimFinding(index, 'historical_contraction',
                    f'{row[0]}窗口涨停均值{baseline}家，随后窗口日均有{smaller}家；“涨停不收缩”不符合该表，不能用连板高度代替涨停家数。', (eid,)))
                break
    return findings


@dataclass(frozen=True)
class _SectorPoint:
    eid: str
    subject: str
    metric: str
    value: Decimal
    as_of: str
    source: str


def _sector_points(cards: dict[str, AgentEvidence]) -> list[_SectorPoint]:
    points = []
    for eid, card in cards.items():
        rows = []
        if card.tool == 'mainline_context' and card.source == '本地 DuckDB · D4 同日主线结构':
            for match in re.finditer(r'([^：；;()\s]+)\(([^()]*)\)', card.detail):
                name, body = match.groups()
                for metric, pattern in (('pct_chg', rf'(?:^|[，,])涨({_NUMBER})%'), ('limit_up_count', rf'(?:^|[，,])涨停({_NUMBER})(?:[,，]|$)')):
                    value = re.search(pattern, body)
                    if value:
                        rows.append((name, metric, value[1]))
        elif card.tool == 'finance_query' and card.source in {'本地结构化数据 · 板块日频行情', '本地结构化数据 · 题材涨停热度日频'}:
            pairs = [pair.split('=', 1) for pair in card.detail.split('；') if '=' in pair]
            fields = dict(pairs)
            if len(fields) != len(pairs):
                continue
            name = fields.get('板块名称', '')
            for field, metric in (('涨跌幅', 'pct_chg'), ('涨停家数', 'limit_up_count')):
                if name and field in fields and re.fullmatch(_NUMBER, fields[field]):
                    rows.append((name, metric, fields[field]))
        points.extend(_SectorPoint(eid, name, metric, Decimal(value), card.source_date, card.source) for name, metric, value in rows)
    return points


def _sector_findings(index: int, text: str, points: list[_SectorPoint]) -> list[ClaimFinding]:
    findings = []
    names = sorted({p.subject for p in points}, key=len, reverse=True)
    if not names:
        return findings
    # Longest names first: PCB概念 must never be read as PCB. No automatic alias
    # map: a shared prefix is precisely the ambiguity we must not silently fix.
    mentions = list(re.finditer('|'.join(map(re.escape, names)), text))
    refs = set(cited_evidence_ordinals(text))
    dates = set(re.findall(r'\d{4}-\d{2}-\d{2}', text))
    scoped = [p for p in points if (not refs or p.eid in refs) and (not dates or p.as_of in dates)]
    for pos, match in enumerate(mentions):
        name = match.group()
        end = mentions[pos + 1].start() if pos + 1 < len(mentions) else len(text)
        clause = text[match.end():end]
        pct = re.match(rf'(?:板块)?(?:当日|今日|涨跌幅|涨幅|下跌|上涨|为|是|\s)*\s*({_NUMBER})%', clause)
        if pct:
            value = Decimal(pct[1])
            selected = [p for p in scoped if p.metric == 'pct_chg']
            correct = [p for p in selected if p.subject == name and abs(p.value - value) <= Decimal('0.01')]
            wrong = [p for p in selected if p.subject != name and abs(p.value - value) <= Decimal('0.01')]
            if not correct and wrong and len({p.subject for p in wrong}) == 1:
                p = wrong[0]
                findings.append(ClaimFinding(index, 'entity_metric_mismatch',
                    f'所写{name}的{value}%在本轮所引数据中属于{p.subject}；请区分板块全名、日期和来源，不自动合并同名或近名板块。', (p.eid,)))
    if '涨停' in text and re.search(r'当前\s*\d+家|涨停(?:家数)?(?:为|是)?\s*\d+家', text):
        # Conflicts require same exact subject AND date, distinct sources.
        for name in {m.group() for m in mentions}:
            candidates = [p for p in points if p.metric == 'limit_up_count' and p.subject == name and p.as_of and (not dates or p.as_of in dates)]
            for a in candidates:
                b = next((p for p in candidates if p.as_of == a.as_of and p.source != a.source and p.value != a.value), None)
                if b:
                    findings.append(ClaimFinding(index, 'source_caliber_conflict',
                        f'{name}同日不同来源涨停家数分别为{a.value}与{b.value}；需明确来源清单及统计口径，不能把任一个当成统一当前值。', (a.eid, b.eid)))
                    break
        # An unsuffixed name cannot silently import the concept's count either.
        if not findings and '当前' in text:
            for name in {m.group() for m in mentions}:
                related = [p for p in points if p.subject == name + '概念' and p.metric == 'limit_up_count' and p.as_of and (not dates or p.as_of in dates)]
                if len({(p.as_of, p.value) for p in related}) > 1 and len({p.as_of for p in related}) == 1:
                    values = '、'.join(str(v) for v in sorted({p.value for p in related}))
                    findings.append(ClaimFinding(index, 'source_caliber_conflict',
                        f'{name}与{name}概念不能直接视为同一实体；后者不同来源涨停数为{values}，需分别注明来源口径。', tuple(dict.fromkeys(p.eid for p in related))))
    return findings


def review_evidence_claims(sentences: list[dict[str, object]], outcome: AgentOutcome) -> tuple[ClaimFinding, ...]:
    by_hash = {c.content_hash: c for c in outcome.evidence}
    if len(by_hash) != len(outcome.evidence):
        return ()  # ambiguous evidence identity is the structural gate's job
    bound = {h for b in outcome.bindings for h in b.evidence_hashes}
    cards = {eid: by_hash[h] for h, eid in evidence_ordinal_table(outcome.evidence).items() if h in bound}
    points = _sector_points(cards)
    findings = []
    for position, row in enumerate(sentences):
        index, text = int(row['index']), str(row['text'])
        # The existing sentence splitter can emit a citation-only row after a
        # full stop. Attach only that immediately adjacent metadata, not the
        # citations of a later substantive sentence.
        if position + 1 < len(sentences):
            following = str(sentences[position + 1]['text'])
            if cited_evidence_ordinals(following) and not strip_evidence_ordinals(following).strip(' 。；;，,[]（）()'):
                text += following
        # Clauses keep explicit corrections/negations local. An unrelated
        # disclaimer in the next sentence cannot cancel a factual finding.
        for clause in re.split(r'[。；;]|(?:但是|但|然而)', text):
            qualified = bool(_QUALIFIER.search(clause))
            # A conditional trigger does not qualify an asserted factual
            # parenthesis (e.g. 若…（相似窗口最低12个）).
            factual_parentheses = [part for part in re.findall(r'[（(]([^（）()]*)[）)]', clause) if not _QUALIFIER.search(part)]
            refs = cited_evidence_ordinals(text)
            selected = {k: v for k, v in cards.items() if k in refs} if refs else cards
            if qualified:
                for part in factual_parentheses:
                    if '相似窗口' in part:
                        scoped = ('双红题材' if '双红' in clause and '双红' not in part else '') + part
                        findings.extend(_history_findings(index, scoped, selected))
                continue
            findings.extend(_history_findings(index, clause, selected))
            # Source conflict needs all same-task bound sources; explicit
            # attribution/qualification below leaves it for semantic review.
            if not re.search(r'口径|来源|不同|分别|清单', clause):
                findings.extend(_sector_findings(index, clause + ''.join(f'[{r}]' for r in refs), points))
            calibration_claim = bool(re.search(r'校准|验证样本|回测|样本量|置信区间', clause))
            if not calibration_claim and _THRESHOLD.search(clause) and re.search(r'升级|降级|需|持续|回升|判断', clause):
                findings.append(ClaimFinding(index, 'uncalibrated_watch_threshold',
                    '观察阈值未说明校准依据；若是主观设定，请在该条件旁标为待验证观察假设，不能因相同数字出现在行情卡上就称阈值已验证。'))
            if not calibration_claim and _WIN_RATE.search(clause):
                findings.append(ClaimFinding(index, 'uncalibrated_win_rate',
                    '胜率判断未给分母、条件和验证方法；请提供校准依据，或改为明确的主观倾向，不以小样本类比代替胜率。'))
    return tuple(dict.fromkeys(findings))
