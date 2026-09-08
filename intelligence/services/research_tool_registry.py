"""GenericResearchOwner 的类型化工具白名单。

工具仍复用已有 agent runner；本模块只负责能力声明、参数边界、去重和
公开 observation，避免第二套数据源实现。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from functools import partial
import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal
import urllib.parse

from intelligence.services.tool_payload import tool_payload_meta

from intelligence.services import agent_research, closed_loop_retrieval, query_ledger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchRunContext,
)

if TYPE_CHECKING:  # pragma: no cover
    # 只在类型检查期 import：episode_scope 运行期 import 本模块，反向的运行期
    # import 会成环。执行路径上 scope 是鸭子类型用的，不需要真的拿到这个类。
    from intelligence.services.episode_scope import EpisodeScope


# 工具流水线的阶段事件名。与 dsh 的 tools/* 同形，但串留在本仓命名空间下：
# 事件名会进 Trace 与评测 artifact，跟 dsh 的字面串绑死，将来换底座就得改数据。
#
# 定义在本模块而不是 episode_scope，是因为发射点在这里，且本模块是它的下层——
# 反过来会成环。episode_scope 转出这三个名字，供事件消费方 import。
TOOL_PRE_EXECUTE = "tool/pre_execute"
TOOL_RESULT = "tool/result"
TOOL_ERROR = "tool/error"


# 第四个字段 ``produces`` 声明该工具能贡献哪些 output_id（词表来自 task_frame.py
# 题型映射 + query_understanding.py operator 映射）。**保守声明，宁缺勿滥**——只
# 填能从 runner 代码路径确认的；拿不准就留空 frozenset()。
#
# ``produces`` 不改变路由，不改变工具可用性。它只服务于事前可满足性预检：
# 「这套授权工具在理论上能不能产出某个 required_output」。预检 fail-open——
# 声明不全只会漏抓，不会误拦（详见 ``check_satisfiability``）。
_DEFAULT_TOOL_METADATA: dict[str, tuple[str, str, str, frozenset[str]]] = {
    "finance_query": (
        "finance_query",
        "按语义数据集、指标、维度、筛选和时间范围查询本地结构化金融数据",
        "current",
        # risk_signals：实测 market_watch 回合里由 duckdb_semantic_query 绑定并判
        # fulfilled（3 例），不是推测。见 TestProducesMatchesHistory。
        #
        # ⚠️ 可复现性：证据来自 ~/tmp 和 ~/agent-memory/.foresight 下的
        # continuous-episode.json（gitignored、随清理消失）。观测时（2026-08-06）
        # 全部 45 份存在且可读，但这不可在 CI 里复验。将来对账发现这条可疑时，
        # 重跑 /tmp/check_produces_vs_history.py 的逻辑确认 episode 文件是否仍在。
        frozenset(
            {"supporting_evidence", "data_date", "market_change", "risk_signals"}
        ),
    ),
    "evidence_search": (
        "evidence_search",
        "对本地知识证据执行窄口径、宽口径和反方闭环检索",
        "current",
        frozenset({"supporting_evidence", "counterpoint"}),
    ),
    "kb_search": (
        "kb_search",
        "本地知识库检索",
        "stable",
        frozenset({"supporting_evidence", "direct_definition", "direct_explanation", "direct_answer"}),
    ),
    "web_search": (
        "web_search",
        "全网网页检索",
        "current",
        frozenset({"supporting_evidence", "event_facts", "impact_transmission"}),
    ),
    # 取页（不是检索）：给 web_search 回来的 URL 拉正文。knevo 在 2026-09-02 茅台题上
    # 赢的机制就是这一步——我们的 web_search 只回 160 字符 snippet，线索到不了可读证据。
    # produces 只声明能从 runner 路径确认的：正文里有什么全看页面，保守留两项。
    "web_fetch": (
        "web_fetch",
        "按 URL 取网页正文全文（取页，不是检索；URL 先由 web_search / news_search 给出）",
        "current",
        frozenset({"supporting_evidence", "event_facts"}),
    ),
    "news_search": (
        "news_search",
        "财经新闻检索",
        "current",
        frozenset(
            {
                "supporting_evidence",
                "event_facts",
                "impact_transmission",
                "prime_news",
            }
        ),
    ),
    "graph_lookup": (
        "graph_lookup",
        "知识图谱实体与关系",
        "stable",
        frozenset({"chain_mapping", "company_mapping", "relation_map"}),
    ),
    "evidence_lookup": (
        "evidence_lookup",
        "本地证据索引",
        "stable",
        frozenset({"supporting_evidence"}),
    ),
    "memory_lookup": (
        "memory_lookup",
        "用户自己过去的判断与纠偏原则（历史先验，不是市场事实）",
        "stable",
        # 只声明先验专用槽。市场事实类 id（supporting_evidence / event_facts
        # …）按定义不是本工具的产出；残差地板的 prime_memory 才是它能填的格子。
        frozenset({"prime_memory"}),
    ),
    "l3_lookup": (
        "l3_lookup",
        "官方公告与互动证据",
        "current",
        frozenset({"supporting_evidence", "fact_value"}),
    ),
    "market_data": (
        "market_data",
        "结构化行情与市场时序",
        "current",
        frozenset(
            {
                "current_baseline",
                "market_summary",
                "supporting_evidence",
                "data_date",
                "prime_quote",
            }
        ),
    ),
    "financial_data": (
        "financial_data",
        "结构化逐季财务指标",
        "current",
        frozenset({"financial_assessment", "metric_evidence", "supporting_evidence"}),
    ),
    "mainline_context": (
        "mainline_context",
        "同日主线与板块结构",
        "current",
        frozenset({"mainline_structure", "supporting_evidence"}),
    ),
    # 子研究（spec 2026-09-03-subagent-tool-design：抄 dsh tool-subagent 的形状，账本用我们的）。
    # 它不是新数据源：每支分支跑的是同一台 Episode 机器、同一份只读工具，证据 append 进
    # 父账本、hash 由父账本铸——所以 produces 只声明「证据」这一项，分支拿到什么全看它
    # 点了哪些工具。runner 由运行时按 episode 绑定（要协调器 + 父证据账本），装配层
    # 没有 runner 就不挂（没源不挂）。
    "sub_research": (
        "sub_research",
        "把 1–3 个可独立取证的子问题并行交给子研究分支，各支带自己的工具预算跑到终态后一次返回证据",
        "current",
        frozenset({"supporting_evidence"}),
    ),
    # 派生计算（spec capability-amplification §3.4，2026-09-08）：对本回合已绑定的证据跑一段
    # Python（口径核对 / 差额 / 敏感性 / 统计检验），沙箱不外呼不写库，产物带
    # input_evidence_hashes + 原样脚本 + 继承自输入的 as_of。它不修任何已量出的缺陷，
    # 开的是「现有工具完全答不了」的一类题。runner 由运行时按 episode 绑（要证据账本），
    # 装配层没有账本就不挂（与 sub_research 同规矩）。produces 不写自己的名字——
    # 词表里 output_id ≠ 工具名（test_produces_only_contains_known_output_ids）；派生结果
    # 以 supporting_evidence 身份进绑定，档次由 evidence_tier=derived_calculation 说明。
    "derived_calculation": (
        "derived_calculation",
        "在只读沙箱里对本回合已取到的证据跑一段 Python 做计算或跨源口径核对，结果作为带输入哈希链的派生证据返回",
        "current",
        frozenset({"supporting_evidence"}),
    ),
}
DEFAULT_RESEARCH_CAPABILITIES = tuple(
    dict.fromkeys(
        capability
        for capability, _description, _freshness, _produces in _DEFAULT_TOOL_METADATA.values()
    )
)


class UnknownResearchTool(ValueError):
    """LLM 选择了未注册工具。"""


class InvalidResearchToolArguments(ValueError):
    """模型给出的工具参数不满足该工具自己的接口。"""

    def __init__(self, message: str, *, code: str = "invalid_arguments") -> None:
        super().__init__(message)
        self.code = code


QUERY_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "minLength": 1,
            # 「必须在工具描述中加以说明」那一半（ch4 参数传递的保真性）：
            # 另一半是 execute() 把代偿写进 observation。两半都要有，
            # 只做转换不声明就是书里点名的静默输入转换。
            #
            # 实测依据：551 次 query 类调用里 276 次（50%）把整个参数对象
            # 又 JSON 编码了一遍，kb_search 高达 83%。见
            # ``unwrap_double_encoded_query`` 的 docstring。
            "description": (
                "检索词本身，纯文本。"
                '例："瑞华泰 聚酰亚胺薄膜 产能"。'
                '不要再包一层 JSON——写成 "{\\"query\\": \\"…\\"}" 时，'
                "系统会拆掉外层并在返回里说明，但那一轮已经浪费了。"
            ),
        }
    },
    "required": ["query"],
    "additionalProperties": False,
}
EMPTY_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
# financial_data 仍是一回合一份快照（query_scope="episode"），但快照的**窗口**由模型
# 可选指定：不传取最近 6 期；传「2024年报」则放宽到覆盖该期。2026-09-02 茅台题两臂
# 都拿不到 2024 年报，正是因为它固定 6 期而 2024-12-31 是第 7 行——模型无从告诉工具
# 自己要哪一期。
FINANCIAL_DATA_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "report_period": {
            "type": "string",
            "minLength": 1,
            "description": (
                "可选。要覆盖到的报告期，写年份加期别，"
                '例："2024年报"、"2025三季报"、"2025Q1"、"2024"（按年报）。'
                "不传时取最近 6 期。一轮只取一次快照，要看某一期就在这次调用里传。"
            ),
        }
    },
    "additionalProperties": False,
}


# 逐工具的 query 形状提示。**只给形状确实不同的那几个**，其余用通用描述——
# 每个工具都写一句会稀释掉真正重要的差异。
#
# 依据是 2026-08-12 的历史对账 + 代码核对，不是猜的：
#   evidence_lookup  28/28 空手。``KnowledgeAdapter.get_evidence`` 是
#                    ``item.get("target") != target`` **精确字符串相等**，
#                    无归一、无分词、无模糊。实测「瑞华泰」→3 条，
#                    「瑞华泰 688323 估值 PB 情景 保守 中性 乐观」→0 条。
#                    **工具没坏，是被当成搜索引擎用了。**
#   graph_lookup     0% 空手。它走 ``get_concept_matches`` 的打分模糊匹配，
#                    所以长 query 也能命中——正是这个对照证明了上面那条是形状问题。
#
# ch4 §工具描述的艺术：「清晰列出工具的边界条件——做不到什么、不接受什么输入
# ——往往比描述能力本身更重要」。
_QUERY_PARAM_HINTS: dict[str, str] = {
    "evidence_lookup": (
        "**必须是索引里登记的实体或概念名本身**，单个词，"
        "按精确字符串匹配——多加一个词就会零命中。"
        '例："瑞华泰"、"3D打印"。'
        '不要传检索短语：写成 "瑞华泰 688323 估值 PB 情景" 必然查不到任何东西。'
        "不确定名字怎么登记的，先用 graph_lookup 找到准确名称再来查。"
    ),
}


def query_parameters(tool: str) -> dict[str, object]:
    """按工具生成 query 参数 schema：形状不同的给专属提示，其余用通用描述。"""

    hint = _QUERY_PARAM_HINTS.get(tool)
    if not hint:
        return dict(QUERY_TOOL_PARAMETERS)
    base = QUERY_TOOL_PARAMETERS["properties"]["query"]
    assert isinstance(base, Mapping)
    return {
        **QUERY_TOOL_PARAMETERS,
        "properties": {"query": {**base, "description": hint}},
    }


ToolInput = object
ToolArgumentParser = Callable[
    [Mapping[str, object]],
    tuple[ToolInput, str],
]
def parse_query_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    if set(arguments) != {"query"}:
        raise InvalidResearchToolArguments("expected one query argument")
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise InvalidResearchToolArguments(
            "query must be a non-empty string",
            code="invalid_query",
        )
    cleaned = query.strip()
    return cleaned, cleaned


def parse_snapshot_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    if arguments:
        raise InvalidResearchToolArguments("snapshot tool accepts no arguments")
    return "", "snapshot"


URL_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "minLength": 1,
            "description": (
                "要取正文的网页地址，必须是完整的 http(s) URL，"
                "通常来自 web_search / news_search 返回的 source。"
                '例："https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/'
                'stockid/600519.phtml"。一次一个 URL。'
            ),
        }
    },
    "required": ["url"],
    "additionalProperties": False,
}


def parse_url_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    if set(arguments) != {"url"}:
        raise InvalidResearchToolArguments("expected one url argument")
    url = arguments.get("url")
    if not isinstance(url, str) or not url.strip():
        raise InvalidResearchToolArguments(
            "url must be a non-empty string",
            code="invalid_query",
        )
    cleaned = url.strip()
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidResearchToolArguments(
            "url must be an absolute http(s) URL with a host",
            code="invalid_query",
        )
    return cleaned, cleaned


SUB_RESEARCH_MAX_GOALS = 3
# 一支分支成功一次的最小工具窗（秒）。不是延迟实测，是设计常数：与
# ``runtime/sub_research.MAX_SECONDS_PER_BRANCH`` 同值（测试钉相等）——窗比它小，
# 分支拿到的预算就装不下一次「查一两个工具 + 收口」，spec §4 的可达性判据就是这个数。
SUB_RESEARCH_MIN_WINDOW_SECONDS = 60.0
SUB_RESEARCH_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "goals": {
            "type": "array",
            "minItems": 1,
            "maxItems": SUB_RESEARCH_MAX_GOALS,
            "items": {"type": "string", "minLength": 1},
            "description": (
                "1–3 个彼此独立、各自可以直接去取证的子问题，每条一句话写清要查什么。"
                '例：["长电科技 2025 年报 先进封装收入占比", "封测行业 2026 年产能利用率 卖方数据"]。'
                "同一个问题不要拆成因果相连的两步（第二步依赖第一步结果的不要拆）；"
                "重复或空的条目会被拒绝，不会静默截断。"
            ),
        }
    },
    "required": ["goals"],
    "additionalProperties": False,
}


def parse_sub_research_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    """``goals`` 读且只读这一个参数；空 / 超 3 / 重复 → 拒绝带原因，不静默截断（spec §3 第 3 条）。

    runner 输入是 goals 的 JSON 数组串（工具 runner 的第一个位置参数是字符串），
    display 用「；」连接给事件与模型看。
    """

    if set(arguments) != {"goals"}:
        raise InvalidResearchToolArguments("sub_research accepts exactly one goals argument")
    raw_goals = arguments.get("goals")
    if not isinstance(raw_goals, list) or not raw_goals:
        raise InvalidResearchToolArguments(
            "goals argument must be a non-empty array of strings",
            code="invalid_query",
        )
    goals: list[str] = []
    for item in raw_goals:
        if not isinstance(item, str) or not item.strip():
            raise InvalidResearchToolArguments(
                "each item in the goals argument must be a non-empty string",
                code="invalid_query",
            )
        goal = item.strip()
        if goal in goals:
            raise InvalidResearchToolArguments(
                f"goals argument repeats a goal: {goal}",
                code="invalid_query",
            )
        goals.append(goal)
    if len(goals) > SUB_RESEARCH_MAX_GOALS:
        raise InvalidResearchToolArguments(
            f"goals argument supports at most {SUB_RESEARCH_MAX_GOALS} unique goals",
            code="invalid_query",
        )
    return json.dumps(goals, ensure_ascii=False), "；".join(goals)


# 派生计算（spec capability-amplification §3.4）：模型写一段 Python，在沙箱里对**本回合
# 已绑定的证据**做算术 / 口径核对 / 敏感性，产物带 input_evidence_hashes + script + as_of。
# 参数面只有四个键；脚本正文的合法性（禁用模块等）在 runner 里判，回结构化错误，
# 不在这里拒——模型改一次脚本就能过，不该按「参数错」计一次 invalid_action。
DERIVED_CALCULATION_MAX_TIMEOUT = 60
DERIVED_CALCULATION_DEFAULT_TIMEOUT = 20
DERIVED_CALCULATION_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "script": {
            "type": "string",
            "minLength": 1,
            "description": (
                "要在沙箱里运行的 Python 脚本正文。可用变量 EVIDENCE（本回合已有证据的列表，"
                "每条含 ref（E 号）/ hash / tool / title / detail / source / as_of / tier / "
                "observations[{metric, value, as_of, subject}]）；用 emit({...}) 输出唯一结果字典"
                "（数值、判定、说明都放进去），不 emit 视为没有结果。可 import 标准库与 "
                "numpy / pandas；不能联网、不能起进程、不能写工作目录以外的文件。"
                "需要查本地行情库时先传 use_duckdb=true，再用 duckdb_connect() 拿只读连接。"
            ),
        },
        "purpose": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": (
                "一句话说明这次计算要回答什么（例：「核对 2024 年报净利润两个来源是否一致」）。"
                "会原样写进产物标题，供读收据的人对照脚本。"
            ),
        },
        "use_duckdb": {
            "type": "boolean",
            "description": "是否挂载本地行情 DuckDB 的只读连接（默认 false；只在脚本要查库时开）。",
        },
        "timeout_seconds": {
            "type": "integer",
            "minimum": 1,
            "maximum": DERIVED_CALCULATION_MAX_TIMEOUT,
            "description": f"脚本墙钟上限秒数，默认 {DERIVED_CALCULATION_DEFAULT_TIMEOUT}，最多 {DERIVED_CALCULATION_MAX_TIMEOUT}。",
        },
    },
    "required": ["script", "purpose"],
    "additionalProperties": False,
}


def parse_derived_calculation_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    """四个键各按类型读，多余键 / 空脚本 / 空目的直接拒，不猜不补。

    runner 输入是规整后参数的 JSON 串（工具 runner 的第一个位置参数是字符串），
    display 用 purpose 给事件与模型看——脚本正文不进 display。
    """

    allowed = {"script", "purpose", "use_duckdb", "timeout_seconds"}
    unknown = set(arguments) - allowed
    if unknown:
        raise InvalidResearchToolArguments(
            "derived_calculation accepts only the script / purpose / use_duckdb / timeout_seconds "
            "arguments; unexpected: " + ", ".join(sorted(str(item) for item in unknown))
        )
    script = arguments.get("script")
    if not isinstance(script, str) or not script.strip():
        raise InvalidResearchToolArguments(
            "script argument must be a non-empty Python source string",
            code="invalid_query",
        )
    purpose = arguments.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip():
        raise InvalidResearchToolArguments(
            "purpose argument must be a non-empty string (one sentence: what the calculation answers)",
            code="invalid_query",
        )
    use_duckdb = arguments.get("use_duckdb", False)
    if not isinstance(use_duckdb, bool):
        raise InvalidResearchToolArguments("use_duckdb argument must be a boolean")
    timeout = arguments.get("timeout_seconds", DERIVED_CALCULATION_DEFAULT_TIMEOUT)
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise InvalidResearchToolArguments("timeout_seconds argument must be an integer")
    if not 1 <= timeout <= DERIVED_CALCULATION_MAX_TIMEOUT:
        raise InvalidResearchToolArguments(
            f"timeout_seconds argument must be between 1 and {DERIVED_CALCULATION_MAX_TIMEOUT}"
        )
    cleaned_purpose = purpose.strip()[:200]
    payload = {
        "script": script,
        "purpose": cleaned_purpose,
        "use_duckdb": use_duckdb,
        "timeout_seconds": timeout,
    }
    return json.dumps(payload, ensure_ascii=False), cleaned_purpose


def parse_financial_data_arguments(
    arguments: Mapping[str, object],
) -> tuple[str, str]:
    """快照工具 + 一个可选 ``report_period``。空参合法，等同旧的无参快照。"""

    if not arguments:
        return "", "snapshot"
    if set(arguments) != {"report_period"}:
        raise InvalidResearchToolArguments(
            "financial_data snapshot accepts only an optional report_period argument"
        )
    value = arguments.get("report_period")
    if not isinstance(value, str) or not value.strip():
        raise InvalidResearchToolArguments(
            "report_period must be a non-empty string when given",
            code="invalid_query",
        )
    cleaned = value.strip()
    return cleaned, cleaned


def unwrap_double_encoded_query(
    raw: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    """模型把整个参数对象又 JSON 编码了一遍时，拆回来并**说出来**。

    失败形状（2026-08-12 历史对账，扫 44564 份 run 产物）：模型发出的
    ``query`` 值本身又是一个 JSON 串，例如
    ``{"query": "{\\"query\\":\\"瑞华泰 688323 D5 PB 情景估值\\"}"}``，
    于是检索器拿着那串花括号去做全文检索，必然空手。
    **551 次 query 类调用里 276 次（50%）是这个形状**，kb_search 高达 83%。

    同工具内部的对照（聚合相关性会误导，必须按工具分开看）：

    | 工具 | 包了的空手率 | 没包的空手率 |
    |---|---|---|
    | evidence_search | 100% (14/14) | 37% (7/19) |
    | web_search | 100% (4/4) | 14% (4/28) |
    | news_search | 46% | 55% ← **无效应** |

    即：它确实打死了 evidence_search 与 web_search，但**解释不了 news_search**。
    别把它当成所有空手的原因。

    ⚠ **必须告知模型，不能静默改**。ai-agent-book ch4「参数传递的保真性」把
    静默输入转换列为比功能缺失更隐蔽的反模式（Cursor 静默转换弯引号那个案例），
    并明确要求「如果确实需要对输入进行规范化处理，必须在工具描述中加以说明，
    并在工具返回中明确告知模型」。本函数只负责拆 + 生成告知文本，
    ``execute`` 负责把它拼进 observation，参数描述里另有一句写明。
    仓内先例：``finance_query.normalize_spec`` 的日期代偿就是这么做的。

    只拆**单键 query** 这一种形状。多键或键名不同的一律原样退回——
    认不出来就别动（BUILD 模式 7），猜着拆会把模型真正想搜的内容改掉。
    """

    if set(raw) != {"query"}:
        return dict(raw), ""
    value = raw.get("query")
    if not isinstance(value, str):
        return dict(raw), ""
    text = value.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return dict(raw), ""
    try:
        inner = json.loads(text)
    except (TypeError, ValueError):
        return dict(raw), ""
    if not isinstance(inner, dict) or set(inner) != {"query"}:
        return dict(raw), ""
    unwrapped = inner.get("query")
    if not isinstance(unwrapped, str) or not unwrapped.strip():
        return dict(raw), ""
    return (
        {"query": unwrapped.strip()},
        (
            "已自动拆掉多包的一层 JSON（本次实际检索的是内层的检索词）；"
            "后续 query 请直接传检索词本身，不要再包一层 {\"query\": ...}"
        ),
    )


@dataclass(frozen=True)
class PreparedToolArguments:
    tool: str
    raw: Mapping[str, object]
    runner_input: ToolInput
    normalized_key: str
    display_query: str
    # 输入被规范化时的告知文本，由 ``execute`` 拼进 observation 交回模型。
    # 空串表示没做任何转换——这是常态，别默认非空。
    normalization_note: str = ""


ToolCutoffResolver = Callable[
    [PreparedToolArguments, ResearchRunContext],
    InformationCutoff,
]


@dataclass(frozen=True)
class ToolRunResult:
    evidence: tuple[agent_research.AgentEvidence, ...]
    observation: str
    trace: ProviderTrace
    gaps: tuple[str, ...] = ()
    dataset: str = "unknown"
    caliber: str = ""
    payload_field_names: tuple[str, ...] = ()
    payload_sha256: str = ""
    telemetry: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        evidence = tuple(self.evidence)
        if any(not isinstance(item, agent_research.AgentEvidence) for item in evidence):
            raise TypeError("tool evidence must contain AgentEvidence values")
        if not isinstance(self.trace, ProviderTrace):
            raise TypeError("tool trace must be a ProviderTrace")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "observation", str(self.observation or ""))
        object.__setattr__(
            self,
            "gaps",
            tuple(
                dict.fromkeys(
                    str(item).strip() for item in self.gaps if str(item).strip()
                )
            ),
        )
        dataset, caliber, names, digest = tool_payload_meta(
            dataset=self.dataset,
            caliber=self.caliber,
            field_names=self.payload_field_names,
        )
        object.__setattr__(self, "dataset", dataset)
        object.__setattr__(self, "caliber", caliber)
        object.__setattr__(self, "payload_field_names", names)
        object.__setattr__(self, "payload_sha256", digest)
        object.__setattr__(self, "telemetry", dict(self.telemetry or {}))


class ToolRunnerAdapter:
    """Normalize legacy tuple runners into the registry's one true result type."""

    def __init__(self, runner: agent_research.ToolRunner) -> None:
        self._runner = runner

    def __call__(
        self,
        value: ToolInput,
        context: agent_research.AgentToolContext,
    ) -> ToolRunResult:
        raw = agent_research._run_tool(self._runner, value, context)
        if isinstance(raw, ToolRunResult):
            return raw
        if not isinstance(raw, tuple):
            raise TypeError("research tool runner must return ToolRunResult")
        if len(raw) == 3:
            evidence, observation, trace = raw
            gaps: tuple[str, ...] = ()
        elif len(raw) == 4:
            evidence, observation, trace, raw_gaps = raw
            gaps = tuple(raw_gaps)
        else:
            raise TypeError("legacy research tool runner returned invalid result")
        return ToolRunResult(
            evidence=tuple(evidence),
            observation=str(observation or ""),
            trace=trace,
            gaps=gaps,
        )


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("tool schema must be JSON-compatible")


def _copy_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _copy_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_json(item) for item in value]
    return value


def copy_tool_parameters(parameters: Mapping[str, object]) -> dict[str, object]:
    copied = _copy_json(parameters)
    if not isinstance(copied, dict):
        raise TypeError("tool parameters must be an object schema")
    return copied


def _remember_authorized_trade_dates(
    context: ResearchRunContext,
    evidence: list[agent_research.AgentEvidence],
) -> None:
    """把本轮已交付证据的交易日记到 context，供后续窗口闸门认。"""

    dates = context.authorized_trade_dates
    for item in evidence:
        parsed = closed_loop_retrieval.parse_source_date(getattr(item, "source_date", None))
        if parsed is not None:
            dates.add(parsed.isoformat())


@dataclass(frozen=True)
class ToolObservation:
    tool: str
    query: str
    evidence: tuple[agent_research.AgentEvidence, ...]
    observation: str
    trace: ProviderTrace
    gaps: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()
    dataset: str = "unknown"
    caliber: str = ""
    payload_field_names: tuple[str, ...] = ()
    payload_sha256: str = ""
    telemetry: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str
    description: str
    cost: str
    freshness: str
    runner: agent_research.ToolRunner | ToolRunnerAdapter
    # 行为契约：什么时候该用它、怎样用才不误读、什么时候该换别的工具。
    #
    # ``description`` 只说「是什么」。马书 ch08 的结论是「优秀的工具提示词不是
    # 功能文档，而是行为契约」；ch27 模式六进一步给了理由——**时序对齐**：模型
    # 决定调用某工具时，该工具的约束正好在它的注意力焦点内，而写在系统提示词里
    # 的同一句话需要模型在数万 token 的上下文里「回忆」，长会话中不可靠。
    #
    # 数据类层面空字符串合法（测试与探针替身要用），但装配面不放行：
    # ``default_registry`` / ``build_episode_registry`` 出口都过 ``require_tool_contracts``，
    # 模型能点到的工具必须有契约。没有经过验证的契约别编——写不出来就先别挂进注册表。
    contract: str = ""
    # ``episode`` means the tool returns one complete turn-scoped snapshot;
    # rewriting its query cannot produce a different evidence surface.
    query_scope: Literal["query", "episode"] = "query"
    parameters: Mapping[str, object] = field(
        default_factory=lambda: dict(QUERY_TOOL_PARAMETERS)
    )
    parse_arguments: ToolArgumentParser = parse_query_arguments
    cutoff_resolver: ToolCutoffResolver | None = None
    # 该工具能贡献哪些 output_id。声明式契约，服务于事前可满足性预检——
    # ``check_satisfiability`` 用它在工具真正运行前判断「这套工具理论上能否
    # 产出某 required_output」。空 frozenset 合法（保守声明：拿不准就留空，
    # 预检会 fail-open 放行，不会误拦）。
    produces: frozenset[str] = field(default_factory=frozenset)
    # 这个工具**成功一次**至少要几秒（领域申报，来自生产实测；见 MIN_WINDOW_SECONDS）。
    # 底座在组菜单时拿它对照本轮能授的工具窗：装不下的就不摆给模型——与其让模型
    # 点一个必超时的工具烧掉 23s 再吃一个 tool_timeout，不如这轮就别让它看见。
    # None = 没有可靠读数，不裁。这是可见性，不是预算：不改任何授予算术。
    min_window_seconds: float | None = None
    # 重放安全（运行底座终态稿 §2 钦定词 / §5 接触点 1）：崩溃后能否用同参数重跑。
    # 这是**意图侧的声明**，不是效果侧的「幂等」——读工具默认 ``safe``；将来注册写工具
    # （下单、落库、发消息）必须显式 ``never``，恢复时对它只合成 ``tool_error{interrupted}``、
    # 绝不重跑。底座读它，不改任何执行行为。
    replay: Literal["safe", "never"] = "safe"

    def __post_init__(self) -> None:
        if not isinstance(self.runner, ToolRunnerAdapter):
            object.__setattr__(self, "runner", ToolRunnerAdapter(self.runner))
        frozen_parameters = _freeze_json(self.parameters)
        if not isinstance(frozen_parameters, Mapping):
            raise TypeError("tool parameters must be an object schema")
        object.__setattr__(self, "parameters", frozen_parameters)
        if not isinstance(self.produces, frozenset):
            object.__setattr__(self, "produces", frozenset(self.produces))
        if self.replay not in ("safe", "never"):
            raise ValueError(f"tool replay declaration must be safe|never: {self.replay!r}")


class ResearchToolRegistry:
    def __init__(
        self,
        specs: tuple[ToolSpec, ...],
        *,
        opening_prefetch: tuple[agent_research.AgentEvidence, ...] = (),
    ) -> None:
        self._specs = {spec.name: spec for spec in specs}
        self.opening_prefetch = tuple(opening_prefetch)

    def resolve(self, name: str) -> ToolSpec:
        spec = self._specs.get(str(name).strip())
        if spec is None:
            raise UnknownResearchTool(str(name))
        return spec

    def with_specs(self, *extra: ToolSpec) -> "ResearchToolRegistry":
        """同一份注册表加几个 episode 期才绑得出 runner 的工具（如 ``sub_research``）。

        原注册表不动；同名以新的为准。``opening_prefetch`` 原样带过去。
        """

        merged = {**self._specs, **{spec.name: spec for spec in extra}}
        return ResearchToolRegistry(
            tuple(merged.values()),
            opening_prefetch=self.opening_prefetch,
        )

    def without(self, *names: str) -> "ResearchToolRegistry":
        """去掉几个工具的副本——子研究分支的注册表不含 ``sub_research``（深度 = 1）。"""

        dropped = {str(name).strip() for name in names}
        return ResearchToolRegistry(
            tuple(spec for spec in self._specs.values() if spec.name not in dropped),
            opening_prefetch=self.opening_prefetch,
        )

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def capabilities(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(spec.capability for spec in self._specs.values()))

    def authorized_specs(
        self,
        allowed: tuple[str, ...] | None = None,
    ) -> tuple[ToolSpec, ...]:
        """Return registered tools whose declared capability is authorized.

        Order is sorted by ``name`` so ``prompt_block`` and
        ``tool_definitions`` stay stable if registration insertion order
        changes.
        """

        if allowed is None:
            specs = tuple(self._specs.values())
        else:
            allowed_set = set(allowed)
            specs = tuple(
                spec
                for spec in self._specs.values()
                if spec.capability in allowed_set
            )
        return tuple(sorted(specs, key=lambda spec: spec.name))

    def tool_definitions(
        self,
        allowed: tuple[str, ...] | None = None,
    ) -> list[dict[str, object]]:
        """Expose the authorized read-only tools as function-call schemas."""

        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    # 契约跟着工具描述走，而不是塞进系统提示词——见 ToolSpec.contract。
                    "description": (
                        f"{spec.description}\n{spec.contract}"
                        if spec.contract
                        else spec.description
                    ),
                    "parameters": copy_tool_parameters(spec.parameters),
                },
            }
            for spec in self.authorized_specs(allowed)
        ]

    def prepare(
        self,
        name: str,
        arguments: str | Mapping[str, object] | PreparedToolArguments,
    ) -> PreparedToolArguments:
        spec = self.resolve(name)
        if isinstance(arguments, PreparedToolArguments):
            if arguments.tool != spec.name:
                raise InvalidResearchToolArguments(
                    "prepared arguments belong to another tool"
                )
            return arguments
        if isinstance(arguments, str):
            raw: dict[str, object] = {"query": arguments}
        elif isinstance(arguments, Mapping):
            copied = _copy_json(arguments)
            if not isinstance(copied, dict):
                raise InvalidResearchToolArguments("tool arguments must be an object")
            raw = copied
        else:
            raise InvalidResearchToolArguments("tool arguments must be an object")
        raw, normalization_note = unwrap_double_encoded_query(raw)
        try:
            runner_input, display_query = spec.parse_arguments(raw)
        except InvalidResearchToolArguments:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidResearchToolArguments(str(exc)) from exc
        try:
            canonical = json.dumps(
                raw,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise InvalidResearchToolArguments(
                "tool arguments must be JSON serializable"
            ) from exc
        normalized_key = (
            query_ledger.normalize_query(display_query)
            if set(raw) == {"query"} and isinstance(raw.get("query"), str)
            else canonical
        )
        return PreparedToolArguments(
            tool=spec.name,
            raw=raw,
            runner_input=runner_input,
            normalized_key=normalized_key,
            display_query=str(display_query or "").strip() or canonical,
            normalization_note=normalization_note,
        )

    def prompt_block(self, allowed: tuple[str, ...] | None = None) -> str:
        return "\n".join(
            f"- {spec.name}（{spec.capability}，{spec.cost}，{spec.freshness}）："
            f"{spec.description}"
            + (f"\n  · {spec.contract}" if spec.contract else "")
            for spec in self.authorized_specs(allowed)
        )

    def execute(
        self,
        name: str,
        arguments: str | Mapping[str, object] | PreparedToolArguments,
        *,
        context: ResearchRunContext,
        step_id: str,
        is_cancelled: Callable[[], bool] | None = None,
        scope: EpisodeScope | None = None,
        tool_call_id: str = "",
    ) -> ToolObservation:
        """执行一个工具。

        ``scope`` 缺省为 ``None``，此时行为与接线前**逐字节一致**：不发事件、
        不登记调用。这是刻意的——现存三十余个调用方一个都不用改，
        阶段事件是给愿意传 scope 的调用方的增量能力，不是所有人的新负担。
        """

        spec = self.resolve(name)
        if spec.capability not in context.contract.allowed_capabilities:
            # 错误契约保持不变（仍抛 UnknownResearchTool、消息逐字不变）：
            # ``unknown_or_unauthorized_tool`` 这个串有 4 个生产者、1 个分支消费者
            # （agent_episode.py:311），并且进了模型可见的消息文本。拆它是一次
            # 有意的错误契约变更，不该混在「接入阶段事件」里做。
            #
            # 但**区分**不用等：它落进阶段事件（新增，无存量消费者），
            # 于是诊断拿到了区分，契约一点没动。
            if scope is not None:
                decision = scope.authorize(name)
                scope.emit(
                    TOOL_ERROR,
                    {
                        "tool": spec.name,
                        "tool_call_id": tool_call_id,
                        "step_id": step_id,
                        "stage": "authorize",
                        # 与 wire 上那个压扁的串不同，这里是分开的
                        "reason": decision.reason,
                        "capability": decision.capability,
                    },
                )
            raise UnknownResearchTool(
                f"能力未授权：{spec.capability}（工具 {spec.name}）"
            )

        prepared = self.prepare(name, arguments)
        if spec.name in {"news_search", "web_search"}:
            from intelligence.services.task_frame import (
                strip_default_a_share_search_token,
            )

            query_text = (
                prepared.runner_input
                if isinstance(prepared.runner_input, str)
                else prepared.display_query
            )
            cleaned, hygiene_note = strip_default_a_share_search_token(
                str(query_text or ""),
                context.contract.question,
            )
            if hygiene_note:
                raw = dict(prepared.raw)
                if "query" in raw:
                    raw["query"] = cleaned
                prepared = replace(
                    prepared,
                    raw=raw,
                    runner_input=(
                        cleaned
                        if isinstance(prepared.runner_input, str)
                        else prepared.runner_input
                    ),
                    display_query=cleaned or prepared.display_query,
                    normalized_key=query_ledger.normalize_query(cleaned)
                    if cleaned
                    else prepared.normalized_key,
                    normalization_note="；".join(
                        part
                        for part in (prepared.normalization_note, hygiene_note)
                        if part
                    ),
                )
        normalized = prepared.normalized_key
        effective_context = context
        if spec.cutoff_resolver is not None:
            requested_cutoff = spec.cutoff_resolver(prepared, context)
            if not isinstance(requested_cutoff, InformationCutoff):
                raise TypeError("tool cutoff resolver must return InformationCutoff")
            effective_context = replace(
                context,
                information_cutoff=InformationCutoff(
                    min(
                        context.information_cutoff.as_of_date,
                        requested_cutoff.as_of_date,
                    ),
                    requested_cutoff.source,
                ),
            )

        def fetch() -> ToolObservation:
            if scope is not None:
                # 登记必须在 runner 真的被调起时发生，不在「决定要调」时。
                # 这个闭包由 query_ledger.executed 决定跑不跑——被去重挡掉的调用
                # 根本不进这里，于是可达性收据里也就不会把它记成跑过了。
                scope.record_invocation(spec.name)
                scope.emit(
                    TOOL_PRE_EXECUTE,
                    {
                        "tool": spec.name,
                        "tool_call_id": tool_call_id,
                        "step_id": step_id,
                        "capability": spec.capability,
                        "query": prepared.display_query,
                        "cutoff": (
                            effective_context.information_cutoff.as_of_date.isoformat()
                        ),
                    },
                )
            run_result = spec.runner(
                prepared.runner_input,
                agent_research.AgentToolContext(
                    effective_context.deadline,
                    is_cancelled or (lambda: False),
                    effective_context.information_cutoff,
                ),
            )
            evidence = list(run_result.evidence)
            observation = run_result.observation
            # 代偿必须让模型看见：输入被改过而不说，模型下一轮还会照原样写，
            # 且它无法自行诊断为什么检索总是空手（ch4「参数传递的保真性」）。
            if prepared.normalization_note:
                observation = "；".join(
                    part for part in (observation, prepared.normalization_note) if part
                )
            trace = run_result.trace
            gaps = run_result.gaps
            if is_cancelled is not None and is_cancelled():
                raise RuntimeError("agent tool cancelled")
            served_date = closed_loop_retrieval.latest_served_date(
                evidence,
                date_getter=lambda item: item.source_date,
            )
            if served_date is None:
                parsed_trade_date = closed_loop_retrieval.parse_source_date(
                    trace.source_trade_date
                )
                served_date = (
                    parsed_trade_date.isoformat()
                    if parsed_trade_date is not None
                    else None
                )
            evidence, rejected = closed_loop_retrieval.filter_future_dated(
                evidence,
                information_cutoff=effective_context.information_cutoff,
                date_getter=lambda item: item.source_date,
            )
            trace_trade_date = closed_loop_retrieval.parse_source_date(
                trace.source_trade_date
            )
            if (
                trace_trade_date is not None
                and trace_trade_date
                > effective_context.information_cutoff.as_of_date
                and evidence
                and not any(item.source_date for item in evidence)
            ):
                rejected.extend(evidence)
                evidence = []
            remaining_after_cutoff_filter = list(evidence)
            if rejected:
                cutoff_iso = effective_context.information_cutoff.as_of_date.isoformat()
                if remaining_after_cutoff_filter:
                    observation = (
                        "；".join(
                            f"{item.title}：{item.detail[:80]}"
                            for item in remaining_after_cutoff_filter
                        )
                        or observation
                    )
                else:
                    # T2-a：全滤时空手会让模型以为「源里没有」。把越界条目标注后交还。
                    evidence = [
                        replace(
                            item,
                            title=(
                                item.title
                                if "晚于问句日" in item.title
                                else f"晚于问句日 {cutoff_iso}｜{item.title}"
                            ),
                            detail=(
                                f"{item.detail}（晚于问句日 {cutoff_iso}，不是源里没有）"
                            ),
                            content_hash="",
                        )
                        for item in rejected
                    ]
                    evidence = [
                        replace(
                            item,
                            content_hash=agent_research.evidence_content_hash(item),
                        )
                        for item in evidence
                    ]
                    listed = "；".join(
                        f"{item.title}：{item.detail[:80]}" for item in evidence
                    )
                    observation = (
                        f"源返回 {len(evidence)} 条，全部晚于问句日 {cutoff_iso}，"
                        f"已标注后交付；不是源里没有。{listed}"
                    )
            evidence = [
                item
                if item.content_hash
                else replace(
                    item,
                    content_hash=agent_research.evidence_content_hash(item),
                )
                for item in evidence
            ]
            trace = replace(
                trace,
                status=(
                    "future_of_cutoff"
                    if rejected and not remaining_after_cutoff_filter
                    else trace.status
                ),
                detail=(
                    f"{trace.detail}; future_of_cutoff={len(rejected)}".strip("; ")
                    if rejected
                    else trace.detail
                ),
                result_count=len(evidence),
                parent_id=context.trace_parent_id,
                step_id=step_id,
                requested_date=(
                    trace.requested_date
                    or effective_context.information_cutoff.as_of_date.isoformat()
                ),
                served_date=served_date,
            )
            # The content hash is the stable identifier carried into
            # AgentOutcome/verifier. Do not mint a second observation-only ID.
            hashes = tuple(item.content_hash for item in evidence)
            telemetry = dict(run_result.telemetry) if run_result.telemetry else {}
            if spec.name == "kb_search":
                # 按 cutoff/规范化之后的实际送达计，不写死 800；V3 改管道读数跟上。
                telemetry = agent_research.kb_delivery_telemetry(evidence, observation)
            _remember_authorized_trade_dates(context, evidence)
            if scope is not None:
                emitted = {
                    "tool": spec.name,
                    "tool_call_id": tool_call_id,
                    "step_id": step_id,
                    "status": trace.status,
                    "evidence_count": len(evidence),
                    # hash 是带进 AgentOutcome/verifier 的稳定标识，
                    # 事件里带上它，Trace/UI/评测三者才对得上账。
                    "evidence_hashes": list(hashes),
                    "gaps": list(gaps),
                    "dataset": run_result.dataset,
                    "caliber": run_result.caliber,
                    "payload_field_names": list(run_result.payload_field_names),
                    "payload_sha256": run_result.payload_sha256,
                }
                if telemetry:
                    emitted["telemetry"] = telemetry
                scope.emit(TOOL_RESULT, emitted)
            return ToolObservation(
                tool=spec.name,
                query=prepared.display_query,
                evidence=tuple(evidence),
                observation=observation,
                trace=trace,
                gaps=gaps,
                evidence_hashes=hashes,
                dataset=run_result.dataset,
                caliber=run_result.caliber,
                payload_field_names=run_result.payload_field_names,
                payload_sha256=run_result.payload_sha256,
                telemetry=telemetry,
            )

        ledger_call = partial(
            query_ledger.executed,
            f"generic:{spec.name}",
            normalized,
            fetch,
            variant=(
                f"{spec.freshness};cutoff="
                f"{effective_context.information_cutoff.as_of_date.isoformat()}"
            ),
        )
        if scope is None:
            return ledger_call()
        try:
            return ledger_call()
        except BaseException as exc:
            # 只观测，不改变传播：事件发完原样 raise。吞掉异常会把一次失败静默成
            # 一次空结果，那正是 ToolPipeline docstring 里禁止的做法。
            # 捕 BaseException 是为了让取消（可能以 BaseException 子类抛出）
            # 也留下收据；因为立即 re-raise，不存在吞掉控制流的风险。
            scope.emit(
                TOOL_ERROR,
                {
                    "tool": spec.name,
                    "tool_call_id": tool_call_id,
                    "step_id": step_id,
                    "stage": "execute",
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                },
            )
            raise


# 行为契约（见 ``ToolSpec.contract``）。**只写验证过的**：每条要么来自线上实测的
# 失败模式，要么是复述 CLAUDE.md 里已有的红线。没有依据的宁可留空——工具提示词是
# 模型判断「该不该用、结果怎么读」的依据，编一句进去比不写更糟。
_TOOL_CONTRACTS: dict[str, str] = {
    "market_data": (
        "返回的是最近一个已收盘交易日的快照，不是实时也不一定是今天："
        "当日盘中或次日开盘前查询会回退到上一交易日，此时应明写数据截至日期，"
        "不要把它当作提问当天的行情。美股按北京时间 21:30→次日 04:00 跨日，"
        "北京时间凌晨查到的「前一天」通常是正在进行的那一场，不是数据过期。"
        "隔夜或外盘混合预测会附带美股指数与龙头的结构化报价"
        "（费半/英伟达/美光/海力士/闪迪）；引用涨跌幅以该块为准，"
        "新闻标题里的数字不作为精确行情。"
    ),
    "l3_lookup": (
        "查询成功不等于查到了证据：实测存在「company 查询成功但没有解析到可用证据」"
        "的情况。返回为空时只能说明本次没检索到，不能据此断言该公司没有相关公告，"
        "应写成明确的证据缺口而不是否定结论。"
    ),
    "web_search": (
        "网页与研报是二手材料，默认只能作为线索和上下文，不能直接当作公司级硬事实。"
        "订单/中标/产能/量产这类结论需要 l3_lookup 的公告或互动证据确认；"
        "只有网页来源时，写成「待验证线索」并点明缺的是哪一份一手材料。"
    ),
    "news_search": (
        "新闻是二手材料，同一条消息被多家转载不构成交叉验证。"
        "涉及公司经营事实时需要 l3_lookup 的公告确认；"
        "只有新闻来源时写成「待验证线索」，不要升级为既定事实。"
    ),
    # §3.6 三条契约逐条落：① 空结果语义（取不到页 / 页上没字 ≠ 事实不存在）；
    # ② 来源分档与 as_of 来源（public_web、二手；as_of 取页面日期，取不到才记抓取日且
    #    观察值里写明）；③ 参数含义与拒绝条件（一个绝对 http(s) URL，其它形状直接拒）。
    # 依据：runner ``agent_research._web_fetch`` 与 ``web_research.fetch_web_page`` 的
    # 分状态返回；「二手不升一手」复述 web_search 那条与 CLAUDE.md 的分层红线。
    "web_fetch": (
        "取回的是网页正文原文，属二手公开材料（与 web_search 同档）：数字可以读、可以引，"
        "但公司级硬事实仍以 l3_lookup 公告或 financial_data 一手数据为准，"
        "只有网页来源时写成「待验证线索」并点明缺的一手材料。"
        "证据日期取页面自述的发布/更新日；页面没有日期时记为抓取日并在观察值里标明，"
        "引用时不要把抓取日说成数据日期。"
        "「取页失败」（HTTP 错误 / 超时 / 无法解析）是工具故障，不是页面没有该信息，"
        "可换 URL 或改用 web_search；「取页成功但无正文」同样不能当否定证据。"
        "参数只有一个 url，必须是 web_search / news_search 给出的完整 http(s) 地址，"
        "不接受站点名或检索词。"
    ),
    # 依据在 ``market_financials`` 的块构造：口径行逐字写着「均为累计值（中报=上半年
    # 累计、三季报=前三季累计），本块不做单季还原」。而该模块的另一行「使用要求：…」
    # 会被 ``episode_tools._NON_EVIDENCE_PREFIXES`` 过滤掉，模型看不到——所以口径这条
    # 必须在工具契约里再说一次，不能指望它从证据正文里读到。
    "financial_data": (
        "返回的是已披露报告期的季报数据，不是当前状态：引用时必须带报告期，"
        "不要把「三季报净利」说成「当前净利」。数值为累计口径"
        "（中报=上半年累计、三季报=前三季累计），本工具不做单季还原；"
        "要单季必须显式声明是自己推算的。返回为空只说明这两个源没取到，"
        "应写成证据缺口，不得据此推断公司没有该项财务表现。"
        # P0b（2026-09-03）：窗口可指定，且每行自带日期。这两句都是 runner 行为，
        # 模型从证据正文读不出来。
        "默认只取最近 6 期；问的是更早的某一期（如两年前的年报），"
        "要在 report_period 里写明该期，否则那一行不在返回里，不等于没有该期数据。"
        "每行的日期是该期披露日（缺披露日时为报告期截止日），引用时按此写 as-of，"
        "不要用取数日。"
    ),
    # memory_lookup 的 description 已声明「不是市场事实、不能当作证据引用」，这里只补
    # 它无法自述的那半条：空命中的含义。runner 的空分支返回「用户记忆无相关命中」，
    # 而「没查到用户说过」和「用户没有看法」是两件事。
    "memory_lookup": (
        "返回的是这位用户自己的历史判断与纠偏原则，属于先验而非市场事实，"
        "不能当作证据支撑当前世界的结论；绑定时用 user_premise。"
        "空命中只说明该主体此前没有留下记录，不等于用户没有看法，"
        "更不能反推市场事实——如实写「用户记忆无相关命中」即可。"
    ),
    # 三条依据都在 ``episode_tools`` 的 runner 里，且 description 一条都没说：
    # ① ``_AGENT_FINANCE_QUERY_MAX_ROWS = 25`` 会把 limit 压到 25 行，observation 事后
    #    追一句「已截断至 N 条」——但那是**拿到结果之后**才看得到的，模型下单时不知道，
    #    最危险的读法是把 25 行的截断结果当全集做「全市场最高/唯一」这类全称断言。
    # ② 未授权历史窗口时 runner **直接不执行**（返回 parse_error + 空证据），
    #    不是查了没有。③ 空结果的 gap 逐字是「没有结构化结果」，是缺口不是否定结论。
    # 跨 dataset 字段混用**刻意不写**：description 已带 dataset_field_hint，且
    # ``finance_query.validation_retry_hint`` 现在会跨 dataset 指出字段归属，重复即噪声。
    "finance_query": (
        "结果会按 Agent 上下文预算截断（当前上限 25 行），返回的是满足条件的前若干行"
        "而不一定是全集：不要据此写「全市场最高」「只有这些」这类全称断言，"
        "需要更完整的切片就加筛选、分组或排序后再查一次。"
        "日期要放进 time_range，不要写成 filters 条件。"
        "当前任务未授权历史窗口时，旧日期的查询不会被执行而是直接退回，"
        "此时按提示把时间窗调回截止日附近，不要反复重试同一个窗口。"
        "返回为空只说明该 dataset 在这组条件与时点下没有结构化结果，"
        "应写成证据缺口，不得据此推断事实不存在。"
        "新高家数/新高结构类问题用 stock_high_daily（表内只含当日创新高的个股，"
        "按 high_period/sw_l1 分组计数即新高结构）；"
        "sector_stock_daily.high_status 显示「非新高」是事实标注，不是数据缺失。"
        "下周/周末大事、事件日历用 event_daily（复盘会编辑催化，不是官方日程全集；"
        "event_date 可以晚于信息截止日）。"
    ),
    # 依据在 ``evidence_search._project_evidence``：它把 ``conclusion`` 与
    # ``counter_clues`` 合成同一个 evidence 列表，stance（"支持"/"反方"）**只出现在
    # observation 文本的方括号前缀里**，AgentEvidence 对象本身不带这个字段。
    # 模型若只从证据列表引用而不看 observation 的前缀，会把反证当成支持性证据——
    # 这是这个工具独有的、description 完全没警告的误读。
    # 成本那句来自 2026-08-10 实测：冷调用 28.2s，占满当时 30s 工具批次的 94%。
    "evidence_search": (
        "这是一次调用内跑 narrow→broad→counter 三轮的闭环检索，"
        "返回的证据列表**同时包含支持与反方两类**，立场只标在观察文本的"
        "[支持] / [反方] 前缀上，证据条目本身不带立场字段："
        "引用前必须回观察文本核对该条属于哪一方，不要把反证当成支持性证据。"
        "它也是最慢的工具（实测冷调用可达 28 秒），"
        "只在确实需要反证或替代解释时用；单纯找资料用 kb_search。"
    ),
    # 复述 CLAUDE.md 的 PDF ingest 分层红线。kb_search 命中的是 wiki 实体页/概念页正文，
    # 而那些页面按来源分层写在不同 section 里：券商材料只进「## 高信度研究线索」
    # （fact_hardness=review_candidate）或「## 观察列表」，只有一手公司事实才在
    # 「## 边际变化」。检索命中不区分 section，模型看不到这层分级。
    "kb_search": (
        "命中的是本地知识库页面正文，而这些页面按来源分层："
        "「边际变化」是公告/订单/中标这类一手公司事实，"
        "「高信度研究线索」是券商研报的待复核判断，「观察列表」更弱。"
        "检索结果不带这层标记，引用前先看命中片段落在哪一节："
        "券商来源的结论只能作为待验证线索，需要 l3_lookup 的公告确认后才能当硬事实。"
        # 「无命中」与「检索失败」是两件事，契约必须先把它们分开再谈怎么读，
        # 否则这句话会教模型把工具故障读成「知识库没回填」。2026-08-12 实测：
        # 历史 22 次 kb_search 全部无命中，逐条统计 14 error + 6 timeout + 2 真 empty。
        "返回文本明确说「检索未能执行完成」时那是工具故障，不是知识库为空，"
        "此时既不能写成证据缺口也不能下否定结论，应改写检索词重试或换工具；"
        "只有在确实「无命中」时，才说明知识库没有回填过，且仍不等于该事实不存在。"
    ),
    # 两条依据都直接来自 ``agent_research.build_graph_tools._graph_lookup`` 的构造：
    # 概念项 detail 逐字是 f"匹配分 {score}"（文本匹配分，不是业务关联度）；
    # 公司项 detail 逐字是 f"{concept}｜{strength}/{evidence_layer}"。
    # 而 CLAUDE.md 规定研报级产业链归类一律降级 graph_only（strength=peripheral,
    # fact_hardness=research_claim）——即图谱里本来就混着大量未经确认的映射。
    "graph_lookup": (
        "返回的是图谱里已登记的映射关系，不是经过确认的公司级事实。"
        "概念项的「匹配分」只是文本匹配强度，不代表业务关联强度，不要当作重要性排序。"
        "公司项后面的 strength/evidence_layer 是这条映射的可信度分级："
        "peripheral 或研报推断来源的产业链归类只能作为线索，"
        "要断言某公司确有该业务，需要 l3_lookup 的公告或 kb_search 的一手事实确认。"
        "图谱无命中说明尚未登记该映射，不等于不存在关联。"
    ),
    # 依据在 ``_evidence_lookup`` 的 detail 构造：每条逐字带
    # f"（{source}，{source_date or '无日期'}，质量 {confidence or '?'}）"。
    # 这三个标记已经在证据正文里了，但没人告诉模型它们该怎么用——尤其
    # CLAUDE.md 的 broker_research_high 不得直接升级为 hard_fact 这条红线。
    "evidence_lookup": (
        "查的是已回填的本地证据索引，每条自带来源、日期与质量标记，"
        "引用时要把这三项一起带出：券商研报来源的条目属二手材料，"
        "不能直接升级成公司级硬事实；标着「无日期」的条目不能用来支撑时效性结论。"
        "索引是回填产物、覆盖并不均匀，无命中只说明没有登记过相关证据，"
        "应写成证据缺口，不是否定结论。"
    ),
    # 覆盖缺口是 2026-08-10 实测的库内事实（不写死日期，日期会过期）：
    # fact_mainline_stock_daily / theme_daily 只有 35 个交易日、起点晚于
    # sector 表（88 天），早期日期查不到题材级主线。runner 另有两个空分支：
    # 结构化主线比市场快照旧时返回 stale 结果，block 含「当前交易日的题材级主线未知」
    # 时按空处理——两者都不是「当天没有主线」。
    "mainline_context": (
        "同日主线结构来自本地库的主线表，而这几张表的覆盖并不是每个交易日都齐全，"
        "题材与个股两张的起始日明显晚于板块表，较早的日期查不到。"
        "返回为空或提示「题材级主线未知」，说明该交易日没有回填主线数据，"
        "不能据此说当天没有主线；数据比行情快照旧时会退回并说明，"
        "此时应写出数据截至日期，不要当作提问当天的主线。"
    ),
    # spec 2026-09-03-subagent-tool-design §3 三条契约逐条落：① 空结果语义；② 来源分档
    # 与 as_of 继承自分支里真正调的那个工具、不因经过子研究而升档；③ 参数含义与拒绝条件。
    # dsh 「Success contains only the child's final text」那条**不抄**：分支回的是带 hash
    # 的证据条目，父臂结论只能绑到这些证据上，绑到分支总结文本进不了 admit_finish。
    "sub_research": (
        "返回的是各分支查到的证据条目本身（每条带来源、日期、档次），不是分支写的总结："
        "结论要绑到这些证据上，分支的状态说明不能当依据引用。"
        "证据的档次与日期继承自分支里实际调用的工具（公告仍是一手、网页仍是二手），"
        "不因为经过子研究而升档。"
        "某支 completed 但零证据，只说明该方向本轮没找到可绑定的证据，是缺口不是否定结论；"
        "某支 failed 会带失败原因，表示该子问题没有被研究过，不是没有答案。"
        "参数只有 goals：1–3 个彼此独立、能直接取证的子问题；空、重复或超过 3 个会被拒绝而不是截断。"
        "每支分支有自己的调用与时间预算（≤ 60 秒），适合并行拆几个互不依赖的取证方向，"
        "不适合把一个需要先后依赖的推理链拆开。"
    ),
    # §3.6 三条契约逐条落：① 空结果语义（没 emit / 脚本报错 / 超时 / 越界都是「计算没产出」，
    #    不是任何数值，也不是否定证据）；② 来源分档与 as_of 来源（派生证据档次不高于输入里
    #    最低的那档；as_of 取输入里最旧的一条，不是运行日）；③ 参数含义与拒绝条件（四个键；
    #    禁用模块 / 外呼 / 越界写在 runner 里回结构化错误码）。依据：``derived_calculation.py``
    #    的 runner 分状态返回与 ``calculation_sandbox`` 的两层隔离。
    "derived_calculation": (
        "返回的是对本回合已有证据做计算后的派生证据（带 input_evidence_hashes 与原样脚本）："
        "它的档次不高于输入里最低的那一档，日期取输入里最旧的 as_of，不是今天。"
        "结论要绑到这条派生证据上，并同时引用它的输入证据；沙箱算出的数与某个来源不一致时，"
        "先看两边的输入是否同一批证据，不要二选一。"
        "「没有 emit」「脚本报错」「超时」「触发沙箱限制」都表示计算没产出，不是任何数值，"
        "也不能当否定证据；错误码会带原因，改脚本可重试。"
        "本回合还没有任何证据时会拒绝（no_bound_evidence）：先取证再计算。"
        "参数 script 是 Python 正文（用 EVIDENCE 读证据、emit 出结果，不能联网 / 起进程 / 越界写文件），"
        "purpose 一句话说明算什么，use_duckdb 只在要查本地行情库时开，timeout_seconds 默认 20 最多 60。"
    ),
}


class ToolContractMissing(ValueError):
    """装配了一个没有行为契约的工具。"""


def require_tool_contracts(specs: Iterable[ToolSpec]) -> None:
    """装配期守门：进注册表的每个工具都要有非空 ``contract``（spec §3.6 第 8 条）。

    ``ToolSpec.contract`` 在数据类层面允许空串（测试与探针替身要用），但**模型能点到
    的**每个工具都得说清自己是谁——空了怎么读、as_of 从哪来、参数读不读。knevo 22 次
    调用里 ``finance_statement`` 无 provider、``finance_graph_context`` 找不到实体、
    ``finance_shareholders`` 失败，全是「工具挂在菜单上、底下没契约」的形状；这道门
    防的是把那个状态抄进来。

    2026-09-03 首次对生产装配跑这道门的读数：``build_episode_registry`` 里
    ``evidence_search`` / ``finance_query`` / ``memory_lookup`` 三个是裸的——
    ``_TOOL_CONTRACTS`` 早就为它们写好了条目，只是从没接到 spec 上。
    ``produces`` 不进这道门（§1.2：它是软先验）。
    """

    bare = sorted(
        spec.name for spec in specs if not str(spec.contract or "").strip()
    )
    if bare:
        raise ToolContractMissing(
            "tools registered without a behaviour contract: "
            + ", ".join(bare)
            + "；每个进注册表的工具都要在 _TOOL_CONTRACTS 有条目"
            "（空结果语义 / 来源分档与 as_of 来源 / 参数含义与拒绝条件）"
        )


# 成功一次至少要的工具窗（秒）。2026-09-03 生产 825 份 episode / 2948 次工具事件的
# 实测（`docs/verification/2026-09-03-tool-duration-floor-offline.md`）：11 个工具里 9 个
# p95 < 9s，任何授予都够，不登记；尾巴只有两条 RAG 工具——
#   kb_search       成功 30 / 真超时 57，成功耗时 p50 9.5s、80% 在 20s 内（一次检索 + 一次相关性裁判）
#   evidence_search 成功  3 / 真超时 66，成功耗时 32–40s（narrow→broad→counter 多轮检索 + 语义裁判）
# 数字是成功样本的分位，被 ~23s 的实授窗右截断，只会低估不会高估。改数字要重跑那份脚本。
MIN_WINDOW_SECONDS: dict[str, float] = {
    "kb_search": 20.0,
    "evidence_search": 30.0,
    # 设计常数而非实测：一支分支的时间上限（见 SUB_RESEARCH_MIN_WINDOW_SECONDS）。
    "sub_research": SUB_RESEARCH_MIN_WINDOW_SECONDS,
}


def default_registry(tools: dict[str, agent_research.ToolRunner]) -> ResearchToolRegistry:
    specs = tuple(
        ToolSpec(
            name=name,
            capability=name,
            description=description,
            contract=_TOOL_CONTRACTS.get(name, ""),
            cost="local" if freshness == "stable" else "external",
            freshness=freshness,
            runner=tools[name],
            min_window_seconds=MIN_WINDOW_SECONDS.get(name),
            query_scope=(
                "episode"
                if name in {"market_data", "financial_data", "mainline_context"}
                else "query"
            ),
            parameters=(
                FINANCIAL_DATA_PARAMETERS
                if name == "financial_data"
                else URL_TOOL_PARAMETERS
                if name == "web_fetch"
                else SUB_RESEARCH_PARAMETERS
                if name == "sub_research"
                else DERIVED_CALCULATION_PARAMETERS
                if name == "derived_calculation"
                else EMPTY_TOOL_PARAMETERS
                if name in {"market_data", "mainline_context"}
                else query_parameters(name)
            ),
            parse_arguments=(
                parse_financial_data_arguments
                if name == "financial_data"
                else parse_url_arguments
                if name == "web_fetch"
                else parse_sub_research_arguments
                if name == "sub_research"
                else parse_derived_calculation_arguments
                if name == "derived_calculation"
                else parse_snapshot_arguments
                if name in {"market_data", "mainline_context"}
                else parse_query_arguments
            ),
            produces=produces,
        )
        for name, (capability, description, freshness, produces) in _DEFAULT_TOOL_METADATA.items()
        if name in tools
    )
    require_tool_contracts(specs)
    return ResearchToolRegistry(specs)


def sub_research_tool_spec(
    runner: agent_research.ToolRunner | ToolRunnerAdapter,
) -> ToolSpec:
    """把一个 episode 期绑好的 runner 装成 ``sub_research`` 的 ToolSpec。

    走 ``default_registry`` 同一条装配路径，描述 / 契约 / 参数面 / 地板都取自同一张表，
    不在运行时另抄一份——第二份必然漂。runner 由 ``runtime`` 层提供（要协调器与父证据
    账本，``services`` 层拿不到）。
    """

    return default_registry({"sub_research": runner}).resolve("sub_research")


def derived_calculation_tool_spec(
    runner: agent_research.ToolRunner | ToolRunnerAdapter,
) -> ToolSpec:
    """把一个 episode 期绑好的沙箱 runner 装成 ``derived_calculation`` 的 ToolSpec。

    与 ``sub_research_tool_spec`` 同一条路：描述 / 契约 / 参数面取自同一张表。runner 要
    这一个 episode 的证据账本，由 ``services.derived_calculation.bind_derived_calculation_tool``
    绑好、``ContinuousAgentEpisode`` 起步时并进注册表。
    """

    return default_registry({"derived_calculation": runner}).resolve("derived_calculation")


# ---------------------------------------------------------------------------
# 事前可满足性预检（fail-open）
# ---------------------------------------------------------------------------

SatisfiabilityStatus = Literal["covered", "unknown", "suspicious"]


@dataclass(frozen=True)
class SatisfiabilityCheck:
    """单个 required_output 的事前可满足性判定结果。"""

    output_id: str
    status: SatisfiabilityStatus
    contributing_tools: tuple[str, ...] = ()
    reason: str = ""


def check_satisfiability(
    required_output_ids: tuple[str, ...] | list[str] | frozenset[str],
    authorized_specs: tuple[ToolSpec, ...] | list[ToolSpec],
    *,
    normalize: Callable[[str], str] | None = None,
) -> tuple[SatisfiabilityCheck, ...]:
    """事前预检：这套授权工具的 produces 并集能否覆盖每项 required_output。

    fail-open 判据：

    - ``covered``：至少一个工具声明了该 output_id → 放行
    - ``unknown``：没有工具声明过它 → 放行（未知≠不可能；声明不全只会漏抓）
    - ``suspicious``：所有相关工具（有非空 produces 的工具）都声明了、
      且都不含它 → 送裁定，不自动拦

    关键不变量：**声明不全只会漏抓，不会误拦**。一个不完整的 produces 表
    如果能造成误拦，它就成了新的静默失败源，比不做更糟。

    ``normalize`` 是 output_id 归一钩子（默认恒等）。契约侧与 produces 侧用的
    并非同一套字面 id：``evidence_boundary`` 在判缺时归一到 ``counterpoint``、
    ``direct_answer`` 归一到 ``direct_assessment``。不归一就比对，这两项会双双
    落到 ``suspicious``——实测 62 条真实 query 的 179 个 output 实例里，
    不归一 suspicious 占 53%，归一后 16%，**其中 65 个纯属字面差异**。
    归一表是 runtime 层的事实源（``_LEGACY_OUTPUT_ALIASES``），而本模块在
    services 层不得反向 import（``scripts/layer_audit.py`` 门禁），故以回调注入
    而非在此复制第二份。
    """

    def _identity(value: str) -> str:
        return value

    norm = normalize if callable(normalize) else _identity
    specs = tuple(authorized_specs)
    # 只看声明了非空 produces 的工具——空 produces 的工具（保守留空）不参与
    # 「全部声明了但都不含」的推理，因为它们没表态。
    declared_specs = tuple(spec for spec in specs if spec.produces)
    normalized_produces = {
        spec.name: frozenset(norm(item) for item in spec.produces) for spec in specs
    }
    all_declared: frozenset[str] = frozenset().union(
        *(normalized_produces[spec.name] for spec in declared_specs)
    ) if declared_specs else frozenset()

    results: list[SatisfiabilityCheck] = []
    for output_id in required_output_ids:
        normalized_id = norm(output_id)
        contributing = tuple(
            dict.fromkeys(
                spec.name
                for spec in specs
                if normalized_id in normalized_produces[spec.name]
            )
        )
        if contributing:
            results.append(
                SatisfiabilityCheck(
                    output_id=output_id,
                    status="covered",
                    contributing_tools=contributing,
                    reason=f"声明可产出该 output 的工具：{', '.join(contributing)}",
                )
            )
            continue
        # 没有任何工具声明它。区分两种情况：
        if not declared_specs:
            # 所有工具的 produces 都留空——完全未知，放行
            results.append(
                SatisfiabilityCheck(
                    output_id=output_id,
                    status="unknown",
                    reason="无工具声明了 produces，无法预判",
                )
            )
        else:
            # 有工具声明了 produces，但没人声明这个 output_id。
            # 如果它看起来像是一个已知词表里的 id（即在 all_declared 的「近邻」里），
            # 标为 suspicious；否则仍然 unknown（可能是声明表还没覆盖的新 id）。
            #
            # 判据保持保守：只要所有有声明的工具都没覆盖它，就标 suspicious 送裁定。
            # fail-open 的意思是「可疑项送裁定，不自动拦」——这里只是标记，不拦。
            results.append(
                SatisfiabilityCheck(
                    output_id=output_id,
                    status="suspicious",
                    reason=(
                        f"已声明的工具 produces 并集（{len(all_declared)} 项）"
                        f"不含此 output_id；可能需要额外工具或声明补充"
                    ),
                )
            )
    return tuple(results)
