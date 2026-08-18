"""数据块 provider 注册表：统一注册顺序 + 开关收敛（方案 1 PR3）。

此前每个数据块一个 ``include_*_block`` 布尔开关（AskOptions 上十几个字段），
新增块要同时改 AskOptions 和 ask.py 门控。本注册表做两件事：

1. **权威注册顺序**：``REGISTRY`` 按 ask.py 的汇总顺序列出全部数据块 provider
   （name/label/说明/对应旧开关字段），后续 LLM 检索 planner（方案 2）直接把
   它作为机读 provider 描述输入。
2. **开关收敛**：``AskOptions.enabled_providers: tuple[str, ...] | None`` 一个
   字段选块——``None``（默认）走旧 ``include_*_block`` 开关（完全兼容）；
   给定集合时只有名单内的 provider 参与门控（``applies()`` 意图门控仍生效，
   即 enabled 只是"允许"，不是"强制取数"）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intelligence.services.ask import AskOptions


@dataclass(frozen=True)
class ProviderSpec:
    """一个数据块 provider 的机读描述（注册顺序即汇总顺序）。"""

    name: str
    label: str
    description: str
    legacy_option: str


REGISTRY: tuple[ProviderSpec, ...] = (
    ProviderSpec("D0", "盘面时序直查", "白名单指标过去 N 个交易日逐日直查（本地 DuckDB）", "include_timeseries_block"),
    ProviderSpec("D6", "多日中期趋势", "题材近 N 日双红天数/成交额趋势/拥挤度分位（中期赔率视角）", "include_midterm_block"),
    ProviderSpec("D9", "L2 大单资金流", "个股主买/总买净额+量化单特征 + 大单净流入榜（自有口径）", "include_moneyflow_block"),
    ProviderSpec("D12", "资金面三件套", "个股两融/大宗/未来90天解禁时间表（东财 datacenter）", "include_capital_block"),
    ProviderSpec("D13", "龙虎榜席位", "个股近 N 个上榜日买卖前五席位类型分布（营业部/游资/机构，本地库）", "include_dragon_block"),
    ProviderSpec("D8", "历史类比检索", "题材自身历史相似形态窗口及后续实际走法（小样本历史事实）", "include_analog_block"),
    ProviderSpec("D10", "市场情绪环境类比", "市场级情绪向量（涨停/连板/双红/量能等）历史相似窗口及后续实际走法（小样本历史事实）", "include_regime_block"),
    ProviderSpec("D11", "个股走势类比", "个股自身历史相似量价结构窗口及后续多窗口实际走法（小样本历史事实）", "include_stock_analog_block"),
    ProviderSpec("D7", "逐季财报", "东财 F10 / 新浪三表 / AKShare 逐季营收/净利/毛利率 + 现金流/合同负债/存货/股东户数", "include_financials_block"),
    ProviderSpec("W7", "web 事件检索", "东财资讯 + web 全网近 N 天新闻（只列不编，消息面存在性证据）", "include_news_block"),
    ProviderSpec("M", "用户记忆检索", "相关性召回的用户既有核心判断/纠偏原则/回检胜率", "include_memory_block"),
    # 与 M（用户记忆）严格区分：MARKET_DAILY 是同日结构化市场总览。
    ProviderSpec("MARKET_DAILY", "最新市场总览", "fact_market_daily 同日结构化盘面事实", ""),
    ProviderSpec("V", "回检块", "该题材/个股登记过的可证伪判断及最新裁决", "include_recall_block"),
    ProviderSpec("D1", "市场价值与替代队列", "CAR/峰后回撤/半衰期代理/同题材强势替代队列", "include_market_value_block"),
    ProviderSpec("D4", "主线题材结构", "同日主线结构；快照滞后时仅提供数据边界", "include_mainline_context_block"),
    # D0-D9 已占满，沿用 MARKET_DAILY 的描述式命名。legacy_option 为空 = 默认参与，
    # 但仍受 enabled_providers 约束（此前它无条件追加，且撞了 D5 估值数据块）。
    ProviderSpec("MAINLINE_KB", "主线方向的知识库积累", "当日主线方向逐个取概念页/公司暴露/已入库证据，并点出库内尚无积累的方向", ""),
    ProviderSpec("D2", "客户证据硬度", "客户/订单/量产/送样/验证证据按硬度分层", "include_customer_hardness_block"),
    ProviderSpec("D5", "估值数据块", "目标 PE/PB/市值 + 同题材可比估值带与横截面分位", "include_valuation_block"),
    # D3 依赖前面块累积的 evidence_text，在 ask.py 串行收尾，但同受本注册表门控。
    ProviderSpec("D3", "二阶导研究队列", "强势替代表达/目标股再升级/产业瓶颈补盲", "include_second_derivative_block"),
)

_BY_NAME = {spec.name: spec for spec in REGISTRY}

PROVIDER_NAMES: tuple[str, ...] = tuple(spec.name for spec in REGISTRY)


def provider_enabled(options: "AskOptions", name: str) -> bool:
    """provider 是否被允许参与门控：enabled_providers 优先，None 回退旧开关。"""
    spec = _BY_NAME[name]
    if options.enabled_providers is not None:
        return name in options.enabled_providers
    return bool(getattr_legacy(options, spec.legacy_option))


def getattr_legacy(options: "AskOptions", legacy_option: str) -> bool:
    """读取旧 include_*_block 开关；字段名由 REGISTRY 静态声明（非动态猜测）。"""
    if not legacy_option:
        return True
    value: bool = {
        "include_timeseries_block": options.include_timeseries_block,
        "include_midterm_block": options.include_midterm_block,
        "include_moneyflow_block": options.include_moneyflow_block,
        "include_capital_block": options.include_capital_block,
        "include_dragon_block": options.include_dragon_block,
        "include_analog_block": options.include_analog_block,
        "include_regime_block": options.include_regime_block,
        "include_stock_analog_block": options.include_stock_analog_block,
        "include_financials_block": options.include_financials_block,
        "include_news_block": options.include_news_block,
        "include_memory_block": options.include_memory_block,
        "include_recall_block": options.include_recall_block,
        "include_market_value_block": options.include_market_value_block,
        "include_mainline_context_block": options.include_mainline_context_block,
        "include_customer_hardness_block": options.include_customer_hardness_block,
        "include_valuation_block": options.include_valuation_block,
        "include_second_derivative_block": options.include_second_derivative_block,
    }[legacy_option]
    return value
