# residual retrieval prime live 对照（2026-08-19）

> 代码：`feat/residual-retrieval-prime` @ `eacda137`（`d36f43e2` + merge `gitea/main` `0c0a61b5`）  
> sidecar：`:8796`，隔离用户 `residual-prime-0819`  
> 生产 `:8792` 未切（`1be19329`）  
> 入口：`POST /api/conversations` → `.../messages`（`continuous_episode`）  
> PR：http://127.0.0.1:3300/a77/finance-workspace-private/pulls/215

## 题目

「基于8.15的行情现状，你认为周一的机会在哪」

这是 08-16 空壳 completed 的原题（`run_20260816_102941`），不是第五轮外盘预测题。现场分类仍是 `general_finance_qa`（「超纯应材估值怎么看」会进估值命中路径，不能当残差 live）。

## 判定

**#215 live 通过。** 授权地板 + 窄槽同时生效；模型调用了 `market_data` 与 `news_search`，并把结果绑进 `prime_quote` / `prime_news`。公开稿不是空壳。

- `question_type=general_finance_qa`，`evidence_policy=general_finance_evidence`
- 授权含 `market_data` / `news_search` / `memory_lookup` / `kb_search` / `web_search`
- 契约槽：`prime_quote`（required, evidence, 仅 `market_data`）/ `prime_news`（required, evidence, 仅 `news_search`）/ `prime_memory`（optional, user_premise）
- 工具：`finance_query`（历史窗口未授权）+ `news_search`（东财 8-15 标题 6 条）+ `market_data`（8-18 总览）
- 绑定：`prime_quote` ← E7–E14；`prime_news` ← E1–E6；`prime_memory` 未检索，gap 写「缺用户历史判断台账」
- 公开稿保留主线抱团 / 电子 31.2% / 强势股沸点判断（E8–E14）。核验裁掉了新闻标题里的回购/净利数字（E1/E2/E3/E6），episode `outcome=partial`，run 对外 `completed`
- 未调 `memory_lookup`（台账空、槽位 optional，符合设计）

**不合、不切 8792。** P1-D 不开。第五轮外盘题不走这条残差地板。

## 验收

| 条 | 要求 | 读数 | 结果 |
|---|---|---|---|
| 题型 | 现场仍是残差，不是 forecast/估值 | `general_finance_qa` | 过 |
| 授权地板 | 行情+新闻+先验+kb+web | 六件套都在 allowed | 过 |
| 窄槽 | 三 prime；quote/news 单工具；memory 可选 | 与契约一致 | 过 |
| 消费 | 不只授权，还调用并绑定 | market_data + news_search；两槽均有 hash | 过 |
| 空台账 | 不得因缺记忆打成失败 | prime_memory 未填，只进 gap | 过 |
| 空壳 | 不得再 completed 空判断 | 公开稿有方向判断 + E 号 | 过 |
| 命中路径 | forecast 菜单不泄漏 | 单测锁定；本题不是 forecast | 过 |

## 残留

- 核验仍裁新闻标题数字（与 P0-A 同型），不放宽闸。
- `finance_query` 要 8-15 切片被 `historical_window_not_authorized_by_task` 挡住，诚实写进 gap。
- 未测笑话/天气 live（单测已锁空授权）。

## 产物

- 验收 run：`~/.finance-runtime/residual-prime-live/users/residual-prime-0819/runs/run_20260819_102323_430367/`
- 收据：`~/.finance-runtime/residual-prime-live/receipt.json`
- sidecar 已停；8792 仍 `1be19329`
