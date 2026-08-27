# P0-A live 对照：隔夜混合预测授权（2026-08-19）

> 代码：`feat/overnight-forecast-auth` @ `ee71b4f3`  
> sidecar：`:8796`，`source_revision=ee71b4f3`，`code_matches_repo=true`  
> 生产 `:8792` 未切（仍 `8bbfc4e4`，users 仍 `linxiaoqi5111`）  
> 入口：`POST /api/conversations` → `.../messages`（`execution_kind=continuous_episode`）  
> 用户目录：`~/.finance-runtime/overnight-auth-live/users/overnight-auth-0819`  
> 对照基线：`run_20260819_000940_130301`（第五轮原题，无 news/web）

## 题目

「基于周二的盘面数据，你认为主线是什么。今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会」

## 判定

**P0-A live 通过。** 授权缺口已补上，模型也调用了 `news_search`。外盘前提不再是「只标 `user_premise` 然后结束」。

**P1-C 不取消。** 稿里出现了存储/光通信领跌，但没有 Knevo 那种互斥因果裁决（AI 逻辑证伪 vs 存储周期见顶），也没有英伟达对照。公开稿还被核验裁掉了标题里的领跌数字。

下一刀仍是 **P0-B**（结构化美股个股/指数字段，让数字能绑定），不是再挂工具。

## 验收对照

| 条 | 要求 | 读数 | 结果 |
|---|---|---|---|
| 1 | 原题授权含 `news_search` + `web_search` | `allowed_capabilities` = `market_data / mainline_context / news_search / web_search / finance_query / evidence_search`；plan 追加可选 W7 + WEB | 过 |
| 2 | 外盘前提工具核验或显式缺口 | 第二轮调用 `news_search`「美股 科技股 大跌 原因 8月18日」→ E24–E29；gaps 写明盘中非收盘、缺同窗口归因。零 `user_premise` | 过 |
| 3 | 不要求领跌表 | 不作为本刀通过条件 | 不适用 |
| 4 | 不要求 ≥2 因果假说 | 情景树仍是量能/美股路径 A/B/C | 不适用 |
| 5 | 不发明无据阈值 | 公开稿无 2.2 万亿 / 涨停≥60 / 电子 27%。首稿曾写「电子≥25% / 涨停骤减至 30 家」，repair 后去掉 | 过 |
| 6 | E 覆盖 ≥23 | 29 条（market_data 16 + mainline 7 + news 6） | 过 |
| 7 | 纯 A 股预测不回退 | 本 sidecar 未复跑「今晚复盘」；离线测试已锁。第六轮保留题仍要 live 一道 | 离线过 / live 未跑 |

`web_search` 已授权、本发未调用。`news_search` 走东财 `directional_news` fallback（6 条标题，`fallback_success`）。

## 相对第五轮基线

| | 基线 `000940_130301` | 本发 `011622_893108` |
|---|---|---|
| 授权 | 四件套，无 news/web | 六件套，含 news/web |
| 工具 | 2（盘面 + 主线） | 3（+ `news_search`） |
| 证据 | E1–E23 | E1–E29 |
| 美股前提 | `user_premise` 挂起 | 工具取到 8-18 夜标题；公开稿改写为「盘中快照 + 缺归因」 |
| 报告 | `partial` | `partial`（repair 裁掉 `invalidation_conditions` 的核验绑定） |
| 用时 | ~60s | 61s（01:16:22 → 01:17:23） |

## 模型已经看见、核验不让写的东西

`news_search` 观察（2026-08-18 22:43–23:05）：

- 费城半导体指数跌 6%（E24/E25）
- SK 海力士 −7.4%、闪迪 −8%（E27/E28）
- 光通信龙头业绩超预期仍跌超 17%（E29）

首稿和 repair 稿都写了「费半跌约 6%，存储与光通信领跌…恰是与 A 股 AI 算力映射最强的环节（E24、E27、E29）」。

语义核验驳回：E24 被当成「新闻时间戳」，标题里的 6% / −7.4% / −8% / −17% 不计入绑定数字；E27/E29 一度被标成「不存在」。公开 `answer.md` 因此删掉全部美股数字与领跌名字，只留「仅按已核验跌幅事实处理」，E 引用停在 E23。

这不是授权失败。这是 **标题新闻绑不住数字**。P0-B 要给可绑定字段（指数 + 当期领跌样本），不要再加一条同质标题检索。

## 对后续优先级的含义

1. **P0-A 关闭。** 混合预测题够得着 news/web；本发也用了。
2. **P0-B 仍是下一刀。** 缺英伟达对照；存储/光通信只在标题里；核验不认。指数层已有 `external_market` / `global_index_daily`，缺个股结构进证据编号。
3. **P1-C 保持 P1。** 授权对照没有自发长出「AI 证伪 vs 存储见顶」互斥假说。情景树仍是路径分支。
4. **验证器消融仍值得做，但预期要改。** 本发裁掉的不只是发明阈值，还有**标题里已出现的领跌数字**。消融若只放出 25%/30 家，P0-B 仍必要；若放出费半/闪迪且带 E 号，P0-B 的绑定缝可以更窄。
5. **`[M]` 未授权、未调用。** 与 R2 一致，不当深度判据。

## 身份与环境

- sidecar users：`overnight-auth-0819`（非生产 `linxiaoqi5111`）
- `WORKBENCH_GROUNDED_PRESENTER=0`（`start-sidecar` 默认）；本发仍是 `continuous_episode` / `continuous_glm` / `glm-5.2`
- 未持 `/tmp/finance-8792-live.lock`
- 停机：`scripts/live_probe.py stop-sidecar --out-dir ~/.finance-runtime/overnight-auth-live`

## 产物

- run：`~/.finance-runtime/overnight-auth-live/users/overnight-auth-0819/runs/run_20260819_011622_893108/`
- 压缩读数：`~/.finance-runtime/overnight-auth-live/receipt.json`
