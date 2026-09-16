"""排序与情景表达契约（10 号单）：把「谁更值得研究」答成可机械再排序的结构。

背景（为什么要这个层）：
    多公司排序题（「英维克、申菱环境、高澜股份谁更值得优先研究」）今天落在
    theme_analysis / news_impact，契约只要求 direct_assessment + chain_mapping +
    counterpoint——模型给一串名单和形容词就能过门，没有同维度矩阵、没有竞争解释、
    也没有「什么变化会改排序」。用户看完不知道谁更值得继续研究、为什么、什么时候
    该改判。Knevo 的五维排序（q2 蒸馏）有维度和翻转触发矩阵的好思路，但权重/胜率
    全是拍脑袋；本层只借结构，不借数字。

设计（沿 scenario_tree / track_contract 的表达层惯例，零新数据源）：
    - **表达层模板**：注入 synthesis prompt（legacy）与 episode 指令的格式契约，
      不新增证据、不改证据链。矩阵与改判条件用**固定表头的 Markdown 表**表达——
      人读的表就是机器读的表，表格、正文、计算只有一份。
    - **确定性意图路由**：排序词面 × 多对象信号双门；涨幅排行/成交额前 N 等
      快事实排除；非排序题零改动。
    - **程序核对**：缺矩阵 / 缺改判条件 / 竞争解释不足 / 缺下一步 → 合成 id 并入
      ``missing_outputs``（与 track_contract 同一条 contract_rewrite 修复路径）。
    - **机械再排序**：``apply_scenario`` 按改判条件表的箭头（↑ 上移一位、↑↑ 两位）
      稳定重排——不凭空给权重、概率或弹性；未覆盖的变量如实答「排序不变，需补敏感性」。
      这也是反向验证的判据：改成本/订单/需求条件应改排序，只换文案不应改推导。
    - **让输出成为下一轮输入**：改判条件登记 ``checkpoints.jsonl``
      （source=``ranking_flip_condition``），07 回检、09 续研、foresight 发问都读得到。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# ——————————————————————————————————————————— 固定表头（程序据此解析，契约里逐字给模型）
MATRIX_HEADERS: tuple[str, ...] = (
    "公司",
    "优先级",
    "需求暴露",
    "收入/利润传导",
    "兑现时间",
    "已定价程度",
    "关键分歧",
)
FLIP_HEADERS: tuple[str, ...] = ("变量", "变化", "受影响公司", "方向", "观察指标×时间窗")
RERANK_HEADERS: tuple[str, ...] = ("公司", "原优先级", "新优先级", "变动原因")
NEXT_ACTION_LABELS: tuple[str, ...] = ("补关键缺口", "比较替代解释", "检验条件")
# 一个箭头在位次空间里挪 1.5 位：恰好越过紧邻的那一家（若那一家没被同一条件同向推动）。
# 不是权重——排序题不给权重；这是把「↑ = 上移一位」写成稳定排序能吃的确定性规则。
ARROW_STEP = 1.5

# ——————————————————————————————————————————— 意图
_EXCLUDE_RE = re.compile(
    r"涨幅排行|跌幅排行|排行榜|龙虎榜"
    r"|(?:涨幅|跌幅|成交额|换手率?|市值|股价|涨停|连板)(?:最大|最高|最低|最多|排序|排名|排行|榜|前\s*\d+)"
    r"|前\s*\d+\s*(?:名|只|个)"
)
_STRONG_CUE_RE = re.compile(
    r"排个?序|排一下|优先级|优先研究|优先看|优先跟踪|更值得|最值得|补涨顺序|预期差"
    r"|最受益|再排序|重新排|先看谁|先研究|排名|按.{0,8}排"
)
_WEAK_CUE_RE = re.compile(r"谁更|哪家更|哪个更|哪只更|哪家最|谁最|哪个最|最强|最大|最高|最弱|最小|最快")
_TOKEN = r"[一-鿿A-Za-z0-9]{2,8}"
_SEP = r"(?:、|和|与|跟|vs|VS|／|/)"
_LIST2_RE = re.compile(rf"{_TOKEN}{_SEP}{_TOKEN}")
_LIST3_RE = re.compile(rf"{_TOKEN}{_SEP}{_TOKEN}{_SEP}{_TOKEN}")
# 群指代只认「家 / 公司 / 标的 / 个股」这类公司口径；「哪个更」单独不算——
# 「需求和成本哪个更重要」是概念二选一，不是排序题（冒烟负样本）。
_GROUP_RE = re.compile(
    r"(?:这|那|以上|上述)?(?:几|两|三|四|五|六|\d)家|哪家|哪几家|各家|几家公司|哪些公司"
    r"|哪些标的|哪些个股|哪几只|哪只"
)
# 自足的排序问法：不点名对象也要求给出一份排序（模型自己挑公司）。
_SELF_CONTAINED_RE = re.compile(
    r"谁最受益|受益最大|谁最先|补涨顺序|预期差排序|排个序|排一下|优先级排序|排序一下"
)
_SCENARIO_UPDATE_RE = re.compile(
    r"(?:如果|若|假如|假设|万一|一旦).{0,60}?(?:排序|优先级|顺序|排名|名次).{0,10}?"
    r"(?:怎么变|会怎样|会怎么样|会不会变|有什么变化|有何变化|还成立|要不要变|会变|变化|影响)"
    r"|再排序|重新排序|重排一下|排序还成立"
)


def parse_ranking_intent(query: str, question_type: str | None = None) -> bool:
    """排序词面 × 多对象信号双门；快事实榜单排除。

    三个及以上对象（「A、B、C」）或群指代（「这三家」「哪家」）配任一排序词面即命中；
    两个对象只认强词面（更值得 / 优先 / 排序 / 预期差…），「需求和成本哪个更重要」这类
    概念二选一不进来。``question_type`` 只用于未来收窄，当前不据它放行。
    """
    del question_type  # 保留签名与 scenario_tree / track_contract 一致
    text = re.sub(r"\s+", "", str(query or ""))
    if not text or _EXCLUDE_RE.search(text):
        return False
    # 再排序追问（「如果铜价回落，排序会怎么变」）天然是排序题：对象在上一轮，不必再点名。
    if _SCENARIO_UPDATE_RE.search(text) or _SELF_CONTAINED_RE.search(text):
        return True
    strong = _STRONG_CUE_RE.search(text) is not None
    weak = _WEAK_CUE_RE.search(text) is not None
    if _LIST3_RE.search(text) or _GROUP_RE.search(text):
        return strong or weak
    if _LIST2_RE.search(text):
        return strong
    return False


def parse_scenario_update_intent(query: str) -> bool:
    """再排序题：「如果/若 … 排序会怎么变」「再排序」。独立于情景树的门。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return _SCENARIO_UPDATE_RE.search(text) is not None


# ——————————————————————————————————————————— 契约文本
def _matrix_header_line() -> str:
    return "| " + " | ".join(MATRIX_HEADERS) + " |"


def _flip_header_line() -> str:
    return "| " + " | ".join(FLIP_HEADERS) + " |"


def _rerank_header_line() -> str:
    return "| " + " | ".join(RERANK_HEADERS) + " |"


def _structure_lines(evidence_note: str, memory_note: str) -> list[str]:
    return [
        "1. **主判断**（开头 ≤3 句）：谁优先、为什么、最大的不确定变量是什么。",
        "2. **公司矩阵**（Markdown 表，表头逐字为）：",
        _matrix_header_line(),
        "每家公司一行；「优先级」填 1..N 的整数（1 最优先，不并列）；每格写「取值"
        f"（{evidence_note}）」或「缺数：需要什么数据」，禁止空格、禁止只写形容词；"
        "同一维度所有公司都要填，不能只输出产业链名单。",
        "3. **财务传导**：每家一行「需求变化 → 收入/成本/利润 → 兑现时间 → 市场预期差」；"
        "有数据的写幅度与口径（如「毛利率 +2pct，2026Q2 单季」），没数据写范围条件和"
        "优先补什么；禁止编造具体弹性、权重、胜率、概率。",
        "4. **竞争解释**（标题「竞争解释」）：≥2 条互斥解释，各自解释当前排序为什么成立/"
        "不成立；每条末尾写「区分变量：X；若 X … 则本解释成立」。",
        "5. **改判条件表**（Markdown 表，表头逐字为）：",
        _flip_header_line(),
        "≥2 行；「变量」必须是可观察量（成本、订单、需求、产能、政策、客户资本开支等）；"
        "「方向」用箭头写谁升谁降，如「英维克↑ 申菱环境↓」，↑ 表示上移一位、↑↑ 两位；"
        "「观察指标×时间窗」写看什么指标 + 何时（日期或 N 天内）。",
        "6. **历史类比**（题目涉及历史/相似时才写）：机制相似点与不适用点各 ≥1 条；"
        "不得只列走势形态相似的案例。",
        "7. **下一步**（标题「下一步」，2-3 条）：每条以「补关键缺口：」「比较替代解释：」"
        "「检验条件：」之一开头，写成下一轮能直接执行的研究动作。",
        "8. **再排序题**（如果/若 … 排序会怎么变）：先写命中了上一轮改判条件表的哪一行"
        f"（{memory_note}），再给「新旧排序对照」表（表头逐字为）：",
        _rerank_header_line(),
        "最后更新观察点；未被改判条件表覆盖的变量，如实写「排序不变，需补该变量的敏感性」。",
        "9. 纪律：无数据处写缺数与优先补什么，不用形容词补位；不给数值概率；"
        "不输出买卖指令。",
    ]


def build_ranking_guidance() -> str:
    """排序与情景表达契约（注入 synthesis prompt；legacy 检索块记号）。"""
    return "\n".join(
        [
            "## 排序与情景表达契约（本题为多对象研究优先级/排序题，回答必须按此结构组织）",
            *_structure_lines(
                "证据编号如 [D6]/[W7]/[L1-x]",
                "上一轮结论取 [M] 用户记忆或 [V] 回检块，没有就声明「无上一轮排序，本期建立基线」",
            ),
        ]
    )


def build_ranking_guidance_for_episode() -> str:
    """episode 主路径版——纪律同 :func:`build_ranking_guidance`，证据记号换成 E1、E2…。"""
    return "\n".join(
        [
            "【排序与情景表达契约】本题为多对象研究优先级/排序题，draft 必须按此结构组织"
            "（表头逐字照抄，程序据此解析；这些是正文表达要求，不是可绑定的 output_id）：",
            *_structure_lines(
                "证据序号 E1、E2…",
                "上一轮结论只能来自 conversation_context 里的先前排序或 memory_lookup 召回，"
                "没有就声明「无上一轮排序，本期建立基线」",
            ),
        ]
    )


def ranking_guidance_for_query(query: str, question_type: str | None = None) -> str:
    """命中意图返回表达契约，否则空串（不注入，行为不变）。"""
    if not parse_ranking_intent(query, question_type):
        return ""
    return build_ranking_guidance()


def episode_ranking_rule(
    query: str,
    question_type: str | None = None,
    *,
    conversation_context: str = "",
) -> str:
    """episode 指令的条件注入口：命中排序意图返回 episode 版契约，否则空串。

    再排序追问且会话上下文里有上一轮矩阵时，追加系统机械推演出的「再排序基线」
    （见 :func:`rerank_baseline_note`）——情景变化更新排序这件事由确定性规则先算一遍，
    模型负责解释与据证据偏离，而不是凭印象重排。
    """
    if not parse_ranking_intent(query, question_type):
        return ""
    text = build_ranking_guidance_for_episode()
    if parse_scenario_update_intent(query):
        note = rerank_baseline_note(query, conversation_context)
        if note:
            text = f"{text}\n{note}"
    return text


# ——————————————————————————————————————————— 解析
_TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{2,}:?$")
_EVIDENCE_ID_RE = re.compile(r"E\d+|\[[A-Z]\d*(?:-[\w-]+)?\]")
_INT_RE = re.compile(r"\d+")
_CODE_RE = re.compile(r"\d{6}")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)、）])\s*(.+)$")
_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s*|\*\*)?(.{1,24}?)(?:\*\*)?\s*[：:]?\s*$")
_ARROW_RE = re.compile(r"(↑+|↓+|上移|下移|上升|下降|升|降)")
_TAGGED_MOVE_RE = re.compile(rf"({_TOKEN})\s*(↑+|↓+|上移|下移|上升|下降)")
_DISTINGUISH_RE = re.compile(r"区分变量[：:]\s*([^；;。\n]+)")
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_CN_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_DAYS_RE = re.compile(r"(\d+)\s*(?:个)?\s*(天|日|周|月)")
_EXPLANATION_HEADINGS = ("竞争解释", "互斥解释", "替代解释")
_NEXT_HEADINGS = ("下一步",)


def _norm(text: str) -> str:
    return (
        re.sub(r"\s+", "", str(text or ""))
        .replace("×", "x")
        .replace("Ｘ", "x")
        .replace("X", "x")
        .replace("*", "x")
        .replace("＊", "x")
        .replace("／", "/")
    )


def _tables(text: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in str(text or "").splitlines():
        if _TABLE_LINE_RE.match(line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and all(_SEPARATOR_CELL_RE.match(cell) for cell in cells if cell):
                continue
            current.append(cells)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _find_table(
    tables: list[list[list[str]]],
    headers: tuple[str, ...],
) -> tuple[list[list[str]], dict[str, int]] | None:
    for table in tables:
        header = table[0]
        mapping: dict[str, int] = {}
        for key in headers:
            index = next(
                (i for i, cell in enumerate(header) if _norm(key) in _norm(cell)),
                None,
            )
            if index is None:
                break
            mapping[key] = index
        if len(mapping) == len(headers):
            return table[1:], mapping
    return None


def _cell(row: list[str], mapping: dict[str, int], key: str) -> str:
    index = mapping[key]
    return row[index].strip() if index < len(row) else ""


def _clean_company(cell: str) -> str:
    text = re.sub(r"[*`_]", "", str(cell or ""))
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    return text.strip()


@dataclass(frozen=True)
class RankingRow:
    company: str
    priority: int | None
    cells: dict[str, str] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    gap_count: int = 0
    code: str | None = None


@dataclass(frozen=True)
class FlipCondition:
    variable: str
    change: str
    companies: tuple[str, ...]
    moves: dict[str, int] = field(default_factory=dict)
    watch: str = ""
    raw_direction: str = ""


@dataclass(frozen=True)
class CompetingExplanation:
    text: str
    distinguishing_variable: str | None = None


@dataclass(frozen=True)
class RankingArtifact:
    matrix: tuple[RankingRow, ...]
    flip_conditions: tuple[FlipCondition, ...]
    explanations: tuple[CompetingExplanation, ...]
    next_actions: tuple[str, ...]
    main_judgment: str = ""
    rerank_rows: tuple[dict[str, str], ...] = ()

    @property
    def order(self) -> tuple[str, ...]:
        """基线排序：优先级列升序，没填优先级的排最后且保持表内顺序。"""
        indexed = list(enumerate(self.matrix))
        indexed.sort(
            key=lambda item: (
                item[1].priority is None,
                item[1].priority if item[1].priority is not None else 0,
                item[0],
            )
        )
        return tuple(row.company for _, row in indexed)

    @property
    def priority_complete(self) -> bool:
        priorities = [row.priority for row in self.matrix]
        return bool(priorities) and all(p is not None for p in priorities) and len(
            set(priorities)
        ) == len(priorities)

    def to_payload(self) -> dict[str, object]:
        return {
            "matrix": [asdict(row) for row in self.matrix],
            "order": list(self.order),
            "priority_complete": self.priority_complete,
            "flip_conditions": [asdict(item) for item in self.flip_conditions],
            "explanations": [asdict(item) for item in self.explanations],
            "next_actions": list(self.next_actions),
            "main_judgment": self.main_judgment,
            "rerank_rows": [dict(row) for row in self.rerank_rows],
            "numeric_probabilities_allowed": False,
            "arrow_step": ARROW_STEP,
        }


def _parse_matrix(tables: list[list[list[str]]]) -> tuple[RankingRow, ...]:
    found = _find_table(tables, MATRIX_HEADERS)
    if found is None:
        return ()
    rows, mapping = found
    parsed: list[RankingRow] = []
    for row in rows:
        company_cell = _cell(row, mapping, "公司")
        company = _clean_company(company_cell)
        if not company:
            continue
        priority_match = _INT_RE.search(_cell(row, mapping, "优先级"))
        cells = {
            key: _cell(row, mapping, key)
            for key in MATRIX_HEADERS
            if key not in {"公司", "优先级"}
        }
        row_text = " ".join(row)
        code_match = _CODE_RE.search(company_cell)
        parsed.append(
            RankingRow(
                company=company,
                priority=int(priority_match.group()) if priority_match else None,
                cells=cells,
                evidence_ids=tuple(dict.fromkeys(_EVIDENCE_ID_RE.findall(row_text))),
                gap_count=sum(1 for value in cells.values() if "缺数" in value),
                code=code_match.group() if code_match else None,
            )
        )
    return tuple(parsed)


def _arrow_delta(token: str) -> int:
    if token.startswith("↑"):
        return len(token)
    if token.startswith("↓"):
        return -len(token)
    if token in {"上移", "上升", "升"}:
        return 1
    if token in {"下移", "下降", "降"}:
        return -1
    return 0


def _split_companies(cell: str) -> tuple[str, ...]:
    parts = re.split(r"[、，,/／;；\s]+", re.sub(r"[*`]", "", str(cell or "")))
    return tuple(_clean_company(part) for part in parts if _clean_company(part))


def _parse_moves(direction: str, companies: tuple[str, ...]) -> dict[str, int]:
    moves: dict[str, int] = {}
    tagged = _TAGGED_MOVE_RE.findall(direction)
    if tagged:
        for name, token in tagged:
            delta = _arrow_delta(token)
            if delta:
                moves[_clean_company(name)] = delta
        return moves
    arrows = [_arrow_delta(token) for token in _ARROW_RE.findall(direction)]
    arrows = [delta for delta in arrows if delta]
    if not arrows:
        return moves
    if len(arrows) == len(companies):
        return {company: delta for company, delta in zip(companies, arrows)}
    if len(arrows) == 1:
        return {company: arrows[0] for company in companies}
    return moves


def _parse_flips(tables: list[list[list[str]]]) -> tuple[FlipCondition, ...]:
    found = _find_table(tables, FLIP_HEADERS)
    if found is None:
        return ()
    rows, mapping = found
    parsed: list[FlipCondition] = []
    for row in rows:
        variable = _cell(row, mapping, "变量")
        if not variable:
            continue
        companies = _split_companies(_cell(row, mapping, "受影响公司"))
        direction = _cell(row, mapping, "方向")
        moves = _parse_moves(direction, companies)
        parsed.append(
            FlipCondition(
                variable=variable,
                change=_cell(row, mapping, "变化"),
                companies=companies or tuple(moves),
                moves=moves,
                watch=_cell(row, mapping, "观察指标×时间窗"),
                raw_direction=direction,
            )
        )
    return tuple(parsed)


def _parse_rerank(tables: list[list[list[str]]]) -> tuple[dict[str, str], ...]:
    found = _find_table(tables, RERANK_HEADERS)
    if found is None:
        return ()
    rows, mapping = found
    return tuple(
        {key: _cell(row, mapping, key) for key in RERANK_HEADERS}
        for row in rows
        if _clean_company(_cell(row, mapping, "公司"))
    )


def _is_heading_for(line: str, keywords: tuple[str, ...]) -> bool:
    match = _HEADING_RE.match(line)
    if match is None:
        return False
    title = re.sub(r"[*#\s]", "", match.group(1))
    return any(title.startswith(keyword) or keyword in title for keyword in keywords) and len(
        title
    ) <= 24


def _section_items(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    lines = str(text or "").splitlines()
    items: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if not inside:
            if _is_heading_for(stripped, keywords):
                inside = True
                # 标题行内联内容：「竞争解释：A…」
                tail = stripped.split("：", 1)[1] if "：" in stripped else ""
                if tail.strip() and not _is_heading_for(tail.strip(), keywords):
                    items.append(tail.strip())
            continue
        if not stripped:
            continue
        if stripped.startswith("#") or _TABLE_LINE_RE.match(stripped):
            break
        if _HEADING_RE.match(stripped) and not _BULLET_RE.match(stripped) and len(
            stripped
        ) <= 24 and stripped.endswith(("：", ":")):
            break
        bullet = _BULLET_RE.match(stripped)
        items.append(bullet.group(1).strip() if bullet else stripped)
    return tuple(items)


def _parse_explanations(text: str) -> tuple[CompetingExplanation, ...]:
    parsed: list[CompetingExplanation] = []
    for item in _section_items(text, _EXPLANATION_HEADINGS):
        found = _DISTINGUISH_RE.search(item)
        parsed.append(
            CompetingExplanation(
                text=item,
                distinguishing_variable=found.group(1).strip() if found else None,
            )
        )
    return tuple(parsed)


def _parse_next_actions(text: str) -> tuple[str, ...]:
    actions: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        bullet = _BULLET_RE.match(line)
        body = re.sub(r"^[*_`]+|[*_`]+$", "", (bullet.group(1) if bullet else line).strip())
        body = re.sub(r"^\*\*|\*\*", "", body)
        if any(body.startswith(label) for label in NEXT_ACTION_LABELS):
            actions.append(body)
    return tuple(dict.fromkeys(actions))


def _main_judgment(text: str) -> str:
    for block in re.split(r"\n\s*\n", str(text or "")):
        candidate = block.strip()
        if not candidate or candidate.startswith(("#", "|")):
            continue
        return candidate[:400]
    return ""


def parse_ranking_artifact(answer: str) -> RankingArtifact:
    """从答案解析矩阵、改判条件、竞争解释、下一步。解析不到就空，不猜。"""
    text = str(answer or "")
    tables = _tables(text)
    return RankingArtifact(
        matrix=_parse_matrix(tables),
        flip_conditions=_parse_flips(tables),
        explanations=_parse_explanations(text),
        next_actions=_parse_next_actions(text),
        main_judgment=_main_judgment(text),
        rerank_rows=_parse_rerank(tables),
    )


# ——————————————————————————————————————————— 程序核对 → missing_outputs
RANKING_CONTRACT_OUTPUT_IDS: dict[str, str] = {
    "matrix": "ranking_matrix",
    "flip_conditions": "ranking_flip_conditions",
    "competing_explanations": "ranking_competing_explanations",
    "next_actions": "ranking_next_actions",
    "rerank_table": "ranking_rerank_table",
}
RANKING_CONTRACT_OUTPUT_ID_SET = frozenset(RANKING_CONTRACT_OUTPUT_IDS.values())
EXPRESSION_SLOT_HINTS: dict[str, str] = {
    "ranking_matrix": "固定表头的公司矩阵表（每家一行，优先级 1..N）",
    "ranking_flip_conditions": "固定表头的改判条件表（≥2 行，方向用 ↑/↓）",
    "ranking_competing_explanations": "「竞争解释」段 ≥2 条互斥解释并各写「区分变量：…」",
    "ranking_next_actions": "「下一步」段，每条以 补关键缺口：/比较替代解释：/检验条件： 开头",
    "ranking_rerank_table": "「新旧排序对照」表（公司 / 原优先级 / 新优先级 / 变动原因）",
}


def missing_contract_elements(
    answer: str,
    *,
    scenario_update: bool = False,
) -> tuple[str, ...]:
    """扫描回答缺了契约的哪几件。非排序题的调用方应先自己判断是否要查。"""
    artifact = parse_ranking_artifact(answer)
    missing: list[str] = []
    if len(artifact.matrix) < 2 or not artifact.priority_complete:
        missing.append("matrix")
    if len(artifact.flip_conditions) < 2 or not any(
        item.moves for item in artifact.flip_conditions
    ):
        missing.append("flip_conditions")
    if len(artifact.explanations) < 2 or not any(
        item.distinguishing_variable for item in artifact.explanations
    ):
        missing.append("competing_explanations")
    if not artifact.next_actions:
        missing.append("next_actions")
    if scenario_update and not artifact.rerank_rows:
        missing.append("rerank_table")
    return tuple(missing)


def contract_missing_outputs(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
) -> tuple[str, ...]:
    """程序核对：排序题的契约缺件 → missing_outputs 词表输出项 id。非排序题恒空。"""
    if not parse_ranking_intent(query, question_type):
        return ()
    return tuple(
        RANKING_CONTRACT_OUTPUT_IDS[key]
        for key in missing_contract_elements(
            answer, scenario_update=parse_scenario_update_intent(query)
        )
        if key in RANKING_CONTRACT_OUTPUT_IDS
    )


def merge_ranking_missing_outputs(
    existing: tuple[str, ...] | list[str],
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
) -> tuple[str, ...]:
    """把排序契约缺件并入 repair 用的 missing_outputs。非排序题原样返回。"""
    extra = contract_missing_outputs(answer, query=query, question_type=question_type)
    return tuple(dict.fromkeys((*tuple(existing or ()), *extra)))


def expression_slot_note(slots: tuple[str, ...]) -> str:
    """修复目标里的排序表达槽说明：写进 draft，不当 output 绑。"""
    hints = [
        f"{slot} → {EXPRESSION_SLOT_HINTS[slot]}"
        for slot in slots
        if slot in EXPRESSION_SLOT_HINTS
    ]
    return "；".join(hints)


# ——————————————————————————————————————————— 机械再排序
_NEGATIVE_WORDS = (
    "回落", "下跌", "下降", "降价", "落空", "减少", "延迟", "推迟", "取消", "缩量",
    "不及", "低于", "走弱", "转弱", "收缩", "下滑", "恶化", "流失", "跌破", "放缓", "丢失",
)
_POSITIVE_WORDS = (
    "上涨", "涨价", "上升", "提高", "增加", "放量", "落地", "兑现", "超预期", "高于",
    "扩产", "加速", "改善", "突破", "新增", "获得", "中标", "上调", "提价", "转正",
)


def _sign(text: str) -> int:
    body = _norm(text)
    negative = any(word in body for word in _NEGATIVE_WORDS)
    positive = any(word in body for word in _POSITIVE_WORDS)
    if negative and not positive:
        return -1
    if positive and not negative:
        return 1
    return 0


def _variable_tokens(variable: str) -> tuple[str, ...]:
    parts = re.split(r"[/／、，,与和及或\s()（）]+", _norm(variable))
    return tuple(part for part in parts if len(part) >= 2)


def _token_hit(token: str, body: str, companies: tuple[str, ...]) -> str | None:
    """变量词面命中：整词在文本里；或「公司名 + 变量」拆开后两半都在（「高澜股份订单」vs
    「高澜股份拿到公告级订单」）。返回用于取方向窗口的命中片段。"""
    if token in body:
        return token
    for company in companies:
        name = _norm(company)
        if not name or name not in token or name not in body:
            continue
        remainder = token.replace(name, "")
        if len(remainder) >= 2 and remainder in body:
            return remainder
    return None


def _match_details(
    artifact: RankingArtifact,
    scenario_text: str,
) -> tuple[tuple[FlipCondition, ...], tuple[FlipCondition, ...]]:
    """返回（命中的行，变量命中但方向相反的行）。"""
    body = _norm(scenario_text)
    if not body:
        return (), ()
    companies = tuple(row.company for row in artifact.matrix)
    matched: list[FlipCondition] = []
    opposite: list[FlipCondition] = []
    for condition in artifact.flip_conditions:
        hit = next(
            (
                found
                for token in _variable_tokens(condition.variable)
                if (found := _token_hit(token, body, companies)) is not None
            ),
            None,
        )
        if hit is None:
            continue
        row_sign = _sign(condition.change)
        start = body.find(hit)
        window = body[max(0, start - 12) : start + len(hit) + 14]
        text_sign = _sign(window)
        if row_sign and text_sign and row_sign != text_sign:
            opposite.append(condition)
            continue
        matched.append(condition)
    return tuple(matched), tuple(opposite)


def match_conditions(
    artifact: RankingArtifact,
    scenario_text: str,
) -> tuple[FlipCondition, ...]:
    """改判条件表里被情景文本命中的行：变量词面出现，且变化方向不相反。"""
    return _match_details(artifact, scenario_text)[0]


@dataclass(frozen=True)
class ScenarioUpdate:
    matched: tuple[FlipCondition, ...]
    before: tuple[str, ...]
    after: tuple[str, ...]
    moved: dict[str, tuple[int, int]] = field(default_factory=dict)
    watchpoints: tuple[str, ...] = ()
    unchanged: bool = True
    reason: str = ""

    def to_payload(self) -> dict[str, object]:
        return {
            "matched": [asdict(item) for item in self.matched],
            "before": list(self.before),
            "after": list(self.after),
            "moved": {name: list(pair) for name, pair in self.moved.items()},
            "watchpoints": list(self.watchpoints),
            "unchanged": self.unchanged,
            "reason": self.reason,
        }


def apply_scenario(
    artifact: RankingArtifact,
    *,
    scenario_text: str | None = None,
    conditions: tuple[FlipCondition, ...] | None = None,
) -> ScenarioUpdate:
    """按命中的改判条件机械重排：↑ 上移约一位、↓ 下移约一位，未命中则排序不变。

    不给权重、不给概率。分数只是把箭头翻译成稳定排序能吃的键：
    ``score = -优先级 + ARROW_STEP × 箭头数``，同分按原优先级。
    """
    before = artifact.order
    opposite: tuple[FlipCondition, ...] = ()
    if conditions is None:
        conditions, opposite = _match_details(artifact, scenario_text or "")
    if not artifact.matrix or not artifact.priority_complete:
        return ScenarioUpdate(
            matched=tuple(conditions),
            before=before,
            after=before,
            reason="矩阵缺优先级列，无法机械再排序",
        )
    if not conditions:
        reason = (
            "改判条件表只写了该变量的反向变化（"
            + "、".join(f"{item.variable}{item.change}" for item in opposite)
            + "）：排序不变，需补充本方向的敏感性"
            if opposite
            else "改判条件表没有覆盖该变量：排序不变，需补充该变量的敏感性"
        )
        return ScenarioUpdate(
            matched=(),
            before=before,
            after=before,
            reason=reason,
        )
    base_priority = {row.company: int(row.priority or 0) for row in artifact.matrix}
    score = {name: -float(priority) for name, priority in base_priority.items()}
    applied = False
    for condition in conditions:
        for name, delta in condition.moves.items():
            if name in score and delta:
                score[name] += ARROW_STEP * delta
                applied = True
    ordered = sorted(score, key=lambda name: (-score[name], base_priority[name]))
    after = tuple(ordered)
    moved = {
        name: (before.index(name) + 1, after.index(name) + 1)
        for name in before
        if before.index(name) != after.index(name)
    }
    watchpoints = tuple(
        dict.fromkeys(item.watch for item in conditions if item.watch.strip())
    )
    if not applied:
        reason = "命中的改判条件没有写清受影响公司与方向，排序不变"
    elif not moved:
        reason = "命中条件的箭头不足以越过相邻公司，排序不变"
    else:
        reason = "按改判条件表箭头机械重排"
    return ScenarioUpdate(
        matched=tuple(conditions),
        before=before,
        after=after,
        moved=moved,
        watchpoints=watchpoints,
        unchanged=not moved,
        reason=reason,
    )


# ——————————————————————————————————————————— 跨轮：上一轮矩阵 → 机械再排序基线
_ROLE_MARK_RE = re.compile(r"^(user|assistant):\s?", re.M)


def latest_prior_artifact(conversation_context: str) -> RankingArtifact | None:
    """会话上下文里最近一条带完整矩阵的 assistant 回答。没有就 None，不猜。

    ``ConversationContext.to_prompt_block`` 把历史渲染成 ``role: content`` 行；这里按
    角色标记切段，只看 assistant 段，从最近往前找第一份解析得出、优先级完整的矩阵。
    """
    text = str(conversation_context or "")
    if not text.strip():
        return None
    marks = [(match.start(), match.group(1)) for match in _ROLE_MARK_RE.finditer(text)]
    segments: list[str] = []
    for index, (start, role) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(text)
        if role == "assistant":
            segments.append(text[start:end])
    if not segments:
        segments = [text]
    for segment in reversed(segments):
        artifact = parse_ranking_artifact(segment)
        if len(artifact.matrix) >= 2 and artifact.priority_complete:
            return artifact
    return None


def _render_order(order: tuple[str, ...]) -> str:
    return " > ".join(order) if order else "（空）"


def rerank_baseline_note(query: str, conversation_context: str) -> str:
    """再排序基线：按上一轮改判条件表机械推演，注入 episode 指令。没有上一轮矩阵返回空串。"""
    prior = latest_prior_artifact(conversation_context)
    if prior is None:
        return ""
    update = apply_scenario(prior, scenario_text=query)
    lines = [
        "【再排序基线】系统已按上一轮改判条件表机械推演（这是推演基线，不是新证据）：",
        f"- 上一轮排序：{_render_order(update.before)}",
    ]
    if update.matched:
        lines.append(
            "- 命中的改判条件："
            + "；".join(
                f"{item.variable}{item.change} → {item.raw_direction or '（方向未写）'}"
                + (f"（观察：{item.watch}）" if item.watch.strip() else "")
                for item in update.matched
            )
        )
        moved = "；".join(
            f"{name} {pair[0]}→{pair[1]}" for name, pair in update.moved.items()
        )
        lines.append(
            f"- 机械再排序结果：{_render_order(update.after)}"
            + (f"（变动：{moved}）" if moved else "（箭头不足以越过相邻公司，排序不变）")
        )
        if update.watchpoints:
            lines.append("- 观察点更新：" + "；".join(update.watchpoints))
    else:
        lines.append(f"- {update.reason}")
    lines.append(
        "- draft 的「新旧排序对照」表必须以此为基线；若你据本轮证据偏离机械结果，"
        "在「变动原因」列写出依据（证据序号）。未命中的情景变量如实写"
        "「排序不变，需补该变量的敏感性」并给出优先补什么。"
    )
    return "\n".join(lines)


def _rerank_table_order(artifact: RankingArtifact) -> tuple[str, ...]:
    rows = []
    for row in artifact.rerank_rows:
        company = _clean_company(row.get("公司", ""))
        match = _INT_RE.search(row.get("新优先级", ""))
        if company and match:
            rows.append((int(match.group()), company))
    rows.sort()
    return tuple(company for _, company in rows)


# ——————————————————————————————————————————— 收据（EVAL 可读）
def ranking_receipt(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    as_of: str | None = None,
    conversation_context: str = "",
) -> dict[str, object]:
    """EVAL 可读收据：``missing_outputs`` 恒在场；``ranking_intent`` 区分「契约齐」与「不适用」。

    再排序题另给 ``prior_rerank``（机械推演）与 ``rerank_consistent``（模型的新旧对照表
    是否与机械结果同序；无对照表或无上一轮矩阵时 None）——「表格、正文、计算一致」的程序核对。
    """
    intent = parse_ranking_intent(query, question_type)
    scenario_update = parse_scenario_update_intent(query) if intent else False
    artifact = parse_ranking_artifact(answer) if intent else None
    missing = contract_missing_outputs(answer, query=query, question_type=question_type)
    prior_rerank: dict[str, object] | None = None
    rerank_consistent: bool | None = None
    if scenario_update and artifact is not None:
        prior = latest_prior_artifact(conversation_context)
        if prior is not None:
            update = apply_scenario(prior, scenario_text=query)
            prior_rerank = update.to_payload()
            model_order = _rerank_table_order(artifact)
            if model_order:
                rerank_consistent = model_order == update.after
    return {
        "check": "ranking_contract",
        "ranking_intent": intent,
        "scenario_update_intent": scenario_update,
        "missing_outputs": list(missing),
        "matrix_rows": len(artifact.matrix) if artifact else 0,
        "flip_rows": len(artifact.flip_conditions) if artifact else 0,
        "competing_explanations": len(artifact.explanations) if artifact else 0,
        "next_actions": len(artifact.next_actions) if artifact else 0,
        "as_of": as_of,
        "artifact": artifact.to_payload() if artifact else None,
        "prior_rerank": prior_rerank,
        "rerank_consistent": rerank_consistent,
    }


# ——————————————————————————————————————————— 改判条件 → checkpoints（07 回检 / 09 续研的输入）
FLIP_SOURCE = "ranking_flip_condition"
FLIP_CATEGORY = "改判条件"
_DEFAULT_DUE_DAYS = 30


def _as_of_date(as_of: str | None) -> date:
    raw = str(as_of or "").strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


def _due_from_watch(watch: str, as_of: str | None) -> str:
    text = str(watch or "")
    found = _DATE_RE.search(text)
    if found:
        return found.group(1)
    cn = _CN_DATE_RE.search(text)
    if cn:
        return f"{cn.group(1)}-{int(cn.group(2)):02d}-{int(cn.group(3)):02d}"
    base = _as_of_date(as_of)
    span = _DAYS_RE.search(text)
    if span:
        amount = int(span.group(1))
        unit = span.group(2)
        days = amount if unit in {"天", "日"} else amount * 7 if unit == "周" else amount * 30
        return (base + timedelta(days=days)).isoformat()
    return (base + timedelta(days=_DEFAULT_DUE_DAYS)).isoformat()


def flip_condition_claim(condition: FlipCondition) -> str:
    direction = condition.raw_direction.strip() or "、".join(
        f"{name}{'↑' if delta > 0 else '↓'}" for name, delta in condition.moves.items()
    )
    watch = condition.watch.strip() or "未写观察指标"
    return f"改判条件｜若{condition.variable}{condition.change} → {direction}｜观察：{watch}"


def open_flip_condition_records(
    checkpoint_rows: list[dict[str, Any]],
    verdict_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """尚未拿到终态裁决的改判条件条目。"""
    from intelligence.services.checkpoints import TERMINAL_VERDICTS

    scored = {
        str(row.get("id") or "")
        for row in verdict_rows
        if row.get("verdict") in TERMINAL_VERDICTS
    }
    return tuple(
        row
        for row in checkpoint_rows
        if row.get("source") == FLIP_SOURCE
        and str(row.get("id") or "") not in scored
        and str(row.get("claim") or "").strip()
    )


def render_flip_conditions_for_prompt(
    records: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> str:
    if not records:
        return ""
    lines = []
    for row in records:
        due = str(row.get("due") or "未标到期")
        stocks = "、".join(str(item) for item in (row.get("stocks") or ()))
        claim = str(row.get("claim") or "").strip()
        suffix = f"（{stocks}）" if stocks else ""
        lines.append(f"- [due={due}] {claim}{suffix}")
    return "\n".join(lines)


def ingest_flip_conditions(
    checkpoints_path: str | Path,
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    as_of: str | None = None,
    theme: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """把改判条件登记进 checkpoints.jsonl。非排序题 / 无条目 / 重复条目时空操作。"""
    from intelligence.services.checkpoints import (
        load_checkpoints,
        load_verdicts,
        register_checkpoint,
    )

    if not parse_ranking_intent(query, question_type):
        return []
    artifact = parse_ranking_artifact(answer)
    if not artifact.flip_conditions:
        return []
    path = Path(checkpoints_path).expanduser()
    existing, _ = load_checkpoints(path)
    verdicts, _ = load_verdicts(path.with_name("verdicts.jsonl"))
    open_claims = {
        re.sub(r"\s+", "", str(row.get("claim") or ""))
        for row in open_flip_condition_records(existing, verdicts)
    }
    written: list[dict[str, Any]] = []
    themes = [theme] if theme and str(theme).strip() else None
    for condition in artifact.flip_conditions:
        if not condition.variable.strip():
            continue
        claim = flip_condition_claim(condition)
        key = re.sub(r"\s+", "", claim)
        if key in open_claims:
            continue
        _, record = register_checkpoint(
            path,
            claim=claim,
            due=_due_from_watch(condition.watch, as_of),
            category=FLIP_CATEGORY,
            source=FLIP_SOURCE,
            themes=themes,
            stocks=list(condition.companies) or None,
            session_id=session_id,
            metric={"type": "manual"},
        )
        open_claims.add(key)
        written.append(record)
    return written
