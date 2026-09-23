# 2026-09-22 财务链（#835 / #855 / 混比补检 / 变异量具）四叶重验与合入决策工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#59（main 顶端干净收据）。姊妹：#67（研究尾单联合候选，财务线 `d82cb16b5` 已被 squash 进候选 `65fde6171`——两单**互斥路径**，见「决策」）；#75（独立 QC）；#76（R6 四题自然验收）。

## 背景与动机

- PR **#835**（`fix/financial-forward-0921` @ `d82cb16b5`，base 是已合入 main 的 `fix/research-tail-integration-0921`）：财务比例与交付合同前向整合，保主干发布/材料保护。作者标 WIP，等独立验收。09-18 R6 发布套件 baseline 在并发下 180 秒超时，现场无记录。
- PR **#855**（`fix/8792-boundary-ttl-baseline-0922` @ `132afc0b1`，**base = #835 分支**）：两道新门——`track_contract.conclusion_ttl_conflicts()`（同一结论两个有效期）与 `financial_claim_checks.comparison_baseline_gaps()` / `episode_semantic_verifier.comparison_baseline_unsupported()`（触发条件依赖本轮没取到的历史基线，走补数不走删句）。23 条回归题面逐字取自 R3 封存原件；突变 9/9 全红；封存 8 份答卷干跑 R3 两份命中、其余零误报。**关键事实**：main 上 adapter 只把收据塞进 artifact，`_track_public_delivery / append_contract_stub / missing_contract_elements` 全不存在——跟踪契约在 main 上「只记账不执法」，整套执法层至今只活在 R4→R6→#835 这条未合链上。全量 13332P 是**脏树**收据（`…135307Z-1068b42f.json`，绑前一提交），head `132afc0b1` 无干净收据。
- 本地 `fix/financial-comparison-0922`（`5d50cd864`，base `d82cb16b5`，未推）：补 #835 漏检的「2026 中报净现比 0.132，较 2025 全年 1.009 走弱」跨期别混比，`_relative_ratio_comparison_mismatch()`，契约达成 10/18→16/18，撤保护六处逐条见红。
- gitea `fix/mutation-timeout-evidence-0922`（`94eddad18`，代码 `e9e3361a`，**已推无 PR**）：变异量具超时留证（输出直落盘、卡 45 秒转储线程栈、`start_new_session + killpg`、缺 JUnit 记 `executed=None`）；干净收据 `20260922T111226Z-e9e3361a.json` 12534P，前端 110P / E2E 34P/2S / registry 五项 0，撤保护 11 组各有具名红。归因已做实：publication 套件里一条单测在 fork 真实知识库 RAG 检索子进程（`kb_rag.py` 三个调用点，开关 `ask_types.py` `use_wiki_rag` 默认 True），采样 88.4% 在 `selectors.select`；八条变异补齐 **7 杀 1 存活**（`sse-drains-between-read-commit`），#835 不能继承旧 SHA 的「八组全绿」。
- **已定的形态决策**：#855 不拆一半上 main（main 没有执法层，拆过去只多一个没人读的字段）；缺基线走补数不走删句（V8 删除权合同）；不改 `parse_valid_until` 取值规则；变异量具只改评审工具不碰产品代码，180 秒帽不动。

## 决策（先贴用户）

1. **路径互斥**：财务线要么走本单（#835 → #855 → 混比补检 依序合 main），要么走 #67（已 squash 进联合候选 `65fde6171`，与历史线、runtime 线一起合）。同一改动不能两条路都走。推荐：若 #67 候选四叶已绿且用户接受「`contract_receipt` 同一调用点同时承载财务契约与 `history_intent`」的口径，走 #67 并把 #835/#855 关闭留接替指针；否则走本单。
2. **执法层进生产**：合入 #835 链 = 跟踪契约从「只记账」变「执法」，公开交付会开始被 `_track_public_delivery` 披露、缺基线会触发补数计划。这是产品行为变化，需要用户一句「同意执法层上线」。
3. 存活变异 `sse-drains-between-read-commit`：合前必须修（推荐）还是带披露合。

## 目标

1. 三个候选各一套干净四叶收据：#835 head、#855 head、`fix/financial-comparison-0922` head（推送后）；`--expect-revision` 全等。
2. 给 `fix/mutation-timeout-evidence-0922` 开 PR（作者当时因本机只有 GitHub `gh` 没开；用 `python3 scripts/gitea_pr.py open`），base main，描述含归因结论与「不翻旧案」声明。
3. 存活变异处置：修（补一条能红的测试）或带披露；处置写进 #835 描述。
4. 决策 1 选本单路径时：#75 独立 QC → 用户确认 → 依序 `merge --record`，每合一张就在 main tip 复跑 python 叶；选 #67 路径时：`gitea_pr.py close 835/855 --pointer-file` 指向候选 PR。
5. R6 四题自然验收条件卡交 #76（固定 SHA、frozen 数据根、首发 1 / 重发 0、K3 写手 + 剥 `temperature` shim 声明）。

## 非目标（写死认领）

- ❌ 不归因 09-18 那次超时（现场不存在，量具只保证下次可归因）。
- ❌ 不改 `_observations` 按契约主体反查只匹配到表头的既有洞（两道已上线财务门返回空是「判不了」不是「没问题」）；单独立单，本单只在 PR 描述登记。
- ❌ 不抬 180 秒帽、不改变异定义、不改还原校验。
- ❌ 不跑真实模型（归 #76）。
- ❌ 不同时走两条路径。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/8792-ttl-baseline-20260922/`（`dry-run-sealed*.log`、`mutation-check.log`、`full-suite-r2.log/.exit`） | #855 突变、干跑、全量日志（无干净 head 收据） |
| gitea `fix/8792-boundary-ttl-baseline-0922:docs/handoffs/inflight/fix-8792-boundary-ttl-baseline-0922.md` | 「为什么不拆一半上 main」的查实 |
| `~/.finance-runtime/reviews/financial-comparison-20260922/`（`probe-before/after.json`） | 混比漏检实测与修后 |
| `~/.finance-runtime/reviews/mutation-timeout-evidence-20260922/`、`~/.finance-runtime/reviews/mutation-timeout-attribution-20260922/` | 量具留证与归因采样 |
| `~/.finance-runtime/test-receipts/20260922T111226Z-e9e3361a.json`、`…131417Z-94eddad1.json` | 量具分支干净全量收据 |
| `intelligence/services/continuous_turn_adapter.py`（#835 版 vs main） | 执法层差异：`_track_public_delivery` 等三符号 |
| `scripts/review_probes/run_extraction_mutations.py`、`scripts/review_probes/research_tail_union_mutations.json` | 变异 runner 与定义 |
| `~/.finance-runtime/reviews/research-tail-union-resume-20260922/README.md` | #67 候选把财务线 squash 进去时解的 8 文件 13 处 |

## 步骤

1. 开工三连；把「决策」三问贴用户，等答复期间做 2–4。
2. `git push gitea fix/financial-comparison-0922`；为量具分支开 PR。
3. 三候选各自独占干净检出，低负载四叶（python 叶带 `--basetemp` 树外目录；#58 未合前 `--ignore=scripts/archive` 并记录）。
4. 存活变异：先复跑该单条变异确认仍存活，再修；新测试要在该变异下红、还原后绿。
5. 按决策路径执行合入或关闭；每一步 `--record` / `--pointer-file`。
6. INDEX #66 行；inflight ≤3K；关闭的 PR 留接替指针。

## 验收

- [ ] 三候选 head 各有干净四叶收据，`check_test_receipt.py --expect-revision <head>` exit 0。
- [ ] 量具 PR 存在且描述含「7 杀 1 存活」与归因采样比例。
- [ ] 阳性对照：把 `comparison_baseline_gaps()` 的主体回退关掉，R3 positive-persistence 封存答卷干跑必须从「基线缺口」变为无命中；还原后回命中。
- [ ] 决策三问各有用户原话记录；所选路径的合并记录或接替指针齐。
- [ ] 若合入：main tip `/api/health` 未变（本单不部署），`_track_public_delivery` 在 main 上可 grep 到。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推；关闭 PR 必留接替指针。
- 不动 #835 冻结 head 去追加提交（那个 SHA 是审阅对象）；新改动在自己的分支上。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；变异跑完 sha256 校验源码还原。
- 不跑真实模型、不动 8792。
- 不写明文密钥。
