"""数据块 provider 注册表：统一注册顺序 + 允许名单。

调用方只通过 ``AskOptions.enabled_providers`` 限制哪些块可以参与门控：

- ``None``（默认）= 全部允许；意图门控 ``applies()`` 仍生效（允许 ≠ 强制取数）。
- 给定集合 = 只有名单内的 provider 允许。测试或编排器用
  ``without_providers(...)`` / ``providers_allowing_memory(...)`` 生成名单。

每个块不再占用 ``AskOptions.include_*_block`` 字段。
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


REGISTRY: tuple[ProviderSpec, ...] = (
    ProviderSpec("D0", "盘面时序直查", "白名单指标过去 N 个交易日逐日直查（本地 DuckDB）"),
    ProviderSpec("D6", "多日中期趋势", "题材近 N 日双红天数/成交额趋势/拥挤度分位（中期赔率视角）"),
    ProviderSpec("D9", "L2 大单资金流", "个股主买/总买净额+量化单特征 + 大单净流入榜（自有口径）"),
    ProviderSpec("D12", "资金面三件套", "个股两融/大宗/未来90天解禁时间表（东财 datacenter）"),
    ProviderSpec("D13", "龙虎榜席位", "个股近 N 个上榜日买卖前五席位类型分布（营业部/游资/机构，本地库）"),
    ProviderSpec("D8", "历史类比检索", "题材自身历史相似形态窗口及后续实际走法（小样本历史事实）"),
    ProviderSpec("D10", "市场情绪环境类比", "市场级情绪向量（涨停/连板/双红/量能等）历史相似窗口及后续实际走法（小样本历史事实）"),
    ProviderSpec("D11", "个股走势类比", "个股自身历史相似量价结构窗口及后续多窗口实际走法（小样本历史事实）"),
    ProviderSpec("D7", "逐季财报", "东财 F10 / 新浪三表 / AKShare 逐季营收/净利/毛利率 + 现金流/合同负债/存货/股东户数"),
    ProviderSpec("W7", "web 事件检索", "东财资讯 + web 全网近 N 天新闻（只列不编，消息面存在性证据）"),
    ProviderSpec("D17", "隔夜美股映射", "fph2026 隔夜美股主题热度/涨跌 → 对照 A 股板块 → 当日 A 股实际（只列映射事实，不表示必然跟涨）"),
    ProviderSpec("M", "用户记忆检索", "相关性召回的用户既有核心判断/纠偏原则/回检胜率"),
    # 与 M（用户记忆）严格区分：MARKET_DAILY 是同日结构化市场总览。
    ProviderSpec("MARKET_DAILY", "最新市场总览", "fact_market_daily 同日结构化盘面事实"),
    ProviderSpec("V", "回检块", "该题材/个股登记过的可证伪判断及最新裁决"),
    ProviderSpec("D1", "市场价值与替代队列", "CAR/峰后回撤/半衰期代理/同题材强势替代队列"),
    ProviderSpec("D4", "主线题材结构", "同日主线结构；快照滞后时仅提供数据边界"),
    # D0-D9 已占满，沿用 MARKET_DAILY 的描述式命名。仍受 enabled_providers 约束。
    ProviderSpec("MAINLINE_KB", "主线方向的知识库积累", "当日主线方向逐个取概念页/公司暴露/已入库证据，并点出库内尚无积累的方向"),
    ProviderSpec("D2", "客户证据硬度", "客户/订单/量产/送样/验证证据按硬度分层"),
    ProviderSpec("D5", "估值数据块", "目标 PE/PB/市值 + 同题材可比估值带与横截面分位"),
    # D3 依赖前面块累积的 evidence_text，在 ask.py 串行收尾，但同受本注册表门控。
    ProviderSpec("D3", "二阶导研究队列", "强势替代表达/目标股再升级/产业瓶颈补盲"),
)

_BY_NAME = {spec.name: spec for spec in REGISTRY}

PROVIDER_NAMES: tuple[str, ...] = tuple(spec.name for spec in REGISTRY)

_MEMORY_PROVIDERS = frozenset({"M", "V"})


def provider_enabled(options: "AskOptions", name: str) -> bool:
    """provider 是否被允许参与门控。未知名字 KeyError（登记表是权威）。"""
    if name not in _BY_NAME:
        raise KeyError(name)
    if options.enabled_providers is None:
        return True
    return name in options.enabled_providers


def without_providers(*names: str) -> tuple[str, ...]:
    """除点名的块以外全部允许。未知名字 fail closed。"""
    banned = {str(item) for item in names}
    unknown = banned - set(PROVIDER_NAMES)
    if unknown:
        raise ValueError(f"unknown evidence providers: {sorted(unknown)}")
    return tuple(item for item in PROVIDER_NAMES if item not in banned)


def providers_allowing_memory(memory: bool) -> tuple[str, ...] | None:
    """Turn controller 的 needs_memory → 允许名单。True = 不限制（None）。"""
    if memory:
        return None
    return without_providers(*sorted(_MEMORY_PROVIDERS))
