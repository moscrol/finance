---
name: watchlist-digest
description: 自选简报——画像清单×当日盘面四袋的确定性接合，冻结题开口前出袋、数字只来自冻结行。触发词：自选简报、我的自选今天怎么样、按我的自选出简报、开盘简报（按自选）、我的清单今天该看什么、watchlist digest。注意：全市场日报用 market-overview；买卖票据题走 StancePack，不经本 skill。
---

# 自选简报（WatchlistDigestPack）

> **单一口径声明**：本文件只是入口指针。接合规则、主张档（（事实）/（推断）/（缺口））、
> 站立日语义、快照合同的唯一正文在
> `intelligence/services/watchlist_digest_pack.py` 与
> `docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md`；
> 发酵摘要口径在 `intelligence/services/theme_fermentation.py`。
> **本文件不复述任何口径**，防止第二份漂移（spec §3.2 明令禁止第二份口径）。

## 正门

```bash
# 只读出简报（缺省=库内最新交易日，不是日历今天）
python3 -m intelligence.cli digest [--date YYYY-MM-DD] [--user <id>] [--db <路径>]

# 加 --write 才把证据快照落盘到 ~/.finance-runtime/watchlist-digest/<user>/<date>/
python3 -m intelligence.cli digest --write
```

Workbench 问答门冻结题：「按我的自选出今天的简报」（`question_type=watchlist_digest`，
确定性回合，Engine A 拒收、编排器 owner 分叉前出袋）。对话里可点开「证据快照」页
（P1b，只读渲染）。

## 硬约束（违反即 bug，测试有钉）

- 观察件不是投顾：公开稿零买卖动作句。
- 公开稿数字只来自包内冻结行；事后对账只对快照，不现场重查。
- 清单唯一真本源 = 本地画像层 `profile.json`（`focus_themes` 手钉 ⊕
  `profile.derived.json` 派生）。**飞书已退役，不作数据源**（2026-08-27 用户纠偏）。
- 清单空 → 缺口句 fail-closed，不回落全市场日报。
