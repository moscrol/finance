# 2026-09-22 研究答案保留：空指针交付门推送、PR 与阻断口径决策工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
姊妹：#76（自然质量验收批，负责「真实自然纠错」样本）、#75（独立 QC）。本单含一处用户决策：`marker_coverage` 从只观测升为阻断吗。

## 背景与动机

- 「研究答案保留」线（分支 `feat/research-answer-preservation`，HEAD `d064dee1c`，已推、无 PR）：同任务安全分析不因格式/质量问题整段删除；保留、准入、核验、交付分账。离线返修 `cdcbc5a8` 工程全绿（11769P + 前端 115P + E2E 34P/2S + 11 撤保护）。
- 09-22 有界 live 一题（首发 1 / 重发 0 / 续问 0，`run_20260922_191550_067475`，102 秒 / 6 工具 / 77 证据），四项分账：**保稿未触发**（模型首次 finish 即被接收，`retained_candidate_count=0`）、**诊断未触发 + 1 处漏报**（`endpoint_not_path` 类人工核出、`evidence_claim_findings=0`）、**自然纠错未触发**（`repair_attempts=0`，没有批注就没有纠错机会）、**金融质量不通过**。未触发不计通过。
- 金融质量四类问题里最严重的是**交付空指针**：模型在自由文本里写完 1500+ 字完整答案，却把结构化 finish 的 draft 填成一句「见正文：……」；运行时按 draft 交付，用户收到 154 字、`report.modules=0`；77 条证据全绑定，结构核验与语义判官双双 passed；该题型必需三输出只有 `counterpoint`，`direct_assessment / evidence_boundary` 缺，系统标 `marker_coverage=incomplete` 但它是 `observation_only`，不可阻断。其余三类：「两段先回调」与 D10 原数据不符（后续 5 日均为正）、选择口径未交代（85 个双红板块只报两个未说排序依据）、模型自造实体 `899050.BK`（只进 gaps 未进公开答案）。
- 修法已提交：本地 `fix/research-empty-delivery-0922`（HEAD `d68b8f512`，1 提交，**未推**）：新增 `intelligence/services/public_delivery_gate.py`（确定性纯函数，无模型无 IO），接在 Engine A 唯一交付收口点 `_complete_continuous_turn` 的 `complete_report` 之前。**双钥匙**：钥匙 1 形态——正文是悬空指针自称内容在别处（见正文 / 如上所述）；钥匙 2 覆盖——确有必需输出没进正文，复用 `task_fulfillment` 同一张词表。单独命中钥匙 2 一律放行（那正是「措辞不同但内容完整」的形状）；正文长度不作钥匙；落点走既有 `answer_status`（missing / partial），不新增终态；缺口模板整篇豁免。实现拍红两次固化成护栏：体量下限会误伤「2026Q2 单季营收 375.75 亿元」类短而完整答案；绝对下限 24 字会误伤 16 字研究项目夹具。全量 12520P / 1F（`test_rag_worker` 暖 worker 超时时序题，单跑 47P）。
- **已定的形态决策**：不删稿（原文 + 批注 + 原会话修订）；判官 passed 不能盖过机械发现；不用正文长度做钥匙；不新增终态类型。

## 决策（先贴用户）

`task_fulfillment.evaluate_marker_coverage` 的 `marker_coverage=incomplete` 现在是 `observation_only`。选项：A 保持只观测，靠新交付门的双钥匙拦「指针 + 缺覆盖」的组合；B 把 `incomplete` 单独升为阻断（partial），会把「措辞不同但内容完整」也拦下，误伤面要先量。推荐 A，并在 #76 的下一次 live 后按 `marker_coverage` 分布再议 B。

## 目标

1. 推送 `fix/research-empty-delivery-0922`，开 PR（base main），描述引用 `run_20260922_191550_067475` 的现场与双钥匙判据；前向 main；低负载四叶；1F 按 #59 口径四读数。
2. 用**真实现场**做回归夹具：把该 run 的 `answer.md` / `continuous-episode.json` 冻结副本（脱敏后）作为夹具，不手写措辞；新交付门对它必须判 partial/missing 且保留全文正文。
3. 阳性对照与反例：短而完整答案（`2026Q2 单季营收 375.75 亿元`）与 16 字研究项目夹具必须放行；把钥匙 1 词表清空后现场夹具必须放行（证明双钥匙不是单钥匙）。
4. 另立三张占位单登记其余三类金融质量问题（回调判定、选择口径未交代、自造实体），写进 INDEX 续表，不在本单修。
5. #75 独立 QC；用户确认后 `merge --record`。给 #76 一张「可稳定触发拒收的题型或注入点」需求卡：正常路径不进修复机制，再抽盲样本价值低。

## 非目标（写死认领）

- ❌ 不改判官、不改 `evidence_claim_findings` 的漏报（`endpoint_not_path`），登记占位。
- ❌ 不修 `test_rag_worker` 时序红。
- ❌ 不跑新的 live（#76）；不重发旧样本。
- ❌ 不合 `feat/research-answer-preservation` 的 20 个提交（它的工程收据绑 `cdcbc5a8`，不移签到当前 revision；是否单独开 PR由用户定）。
- ❌ 不改 `RAG_BGE_MODEL` / 权重问题（#62）。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/research-preservation-natural-live-20260922/audit.json`、`closure.json`、`episodes/`、`frozen-data-manifest.json`、`launch-config-amendment.json` | 四项分账结论件、现场 run、数据冻结、启动偏差声明 |
| `git show fix/research-empty-delivery-0922 --stat` 与提交正文 | 双钥匙判据与两次拍红 |
| `intelligence/services/public_delivery_gate.py`、`task_fulfillment.py::evaluate_marker_coverage`、`continuous_turn_adapter.py::_complete_continuous_turn` | 门、词表、接缝 |
| 分支 `feat/research-answer-preservation`：`docs/handoffs/inflight/feat-research-answer-preservation.md` | 四类金融质量问题原文、已核实为真的部分 |
| `~/.finance-runtime/reviews/research-draft-claim-repair-20260919/final/` | 离线返修 748 件封存（对照，不重跑） |

## 步骤

1. 开工三连；确认 `~/fwp-wt-research-empty-delivery-0922` 无人在写（会话 mtime）且 clean。
2. 推送、开 PR；决策 A/B 贴用户。
3. 现场夹具落 `intelligence/tests/fixtures/...`（脱敏：用户 id、路径），测试文件名含 `live_products`，夹具**不许改措辞**。
4. 前向 main；低负载四叶；1F 四读数。
5. 三张占位单写入 INDEX 续表（编号接本批之后）。
6. 交 #75；确认后合入；INDEX #70 行；inflight ≤3K。

## 验收

- [ ] PR head 四叶收据 revision == head。
- [ ] 现场夹具用例：新门判 `answer_status ∈ {partial, missing}`，正文全文保留、`report.modules` 不为 0 的替代正文被交付或缺口模板被豁免（按实现二选一写死）。
- [ ] 两个短答案反例放行；钥匙 1 词表清空 → 现场夹具放行（阳性对照）。
- [ ] 决策 A/B 有用户原话；若 B，误伤面读数（历史 run 上 `marker_coverage=incomplete` 占比）先落盘。
- [ ] 三张占位单在 INDEX 可见。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- 不跑真实模型；不动生产 users 根；夹具脱敏。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 工程绿 / 离线机制启用 ≠ 自然金融质量通过，收据不移绑文档 tip。
- 不写明文密钥。
