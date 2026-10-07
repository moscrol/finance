"""市场历史比较的共享读取接缝：Episode 预取与 ask 的 D10 共用。

保留旧 D10 的后续事实，补上 river 镜头；两套特征/候选不冒充同一份匹配。
只读、不命名剧本、不读用户画像、不引入外呼。失败逐块声明，不连坐已有证据。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from intelligence.paths import default_market_db_path
from intelligence.services import market_regime_analogs, river_lens
from intelligence.services.research_contract import ResearchDeadline

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoryBlock:
    title: str
    detail: str


def market_history_blocks(
    market_db_path: str | Path | None,
    *,
    as_of: date | str,
    deadline: ResearchDeadline | None = None,
) -> tuple[HistoryBlock, ...]:
    """调用者必须提供已解析的站立日；不默默回落机器今天或库尾日期。"""
    day = date.fromisoformat(str(as_of))
    cutoff = day.isoformat()
    # 两个旧取数模块的默认路径解析不同，在接缝处统一，不能一块读配置库一块读常量库。
    db_path = Path(market_db_path).expanduser() if market_db_path is not None else default_market_db_path()
    try:
        if deadline is not None and deadline.expired:
            facts = "historical_analogs gap：父预算已耗尽，未启动 D10 读取。"
        else:
            facts = market_regime_analogs.regime_block_for_llm(db_path, as_of=day)
    except Exception as exc:
        log.warning("D10 historical facts unavailable (%s)", type(exc).__name__)
        facts = ""
    if not facts.strip():
        facts = (
            f"historical_analogs gap（D10 不可用，截止={cutoff}）："
            "库缺失、不可读、历史不足或无可比窗口。"
            "禁止用画像、框架原文或镜头距离冒充历史后续事实。"
        )
    boundary = (
        "两部分是独立候选集：D10 用市场情绪特征并列历史后续事实，镜头用 river 可比较特征。"
        "同一序号不代表同一窗口，后续事实不可嫁接到镜头候选；"
        "只能按明确日期区间与指标口径核对。镜头未提供后续事实，不得自行补造。"
        "教学 tf.* 特征尚未接入镜头；未读取用户判断台账，不将缺数补零。"
        "环境剧本自动命名与持久化未接入，本块不能称为已验证剧本。"
    )
    try:
        if deadline is not None and deadline.expired:
            raise TimeoutError("history context deadline expired")
        result = river_lens.lens_from_db(
            knowledge_cutoff=cutoff,
            as_of=cutoff,
            window=market_regime_analogs.DEFAULT_WINDOW,
            step=market_regime_analogs.STRIDE,
            top=market_regime_analogs.TOP_K,
            db_path=db_path,
        )
        lens = river_lens.lens_block(result, name="D10")
        if not result.current.stats or not result.candidates:
            lens = "river_lens gap：没有可比较的当前签名或历史窗口；不强行给出对标。\n" + lens
    except TimeoutError:
        lens = "river_lens gap：父预算耗尽或本地读取超时，未完成镜头；保留已取得的 D10 事实。"
    except Exception as exc:
        log.warning("river lens unavailable (%s)", type(exc).__name__)
        lens = (
            "river_lens gap：本地镜头读取或计算失败（可能缺库、schema不兼容或历史不足）；"
            "这不证明没有相似行情，不用 D10 的名次冒充逐维解释。"
        )
    return (
        HistoryBlock("市场情绪环境类比 [D10]", facts),
        HistoryBlock("多维对照镜头 [D10]", f"{boundary}\n截止={cutoff}\n{lens}"),
    )
