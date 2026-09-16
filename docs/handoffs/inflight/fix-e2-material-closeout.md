# E2 材料整合在途

## 这个分支做什么 / 当前状态
整合 P5/P6：单份正文、逐句来源回执；无 D6/P7 结论。
树 `/Users/a77/fwp-wt-e2-material-closeout`，HEAD `d8ba0fb2`（…c6151407→8f6e6eaa→75f44a97→d8ba0fb2）。
PR #770 open（已推 75f44a97，d8ba0fb2 待推）。未合 main、未部署。独立审查已关闭。
8826 已停；8792 由其他线部署，声称前重读 health。

## 本轮真实病因（已修）
作者进修复轮只知道缺哪个输出、不知道上次为什么被拒，于是原样重发。
证据：工件根 `repair-feedback-evidence.json`、`live-repair-evidence.json`。
- 格式错误带坐标：哪个 output 第几条、切几句。
- 尾次拒收过桥：resume 补发一次（repair_last_rejection），不多花调用。
- 判官逐句理由过桥：RepairGoal.rejected_claim_notes（原句+理由、去私有坐标），与 unsupported_claims 分开。
- 矛盾有合法形状：contradicted（supported=false + 非空 anchor_indexes）。
- （d8ba0fb2）修复轮重述冻结成稿形状：claim_finish_format() 单一构造点；不传时消息不变。

## 已验证
8f6e6eaa：全仓 11316P/83S（`20260916T162320Z-8f6e6eaa.json`）；前端 lint/typecheck/107P/build、E2E 34P/2S
（须 `WORKBENCH_PYTHON=…venv-workbench/bin/python`）；十例 9/10；三次自然会话 3/3 completed、judge passed、
0 unavailable，答案 20%/20%/12.5%，缺项陈述逐句核验过。
d8ba0fb2：全仓 11318P/83S（`20260916T171208Z-d8ba0fb2.json` 可采信）；ruff 过。
真实 run_20260917_011813_492269：坐标错误→回灌→同错再犯→repair_last_rejection→repair_goal 1689 字（含重述形状）
→`completed/repair_model_finish`；同形状在 c6151407、8f6e6eaa 死于 invalid_repair_finish。
该 run 最终仍 partial：修复稿写「按行业常识…偏低」，判官无效 tool call→unavailable→只剩退化文。

## 未验证 / 已知边界
- 判官无效 tool call 时用户什么都拿不到；改成「带未复核标识发出」属用户级策略，未自决。
- d8ba0fb2 未重跑前端/十例（不碰 webapp、判官侧）。
- 十例 unbound_numbers 这次红：判官写 bound_material 却给空 anchor_indexes→整份丢弃。未重抽。
- `rejected_claim_indexes` 无人写→`unsupported_claims` 恒空→拒句修复分支从未生效；刻意没动。
- 缺项陈述仍是同源模型判断；T2→T3、跨轮五格、local_only 全读取面未验。

## 下一步
1. 判官无效 tool call：先把失败形状固定成回归，再谈交付策略。
2. rejected_claim_indexes 死字段：接上并重跑证据，或删。
3. 推 gitea 刷新 PR #770；合并/生产切换另等确认。

## 踩过的坑
工件根 `~/.finance-runtime/e2-material-closeout-{8f6e6eaa,d8ba0fb2}/`；probe 打印的 `~/.local/share/...` 不适用。
不设 FWP_TEST_RECEIPT_DIR，不取共享 latest.json。版本史见 `docs/handoffs/2026-09-16-e2-claim-rendering-and-judge-receipts.md`
与 `2026-09-17-repair-round-feedback-and-contradiction-shape.md`。
