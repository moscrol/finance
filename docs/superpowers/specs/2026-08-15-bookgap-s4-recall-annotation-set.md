# S4 · recall@k 标注集：让已有的尺子开始出数（双仓）

- 索引：`2026-08-15-bookgap-index.md` · 靶：第 3 章 🔴 + 质检 Q1/Q2 · 仓：双仓 · 优先级 **P0**
- 并行安全：纯数据+文档，立即可开工

## 1. 背景（证据）

- 尺子已有：`intelligence/eval/retrieval_recall.py`（同报学术 recall@k 与
  hit_rate@k，归档记录不入召回），CLI 要求 `--cases`，**仓内没有任何
  标注 JSONL**——「分数不存在」（质检 Q1）。
- 悬而未决的实例：08-09 S3 缺 `cause_attribution`，judge 说「证据只支持
  盘面观察证不了归因」——**到底是检索不足还是题目超纲，没有指标能回答**。
- Q2 陷阱已知：`user_memory_retriever` 在 `limit=k` 时 judgments/corrections
  **各**取 k，召回集合可达 2k——标注口径必须写清「生产 @k = 每通道 k」。
- KB 仓已有原料：`~/knowledge-base-private/eval/` 下 `queries.jsonl`、
  `queries.real.jsonl`、`acceptance.md`、`relabel-draft.md`——KB 侧检索
  评测已起步，finance 侧是空白。

## 2. 目标 / 非目标

- 目标（finance 侧）：建 20 条人工标注 case（JSONL），覆盖
  user_memory 检索（judgments/corrections/experience cards 三通道）与
  wiki RAG 检索两类，跑通 `retrieval_recall.py` 得出第一份基线分数。
- 目标（KB 侧）：盘点 `eval/queries.real.jsonl` 的标注完整度，能直接
  复用的并入同一份基线报告（分开列，不混分母）。
- 目标：写死 @k 口径文档（每通道 k vs 全局 top-k），进 trace-profile
  或独立 conventions 文档。
- 非目标：不改检索器实现（发现的缺陷登记，修复另立 spec）；不做
  RAPTOR/GraphRAG（08-13 质检明确否决）。

## 3. 改动面

| 落点 | 内容 |
|---|---|
| `intelligence/eval/cases/retrieval_recall_v1.jsonl`（finance，新） | 20 条：`{query, expected_record_ids/expected_doc_ids, channel, k, 出处}`；标注依据必须是真实历史 run 或真实笔记，不许造 |
| `docs/verification/2026-08-15-recall-baseline.md`（finance，新） | 首份基线：recall@k / hit_rate@k 按通道分列 + Q2 口径声明 |
| KB 仓 `eval/`（盘点为主） | `queries.real.jsonl` 标注完整度报告；缺标注的列成待标清单，不代标 |

标注来源建议：S3 那类「judge 说证不了」的历史 case（从
`intelligence/eval/runs/` 冻结产物取 query，人工判 expected）+
`.foresight/` 台账里有明确回看结论的记录。

## 4. 验收判据（预注册）

1. 20 条 case 每条带出处（run 产物路径或笔记路径），抽验 5 条能对上原文。
2. `retrieval_recall.py --cases retrieval_recall_v1.jsonl` 跑通出分，
   报告含按通道分列的 recall@k 与 hit_rate@k。
3. 口径文档明确回答：「生产 @k 是每通道 k」，且尺子文档与之一致（Q2 收口）。
4. 对 08-09 S3 那条：标注后能给出定性回答（检索不足 or 题目超纲），
   写进基线报告——这是本 spec 的存在理由，必须回答。

## 5. 风险

- 标注是体力活且有主观性：每条写 1 行标注理由；拿不准的进
  「待用户裁决」列表而不是硬标。
