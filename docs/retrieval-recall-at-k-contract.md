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
| `user_memory` | `relevant_memory_records(..., limit=k)` | judgments 至多 k ∪ corrections 至多 k | 旧集 `ts`；新集显式 `stable` 身份 | 5（`DEFAULT_LIMIT`） |
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

### user_memory 标注准入（2026-10-04）

CLI、`evaluate_cases(..., user_memory_retriever)` 与 `compare_memory_tiers` 在检索前
用生产 loader 核对每个标注：目标必须存在、未退出且处于读取窗口。缺失、已退出、
窗口外或身份不唯一分别记 `missing` / `inactive` / `outside_window` / `ambiguous`。
候选池中有身份碰撞也拒绝评分，避免把多条非标注召回合成一条。
CLI 返回 JSON `status=invalid_memory_labels`、退出码 2，无命中/召回分数；
直接 API 抛 `InvalidMemoryLabels`，详细原因在 `report`。不删题、回填或更改用户台账。

旧 `ts` 身份保持显式兼容，只有唯一且可达才准入。新冻结集可使用
`--memory-identity stable`（API：`identity_mode="stable"`）：标签为
`judgment:<id>` 或 `correction:<id>`；无 id 的旧行用
`memory_status.memory_record_id(kind, ts, content)` 派生同格式身份，正文分别取
`memo` / `correction`，仅用于评测、不写回。不同台账和同秒不同正文不会合并。
用 `memory_recall_labels.memory_identity` 生成标签，不手抄推算。

有效但与查询不匹配的目标仍作为正常 miss 计分。准入只证明标签可测，
不能证明标签语义正确，亦不能证明用户最终答案改善。旧集过期时保存原件和失效原因，
重新冻结新集；禁止只留下易命中的题，再与旧分母比较。

2026-10-04 的真实快照复核发现旧15题仅4题仍有可达目标，见
`docs/verification/2026-10-04-memory-recall-baseline.md`；旧7/15不能作为当前基线。

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
