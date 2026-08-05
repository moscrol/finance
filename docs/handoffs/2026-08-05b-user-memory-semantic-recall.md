# Handoff：user_memory 召回改造——接上游意图 + 语义检索

> 接替已作废的 `2026-08-05-user-memory-recall-cjk.md`（那份把问题当成"怎么从字符串猜实体"，
> 而实体在上游已被 LLM 抽好）。
> **架构方向由用户拍定：用语义检索，不用关键词匹配。**

## 0. 先看这些实测数字，它们决定方案（别跳过）

**[实测 2026-08-05 复核]** 用户真实台账规模（`/Users/a77/agent-memory/.foresight/linxiaoqi5111/`）：

| 台账 | 条数 |
|---|---|
| `judgments.jsonl` | **文件不存在** |
| `corrections.jsonl` | 53 |
| `checkpoints.jsonl` | 28 |
| `verdicts.jsonl` | 60 |
| 合计 | **141 条** |

> 上一版写的 50/28/54（~132）是几天前的数，已按 `wc -l` 复核更正。

**台账在哪不是固定的，评测前必须先钉住。** `userspace.users_dir()`
（`userspace.py:63-71`）由环境变量 `FORESIGHT_USERS_DIR` 重定向，不设时才落在仓库内
`intelligence/users/`。仓库内那份只有 `corrections` 8 条（`users/default/`）或 27 条
（`users/linxiaoqi5111/`），**比真台账少一个量级**。同一套代码在两处会得出完全不同的
假阳性率，所以评测报告必须写明本次 `FORESIGHT_USERS_DIR` 指向哪里。

**[实测] `users_root` 的语义是叶目录，不是父目录——传错会静默返回空召回。**
`_ledger_paths`（`user_memory.py:140-164`）在 `users_root is not None` 时直接拼
`root / "judgments.jsonl"` 等四个文件名，**`user` 参数被完全忽略**（根本不走
`userspace.user_space(user)` 那条分支）。所以：

```
users_root=.../.foresight  + user='linxiaoqi5111'  → 找 .foresight/judgments.jsonl → 全 0
users_root=.../.foresight/linxiaoqi5111            → 正确
```

台账文件缺失时 loader 不报错、返回空列表，于是错路径的读数是 **0 命中**，
和「语义检索没效果」**长得一模一样**。本轮第一次探测就踩了这个。
第二档量 embedding 效果前，先跑一次已知非空的对照
（`theme="瑞华泰"` 应得 3 条 corrections）确认路径是通的，再解读任何 0 命中。

**推论一：不要建索引。** 141 条的量级，全量 embedding + 暴力余弦就够，
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

## 1. 第一步：接上游已有的结构化意图 — ✅ 已完成（未提交）

**这一步和语义检索无关，但要先做**——它是零成本的基线提升，也是语义方案的对照组。

改动落在 worktree `/Users/a77/finance-workspace-private/.worktrees/headless-tool-pairing`
（分支 `fix/headless-tool-correlation-observability`）。**主检出树不是这棵**——主树在
`fix/grounded-chain-critical-path` 且工作树不干净，在主树 grep `memory_lookup` 会一无所获。

### 实际实现

`episode_tools.py` 新增纯函数 `_memory_recall_intent(subject, subject_kind)`，
把 contract 已解析的 subject 按 kind 路由进 `relevant_memory_records()`：

- `company` / `concept` / `theme` → `theme=subject`
- `market_pattern` / `index` / `external_market` / `unknown` → 不传
- routed subject 短于 `_MIN_ROUTED_SUBJECT_CHARS = 2` → 不传

### 上一版这条指令是错的，别再照做

上一版让「按 kind 决定填 `entity` 还是 `theme`，或两者分流」。**分流不存在。**
`_query_terms`（`user_memory.py:33-46`）把 `theme` 和 `entity` 平铺进同一个 terms 列表；
扫哪些标签由 `relevant_memory_records` 按记录类型写死（judgments 用
`("themes","stocks")`、corrections 用 `("themes",)`，`user_memory.py:220,229`），
**跟调用方传哪个参数无关**。真台账实测两者逐字节相同：

```
theme ='瑞华泰' → 0 judgments 3 corrections
entity='瑞华泰' → 0 judgments 3 corrections
```

统一传 `theme` 的理由：生产台账把公司名记在 `themes` 里（`瑞华泰` 就是 themes 标签，3 条），
而 corrections **根本没有 `stocks` 字段**。按 kind 分流反而会让 `company→entity` 漏掉这 3 条。
**除非 `select_relevant` 先学会区别对待两个参数，不要重新引入分叉。**

### `sector` / `industry` 是死值

全树 grep 过所有 `subject_kind` 生产写入点（`turn_control_core._subject_kind_for`、
`task_frame.py:196`）：没有 `sector`/`industry` 的生产者，已删。`concept` 保留——
但理由是 `SubjectKind` 是 `typing.Literal`、运行期零校验，**不是**因为观察到生产调用方
在产它（只有 `test_episode_tools.py` 的 fixture 在产，而那个 fixture 自身
`question_type="stock_deep_dive"` 在生产里会被映射成 `company`）。

### 效果（真台账对照，非 fixture 现象）

```
relevant_memory_records("那还能追吗")                 → 0 j 0 c
relevant_memory_records("那还能追吗", theme="瑞华泰")  → 0 j 3 c
```

### `ask.py:621` 未改，如实记录

`ask.py:3733` 已正确传 `theme` 与 `anchored_name`；`621` 那处只有 `options.query`，
**该阶段没有已解析好的 subject/theme 可复用**，硬造会引入猜测，故未改。

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
| 基线 | 原始 query，无 routed subject（把 `_memory_recall_intent` 短路成返回 `{}` 即得） |
| +结构化意图 | §1，**已完成**，零新依赖、零模型加载 |
| +语义 | §2 做完 |

每档报**命中数 / 假阳性数 / 延迟**。

### 三个会骗人的地方（都已实测，别踩）

**① fixture 的形状不代表生产，这比 `FORESIGHT_USERS_DIR` 指哪儿更容易骗人。**
真台账**没有 `judgments.jsonl`**，53 条 corrections 的字段是
`ts/correction/themes/original/principle`——没有 `stocks`。所以第一档评测实际只压
corrections 那一条路，`stocks` 标签在今天的生产台账里**完全不可达**。而
`test_episode_tools.py` 的 fixture 是 judgments 重的，照它的形状设计评测集会量错东西。

**② 假阳性率会被 routed subject 的长度主导，不是被路由表主导。**
`_norm` 做子串匹配，且标签被拼成一个串，短 subject 会横扫。真台账实测：

```
theme='AI'   → 5 corrections（打满 DEFAULT_LIMIT）
theme='市场'  → 5 corrections
theme='光刻胶' → 0
```

`AI` 是标准 theme 型 subject，照样路由。`_MIN_ROUTED_SUBJECT_CHARS = 2` 只挡掉单字，
挡不住这个。**评测输出里必须记一列 routed subject（及其长度），否则数字无法归因。**

**③ 长度门槛只被单测钉住，没有行为测试兜底。**
变异测试确认：把 `_MIN_ROUTED_SUBJECT_CHARS` 从 2 改成 1，只有那条单测转红。
单字 subject 罕见，不值得为它再造 fixture，但**如果评测跑出假阳性异常，这块没有测试兜底**。

**允许的结论包括**：「接完结构化意图后残留漏召回很少，语义检索的边际收益不足以
承担模型加载成本」——**反向结论算有效产出**，不要为了交付语义方案而夸大基线的差。

## 4. 验收

**解释器只有一条路。** 全仓 `ls -d .venv*` 只有 `.venv-workbench`；`which ruff` 找不到，
也没有 brew/pipx 版本。**测试和 lint 是同一个解释器**，不要试 `uv run ruff` 或别的入口。
用宿主 `python3`（homebrew 3.14，无任何依赖）会报 `No module named ruff`——
这跟「跑 pytest 必须用 `.venv-workbench/bin/python`」是同一个坑换了个马甲。

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_user_memory.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_kb_rag.py
.venv-workbench/bin/ruff check intelligence/     # ruff 0.11.13
```

> 上一版列的 `intelligence/tests/test_ask.py` **不存在**，实际是 5 个 `test_ask_*.py`。

**§1 完成时的实测读数**（ruff `All checks passed!`，exit 0）：

| 项 | 数 |
|---|---|
| `test_episode_tools.py` 改动前 | 38 passed |
| `test_episode_tools.py` 改动后 | **43 passed** |
| 其中 memory 子集 | 8 passed |
| 相邻四文件（test_user_memory / test_memory_gate / test_agent_episode / test_episode_factory） | 106 passed，无回归 |

**变异测试（已跑，不是只看绿灯）**：

- 抽掉整个路由 hop（`_memory_recall_intent` 恒返回 `{}`）→ **4 条红**
- `_MIN_ROUTED_SUBJECT_CHARS` 2→1 → **1 条红**

> 教训留档：`test_memory_lookup_company_subject_reaches_stock_tagged_records`
> 最初断言「够到 `stocks` 标签」，但在「company 改走 theme」的变异下**依然是绿的**——
> 因为两参数等价，它换任何分支都过。已重定向为
> `..._recalls_only_its_own_records`，只钉 subject 级分区，不再声称哪个 tag 字段命中。

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
