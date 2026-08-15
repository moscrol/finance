# recall@k 首份基线（S4 · 2026-08-15）

- 标注集：`intelligence/eval/cases/retrieval_recall_v1.jsonl`（20 条）
- 口径：`docs/retrieval-recall-at-k-contract.md`（生产 @k = 每通道 k）
- 尺子：`intelligence/eval/retrieval_recall.py`（`--json` 原始读数 `/tmp/s4-um.json`、`/tmp/s4-ec.json`）
- 台账：`$FORESIGHT_USERS_DIR/linxiaoqi5111`（`corrections.jsonl` 58 行；**`judgments.jsonl` 不存在**，[M] 块 judgments 通道空）
- 解释器：`~/finance-workspace-private/.venv-workbench/bin/python`
- 跑数时刻：2026-08-15 13:48–14:05 CST

分数度量检索层，不度量答案正确性。三通道分列，不混分母。

## 1. 总表

| 通道 | n | recall@1 | recall@3 | recall@5 | hit@1 | hit@3 | hit@5 |
|---|---|---|---|---|---|---|---|
| user_memory | 15 | 15.6% | 42.2% | 42.2% | 26.7% | 46.7% | 46.7% |
| experience_cards | 3 | 83.3% | 83.3% | 83.3% | 100% | 100% | 100% |
| kb_rag | 2 | — | — | — | — | — | — |

kb_rag 本窗**不出分**：同索引被 S9 的 `rag_index.py eval --queries eval/queries.real.jsonl` 占用，本任务 hybrid/bm25 查询在 60–240s 全部超时。超时记「通道不可用」，**不记 recall=0**（0 表示检索器跑完但没命中）。同会话早先一次空窗 `retrieve("液冷服务器温控产业链", k=3)` 104s 成功，命中 `wiki/entities/英维克.md` 等，证明通道本身能工作。待 S9 释放索引后用 `--kb-timeout 180` 重跑 kb-019/kb-020。

## 2. user_memory 逐条（k=5）

| case | hit@5 | recall@5 | 漏召回 ts | 机制 |
|---|---|---|---|---|
| r-001 裕太微上涨空间 | 否 | 0 | 09:43:06、12:57:20 | 该召回的是方法论条（标签=瑞华泰/策略），实际召回了标签=裕太微的深挖顺序条 |
| r-002 深挖精智达 | 是 | 0.33 | 13:09:40、14:18:00 | 只命中标签=精智达的一条；跨主题深挖样板未召回 |
| r-003 瑞华泰证伪 | 是 | 1.00 | — | 标签命中 |
| r-004 结构完整≠高分 | 是 | 1.00 | — | @1 未进前 1，@3 起满召回 |
| r-005 大盘/情绪阶段 | 否 | 0 | 13:49:00、14:32:00 | query 无空格，`_query_terms` 把逗号两侧整句当 term，不能打到「大盘」「MA5情绪」 |
| r-006 策略一二三四 | 是 | 1.00 | — | theme=策略方法论 打到标签 |
| r-007 盘前复盘推演 | 否 | 0 | 00:31:00+08 | 整句当 term；记录标签是「日度复盘推演」不是 query 子串 |
| r-008 双盲答卷 | 是 | 1.00 | — | theme=forecast-review-ledger |
| r-009 卖方研报缺失 | 是 | 1.00 | — | theme=知识库入库 |
| r-010 已 ingest 电话会 | 否 | 0 | 11:24:11 | `themes=[]`，整句 term 不是正文子串 |
| r-011 每日清单四问 | 否 | 0 | 11:29:58 | 同上，空标签 |
| r-012 CDP | 否 | 0 | 04:07:18、16:54:41 | 空标签；query「Chrome没开远程调试」不是「IPv6/UUID」正文子串 |
| r-013 Grok 精读 notebook | 否 | 0 | 15:55:37、16:19:49 | 空标签；query 无「Grok」「notebook」连续子串匹配不到整句 |
| r-014 驾驶舱/质量门 | 否 | 0 | 17:52:34 | 空标签；query 逗号后「驾驶舱还要不要生成」不是正文子串（正文是「无需继续生成…驾驶舱」） |
| r-015 汇成二阶导 | 是 | 1.00 | — | theme=汇成股份 |

7/15 hit@5。@3 与 @5 宏平均相同：一旦打上标签，k=3 已够；打不上的 k=5 也救不了。

## 3. experience_cards 逐条

生产默认 k=3；本表 k=1/3/5 同值。

| case | hit@5 | recall@5 | 漏 |
|---|---|---|---|
| ec-016 深挖飞凯材料 | 是 | 0.50 | `2026-06-30T21:36:18.375192+08:00`（candidate「深挖飞凯材料(300398)」）未进相关卡；promoted 样板进了 |
| ec-017 晚间卖方×机构胜率 | 是 | 1.00 | — |
| ec-018 高位主线反证 | 是 | 1.00 | — |

## 4. 08-09 S3：检索不足还是题目超纲

题面（`intelligence/tests/fixtures/episode_seam_ladder_cases.json` `weekly-market-cause`）：

> 以 2026-08-07 收盘为准，本周行情上涨的主要原因是什么？

Judge 原话出处：`docs/verification/2026-08-09-episode-seam-ladder-live.md` §5.8
「草稿把『成长主线获得增量资金推动』写成可核验主因，而已绑定证据只支持指数/成交额/板块量价。」
结构缺口从 5 项收到只剩 `cause_attribution`（同文件 §5.6）。

本尺子三通道实测：

| 通道 | retrieved | 是否可能支撑 cause_attribution |
|---|---|---|
| user_memory（无 theme） | `[]` | 否。台账没有「2026-08-04~07 这一周上涨主因」记录 |
| user_memory（theme=大盘） | 5 条方法论（市场结构/MA5/瑞华泰澄清） | 否。那是怎么拆盘面，不是该周主因 |
| experience_cards | 飞凯样板 / 个股完整路径 / 汇成 95 分 | 否。噪声，与周度归因无关 |
| kb_rag | 本窗超时未出命中 | wiki 无 `2026-08-07` 周度归因页（实体/概念/synthesis 均无该周主因文档；08-07 只有 cninfo 公告 raw） |

**定性回答：就本标注集覆盖的三通道（user_memory / experience_cards / wiki RAG）而言，是题目超纲。**
这三套库里不存在「该周上涨的可核验主因」这条记忆或文档；空召回或噪声召回都不能让 `cause_attribution` 成立。

episode 实际取证路径是 `market_data` + `news_search`（ladder note：mandatory 这两项），**不在本尺子已挂通道里**。judge 已看到盘面、没看到因果新闻——那是 news_search 通道的事。要把 S3 从「超纲」改判「检索不足」，需要另立 evidence_search/news_search 标注集（本 spec 非目标，登记不修）。

## 5. 抽验 5 条出处（验收判据 1）

| case | source_ref | 原文核对 |
|---|---|---|
| r-003 | `corrections.jsonl` `2026-06-30T22:57:37.594296+08:00` | 「公司的澄清/否认不等于硬性抹杀炒作逻辑」 |
| r-004 | 同文件 `2026-06-29T09:37:58+00:00` | 「结构完整不等于高质量」 |
| r-008 | 同文件 `2026-07-05T17:58:30+00:00` | 「必须先确认或生成 2026-07-03.manifest.json」 |
| r-014 | 同文件 `2026-08-04T17:52:34+00:00` | 「无需继续生成 agent-daily、策略矩阵和驾驶舱等渲染层」；08-14 草稿误绑同分钟 `17:48:30`（Devin session 隔离），本集已改绑 |
| ec-017 | `experience_cards.jsonl` `2026-06-30T04:20:00+00:00` | question=「晚间卖方与机构胜率发散框架」 |

## 6. KB 仓 `eval/queries.real.jsonl` 盘点（不混分母）

- 40 题，**0 题缺 `expected_pages`**（待标清单为空）。39/40 有 `optional_pages`。
- 身份是**页面标题**（「光模块」「中际旭创」），不是 finance 尺子的 `wiki/entities/*.md`。两套标注不能直接并表。
- 收口标准见 KB `eval/relabel-draft.md` + `eval/acceptance.md`（2026-08-13 已落地）。
- 复用方式：KB 侧分数继续用 KB 仓自己的 `rag_index.py eval`；finance 基线只引用「40/40 已标」这一完整度事实。本窗 S9 正在跑四臂对照，finance 不抢同一索引。

## 7. 登记缺陷（不修，另立 spec）

1. **中文无分词**：`user_memory._query_terms` 只按标点切。口语整句 query 变成 1–2 个超长 term，空标签记录（r-010..014）必然 0 分。这是 8/15 miss 的主因。
2. **方法论条贴了个股标签**：r-001 该召回「上涨空间走市场结构」但标签是瑞华泰，被「裕太微」深挖条挤掉。
3. **judgments 台账空**：生产 [M] 的一半通道无数据；本集 15 条全部落在 corrections。
4. **kb_rag 评测与 S9 抢索引**：finance 侧 wiki 召回基线要等 S9 释放后再跑。
5. **S3 的因果通道未挂尺**：news_search / evidence_search 不在 `RETRIEVERS`。

## 8. 待用户裁决

无。r-014 已按原文改绑；其余 19 条 relevant ts 均在台账且与 note 同向。拿不准的（r-001 是否该召回未贴「裕太微」的方法论）沿用 08-14 Knevo 审计结论：该召回，当前 0 分记检索不足。
