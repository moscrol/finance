# E2 材料整合在途

## 这个分支做什么
整合 P5/P6：单份正文、逐句来源回执、真实交付；无 D6/P7 结论。

## 当前状态
树 `/Users/a77/fwp-wt-e2-material-closeout`，HEAD `8f6e6eaa`（链 …a4cefcd5→8636a2a2→cc3c9bfe→c6151407→8f6e6eaa）。
PR #770 open，head 仍 a4cefcd5（新四提交未推）。未合 main、未部署。独立审查已关闭，不记通过。
8826 已停；8792 由其他线部署，声称前须重读 health。

## 本轮定位到的真实病因（已修）
作者进修复轮只知道「缺哪个输出」，不知道「上次为什么被拒」，于是原样重发。
证据：工件根下 `repair-feedback-evidence.json`（c6151407 run：invalid_action→repair_goal→同错重犯）。
- 格式病因带坐标：一句一条错误写明哪个 output 的第几条、切成几句。
- 尾次拒收过桥：loop 只回灌首次失败；resume 补发一次（source=repair_last_rejection），不多花调用。
- 判官逐句理由过桥：RepairGoal 新增 rejected_claim_notes（原句+理由、去私有坐标），与策略信号 unsupported_claims 分开，不动修复形状判据。
- 矛盾有合法形状：support_kind=contradicted（supported=false + 非空 anchor_indexes）；此前只能写非法组合、整份报告被丢。

## 已验证（8f6e6eaa，干净树）
全仓 11316P/0F/0E/83S/2xfail，收据 `20260916T162320Z-8f6e6eaa.json` 校验可采信；ruff 通过。
前端 lint/typecheck/107P/build；E2E 34P/2S（须 `WORKBENCH_PYTHON=...venv-workbench/bin/python`，此树无 .venv）。
固定十例 9/10：contradicted_absence 首次通过（判官真返回 contradicted）。
三次自然会话 3/3 completed、judge passed、0 unavailable/0 degraded，答案 20%/20%/12.5%，缺项陈述逐句核验通过。

## 未验证 / 已知边界
- 本轮三次自然会话没触发修复轮 → 修复反馈链只有离线回归 + 修前证据，未在真实修复轮验过。
- 十例的 unbound_numbers 这次红：判官写 bound_material 却给空 anchor_indexes→整份丢弃→unavailable。未重抽、未放宽解析。
- `rejected_claim_indexes` 全仓无人写→`unsupported_claims` 恒空→`classify_repair_failure` 拒句分支从未生效；本轮刻意没动（会改修复路由）。
- 缺项陈述仍是同源模型判断；正式 T2→T3、跨轮五格、local_only 全读取面未验。

## 下一步
1. 造一次真实修复轮（先让作者写坏），验 repair_last_rejection / rejected_claim_notes 在线上确实到达。
2. 决定 rejected_claim_indexes 死字段：要么接上并重跑修复路由证据，要么删。
3. 推 gitea 刷新 PR #770；合并/生产切换另等用户确认，合并候选重跑全部门禁。

## 踩过的坑
工件根 `~/.finance-runtime/e2-material-closeout-8f6e6eaa/`（gate/frontend/e2e/controls/live-u1,u2,n/sidecar）。
probe 打印的 `~/.local/share/...` 路径不适用；不设 FWP_TEST_RECEIPT_DIR，不取共享 latest.json。
完整版本史见 `docs/handoffs/2026-09-16-e2-claim-rendering-and-judge-receipts.md`。
