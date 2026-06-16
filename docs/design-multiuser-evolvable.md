# 多用户 + 可进化：memory / 画像 / 策略迭代落地设计

> 目标（你三条调整）：① 飞书不再是数据源，画像派生只走 DuckDB + 知识库；② 系统可进化（越用越懂你）；③ memory file 和策略迭代都做成按用户定制，为多用户铺路。

## 0. 现状盘点（已读代码）

| 组件 | 现在的形态 | 数据来源 |
|---|---|---|
| foresight 画像 | 单文件 `intelligence/foresight_profile.example.json`（`.local.json` 已 gitignore） | 手写 |
| foresight 记忆 | 单文件 `intelligence/foresight_memory.jsonl`（已 gitignore，问过的问题累积去重） | 自累积 |
| 盘面锚定 | `market_feature_store/exports/*-theme-candidates.json` 快照 | DuckDB 导出 |
| 策略迭代 | `evolution/params.json`（单一、全局、版本化）+ `evolve.py` generate/validate/suggest | DuckDB |
| 知识库题材信号 | `wiki/relations/theme_signals.json`（137 题材：order_signals / market_heat / recognition_timeline / progress_ruler …） | 知识库 |

关键现状：DuckDB schema 里已经有 **未使用** 的 `config_watchlist`、`config_strategy_rule` 两张配置表（只在 schema + 设计文档出现，无写入）。foresight 的 `ask` 刻意做到「不依赖 DuckDB、可离线」。飞书相关派生此前并未落地，所以这次是「新建」而非「改造飞书逻辑」。

## 1. 用户命名空间（多用户的地基）

所有「属于某个用户」的状态收进一个按 user 解析的目录，由 `--user <id>` 或 `FORESIGHT_USER` 环境变量解析，默认 `default`：

```
intelligence/users/<user_id>/
  profile.json            # 用户「钉住」的画像：focus_themes / watchlist / style / horizon（人工 + 长期）
  profile.derived.json    # refresh-profile 自动派生出来的字段（带来源 + as_of 时间戳）
  foresight_memory.jsonl  # 问过的问题（原 foresight_memory.jsonl 平移进来）
  interactions.jsonl      # 反馈事件（哪条问题被点/被忽略/被打分）——「越用越懂」的燃料
  strategy_params.json    # 该用户对 evolution/params.json 的稀疏覆盖（overlay）
```

- **入库的只有模板**：`intelligence/users/default/profile.json`（即现有 example）+ `users/README.md`；其余 `users/*/` 全部 gitignore（含真实自选股/提问/反馈，隐私）。
- 新增 `intelligence/userspace.py` 负责：解析路径、校验 user_id（slug、禁止路径穿越）、提供 `effective_profile(user)`。
- **有效画像 = profile.json（用户钉住，优先）合并 profile.derived.json（数据派生，补充/带来源/带新鲜度）**。用户钉住的永远不被覆盖。
- 向后兼容：显式传 `--profile` / `--memory-file` 仍然优先生效，旧用法不破。

## 2. refresh-profile（你说的「第 2 层」，不碰飞书）

新增 CLI：`python3 -m intelligence.cli refresh-profile --user <id> [--lookback 20] [--date ...] [--apply]`

**来源（只有两条，无飞书）：**
- **DuckDB 强势股**：复用 `market_feature_store.query` 的 `weighted_gainers` / `stock_highs` / `strong_subtheme_trace`，在最近 N 个交易日窗口里取量价加权强势股 + 反复新高的票 → 候选自选股 watchlist；强势 sw_l1 / 子题材 → 候选关注方向。
- **知识库 theme_signals**：按 `market_heat` + `recognition_timeline` 阶段给 137 题材排序，只取「在发酵/升温」的 → 候选 focus_themes。

**派生 + 校验（关键，避免脏画像）：**
- watchlist 候选必须在 DuckDB fact 表里查得到真实代码，查不到的丢弃。
- 题材必须在知识库 concept graph / theme_signals 里存在，未知的丢弃。
- 合并：保留用户钉住项；新派生项打 `source` + `as_of` 戳；长期没再出现的派生项标 `stale` 并降权（不硬删）。

**默认只建议、不落盘**（对齐 evolve 的「suggest only」哲学）：默认打印 diff（新增 / 保留 / 变陈旧 / 丢弃），只有 `--apply` 才写 `profile.derived.json`，绝不静默覆盖用户钉住的画像。

## 3. 越用越懂（可进化回路）

- `interactions.jsonl`：追加 `{ts, user, question, action: shown|picked|dismissed|rated, score}`，由一个 `foresight record-interaction` 子命令（或上层应用）写入。
- **foresight 排序加一项可解释的相关度加成**：最近被用户点过/追问过的题材 & 公司，relevance 小幅上调（加性项，保持可审、不黑箱）。
- **refresh-profile 吃反馈历史**：用户反复互动的题材排序更高；派生出来却从没被碰过的题材随时间衰减。
- 全程确定性 + 可审，延续仓库「可验证 / 可回溯」基因。

## 4. 按用户定制的策略迭代

- `evolution/params.json` 继续做**共享、版本化的 baseline**。
- `users/<id>/strategy_params.json` = 稀疏 overlay（只写要覆盖的键）+ 自己的 `version` + 一行依据。
- `evolution` 加载 `merge(baseline, user_overlay)`；生成记录里标 `user_id` / `base_version` / `overlay_version`。`suggest` 可针对某个用户给建议。
- 仍然满足确定性可复现：相同 merged params + 相同库 → 相同名单。

## 5. 落地顺序（建议两个 PR）

- **PR1（本轮）**：用户命名空间 `userspace.py` + `users/` 目录与模板 + `refresh-profile` 命令（读 DuckDB + KB，suggest/apply）+ foresight/记忆按 `--user` 解析。带单测。
- **PR2**：interaction 反馈回路 + foresight 排序加成 + 按用户的策略 overlay 接进 evolve。

## 6. 需要你拍板的 1 个关键点：用户态存哪

- **方案 A（推荐）**：文件系统 `intelligence/users/<id>/`。foresight 保持可离线、不强依赖 DuckDB；画像/记忆/反馈是「应用配置」，与「市场数据」分层清爽；天然 gitignore 保隐私。refresh-profile 仍然**读** DuckDB+KB。
- **方案 B**：用 DuckDB 配置表（复用现成的 `config_watchlist` + 新建 `config_user_profile` / `config_user_strategy`）。好处是「全部进 DuckDB」符合你说的统一写库；代价是 foresight 从此强依赖 DuckDB、应用配置和市场数据混在一个库里。

> 我的建议：市场「数据」统一进 DuckDB（已落地），但用户「应用态」（画像/记忆/反馈/策略 overlay）走方案 A 的文件系统，保持 foresight 可离线、分层干净。除非你更想要「一个库装下一切」，那走 B。
