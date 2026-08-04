# Handoff：user_memory 召回改造——接上游意图 + 语义检索

> 接替已作废的 `2026-08-05-user-memory-recall-cjk.md`（那份把问题当成"怎么从字符串猜实体"，
> 而实体在上游已被 LLM 抽好）。
> **架构方向由用户拍定：用语义检索，不用关键词匹配。**

## 0. 先看这些实测数字，它们决定方案（别跳过）

**[实测]** 用户真实台账规模（`/Users/a77/agent-memory/.foresight/linxiaoqi5111/`）：

| 台账 | 条数 |
|---|---|
| `judgments.jsonl` | **文件不存在** |
| `corrections.jsonl` | 50 |
| `checkpoints.jsonl` | 28 |
| `verdicts.jsonl` | 54 |
| 合计 | **~132 条** |

**推论一：不要建索引。** 132 条的量级，全量 embedding + 暴力余弦就够，
建/维护一个 ANN 索引是过度工程，还要处理增量更新和 per-user 隔离。

**推论二：`judgments` 缺失是独立问题。** `memory_block_for_query` 第一个加载的就是它
（`user_memory.py` 内 `load_judgments`），而文件不存在。这意味着**"我过去的判断"这一源
当前是空的**，只有纠偏/检查点/裁决。**先查清是谁该写它、为什么没写**，
写进报告；不要在本轮顺手补写入链路（越界）。

**[实测]** 现有检索设施的真实形态：

- `intelligence/services/kb_rag.py` 是**子进程适配器**，通过 `KB_RAG_PYTHON` +
  `RAG_INDEX_DIR` 调知识库仓的 RAG CLI，**不是通用 embedding 服务**
- 索引在 `/Users/a77/knowledge-base-private/.rag_index/`：`bm25.pkl.gz` / `dense.npy` /
  `chunks.jsonl` / `meta.json`，**离线预建、语料是 wiki**，`model: bge-m3, dim: 1024`
- `intelligence/services/` 下**只有 `kb_rag.py` 一处**涉及 embedding

**推论三：没有现成的"给我一段文本的向量"接口。** 你需要自己决定怎么拿向量，
见 §2。

## 1. 第一步：先接上游已有的结构化意图（便宜、必做）

**这一步和语义检索无关，但要先做**——它是零成本的基线提升，也是语义方案的对照组。

**[实测]** 事实：

- `memory_block_for_query` / `relevant_memory_records` **本来就有 `theme` / `entity` 参数**，
  `_query_terms` 会把它们直接当 term 追加
- `ask.py:3733` **已经正确传了**：`memory_block_for_query(options.query, theme, anchored_name, ...)`
- `ask.py:621` 与 `episode_tools.memory_lookup_runner` **只传了原始 query**
- `ResearchTaskContract`（`research_contract.py:668` 起）有 `subject` / `subject_kind`，
  而 `episode_tools` 已在用 `context.contract.*`——**抽好的实体就在手边**

**要做**：

1. `memory_lookup_runner` 传 `entity=context.contract.subject`
   （**先查清 `subject_kind` 的取值域**，决定该填 `entity` 还是 `theme`，或两者按 kind 分流）
2. `ask.py:621` 同理——但**先查清那个阶段有没有解析好的 subject/theme**。
   3733 那处能拿到不代表 621 能；拿不到就如实写进报告，不要硬造。

**这一步做完先跑一次基线测量**（见 §3），它是语义方案的对照组。

## 2. 第二步：语义检索（用户拍定的方向）

### 必须自己定并说明理由的三件事

**① 向量从哪来？** 至少评估这三条，给对照，不要直接选一条：

| 路线 | 要点 | 风险 |
|---|---|---|
| 复用 RAG venv 的 bge-m3 | 与知识库同模型，语义空间一致 | **模型加载成本**。每次查询冷载 bge-m3 不可接受；要么复用常驻 worker（查清它暴不暴露"embed 任意文本"），要么自己起常驻 |
| 更轻的本地模型 | 冷启快、内存小 | 与 wiki 检索**不在同一语义空间**，两边分数不可比 |
| 走已有 RAG CLI，把记忆当第二语料建索引 | 复用全套设施 | 132 条建索引是过度工程；且**记忆是 per-user 私有 + 持续追加**，索引会不断失效 |

**② 记忆侧的向量怎么缓存？** 132 条、变更频率低（用户偶尔纠偏）。
建议按台账文件的 mtime/hash 做失效判断，把向量缓存在**用户自己的空间内**
（与台账同目录），不要写进仓库、不要进 git。

**③ 兜底策略。** 语义路径不可用时（模型缺失、worker 没起、超时）**必须优雅降级**回
现有关键词召回，并留可观测信号——**不能静默返回空**。
参考 `_graph_lookup` 的 `status="empty"` 形状与 `kb_rag` 现有的降级遥测。

### 硬约束（不可协商）

- **隐私**：记忆台账是用户私有判断。向量、缓存、日志、遥测**一律不得包含正文**；
  测试一律用 `users_root=` 临时 fixture，不读真实台账、不入断言、不进提交物。
- **只读 + 无外呼**：agent 工具红线。embedding 必须本地跑，不许调云端 API。
- **不动 `memory_lookup` 已验收的契约**：evidence_tier=`user_memory`、
  自我标注的 `source`、`internal_locator` 指台账路径、空结果信号——这些
  `3cde899a` 刚验收过，别动。
- **不动 `experience_cards.select_relevant_cards`**（另一套实现，匹配对象不同，
  顺手统一算越界）。

## 3. 这是检索质量改动，必须有测量

改召回**不能只靠单测通过**。单测只证明代码按你想的跑。

**建一个评测集（15-25 条）**，每条：

```
query（自然中文，贴近真实提问） | 期望召回 | 不该召回
```

给出**三档对照**：

| 档 | 说明 |
|---|---|
| 基线 | 当前实现（原始 query，无 entity） |
| +结构化意图 | §1 做完 |
| +语义 | §2 做完 |

每档报**命中数 / 假阳性数 / 延迟**。

**允许的结论包括**：「接完结构化意图后残留漏召回很少，语义检索的边际收益不足以
承担模型加载成本」——**反向结论算有效产出**，不要为了交付语义方案而夸大基线的差。

## 4. 验收

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_user_memory.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_ask.py \
  intelligence/tests/test_kb_rag.py
.venv-workbench/bin/python -m ruff check intelligence/
```

**先跑一次记基线**，改完逐项对比，新红要能逐条解释。

**通过标准**：

- 上述文件零新红
- 新增测试至少四条：结构化意图生效、语义召回生效、语义不可用时降级且有信号、
  空结果仍给明确信号
- **每条新测试做变异测试**（改坏被测那行必须转红，然后还原）
- 评测集三档对照表进报告
- `git status --short` 只出现你打算改的文件，无风险文件

## 5. 报告要求

除常规三段（改了哪些文件 / 验收命令原始输出 / 自己判断的部分及依据）外，必须回答：

1. `judgments.jsonl` 为什么不存在？谁本该写它？（只查不修）
2. 向量方案选了哪条？三条的对照数据是什么？模型加载成本实测多少？
3. `ask.py:621` 那个阶段拿得到 subject/theme 吗？拿不到的话现状如何？
4. 三档评测的对照表。如果语义档相对结构化意图档提升有限，**如实说**。

## 6. 不要踩的坑

- **读代码别用固定行号**，用 `sed -n '/^def xxx/,/^def /p'` 或 AST。
- **断言"我们没有 X"前**：全树 grep 同义词 + 读能力图谱 + 读 MOC 看板（`CLAUDE.md` §🗺️）。
  **本轮上一份 handoff 就是因为没查"这个参数从哪来"而整份作废。**
- **提议"造一个 X"之前先搜 X 存不存在**，以及**上游是不是已经产出了它**。
- **改完 grep 复核**，别只看工具返回值（多 worktree + pre-commit stash 窗口）。
- 完成后按维护口径回写能力图谱并跑
  `python3 /Users/a77/agent-memory/scripts/graph_audit.py`（须 exit 0），不建第二份清单。
