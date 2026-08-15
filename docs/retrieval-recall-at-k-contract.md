# recall@k 口径契约（质检 Q2 收口）

- 日期：2026-08-15 · 对应 spec：`docs/superpowers/specs/2026-08-15-bookgap-s4-recall-annotation-set.md`
- 尺子：`intelligence/eval/retrieval_recall.py`
- 标注集：`intelligence/eval/cases/retrieval_recall_v1.jsonl`
- 一句话：**生产 @k = 每通道 k，不是全局 top-k。**

## 1. 为什么不是全局 top-k

`user_memory.relevant_memory_records(limit=k)` 对 judgments / corrections **各**取
至多 k 条，装进 [M] 块的并集可达 2k。这不是尺子的发明，是生产语义
（`intelligence/eval/retrieval_recall.py` 模块注释 +
`intelligence/services/user_memory.py:relevant_memory_records`）。

若把并集再截成全局 top-k，尺子会惩罚生产里合法入块的第二条通道。
标注与读数都按「该通道自己的 k」计。

对照书第 3 章脚注（该书 recall@k = hit rate/success@k）：横向对比 Anthropic /
书上数字时用本尺子的 **hit_rate@k**；学术 recall@k（|命中|/|relevant| 宏平均）
另列，不混用。

## 2. 三通道 k 语义

| 通道 | 生产调用 | 本尺子 retrieved@k | 命中身份 | 生产默认 k |
|---|---|---|---|---|
| `user_memory` | `relevant_memory_records(..., limit=k)` | judgments 至多 k ∪ corrections 至多 k | 台账行 `ts` | 5（`DEFAULT_LIMIT`） |
| `experience_cards` | `select_relevant_cards(..., limit=k)` | 相关卡至多 k | 卡片 `ts` | 3（`ask.py` 不传 limit） |
| `kb_rag` | `kb_rag.retrieve(..., k=k, require_fresh=True)` | 按序去重后的前 k 个页面 | 仓相对 `file_path` | 6（`DEFAULT_RAG_K`） |

常驻经验卡（`promotion ∈ {promoted, methodology}`，`select_resident_cards`）
不看 query、无条件入 prompt，**不属检索召回**，不进本尺子分母。

`kb_rag` 不用 chunk_id 当标注身份：chunk_id 绑定索引 revision，重建即漂移。

## 3. 指标

- recall@k = |retrieved@k ∩ relevant| / |relevant|，宏平均按 case 等权。
- hit_rate@k = retrieved@k 是否命中任一 relevant，宏平均。
- 通道分列，**不混分母**。KB 仓 `eval/queries.real.jsonl` 的分数另表。

## 4. 读数纪律

分数度量检索层召回，不度量答案正确性。分数低先查：

1. 标注是否过期（记录被归档 / `invalidated` 后应改标注）；
2. 记录是否无 `themes`、query 无标点导致 `_query_terms` 把整句当一个 term
   （见基线报告「登记缺陷」，不在本 spec 修检索器）。

## 5. 命令

```
.venv-workbench/bin/python -m intelligence.eval.retrieval_recall \
  --cases intelligence/eval/cases/retrieval_recall_v1.jsonl \
  --channel user_memory --retriever user_memory \
  --users-root "$FORESIGHT_USERS_DIR/$FORESIGHT_USER" \
  --k 1,3,5
```

`--channel` 过滤标注行；`--retriever` 选生产通道。两者应一致。
`kb_rag` 冷启动 hybrid 建议 `--kb-timeout 180`（默认 90s 会被模型加载吃掉）。
