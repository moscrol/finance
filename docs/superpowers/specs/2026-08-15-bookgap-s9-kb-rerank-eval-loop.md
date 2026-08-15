# S9 · KB Hybrid 检索加 rerank + 评测闭环

- 索引：`2026-08-15-bookgap-index.md` · 靶：第 3 章 + KB 仓自述学习重点 · 仓：**knowledge-base-private** · 优先级 P1
- 并行安全：KB 仓 `scripts/` + `.rag_index`，与 finance 仓所有在飞工作零交集
- **本 spec 在 KB 仓内执行，遵守其 AGENTS.md**：教学模式（讲原理 +
  选型对比 + 可迁移知识点）、Git 约定（开分支、合 main 等用户确认）、
  大 JSON 走 `query_relations.py`

## 1. 背景（证据）

- KB 仓 AGENTS.md 用户偏好自述：「学习重点：RAG、Hybrid 检索
  （向量 + BM25 + **rerank**）等；实现时优先选能学到主流/前沿做法的方案」。
- 现状：`.rag_index/` 已有 BM25（`bm25.pkl.gz`）+ 稠密向量（`dense.npy`）
  两路召回；**rerank 层缺失**——三件套差最后一件。
- 评测原料已有：`eval/queries.jsonl`、`eval/queries.real.jsonl`、
  `eval/dense-review-20260813.md`（dense 路的人工复查）、`acceptance.md`。
  即：加 rerank 前后**可以出对照分**，不是盲改。
- finance 侧消费方：8792 的 wiki RAG 检索走 KB 仓 `.rag_venv` 与索引
  （启动器 `KB_RAG_PYTHON` / `RAG_INDEX_DIR`）——rerank 若上线，
  生产问答的证据召回直接受益。

## 2. 目标 / 非目标

- 目标：hybrid 召回（BM25 ∪ dense，各取 top-N）后加 rerank 段，
  产出最终 top-k。候选方案至少对比两个（教学模式要求）：
  ① cross-encoder 本地模型（如 bge-reranker 系列，`.rag_venv` 内跑）；
  ② LLM listwise rerank（走中转，成本高延迟高）。**默认推荐 ①**，
  选型对比写进交付文档（为什么、何时该换 ②、可迁移到哪些场景）。
- 目标：评测闭环——用 `eval/queries.real.jsonl` 出
  「BM25 only / dense only / hybrid / hybrid+rerank」四臂对照表
  （hit_rate@k, k=5/10），rerank 的延迟开销一并报。
- 目标：给 finance 侧一个**开关**（索引查询脚本参数或 env），默认 off，
  打开与否由对照分决定——不许无对照上线。
- 非目标：不动 chunking 与嵌入模型（变量隔离）；不重建全量索引；
  不改 finance 仓代码（消费方开关若需 finance 侧改动，只写建议不动手）。

## 3. 改动面（KB 仓）

| 落点 | 内容 |
|---|---|
| `scripts/`（rerank 模块 + 查询入口参数） | rerank 段实现（懒加载模型，冷启动时间要量）、`--rerank on/off` |
| `requirements-rag.txt` | 新依赖（版本钉死；模型权重不进 git，下载脚本 + 校验和） |
| `eval/`（对照报告） | 四臂对照表 + 延迟表 + 选型对比文档（教学模式） |
| 测试 | rerank 段单测（给定 mock 分数重排正确、off 时旁路字节等价）+ 冷启动预热钩子测试 |

## 4. 验收判据（预注册）

1. 四臂对照表在 `queries.real.jsonl` 全集上出分，hybrid+rerank 的
   hit_rate@5 **不劣于** hybrid（劣于即如实报，结论可以是「不上线」——
   否定结论也算合格交付）。
2. rerank 单查询延迟 p50 ≤500ms（本地 cross-encoder、CPU 或 MPS 实测），
   超了要给预热/批量策略或降级建议。
3. off 旁路：`--rerank off` 结果与现状字节等价（测试断言）。
4. 选型对比文档包含：原理一段、①vs② 成本/质量/延迟三栏、
   「什么时候该换 ②」的触发条件、可迁移场景两例。
5. 模型权重不进 git（pre-commit 红线本来就拦，勿绕）。

## 5. 风险

- `.rag_venv` 装新依赖可能与现有版本冲突：先 `pip install --dry-run`
  留档；冲突则在报告里给隔离 venv 方案，不硬装。
- 中文 rerank 模型质量参差：对照分说话，不预设结论。
