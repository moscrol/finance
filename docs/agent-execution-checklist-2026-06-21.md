<!--
保存说明（由 lbq Mac 归档，非原文一部分）：
- 来源：另一台 Mac（a77）维护的「金融 Agent 执行清单」，生成日期 2026-06-21，进展更新至 2026-06-23。
- 用途：lbq Mac 侧对照执行与对账参考。文中 /Users/a77/... 路径为原机器路径；本机对应 /Users/lbq/Desktop/c c/。
- 真实完成度对账见对话记录（2026-06-28 审计）。
-->

# 金融 Agent 执行清单

## 2026-06-28 lbq Mac 最新逐项对账

### 总结

| 模块 | 最新实测 |
|---|---|
| 知识库证据系统 + 向量记忆层 | ✅ 基本完成；`.rag_index` 存在，`agent-daily` 已能用 `hybrid` 语义召回 |
| 金融生命周期雷达五件套 | ✅ PR #88 已 merge 到当前分支，核心文件已在本机工作树 |
| `agent-daily` 接线验收 | ✅ 2026-06-26 已重跑，JSON / MD / HTML 均生成 |
| RAG 语义层 | ✅ `hybrid` 模式，告警 0，语义命中 9 条 |
| 回归门禁 | ✅ 金融 Agent 相关单测 44/44 通过，编译通过 |
| 工程化 / 评测 / 编排增强 | ✅ 最小闭环：P2#7 ingest 状态 ledger、P2#8/P2#9 RAG 分层元数据与过滤、P4 最小黄金样本/反幻觉门禁、薄编排层均已落地 |

### 知识库侧

| 清单项 | 文件 / 产物 | 最新实测 |
|---|---|---|
| P0.3 Agent Doctor | `scripts/agent_doctor.py` + tests | ✅ 在 |
| P1.4 relations integrity | `check_relations_integrity.py` + tests | ✅ 在 |
| P1.5 evidence source 追溯 | `audit_missing_evidence_sources.py`、`materialize_missing_source_stubs.py` + tests | ✅ 在 |
| missing concept 清洗 | `audit_missing_concepts.py`、`repair_missing_concept_aliases.py`、`remove_polluted_concept_refs.py` + tests | ✅ 在 |
| IMA ingest 管线 | `build_ima_concept_ingest_queue.py`、`ima_stock_ingest_batch.py` + tests | ✅ 在 |
| 向量索引 / 记忆层 | `.rag_index/` + `scripts/rag_index.py` | ✅ 本机可用；`agent-daily` hybrid 查询已验证 |
| KB 测试文件 | `tests/test_*.py` | ✅ 在 |

### 金融生命周期雷达侧

| 清单项 | 文件 / 产物 | 最新实测 |
|---|---|---|
| P1.6 证据升级门禁 `research_judge` | `intelligence/services/research_judge.py` | ✅ 当前分支已有 |
| P1 生命周期快照 `logic_lifecycle` | `intelligence/services/logic_lifecycle.py` | ✅ 当前分支已有 |
| P2 研究任务队列 `research_queue` | `intelligence/services/research_queue.py` | ✅ 当前分支已有 |
| P3 盘面验证层 `market_validation` | `intelligence/services/market_validation.py` | ✅ 当前分支已有 |
| P3.5 snapshot 契约 | `intelligence/services/market_snapshot_contract.py`、`docs/market_snapshot_contract.md`、`scripts/check_market_snapshot_contract.py` | ✅ 当前分支已有 |
| P0.2 Market Snapshot Consumer | snapshot contract + consumer path | ✅ 短期契约层已有；真实 DuckDB snapshot 仍等另一台 Mac 数据输入 |

### 已落地且本分支真有的能力

| 能力 | 文件 / 产物 | 最新实测 |
|---|---|---|
| `logic_market_match` + 批量 | `intelligence/services/logic_market_match.py`、`intelligence/workflows/logic_match.py` | ✅ 在 |
| Question Router + Path Registry | `intelligence/services/question_router.py`、`intelligence/services/path_registry.py`、`intelligence/routing/path_registry.json`、`intelligence/workflows/route.py` | ✅ 在 |
| Daily Ops Ledger | `scripts/build_daily_ops_ledger.py` + tests | ✅ 在 |
| `agent-daily` 日常入口 | `intelligence/workflows/daily_agent.py` | ✅ 生命周期版；已包含 `logic_lifecycle` / `market_validation` / `research_queue` / `research_judge` |
| 语义层接通 | `intelligence/services/kb_rag.py` | ✅ 已接通；`hybrid` 命中 9 条，告警 0 |

### 工程化 / 评测 / 编排

| 清单项 | 最新实测 |
|---|---|
| P0.1 路径环境统一 | ✅ 已补齐最小闭环：`FINANCE_WS`、`FINANCE_ROOT`、`KB_VAULT`、`KNOWLEDGE_WIKI`、`MARKET_SNAPSHOT_DIR`、`VECTOR_INDEX_DIR` 均已进入金融路径层；RAG 侧兼容 `VECTOR_INDEX_DIR` / `RAG_INDEX_DIR` / `KB_RAG_PYTHON` |
| P2#7 Ingest 状态机 | ⚠️ 观测+计划闭环已推进：ingest status ledger + 只读 indexed probe + 只读 ingest action plan（把缺口映射到已有 KB dry-run 命令、已 indexed 项自动跳过）；真正写库仍由 KB 脚本自身 `--apply` + 人工确认，未自动执行 |
| P2#8 向量索引分层 | ✅ 最小版已落地：RAG chunk/query 已输出 `evidence_layer` / `fact_hardness` / `source_type` |
| P2#9 RAG 引用规范 | ✅ 最小版已落地：知识库 `rag_index.py query` 支持按 `evidence_layer` / `fact_hardness` / `source_type` 过滤；金融 `kb_rag` 可透传过滤并解析 metadata |
| P4 黄金样本 / 反幻觉评测 | ✅ deterministic golden 已增强：`tests/test_agent_golden_eval.py` 固定路由分桶、生命周期、盘面验证、证据裁判、研究队列和占位信号反幻觉断言 |
| P4+ agent-eval 维度扩展 | ✅ `agent-eval` 新增 `forbid_entities`（事实错配闸）+ `forbid_phrases`（证据层级 overclaim 闸）；用例从 3 个扩到 6 个（+PCB/固态电池/AI眼镜），实体与证据层均取自知识库真值；scorer 单测 31/31 通过 |
| P4+ 案例接地校验 | ✅ `scripts/validate_agent_cases_grounding.py` 交叉核对用例 expect/forbid 实体与 KB `entity_exposures`；6 case 全部 100% 接地、0 违规；纯逻辑+KB 集成单测通过 |
| P4+ agent-eval 接地预检 | ✅ `agent-eval` live 跑前自动接地预检：用例未对齐 KB 时退出码 2 拦截、不消耗 LLM；缺 KB 自动跳过；`--skip-grounding-check` 可绕过；`tests.test_agent_cases_grounding` 9/9 通过 |
| P4+ 记分卡可视化 | ✅ `agent-eval` scorecard 表格新增 `错配实体` / `证据越级` 两列；事实错配与 overclaim 不再只藏在失败项里；评测相关单测 41/41 通过 |
| 薄编排层 `agent_orchestrator.py` | ✅ 最小版已落地：`orchestrate` 先 route 再渲染执行计划；默认 preview，`--execute` 仅执行 low-risk + auto_execute path |

### 本次执行记录

| 项目 | 结果 |
|---|---|
| PR #88 merge | ✅ 当前分支包含 `ea2ab9f`，最新 merge commit 为 `9ab8e81` |
| 金融 Agent 单测 | ✅ 44/44 通过；P4 相关组合门禁 23/23 通过 |
| 编译门禁 | ✅ 通过 |
| `agent-daily --date 2026-06-26` | ✅ 已重跑 |
| 输出 JSON | ✅ `market_feature_store/exports/2026-06-26-daily-agent.json` |
| 输出 Markdown | ✅ `market_feature_store/exports/2026-06-26-daily-agent.md` |
| 输出 HTML | ✅ `复盘/daily/2026-06-26/2026-06-26-daily-agent.html` |
| 研究任务队列 | ✅ IMA 2；公告/调研/订单 2；等盘面验证 0；降级观察 5 |
| P0.1 vector index path | ✅ `ProjectPaths.vector_index_dir` 已新增；`kb_rag` 优先读 `VECTOR_INDEX_DIR`，兼容 `RAG_INDEX_DIR`；相关单测通过 |
| P4 deterministic 黄金门禁 | ✅ `tests/test_agent_golden_eval.py` 已增强并通过；固定 `液冷服务器`→旧逻辑唤醒、`连板未映射`→噪音/未确认，且缺 L3 不得判为已有事实验证 |
| P2#8 RAG 分层元数据 | ✅ 知识库 `chunking.py` / `retrieval.py` 已支持；RAG tests 61/61 通过；现有索引已刷新分层字段 |
| P2#9 RAG 分层引用过滤 | ✅ 知识库短门禁 4/4 通过；金融 `kb_rag` 短门禁 3/3 通过；CLI `--evidence-layer L0_concept` 已验证 |
| P2#7 ingest status ledger | ✅ `scripts/build_ingest_status_ledger.py` 已新增；单测 2/2 通过；2026-06-26 ledger 已生成，item_count=66，status_counts=`candidate_detected:50/backfill_queued:12/pending_review:4` |
| P2#7 indexed 观测层 | ✅ `scripts/enrich_ingest_status_with_index.py` 已新增；单测 2/2 通过；2026-06-26 indexed ledger 已生成，index_status_counts=`rag_indexed:47/concept_page_exists:6/not_in_kb:13` |
| P2#7 ingest action plan | ✅ `scripts/build_ingest_action_plan.py` 已新增（只读，不执行）；单测 2/2 通过；2026-06-26 计划已生成，action_mode_counts=`already_indexed:5/dry_run:7/read_only:3/manual:1` |
| 薄编排层 `agent_orchestrator.py` | ✅ `intelligence.cli orchestrate` 已新增；单测 3/3 通过；CLI 预览 `今天该看什么` 命中 `agent_daily` 且默认不执行 |
| P4+ agent-eval 扩维度 | ✅ scorer 加 `forbid_entities`/`forbid_phrases`；用例扩到 6 题材（实体/层级取自 KB 真值）；`intelligence.tests.test_agent_eval` 31/31 通过 |
| P4+ 案例接地校验 | ✅ `validate_agent_cases_grounding.py` 对真实 KB 跑：6 case 命中率均 100%、forbid 违规 0、概念无缺失；`tests.test_agent_cases_grounding` 9/9 通过 |
| P4+ 记分卡可视化 | ✅ `agent-eval` scorecard 已显示 `错配实体` / `证据越级`；`intelligence.tests.test_agent_eval + tests.test_agent_cases_grounding` 41/41 通过 |

生成日期：2026-06-21  
机器分工：本 Mac 主要负责知识库沉淀、ingest、relations 清洗、向量化与证据判断；另一台 Mac 负责 DuckDB / market_feature_store / 盘面数据生产。

## 最终目标：逻辑生命周期雷达

我们最终不是要做一个“能回答问题的聊天机器人”，也不是只做证据卡、查漏补缺或漂亮驾驶舱。

最终要做的是一个**盘面数据 + 逻辑证据 + 可回溯材料 + 生命周期判断**的金融 Agent：

```text
一条逻辑从出现、沉睡、唤醒、升温、加速定价、分歧、衰退、证伪，
Agent 能持续记录、比较、解释，并告诉用户今天该做什么。
```

它应该每天回答四个核心问题：

1. **这条逻辑处在生命周期哪一段？**  
   新出现 / 旧逻辑唤醒 / 升温验证 / 加速定价 / 高位分歧 / 衰退观察 / 证伪退出。

2. **状态相比昨天或过去 N 天发生了什么变化？**  
   证据层是否升级，盘面强度是否增强，强势股是否扩散，叙事是否升温，旧材料是否被重新验证。

3. **这条逻辑有没有真正产生过市场价值？**  
   看 CAR、相对强度、成交额边际、强势股扩散、涨停扩散、回撤与半衰期，而不是只看“故事是否好听”。

4. **今天人应该做什么？**  
   做 IMA / 找公告调研订单 / 补 L2 基线 / 等盘面验证 / 降级观察 / 移出队列。

因此，当前所有模块的定位如下：

- `research_judge`：不是终点，只是生命周期判断的**证据层输入**。
- `agent-daily`：不是终点，只是每天生成生命周期快照和任务队列的**日常入口**。
- `concept deepdive`：不是默认全量补库工具，只在生命周期判断需要补 L1/L2/L3 材料时使用。
- `market_snapshot` / DuckDB：是判断生命周期变化的**盘面验证层**。
- 向量召回：是找旧逻辑、旧研报、隐含别名和历史材料的**记忆层**。

## 执行进展

更新时间：2026-06-23 12:06 CST

### 已完成

- P0.1 路径与环境统一：金融 repo `intelligence/paths.py` 已支持 `FINANCE_WS`、`KB_VAULT`、`KNOWLEDGE_WIKI`、旧变量兼容和当前用户 home fallback；新增路径测试 4 条通过。
- P0.3 Agent Doctor：知识库 repo 已新增 `scripts/agent_doctor.py`，能检查 KB、金融 workspace、relations、market snapshot、vector index，并输出 PASS/WARN/FAIL。
- P1.4 relations integrity：已修复 `_entry_count` 对 `entity_exposures.entities.*.concepts` 和 `evidence_index.items` 的计数；`check_relations_integrity.py` 已支持 concepts 引用检查与 `--repair-meta`；真实 `wiki/relations/meta.json` 已修复为当前计数。
- P1.5 evidence source 追溯：新增 `scripts/audit_missing_evidence_sources.py` 和 `scripts/materialize_missing_source_stubs.py`，并补齐所有已找到 raw/manifest trace 的 source stub。
- P1.4 missing concept 分桶与低风险清洗：新增 `scripts/audit_missing_concepts.py`、`scripts/repair_missing_concept_aliases.py`、`scripts/remove_polluted_concept_refs.py`；已用别名表归一 10 个既有缺概念别名、40 个 concept key；新增 17 个高置信 tech alias 并修复 57 个 concept key；移除 4 个明显污染概念、15 个 concept key。
- P1.4/P1.5 合并后收口：知识库 repo 已同步 GitHub 最新 211 个提交并推送；合并冲突已解决，`relations/*.json` 已结构化合并，`missing_source_count=0`，`missing_concept_count=0`，`check_relations_integrity.py --vault wiki` 为 0 错误 / 0 告警。
- Concept 轻量卡补齐：合并远端后新增的 228 个 missing concept 已处理，其中同义词归一 19 类、污染边删除 17 类、生成轻量概念卡 161 张。轻量卡只作为图谱落点和召回入口，不替代 DeepDive。
- Source 追溯补齐：合并后新增的 2 个 missing source 已补 source stub，evidence source audit 已归零。
- P1.6 证据升级门禁：金融 repo 已新增 `intelligence/services/research_judge.py` 和 `scripts/research_judge.py`，支持输入公司/题材，输出“证据状态、已有证据层、缺失证据层、已有证据、建议动作、不可升级原因”。已覆盖贝达药业、铭普光磁、阿石创样例；旧 DeepDive / 市场逻辑精选 / iFinD baseline 等无层级老材料也能映射为可读证据层。
- P3.1 日常 Agent 入口：`agent-daily` 已接入每日复盘 workflow、复盘工作台和驾驶舱总入口。`2026-06-11-daily-agent.html` 已生成新版页面，包含“证据裁判”列和证据卡，能区分“旧逻辑待验证 / 能力栈候选 / 重点验证 / 盘面触发待解释”。
- 自然语言全量复盘路径：`intelligence/routing/path_registry.json` 已把“全量复盘 / 每日复盘”覆盖到 `python3 -m intelligence.cli daily --date {date} --kb-wiki {knowledge_wiki}`，不再只走底层 `market_feature_store.cli daily-review`。`daily` workflow 也已支持 `--kb-wiki`，会传给 `agent-daily` 和 `render_cockpit.py --knowledge-root`。
- P1 生命周期快照：新增 `intelligence/services/logic_lifecycle.py`，`agent-daily` 已按近 6 个交易日 `theme-candidates` 为题材生成“新出现 / 旧逻辑唤醒 / 升温验证 / 加速定价 / 高位分歧 / 衰退观察 / 证伪退出”状态，并在 Markdown/HTML/JSON 证据卡中展示“生命周期阶段、阶段变化、变化原因、下一步”。第一版不依赖 DuckDB，只用当前已有的候选、旧材料命中、证据裁判、priority、强势股和触发信号变化。
- P2 今日研究任务队列：新增 `intelligence/services/research_queue.py`，`agent-daily` 已把生命周期 + 证据裁判翻译为四类人工动作：`今日该做 IMA`、`今日该找公告/调研/订单`、`今日等盘面验证`、`今日降级/观察`。数据缺口和连板占位不进研究任务队列，继续留在回补/待确认区域。
- P3 盘面验证层短期版：新增 `intelligence/services/market_validation.py`，`agent-daily` 已从 `theme-candidates` 读取 priority、触发信号、涨停数、新高数、容量前三、强势股等字段，生成 `强验证 / 中等验证 / 弱验证 / 无盘面验证` 摘要，并展示“验证结论、当前盘面、边际变化、强势股”。这一步不依赖另一台 Mac 的 DuckDB，也还不是 CAR/回测层。
- P3.5 market snapshot 契约：新增 `docs/market_snapshot_contract.md`、`intelligence/services/market_snapshot_contract.py`、`scripts/check_market_snapshot_contract.py`。另一台有 DuckDB 的 Mac 后续只需要同步 `market_snapshot/YYYY-MM-DD.json`、`latest.json`、`meta.json`，本 Mac 可用 `MARKET_SNAPSHOT_DIR` 指向该目录并校验字段完整性。
- GitHub 同步：金融 repo PR #88 已打开并更新 7 个提交：`Add research judge to daily agent`、`Wire daily workflow kb wiki path`、`Route full daily review through kb wiki`、`Add logic lifecycle snapshots to daily agent`、`Add daily research task queue`、`Add market validation summaries to daily agent`、`Add market snapshot contract validation`。
- 收尾清理：金融 repo 和知识库 repo 均已清理 `.DS_Store`、`__pycache__` 与临时未跟踪产物；两个 repo 当前工作区干净。

### 当前量化状态

- 知识库 repo：`main` 工作区干净，无未跟踪文件。
- 金融 repo：功能分支 `feature/research-judge-daily-agent` 已推送到 PR #88；P1 生命周期快照、P2 今日研究任务队列、P3 盘面验证层短期版、P3.5 market snapshot 契约均已提交并推送。
- `missing_source_count`：0。
- `missing_item_count`：0。
- `missing_concept_count`：0。
- `check_relations_integrity.py --vault wiki`：0 错误 / 0 告警。
- 当前真实瓶颈从“图谱缺口 / source trace”转为三件事：日常任务队列是否足够清楚、L3 官方证据如何高效补、L4 盘面验证如何稳定接入另一台 Mac 的 DuckDB 产物。

### 最新验证

- 知识库测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_doctor tests.test_relations_integrity tests.test_missing_source_audit tests.test_materialize_source_stubs tests.test_missing_concept_audit tests.test_repair_missing_concept_aliases tests.test_remove_polluted_concept_refs -v`，28/28 通过。
- 金融路径测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_paths -v`，4/4 通过。
- 脚本编译：`python3 -m py_compile scripts/agent_doctor.py scripts/audit_missing_evidence_sources.py scripts/materialize_missing_source_stubs.py scripts/audit_missing_concepts.py scripts/repair_missing_concept_aliases.py scripts/remove_polluted_concept_refs.py` 通过。
- 2026-06-22 同步后验证：`python3 scripts/check_relations_integrity.py --vault wiki` 通过；`audit_missing_evidence_sources.py --vault wiki --pretty` 为 0；`audit_missing_concepts.py --vault wiki --pretty` 为 0；关键 ingest/RAG 脚本 `py_compile` 通过。
- 金融 Agent / daily workflow 回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_judge tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_paths tests.test_question_router -v`，20/20 通过。
- 金融 Agent 编译：`python3 -m py_compile intelligence/workflows/daily_review.py intelligence/cli.py intelligence/services/question_router.py intelligence/services/research_judge.py intelligence/workflows/daily_agent.py scripts/research_judge.py` 通过。
- P1 生命周期回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_judge tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_paths tests.test_question_router tests.test_logic_lifecycle -v`，25/25 通过；`python3 -m py_compile intelligence/services/logic_lifecycle.py intelligence/workflows/daily_agent.py intelligence/services/research_judge.py scripts/research_judge.py intelligence/workflows/daily_review.py intelligence/cli.py intelligence/services/question_router.py` 通过。
- P2 研究任务队列回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_judge tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_paths tests.test_question_router tests.test_logic_lifecycle tests.test_research_queue -v`，31/31 通过；`python3 -m py_compile intelligence/services/research_queue.py intelligence/services/logic_lifecycle.py intelligence/workflows/daily_agent.py intelligence/services/research_judge.py scripts/research_judge.py intelligence/workflows/daily_review.py intelligence/cli.py intelligence/services/question_router.py` 通过。
- P3 盘面验证回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_research_judge tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_paths tests.test_question_router tests.test_logic_lifecycle tests.test_research_queue tests.test_market_validation -v`，36/36 通过；`python3 -m py_compile intelligence/services/market_validation.py intelligence/services/research_queue.py intelligence/services/logic_lifecycle.py intelligence/workflows/daily_agent.py intelligence/services/research_judge.py scripts/research_judge.py intelligence/workflows/daily_review.py intelligence/cli.py intelligence/services/question_router.py` 通过。
- P3.5 snapshot 契约验证：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_market_snapshot_contract tests.test_paths tests.test_daily_agent tests.test_daily_review_agent_entry tests.test_cockpit_agent_entry tests.test_daily_ops_ledger -v`，19/19 通过。
- 自然语言路由验证：`python3 -m intelligence.cli route '帮我跑今天的全量复盘'` 已命中 `daily_review`，命令模板为 `python3 -m intelligence.cli daily --date {date} --kb-wiki {knowledge_wiki}`。
- Daily dry-run 验证：`python3 -m intelligence.cli daily --date 2026-06-11 --skip-sync --kb-wiki '/Users/a77/Desktop/c c/知识库/wiki' --dry-run` 已显示 `agent-daily` 和 `render_cockpit.py --knowledge-root`。

### 下一步优先级

#### P0：先确认日常入口真的跑通

- 合并 PR #88。
- 在另一台有 DuckDB 的 Mac 上用自然语言或总入口跑一次真实全量复盘。
- 验证输出中必须包含：
  - `theme-candidates` 
  - `daily-agent.json/md/html` 
  - 复盘工作台里的 `Agent 简报` 
  - 驾驶舱每日复盘卡片里的 `Agent 简报` 

这一步只是接线验收，不是最终能力。

#### P1：做生命周期快照，而不是继续堆证据卡（已完成第一版）

新增 `logic_lifecycle` 层，每天为每个题材/逻辑保存一条状态快照。

最小字段：

- `date` 
- `logic_id / concept` 
- `lifecycle_stage` 
- `stage_change` 
- `research_judge_status` 
- `evidence_layers` 
- `missing_layers` 
- `market_strength` 
- `strong_stock_count` 
- `limit_stock_count` 
- `turnover_delta` 
- `semantic_old_material_hit` 
- `top_related_stocks` 
- `next_action` 
- `reason` 

第一版生命周期状态：

- `新出现`：过去窗口没出现，今天第一次进候选。
- `旧逻辑唤醒`：知识库/向量有旧材料，今天被盘面重新触发。
- `升温验证`：连续出现，强势股或成交/涨停扩散增强。
- `加速定价`：L2/L3 证据较完整，盘面强度快速提升。
- `高位分歧`：热度仍在，但回撤/分歧/衰减开始出现。
- `衰退观察`：盘面热度下降，证据无新增，扩散变弱。
- `证伪退出`：关键事实不成立，或盘面验证长期失败。

验收：

- `agent-daily` 不只显示“证据裁判”，还要显示“生命周期阶段”和“相比上一日变化”。2026-06-11 样例已生成：光刻胶/存储芯片/先进封装为“升温验证”，小金属/磷化工为“旧逻辑唤醒”，金属铜/金属钴进入数据缺口。

#### P2：把 daily agent 升级成今日研究任务队列（已完成第一版）

基于生命周期快照和 research_judge，输出四组任务：

- 今日该做 IMA：盘面触发或旧逻辑唤醒，但 L1/L2 叙事材料不足。
- 今日该找公告/调研/订单：有 L2 或 IMA 候选硬事实，但缺 L3 官方验证。
- 今日等盘面验证：L2/L3 较完整，但 L4 不足。
- 今日降级/观察：盘面衰退、证据无新增、生命周期转弱。

验收：

- 用户打开 `Agent 简报` 后，不需要理解内部字段，也能知道今天该做什么。2026-06-11 样例已生成：电子化学品、氟化工进入“今日该做 IMA”；光刻胶、小金属、磷化工、存储芯片、先进封装进入“今日该找公告/调研/订单”，因为已有 L1 旧材料，不重复提示做 IMA；金属铜/金属钴仍留在数据缺口。

#### P3：补 L4 盘面验证层（已完成短期版）

短期：

- 先读 `theme-candidates`、daily exports 和已有强势股映射。
- 计算简化版市场强度：
  - 是否连续出现。
  - 强势股数量变化。
  - 涨停/大涨扩散。
  - 优先级变化。
  - 是否从孤立个股变成产业链共振。

中期：

- 另一台 Mac 导出稳定：
  - `market_snapshot/YYYY-MM-DD.json` 
  - `market_snapshot/latest.json` 
  - `market_snapshot/meta.json` 
- 本 Mac 只读 snapshot，避免依赖本地 DuckDB。
- 当前已完成契约与校验器：
  - `MARKET_SNAPSHOT_DIR` 可指定同步目录。
  - `docs/market_snapshot_contract.md` 记录最小 JSON 字段。
  - `python3 scripts/check_market_snapshot_contract.py --root market_snapshot --date 2026-06-11 --pretty` 可返回 `PASS / WARN / FAIL`。

验收：

- Agent 能明确说“这是证据升级”还是“只是盘面脉冲”。2026-06-11 样例已生成：光刻胶、小金属、电子化学品、氟化工、磷化工、存储芯片、先进封装均出现 `盘面验证=强验证`；金属铜/金属钴为 `中等验证` 但仍因概念/证据缺口留在数据缺口。无历史样本的题材不会再显示从 0 到当前值的虚假边际变化，而是显示“当前首次进入观察窗口”。

#### P4：做历史有效性评估

当生命周期快照积累后，再计算历史成绩单：

- CAR(0,5)、CAR(0,20)
- 相对强度变化
- 胜率
- 半衰期
- 最大回撤
- 强势股扩散率
- 叙事-事实偏离

验收：

- Agent 能回答“这类逻辑历史上有没有赚钱效应，通常活多久，什么时候容易衰退”。

#### P5：再决定补哪些 concept deepdive

Concept DeepDive 的优先级服从生命周期判断：

- 优先补：盘面唤醒 + 缺 L1/L2/L3 + 可能继续升温的题材。
- 暂缓补：只有图谱缺口但没有盘面触发的题材。
- 不补：污染词、别名、占位信号、已衰退逻辑。

DeepDive 不再是默认动作，而是生命周期系统发出的研究任务之一。

## 一句话结论

当前目标不是先做一个“会聊天的金融 Agent”，而是先做一个可审计、可降级、可恢复的金融研究操作系统。成熟 Agent 的关键不是更会说，而是知道自己在哪些证据层上可以判断，在哪些地方必须停下来补证据。

## 总体架构

```text
另一台 Mac
  DuckDB / market_feature_store
  -> market_snapshot/YYYY-MM-DD.json

本 Mac
  知识库 ingest / relations / 向量索引
  -> kb_snapshot/meta.json
  -> vector_index/meta.json

金融 Agent
  Agent Doctor
  -> Market Snapshot Consumer
  -> Evidence Judge
  -> Theme Research Judge
  -> Research Queue
```

## P0：先把地基修稳

### 1. 路径与环境统一

目标：所有核心脚本不再硬编码 `/Users/lbq`、`/Users/a77`。

建议统一环境变量：

- `KB_VAULT`：知识库 wiki 根目录。
- `FINANCE_WS`：金融 repo 根目录。
- `KNOWLEDGE_WIKI`：兼容旧入口，可指向 `KB_VAULT`。
- `MARKET_SNAPSHOT_DIR`：另一台 Mac 导出的市场快照目录。
- `VECTOR_INDEX_DIR`：本 Mac 向量索引目录。

验收：

- 在本 Mac 跑核心 KB 脚本，不需要改源码路径。
- 在无本地 DuckDB 的情况下，知识库相关 agent 能正常运行。
- 核心质量门脚本不再默认读 `/Users/lbq/...`。

### 2. 明确双 Mac 数据边界

目标：本 Mac 不依赖本地 DuckDB 也能运行知识库 Agent。

另一台 Mac 定期导出：

- `market_snapshot/YYYY-MM-DD.json` 
- `market_snapshot/latest.json` 
- `market_snapshot/meta.json` 

市场快照最少包含：

- 交易日期。
- 市场阶段。
- 成交额、涨跌家数、涨停/跌停。
- 容量前三行业。
- 双红题材。
- 涨停热度题材。
- 连板/晋级题材。
- 新高方向。
- 强势股与题材映射。

验收：

- 本 Mac 只读快照即可生成“盘面触发候选”。
- 快照过期时，Agent 必须明确提示“市场数据滞后”，不能冒充最新。

### 3. Agent Doctor

目标：任何分析前先体检。

检查项：

- 当前 repo 路径与分支。
- `KB_VAULT` / `FINANCE_WS` / `MARKET_SNAPSHOT_DIR` 是否存在。
- `relations/*.json` 是否可解析。
- `relations/meta.json` 条数与实际是否一致。
- evidence 是否能追溯到 source / raw / batch manifest。
- 向量索引是否存在、更新时间、覆盖范围。
- 市场快照最新日期。
- 当前机器是否有 DuckDB；如果没有，是否能降级到 snapshot 模式。

输出：

- `PASS`：可完整运行。
- `WARN`：可运行但部分模块降级。
- `FAIL`：不应继续分析。

验收：

- 每次金融 Agent 分析前都能输出可用模块、降级模块、阻塞原因。

## P1：把知识库变成可审计证据系统

### 4. 修 relations meta 和 integrity

目标：`meta.json` 条数、更新时间可信。

重点：

- 修 `_entry_count`，覆盖 `entity_exposures.entities.*.concepts`。
- integrity 检查不能只看 `exposures[]`，也要看 `concepts{}`。
- 区分错误和告警：JSON 解析失败、schema 错误是 FAIL；source 缺失可以先 WARN，但要进修复队列。

验收：

- `entity_exposures`、`evidence_index`、`concept_graph` 条数与实际一致。
- 缺 concept、缺 source、孤儿 evidence、无 trace evidence 都能被查出。

### 5. Evidence Source 可追溯修复

目标：减少 evidence 指向不存在 source page 的情况。

缺失 source 分三类：

- 真实缺页：应该补 `wiki/sources/*.md`。
- 机器批次 source：应该补 batch manifest 或 machine source page。
- 审计/baseline 虚拟 source：应该转成可追溯 manifest，不要伪装成普通 source。

验收：

- 每条 evidence 至少能追到以下之一：source page、raw file、batch summary、machine source manifest。

### 6. 证据升级门禁代码化

目标：不靠 Agent 记忆规则。

判级规则：

- 只有 L0/L1：只能输出题材观察或产业链映射。
- 有 L2 无 L3：能力栈候选，待事实验证。
- 有 L2 + L3：重点验证。
- 有 L2 + L3 + L4：可讨论催化共振或认知差。
- 只有 L4：盘面异动待解释，不能倒推产业逻辑。

输出状态：

- `观察` 
- `能力栈候选` 
- `重点验证` 
- `已有事实验证` 
- `降级观察` 
- `移出队列` 

验收：

- 输入公司/题材，返回状态、可升级原因、不可升级原因、缺失证据层。

## P2：把 ingest 和向量化工程化

### 7. Ingest 状态机

目标：PDF、raw full、disclosure、baseline 不再混流程。

建议状态：

```text
raw_saved
-> extracted
-> classified
-> graph_written
-> entity_candidate
-> reviewed
-> applied
-> indexed
```

每批 ingest 记录：

- 输入文件。
- 抽取结果。
- 分类结果。
- graph_only / exposure_only 数量。
- curated_research 数量。
- hard_delta 数量。
- 真正写入实体数。
- 是否触发 baseline。
- 是否进入向量索引。
- 下一批游标。

验收：

- 每批 ingest 都有状态文件、摘要、错误、下一步动作。

### 8. 向量索引分层

目标：向量库不把不同证据等级混成一锅粥。

建议分层索引：

- `raw/source`：原始材料。
- `concept`：概念页。
- `entity`：实体页。
- `evidence_item`：短证据。
- `report_context`：研报级上下文。
- `disclosure`：公告/监管/官方证据。

每条向量 metadata 必须包含：

- `source_type` 
- `evidence_layer` 
- `fact_hardness` 
- `update_type` 
- `source` 
- `raw_path` 
- `entity` 
- `concept` 
- `created_at` 
- `indexed_at` 

验收：

- 检索结果能按证据层过滤。
- Agent 不能把 L1 检索结果直接写成 L3 事实。

### 9. RAG 引用规范

目标：Agent 回答必须能落回证据。

要求：

- 每个关键判断带 `evidence_id/source/raw_path/layer`。
- 没证据的判断只能标“待验证”。
- 公司弹性判断必须说明财务科目映射。

验收：

- 输出中没有证据的公司结论不会被写成确定判断。

## P3：金融 Agent 本体

### 10. Market Snapshot Consumer

目标：本 Mac 消费另一台 Mac 导出的市场快照。

职责：

- 读取最新快照。
- 判断快照是否过期。
- 生成盘面触发候选。
- 标记触发来源：双红、涨停热度、连板、新高、容量行业。

验收：

- 快照缺失或过期时，Agent 明确降级。
- 输出只叫“盘面触发候选”，不直接叫“投资结论”。

### 11. Theme Research Judge

目标：把题材候选翻译成研究假设。

输出结构：

- 表层事件。
- 已发生需求变化。
- 产业链传导。
- 财务科目映射。
- 受益链条。
- 公司弹性候选。
- 市场误分类。
- 本地证据命中。
- 验证/削弱/证伪路径。
- 研究队列。

验收：

- 每个候选都有“为什么还不能升级”的字段。
- 每个公司候选都有证据层和缺口。

### 12. Research Queue

目标：让 Agent 产出下一步工作，而不是只产出报告。

队列类型：

- 补 baseline。
- 找公告。
- 找互动易。
- 找订单/合同/中标。
- 补 source page。
- 补 raw trace。
- 补 L3。
- 降级 graph_only。
- 移出队列。

验收：

- 每次分析后自动生成 P0/P1/P2 研究任务。

## P4：回归与评测

### 13. 黄金样本集

建议首批题材：

- CPO
- 先进封装
- 固态电池
- 人形机器人
- 商业航天
- MLCC
- 算力 PCB
- 液冷
- 低空经济
- 光刻胶

每个题材保存：

- 应命中的核心公司。
- 应降级公司。
- 应排除公司。
- 证据缺口。
- 期望输出结构。

验收：

- Agent 改动后跑 regression，不允许把 L1 公司误升核心。

### 14. 反幻觉评测

专测三类错误：

- 把研报判断当事实。
- 把盘面热度当产业逻辑。
- 把 baseline 当短期催化。

验收：

- 这些错误能被门禁拦住。

### 15. 双 Mac 同步协议

目标：另一台 Mac 负责 market artifact，本 Mac 负责 KB artifact。

建议产物：

```text
market_snapshot/YYYY-MM-DD.json
market_snapshot/latest.json
market_snapshot/meta.json

kb_snapshot/meta.json
relations/meta.json
vector_index/meta.json
agent_doctor_report.json
```

验收：

- 任意一台机器缺数据，Agent 能明确降级，不静默失败。

## 关于“编排层”的判断

我认为应该做编排层，但要先做薄编排，不要一开始做复杂平台。

### 为什么需要编排层

现在的问题不是单个脚本能力不够，而是流程之间缺少统一调度和状态承接：

- ingest、relations、向量化、market snapshot、evidence judge、research queue 是连续链条。
- 当前很多规则散落在 `AGENTS.md`、`SKILL.md`、workflow 文档和脚本里。
- 失败时缺少统一的恢复点。
- 双 Mac 分工后，更需要一个地方判断“本机能做什么、缺什么、该降级到哪里”。

所以编排层的价值不是“更高级”，而是把流程从人工记忆变成机器可执行。

### 编排层不应该做什么

第一阶段不要做：

- 大而全的 Web 平台。
- 复杂 UI。
- 多 Agent 自主乱跑。
- 自动交易或买卖建议。
- 无人工审核的批量写库。
- 把所有脚本重写成一个大框架。

### 第一阶段编排层应该做什么

建议只做一个轻量 CLI：

```bash
python3 scripts/agent_orchestrator.py doctor
python3 scripts/agent_orchestrator.py ingest-status
python3 scripts/agent_orchestrator.py index-status
python3 scripts/agent_orchestrator.py market-status
python3 scripts/agent_orchestrator.py theme-candidates --date latest
python3 scripts/agent_orchestrator.py judge-theme --term CPO
python3 scripts/agent_orchestrator.py research-queue --term CPO
```

它负责：

- 读取环境变量。
- 检查本机能力。
- 调用已有脚本。
- 汇总状态。
- 生成 JSON/Markdown artifact。
- 遇到缺数据时降级，不直接失败。

### 建议的编排层状态模型

```text
preflight
-> data_available
-> candidate_generated
-> evidence_judged
-> hypothesis_written
-> research_queue_created
-> indexed
```

每一步都要有：

- 输入 artifact。
- 输出 artifact。
- 状态：PASS / WARN / FAIL / SKIP。
- 错误原因。
- 下一步建议。

### 编排层的位置

建议先放在知识库 repo，或者新建一个很薄的 `agent_ops/` 目录。

原因：

- 本 Mac 是知识库与向量化主机。
- Agent 的核心判断依赖 evidence / relations / vector index。
- 市场数据只是 snapshot 输入，不应该让本 Mac 强依赖 DuckDB。

但要保留对金融 repo 的只读调用能力。

### 编排层的最小验收标准

第一版只要做到：

- `doctor` 能判断当前机器可用能力。
- 能读市场 snapshot，而不是强依赖本地 DuckDB。
- 能跑 relations integrity。
- 能跑向量索引状态检查。
- 能对一个题材输出证据层判定和研究队列。
- 全部输出落到 `wiki/raw/agent-runs/YYYY-MM-DD/` 或 `outputs/`。

做到这里，就已经值得继续扩展。

## 推荐执行顺序

1. 修路径与环境变量。
2. 做 Agent Doctor。
3. 修 relations meta / integrity。
4. 设计 market snapshot schema。
5. 做 Market Snapshot Consumer。
6. 做 Evidence Judge。
7. 做 Ingest 状态机。
8. 做向量索引分层。
9. 做 Theme Research Judge。
10. 做 Research Queue。
11. 做黄金样本 regression。

## 当前优先级

下一步建议从 P0-1 开始：统一路径与环境变量。

理由：

- 它影响所有脚本。
- 它会立刻减少跨 Mac、跨用户路径的失败。
- 它是 Agent Doctor、编排层、向量化和 snapshot 消费的共同前置条件。

## 2026-06-21 进展：IMA Deep Dive 与 Concept Ingest 分工

### 结论

已确认不让 IMA 输出第 16 节机器可读 schema。

原因：

- 10000 字以内压缩版提示词会把 IMA 推成摘要模式，Deep Dive 质量明显下降。
- IMA 更适合做 1-15 节深度抽取：题材定锚、产业链、公司映射、边际变化、风险反证、Theme Radar。
- 第 16 节本质是入库 contract，应该由本地桥接脚本根据 1-15 节生成，便于做 schema 校验、概念去噪、alias 判断和人工审核。

### 已落地

- 生产提示词恢复为旧口径 1-15 节：
  `/Users/a77/Desktop/IMA Deep Dive Theme Radar 数据抽取提示词 生产版-旧口径.md` 
- 桥接脚本改为本地生成 ingest contract：
  `/Users/a77/Desktop/c c/知识库/scripts/build_ima_concept_ingest_queue.py` 
- 新增输出：
  `*.ima-ingest-contract.jsonl` 
- 旧提示词标题清洗已修复：
  `玻璃基板题材 Deep Dive + Theme Radar 数据抽取报告` -> `玻璃基板` 

### 玻璃基板样本验证

对优质样本 `/Users/a77/Desktop/glass_substrate_deep_dive.md` 运行桥接后：

- pool items：110
- 本地 ingest contract records：179
- concept queue candidates：27
- queue 类型：
  - concept_alias：2
  - concept_delta_candidate：3
  - new_concept_candidate：22

相比旧桥接的 56 个候选，已过滤掉“上游：设备”“包括……”“需满足……”等描述性污染项。

### 验证

- `python3 -m py_compile scripts/build_ima_concept_ingest_queue.py scripts/build_theme_information_pool.py tests/test_ima_concept_ingest_queue.py` 
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` 
- 当前知识库测试：33/33 OK

## 2026-06-21 进展：IMA Source Manifest / Legacy Source Backfill

### 当前跑通状态

以 `/Users/a77/Desktop/glass_substrate_deep_dive.md` 为样本，已跑通：

```text
IMA markdown
-> 本地 ingest contract jsonl
-> concept ingest queue
-> IMA source manifest note
```

新增能力：

- `build_ima_concept_ingest_queue.py --write-source-note` 
  - 为当前 IMA 原文生成 `wiki/sources/*.md` source manifest。
- `build_ima_concept_ingest_queue.py --source-name "..."` 
  - 可把 raw 文件精确登记成 evidence_index 里缺失的 source 名。
- `materialize_missing_source_stubs.py --include-untraced` 
  - 可 dry-run / apply 生成 `legacy-untraced` stub，专门处理找不到 raw 的历史 source。

### 玻璃基板样本输出

- source manifest：
  `/Users/a77/Desktop/c c/知识库/wiki/sources/IMA Deep Dive: 玻璃基板.md` 
- bridge artifacts：
  `/Users/a77/Desktop/c c/知识库/wiki/raw/theme-radar/backfill-smoke/glass_substrate_deep_dive.ima-concept-ingest-queue.json` 
  `/Users/a77/Desktop/c c/知识库/wiki/raw/theme-radar/backfill-smoke/glass_substrate_deep_dive.ima-concept-ingest-queue.md` 
  `/Users/a77/Desktop/c c/知识库/wiki/raw/theme-radar/backfill-smoke/glass_substrate_deep_dive.ima-ingest-contract.jsonl` 

### 历史 21 个 missing source 的解决策略

优先级：

1. 若能找到原始 IMA / DeepDive markdown，用 raw 文件回填真实 source manifest。
2. 若找不到 raw，只生成 `legacy-untraced` source stub，降低结构性缺失，但不提升证据可信度。

raw 文件回填命令模板：

```bash
python3 scripts/build_ima_concept_ingest_queue.py "/path/to/raw.md" \
  --vault "/Users/a77/Desktop/c c/知识库/wiki" \
  --source-name "IMA canonical: 人形机器人" \
  --write-source-note
```

无 raw 文件时的 legacy stub dry-run：

```bash
python3 scripts/materialize_missing_source_stubs.py \
  --vault "/Users/a77/Desktop/c c/知识库/wiki" \
  --include-untraced
```

真正 apply 前需要人工确认，因为这会让 missing source 结构上归零，但这些 source 仍是低追溯质量。

### 验证

- 当前知识库测试：36/36 OK

## 2026-06-21 进展：IMA 个股未入库批处理落地

### 已完成

- 已补 raw 回填：`已入库/已在wiki_sources_20260621` 中 289 个历史 IMA 个股原文已复制到：
  `/Users/a77/Desktop/c c/知识库/wiki/raw/ima-stock/ingested/2026-06-21/已在wiki_sources/` 
- 新增批处理脚本：
  `/Users/a77/Desktop/c c/知识库/scripts/ima_stock_ingest_batch.py` 
- 新增测试：
  `/Users/a77/Desktop/c c/知识库/tests/test_ima_stock_ingest_batch.py` 
- `未入库` 目录已清空。

### 本次处理结果

- 标准个股卡入库成功：452 个
- source 已存在的重复卡：11 个，已归档到 `已入库/ima_stock_duplicate_source_20260621/` 
- 非个股路线材料：17 个，已移动到 `待人工确认/ima_stock_review_20260621/` 
- 新增 raw 归档：
  - 个股成功入库原文：`wiki/raw/ima-stock/ingested/2026-06-21/` 
  - duplicate source 原文：`wiki/raw/ima-stock/duplicates/2026-06-21/` 

### 批处理报告

- dry-run 报告：`wiki/raw/ima-stock/batch-runs/ima-stock-ingest-batch-20260621-201332.md` 
- 10 个样本 apply：`wiki/raw/ima-stock/batch-runs/ima-stock-ingest-batch-20260621-201347.md` 
- 全量 apply：`wiki/raw/ima-stock/batch-runs/ima-stock-ingest-batch-20260621-201522.md` 
- 失败重跑修复：`wiki/raw/ima-stock/batch-runs/ima-stock-ingest-batch-20260621-201850.md` 
- duplicate 归档：`wiki/raw/ima-stock/batch-runs/ima-stock-ingest-batch-20260621-201941.md` 
- review 移出：`wiki/raw/ima-stock/batch-runs/ima-stock-ingest-batch-20260621-201955.md` 

### 验证

- `python3 -m unittest discover -s tests`：45/45 OK
- `python3 scripts/check_relations_integrity.py --vault "/Users/a77/Desktop/c c/知识库/wiki" --repair-meta`：0 错误 / 2 告警
- `python3 scripts/agent_doctor.py --kb-vault "/Users/a77/Desktop/c c/知识库/wiki" --pretty`：WARN
  - meta mismatch 已清除
  - 仍剩旧问题：446 个 missing concept、21 个 missing source

### 下一步

1. 对 `待人工确认/ima_stock_review_20260621` 的 17 个非个股材料分流：DeepDive 走 concept bridge，海外对标图谱另建 source/raw 规则。
2. 对 21 个 legacy missing source：优先找 raw 回填 source manifest；找不到再创建 `legacy-untraced` stub。
3. 对 446 个 missing concept：继续走 concept 归一、别名判断、概念页生成、图谱登记流水线。

## 2026-06-21 进展：IMA 个股质量修复

### 已完成

- 对新入库 454 个 IMA 个股卡做反向审计：
  - source 覆盖：454/454
  - raw 覆盖：454/454
  - evidence 覆盖：454/454
- 修复 `600760_中航沈飞_逻辑卡_20260614`：
  - 原因：原始 themes 是“歼-35放量、军贸出口、十五五装备采购”等未归一概念，单卡脚本未匹配到现有 concepts，导致 source/entity 已入库但 evidence_index 未新增。
  - 处理：使用现有概念 `航空制造`、`军工` 补充 IMA evidence，不新增未归一概念。
- 对 14 个低结构原始卡补充 `wiki/sources` frontmatter：
  - 已补 company/ticker/source_updated/quality flags。
  - 原始 raw 不改，保留 IMA 导出原貌。
  - score < 70 的卡已标记 `review_required: true`。

### 报告

- `wiki/raw/ima-stock/audits/low-quality-stock-source-frontmatter-backfill-20260621.md` 
- `wiki/raw/ima-stock/audits/600760-evidence-backfill-20260621.json` 

### 验证

- `python3 -m unittest discover -s tests`：45/45 OK
- `python3 scripts/check_relations_integrity.py --vault "/Users/a77/Desktop/c c/知识库/wiki" --repair-meta`：0 错误 / 2 告警
- `python3 scripts/agent_doctor.py --kb-vault "/Users/a77/Desktop/c c/知识库/wiki" --pretty`：WARN
  - 仍剩旧问题：446 个 missing concept、21 个 missing source

## 2026-06-21 进展：Daily Ops Ledger 编排层 v0

### 已完成

- 在金融 repo 新增只读台账脚本：
  `/Users/a77/Desktop/c c/金融/scripts/build_daily_ops_ledger.py` 
- 新增设计规范：
  `/Users/a77/Desktop/c c/金融/docs/superpowers/specs/2026-06-21-daily-ops-ledger-design.md` 
- 新增实现计划：
  `/Users/a77/Desktop/c c/金融/docs/superpowers/plans/2026-06-21-daily-ops-ledger.md` 
- 新增测试：
  `/Users/a77/Desktop/c c/金融/tests/test_daily_ops_ledger.py` 

### 运行命令

```bash
cd "/Users/a77/Desktop/c c/金融"
python3 scripts/build_daily_ops_ledger.py \
  --date 2026-06-21 \
  --knowledge-wiki "/Users/a77/Desktop/c c/知识库/wiki"
```

### 输出

- JSON：`/Users/a77/Desktop/c c/金融/market_feature_store/exports/2026-06-21-daily-ops-ledger.json` 
- Markdown：`/Users/a77/Desktop/c c/金融/market_feature_store/exports/2026-06-21-daily-ops-ledger.md` 

### 本次扫描结果

- 总状态：WARN
- 全量复盘：缺 10 个当日输出。注意 2026-06-21 是周日，缺当日市场复盘不一定异常。
- 晨汇：当日 `wiki/briefings/2026-06-21*.md` 为 0。
- IMA 个股：当天 raw MD 743 个；`未入库` 0；`待人工确认` 0。
- relations 面：核心文件齐全，包括 evidence/entity/concept/theme/catalyst/mention。
- 结构债：
  - missing concepts：446
  - missing evidence sources：21
  - 未覆盖 IMA 的股票实体：468

### 下一步

1. 把台账日期从自然日改成“最近交易日优先”，避免周末误报全量复盘缺失。
2. 给晚间卖方研报和晨汇补固定 inbox 文件夹约定，台账才能判断“待入库/已入库/待复核”。
3. 新增 logic-market matching：读取 theme-candidates，与已有 concept/entity evidence 做匹配，输出“旧逻辑唤醒/新逻辑/噪音”队列。

## 2026-06-21 进展：Path Registry + Question Router v1

### 已完成

- 新增路径注册表：
  `/Users/a77/Desktop/c c/金融/intelligence/routing/path_registry.json` 
- 新增注册表加载器：
  `/Users/a77/Desktop/c c/金融/intelligence/services/path_registry.py` 
- 新增问题路由器：
  `/Users/a77/Desktop/c c/金融/intelligence/services/question_router.py` 
- 新增 route workflow：
  `/Users/a77/Desktop/c c/金融/intelligence/workflows/route.py` 
- 新增 CLI：
  `python3 -m intelligence.cli route "用户问题"` 
- 新增测试：
  `/Users/a77/Desktop/c c/金融/tests/test_question_router.py` 
- 新增设计规范：
  `/Users/a77/Desktop/c c/金融/docs/superpowers/specs/2026-06-21-path-registry-question-router-design.md` 
- 新增实现计划：
  `/Users/a77/Desktop/c c/金融/docs/superpowers/plans/2026-06-21-path-registry-question-router.md` 

### 当前路由类型

- `known_workflow`：明确命中固定路径，例如 deep-dive、front-map、全量复盘、IMA 入库。
- `planner_analysis`：组合分析，例如“为什么动”“旧逻辑唤醒吗”“有没有弹性”。
- `data_gap`：缺 source/raw/concept/IMA 覆盖，先跑 Daily Ops Ledger，再分流补库。
- `clarification_needed`：问题为空或过于模糊，需要追问。

### 样例

```bash
python3 -m intelligence.cli route "玻璃基板 deep-dive" --json
python3 -m intelligence.cli route "玻璃基板今天为什么动，是旧逻辑唤醒吗"
python3 -m intelligence.cli route "446 个 missing concept 和 21 个 missing source 怎么补" --json
```

### 验证

- `python3 -m unittest discover -s tests`：11/11 OK
- `python3 -m py_compile intelligence/services/path_registry.py intelligence/services/question_router.py intelligence/workflows/route.py intelligence/cli.py`：OK

### 下一步

1. 实现 `logic_market_match` 执行器，把 `theme-candidates` 与 `concept_graph/entity_exposures/evidence_index` 对齐。
2. 给 route 增加 `--date` 和 `--kb-wiki`，让计划能绑定具体数据状态。
3. 把 route 接到 `agent` 前置：agent 先看 route decision，再决定调用哪些工具。

## 2026-06-21 进展：Logic Market Match v0

### 已完成

- 新增逻辑-盘面匹配服务：
  `/Users/a77/Desktop/c c/金融/intelligence/services/logic_market_match.py` 
- 新增 workflow：
  `/Users/a77/Desktop/c c/金融/intelligence/workflows/logic_match.py` 
- 新增 CLI：
  `python3 -m intelligence.cli logic-match "题材" --date YYYY-MM-DD` 
- 新增测试：
  `/Users/a77/Desktop/c c/金融/tests/test_logic_market_match.py` 
- 新增设计规范：
  `/Users/a77/Desktop/c c/金融/docs/superpowers/specs/2026-06-21-logic-market-match-design.md` 
- 新增实现计划：
  `/Users/a77/Desktop/c c/金融/docs/superpowers/plans/2026-06-21-logic-market-match.md` 
- 更新 Path Registry：
  `logic_market_match` 现在有命令模板 `python3 -m intelligence.cli logic-match {query} --date {date}` 

### 当前能力

输入日期和题材，读取：

- `market_feature_store/exports/<date>-theme-candidates.json` 
- `wiki/relations/concept_graph.json` 
- `wiki/relations/entity_exposures.json` 
- `wiki/relations/evidence_index.json` 
- `wiki/sources/*.md` 

输出分类：

- `old_logic_wakeup` 
- `new_logic_candidate` 
- `data_gap` 
- `noise_or_unconfirmed` 

### 样例

```bash
cd "/Users/a77/Desktop/c c/金融"
python3 -m intelligence.cli logic-match "光刻胶" \
  --date 2026-06-11 \
  --kb-wiki "/Users/a77/Desktop/c c/知识库/wiki"
```

样例输出：

- JSON：`/Users/a77/Desktop/c c/金融/market_feature_store/exports/2026-06-11-logic-match-光刻胶.json` 
- Markdown：`/Users/a77/Desktop/c c/金融/market_feature_store/exports/2026-06-11-logic-match-光刻胶.md` 

样例结论：

- `光刻胶` 在 2026-06-11 被判定为 `old_logic_wakeup` 
- 盘面命中：是
- concept 命中：是
- entity exposure 命中：12
- evidence 命中：1
- source trace：OK

### 验证

- `python3 -m unittest discover -s tests`：14/14 OK
- `python3 -m py_compile intelligence/services/logic_market_match.py intelligence/workflows/logic_match.py intelligence/services/question_router.py intelligence/cli.py`：OK

### 下一步

1. 批量跑最近几个交易日的 `theme-candidates`，生成“优先补数据队列”。
2. 把 `logic-match` 接到 `route` 输出：route 命中 `run_logic_match` 时可直接生成下一条命令。
3. 增强分类：把 source trace 缺失、evidence 过期、entity exposure 低置信分别计入评分。

## 2026-06-21 进展：Logic Match Batch Gap Queue

### 已完成

- 新增批量匹配能力：
  `python3 -m intelligence.cli logic-match-batch` 
- 支持参数：
  - `--dates 2026-06-09,2026-06-10` 
  - `--recent 3` 
  - `--top-per-date 8` 
  - `--out-json` 
  - `--out-md` 
- Path Registry 已新增：
  `logic_match_batch` 
- Router 的 `data_gap` 路径现在会包含：
  1. `daily_ops_ledger` 
  2. `logic_match_batch` 
  3. `source_backfill` 
  4. `concept_backfill` 
  5. `ima_stock_ingest` 

### 样例命令

```bash
cd "/Users/a77/Desktop/c c/金融"
python3 -m intelligence.cli logic-match-batch \
  --recent 3 \
  --top-per-date 8 \
  --kb-wiki "/Users/a77/Desktop/c c/知识库/wiki" \
  --out-json market_feature_store/exports/logic-match-batch-recent3-top8-20260621.json \
  --out-md market_feature_store/exports/logic-match-batch-recent3-top8-20260621.md
```

### 样例结果

- 扫描日期：2026-06-09、2026-06-10、2026-06-11
- 扫描候选：24 个
- `old_logic_wakeup`：20 个
- `data_gap`：4 个
- gap queue：6 条

高优先级缺口：

1. `连板未映射`：missing concept/entity/evidence
2. `金属钴`：missing concept/entity/evidence
3. `金属铜`：missing concept/evidence
4. `PPE树脂`：missing concept/evidence
5. `人形机器人`：old logic wakeup，但 missing source trace
6. `先进封装`：old logic wakeup，但 missing source trace

### 输出

- `/Users/a77/Desktop/c c/金融/market_feature_store/exports/logic-match-batch-recent3-top8-20260621.json` 
- `/Users/a77/Desktop/c c/金融/market_feature_store/exports/logic-match-batch-recent3-top8-20260621.md` 

### 下一步

1. 先人工看 gap queue，判断 `连板未映射` 是真实概念缺口还是市场分类噪音。
2. 对 `金属钴/金属铜/PPE树脂` 做 concept/evidence 优先补齐判断。
3. 对 `人形机器人/先进封装` 优先查 source trace 缺口，补 source/raw manifest。
