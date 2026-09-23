# 2026-09-22 口径越界 lint（#850 / #854）合入与 K3 无判官再验路线工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#59（main 顶端有干净四叶收据）。姊妹：#75（独立 QC 批）出第二方结论；#76（自然质量验收批）负责有界真实会话；#77（文档批）处理 #849 / #840 两张只读复核文档 PR。本单含**两处用户决策**：合并顺序、lint 接入点的运行时改动授权。

> **09-23 状态订正**：本单 #850 / #854 的合入与设计文档已完成，判据缺陷亦由 #872 修复；INDEX 已随 #858 合入，质检口径随 #879 合入。下面背景、步骤与未勾选验收表是原始派单快照，不代表仍待执行；逐项证据见 `docs/verification/2026-09-22-claim-scope-merge-65/README.md`，最新补验与清理边界见 `docs/handoffs/2026-09-23-claim-scope-final-state.md`。#75 K3 事后审与运行时接入仍未完成，后者需单独授权。

## 背景与动机

- 2026-09-21 K3 写手 + 无判官（#830 已合）首跑两题暴露**四类口径越界**：库内日期冒充最近交易日、5 板块说成全部归属、成交额推资金流入、材料已给亿元仍称缺单位。生产随后回滚：09-22 22:15 `/api/health` 实读 `source_revision=adcda94b5e40`、`agent_runtime.model=glm-5.3-flash`、树干净；`ASK_SEMANTIC_JUDGE` 未设即 `judge_mode=llm`。
- #849（`docs/k3-acceptance-0922`，只读复核）结论：旧证据 104 件哈希全过、两旧 run 确为 K3 且终稿判官 0 调用，但四类越界**不接受**；关判官是用户已定目标，质量差不撤目标，改修日期/范围/量纲合同。
- PR **#850**（`fix/answer-claim-scope-0922` @ `1cf35f516`，base main）：新增 `intelligence/services/answer_claim_scope.py` + `scripts/check_answer_claims.py`，把四类越界做成不依赖模型的检测；CLI 吃冻结 run 的 `run.json / continuous-episode.json / answer.md`，命中退出 1。两次首跑与人工复核一致（材料题 1 条、行情题 3 条）；真实语料压出并修回三缺陷（「单位」多义误报、20 字距漏报、否定句共享关键词误报）。定向 31P（干净树 `ef9ff3b4`）；全量 12542P 是脏树基线收据，不能当 head 全量。
- PR **#854**（`fix/claim-scope-hardening-0922` @ `5f5ce2d11`，**base = `fix/answer-claim-scope-0922`**，9 提交）：三条 fail-open 闭合（限定词绑定到断言前 12 字窗、证据按注册表判定、降级退 2 不退 0），撤回一条被实测推翻的误报判断；1347 个历史 run 回测修掉 30 条误报，命中 96→66 真命中不丢；差分测试钉 `_check_stale_mislabel` 与 claim-scope 的管辖边界；接入点已定位 `intelligence/services/ask.py` 约 4782 行的接缝，**未动运行时**。定向 50P（干净树 `50ffda955`），未跑全量。
- **已定的形态决策**：判据是关键词检出器，换说法可绕，这是已知边界不是缺陷；`calendar_evidence` 只能人工 `--calendar-evidence-source` 声明不从 episode 推；CLI 不 import `finance_query`（用模块内常量 + 测试锁注册表漂移）。接入走仓里既有先例：先 advisory 观察在场率，再升格进修订轮，再谈硬拦。

## 目标

1. 用户决定合并顺序并执行：**推荐 A**——先合 #850（`--expect-head 1cf35f516`），再把 #854 base 改到 main 后合（或直接合，Gitea 会自动 retarget）；B——把 #854 retarget 到 main 一次合入（#850 随之进入）。无论 A/B，四叶收据都在 #854 head 上取（它是超集），另加 #850 head 的定向收据。
2. 两张 PR 去 `WIP:`（若有）、描述补「已知边界」段；#75 独立 QC 结论后用户确认合入，`--record` 留痕。
3. 接入点设计落 `docs/superpowers/specs/<日期>-claim-scope-runtime-integration-design.md`：接缝位置、三档（advisory → 修订轮 → 硬拦）各自的开关名、验收判据「接入后重放冻结 run 的裁决必须与 CLI 逐字段一致，映射错了会静默变绿」。**运行时改动本身不在本单**，需用户单独授权后另立单。
4. K3 再验路线（不执行 live，只把条件写清给 #76）：先离线钉四类反例 + 合法正例进 `check_answer_claims` 的回归夹具；固定题（09-21 两道首跑原题）、固定版本（含 #850/#854 的 main SHA）、预算（首发 1 / 重发 0）；失败即回滚的判据 = CLI 退出码 1 或 judge-off 下四类任一命中。

## 非目标（写死认领）

- ❌ 不修四条原始缺陷本身（写手行为）；本轮只保证再犯必被抓。
- ❌ 不给出召回率：宽探针只覆盖想得到的写法，无人工标注集谈不了率。
- ❌ 不接入 Episode 实时作答路径（需运行时改动授权，另立单）。
- ❌ 不部署 K3、不翻 `ASK_SEMANTIC_JUDGE`；生产保持回滚态直到 #76 的有界 live 过。
- ❌ 不合 #849 / #840（文档，归 #77）；#849 标题 `WIP:` 前缀由 #77 处理。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `intelligence/services/answer_claim_scope.py`、`scripts/check_answer_claims.py`、`intelligence/tests/test_answer_claim_scope.py`、`tests/test_check_answer_claims.py`（分支版） | 规则集、CLI、回归夹具（原句护栏，勿改写成抽象样例） |
| `docs/verification/2026-09-22-claim-scope-hardening/`、`docs/verification/2026-09-22-claim-scope-backtest/`（#854 分支） | 三条闭合探针、1347 run 回测、`evidence/gates.json` |
| 分支 `fix/claim-scope-hardening-0922`：`docs/handoffs/inflight/fix-claim-scope-hardening-0922.md`「接入点设计」节 | 接缝与验收判据原文 |
| 分支 `docs/k3-acceptance-0922`：`docs/handoffs/inflight/docs-k3-acceptance-0922.md` | 四类越界的定义与「不撤目标」决策 |
| `~/.finance-runtime/reviews/k3-acceptance-20260922/` | 只读复核原件 |
| `intelligence/services/ask.py` 约 4782 行 | 接缝；仓内先例（advisory 观察在场率）在同文件搜 `advisory` |
| `~/.finance-runtime/test-receipts/20260922T115539Z-1cf35f51.json`、`…112523Z-a2c8d1f9.json` | #850 定向干净收据；脏树全量收据（只作旁证） |

## 步骤

1. 开工三连；`gitea_pr.py show 850 / 854` 取 head；确认两棵树 clean。
2. 顺序决策贴用户（A/B 各一句代价：A 两次合并两份记录；B 一次但 #850 的独立身份消失）。
3. #854 head 前向到最新 main（若 base 改 main），`merge-tree` 探冲突；低负载四叶；#850 head 定向 `intelligence/tests/test_answer_claim_scope.py tests/test_check_answer_claims.py`。
4. 交 #75 独立 QC；拿结论。
5. 用户确认后按所选顺序 `gitea_pr.py merge … --yes --expect-head … --record …`。
6. 写接入点设计文档（目标 3），只文档不改运行时。
7. 四类反例 + 正例进回归夹具（若 #854 已含则核对即可），给 #76 一张「K3 再验条件卡」。
8. INDEX #65 行；inflight ≤3K。

## 验收

- [ ] #854 head 四叶收据 revision == head；#850 head 定向收据干净。
- [ ] 阳性对照：把 `answer_claim_scope` 的日期规则整段注释掉，对 09-21 行情题冻结 run 跑 CLI 必须从退出 1 变为 0；还原后回 1。
- [ ] 两个冻结 run（材料题 1 条、行情题 3 条）在合入后 main 上 CLI 判定逐字段不变。
- [ ] 合并记录含授权原话与出处；顺序决策记录在 PR 评论。
- [ ] 接入点设计文档含三档开关名与「重放一致」验收句。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- 运行时（`ask.py`）一行不改；接入需单独授权与单独工单。
- 不发真实模型请求（本单零 live）；不动生产 8792。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；`ruff format` 不要顺手格式化没碰的旧代码（仓里只强制 `ruff-check`）。
- 不绕 pre-commit；不写明文密钥。
