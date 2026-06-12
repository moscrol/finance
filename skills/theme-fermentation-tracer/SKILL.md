---
name: theme-fermentation-tracer
description: 题材发酵链路回溯——把知识库消息面（证据/认知跃迁/卖方覆盖）和本地 DuckDB 盘面（板块双红/边际量/涨停热度/个股起涨日）按日期对齐，输出"消息→首板→板块双红→补涨扩散"的完整发酵链路，自动区分起涨股和补涨股。触发词：发酵链路、发酵回溯、谁先启动、起涨补涨、题材怎么发酵的、双红怎么加强的。注意：只看当前题材结构用 theme-radar；本 skill 是带盘面时间轴的历史回溯。
---

# Theme Fermentation Tracer（题材发酵链路回溯）

核心问题：**这个题材是怎么发酵起来的？消息出来后谁先涨、谁补涨、板块双红何时加强？**

## 前置条件

- 知识库仓在同级目录（或设 `KB_VAULT` 环境变量），需要 `wiki/relations/` 下的
  `entity_exposures.json` / `evidence_index.json` / `theme_signals.json`
- 本地存在 `market_feature_store/db/market_feature_store.duckdb`（不入库，需在本机先同步）

## 用法

```bash
python3 skills/theme-fermentation-tracer/scripts/trace.py --theme <题材名> \
    [--start 2026-04-01] [--end 2026-06-12] [--window 60] \
    [--pct-threshold 7.0] [--out /tmp/xxx.md]
```

- `--window`：未指定 start 时从 end 往回看的自然日数（默认 60）
- `--pct-threshold`：无首板记录时，用"单日涨幅 ≥ 阈值"判定量价突破起涨日（默认 7%）

## 数据对齐逻辑

| 层 | 来源 | 用途 |
|---|---|---|
| 消息面 | 知识库 evidence_index（证据+层级）、theme_signals.recognition_timeline（认知跃迁）、sell_side_coverage | 发酵的"因" |
| 板块 | fact_sector_daily（pct_chg×diff_ratio 判双红、连续双红计数、多周期共振）、fact_theme_limit_heat_daily（涨停热度） | 题材整体强度变化 |
| 个股 | fact_limit_advance_daily / fact_theme_limit_stock_daily（首板日优先）、fact_stock_daily / fact_sector_stock_daily（量价突破兜底） | 起涨日判定 |
| 公司分层 | 知识库 entity_exposures（core/related/peripheral） | 梯队标注用 |

题材→板块映射：优先查 `config_theme_sector_link`，无配置时按板块名模糊匹配。

## 输出报告结构

1. **消息面时间线**：窗口内带日期的证据/认知跃迁/卖方覆盖事件表
2. **板块发酵时间线**：双红启动日、双红加强（3 连）日、多周期共振日、涨停热度峰值
3. **个股启动梯队**：按起涨日排序；距首只启动 ≤2 天=起涨、≤7 天=第二梯队、>7 天=补涨
4. **合并链路**：📰消息 / 📈板块 / 🚀个股 三类事件按日合并的因果时间轴

## 边界

- 只读分析，不写 DuckDB、不写知识库；报告默认输出到 `/tmp/`，需要留档时由用户决定是否存 `wiki/synthesis/`
- 起涨/补涨判定是数据规则（首板或涨幅阈值），不是交易建议
- 窗口内缺数据（板块未映射、个股不在事实表）会在对应小节明确提示，不静默编造
