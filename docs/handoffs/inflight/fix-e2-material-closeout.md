# E2 材料整合在途

## 这个分支做什么 / 当前状态
整合 P5/P6：单份正文、逐句来源回执；无 D6/P7 结论。
树 `/Users/a77/fwp-wt-e2-material-closeout`。代码尖 `32eefcfc6`（= `766164f7b` forward-merge `gitea/main@3c70af64d`
+ 跨 PR 语义修复），本文档提交在其上，PR head 以 `git rev-parse gitea/fix/e2-material-closeout` 为准。
PR #770 open、WIP，**领先 main 26、落后 0，merge-tree clean**；合并与切 8792 等用户。8792 现跑 `945c04bd7fdd`（09-21 04:47Z 切），本轮未碰。

## 2026-09-21 前向合并 main + 跨 PR 修复（session finance-workspace-private-7d，非原作者）
- `766164f7b`：合 main（132 提交，含 #819 研究求证意识 / #815 fincalc / #818 注册表）。三处冲突两边保留：
  `_run_judge` 先放 main 的 `JUDGE_MODE_OFF` 早退，再接 P6 的材料两段审 + `_run_judge_once`；数量门「历史句跳过 +
  绑定短日期遮罩」叠加；`lessons_learned.md` 两段都留。
- `32eefcfc6`：合并后 `test_prior_evidence.py` 实际 loop 用例红——`binding_source_errors` 在 material_only 下拒绝一切
  evidence_hash，而 #819 零读复核正是把原件校验过的旧工具原子注入证据池让模型绑定。修在缝上：新增 keyword-only
  `frozen_prior_hashes`，只放行「池内且属于恢复集合」的 hash；`validate_episode_finish` 从 `context.prior_evidence` 取，
  `verify_episode_outcome` 改从 durable 的 `model_input(source=prior_tool_evidence)` 事件读回（`prior_evidence.restored_prior_hashes`）。
  两条规则都没放松（本轮新读仍拒、不在池内仍拒），回归四向 + loop 用例补结构校验断言。
- 教训：前向合并后红的是**对方 PR** 的测试文件；旧演练 `9b4c2310b` 只跑了冲突文件的测试，没跑 #819 的。

## 本轮真实病因（已修，8f6e6eaa→d8ba0fb2）
作者进修复轮只知道缺哪个输出、不知道上次为什么被拒，于是原样重发。
- 格式错误带坐标；尾次拒收 resume 补发（repair_last_rejection）；判官逐句理由过桥（RepairGoal.rejected_claim_notes）；
  矛盾有合法形状（contradicted）；修复轮重述冻结成稿格式（claim_finish_format 单一构造点）。
- 真实 run_20260917_011813_492269：坐标错误→回灌→同错再犯→补发→repair_goal 1689 字（finish_format 与开场逐字节同）→completed；
  同形状在 c6151407 / 8f6e6eaa 死于 invalid_repair_finish。

## QC 修正（04d3c397）
`unreported_invalid_finish` 首版只认 steering_invalid_finish 为送达、把任何 invalid_action 都当终局拒收：
max 档三轮修复第二轮会把第一轮已送达的那条再发；计划错误会套进 invalid_finish 文案。
改为按 `code`（rejection_code，六个 finish 驳回点都写）置位、清零集合加入 repair_last_rejection；emit 点零改动。
回归：纯函数七向 + 两条 loop 连续两次 resume；修前六条全红。

## 已验证（全部对 32eefcfc6 干净树，2026-09-21）
python 12289P/0F/87S/2xfail（`20260921T052130Z-32eefcfc.json`，`check_test_receipt.py --expect-revision 32eefcfc… --base-drift-max 5` 9/9 可采信）；
ruff 过；`run_frontend_gate.py` 六步（install/lint/typecheck/test/build/test:e2e）全 0，`complete/identity_stable` true、`dirty` false；
registry 五条 exit 0（树父目录 `/Users/a77`，同级仓可见）。日志与收据：`~/.finance-runtime/e2-material-closeout-32eefcfc/`。
上一版 df74042c 的读数（11586P、107P 前端、34P/2S e2e）见 `~/.finance-runtime/e2-material-closeout-df74042c/`。

## 未验证 / 已知边界
- 判官「invalid tool call」21 次探针 run 出现 3 次（8636a2a2/c6151407/d8ba0fb2，均 correlated_judge），用户空手；「带未复核标识发出」属用户级策略。
- 十例 unbound_numbers 红（判官 bound_material+空锚点）未重抽；十例与自然会话结论仍挂在 8f6e6eaa，本轮未重跑真实会话。
- `rejected_claim_indexes` 无写入点→拒句修复分支从未生效；刻意没动。
- hrl:650（修复轮调工具）invalid_action 无 code，与 agent_episode 不对称；终局停机，留作已知。
- 缺项陈述仍是同源模型判断；T2→T3、跨轮五格、local_only 全读取面未验。

## 下一步
1. 判官无效 tool call：先固定成回归，再谈交付策略。
2. rejected_claim_indexes 死字段：接上并重跑证据，或删。
3. 合并/生产切换等用户确认；合前再 `git fetch gitea && git merge-tree --write-tree gitea/main <尖>` 复探。
   合入后按 `acceptance-workflow.md` §4 切 8792（当前 945c04bd7fdd，含 #819；P6 的 binding.claims 合同上线前先跑一次 grounded 探针 + 材料题）。

## 踩过的坑
工件根 `~/.finance-runtime/e2-material-closeout-{8f6e6eaa,d8ba0fb2,df74042c}/`。不设 FWP_TEST_RECEIPT_DIR，按时间戳收据取数，别读 latest.json。
探针 sidecar 的 episode 状态落在主树 `state/episodes/`（episode_store 按 FINANCE_WS 解析，gitignored）。
版本史 `docs/handoffs/2026-09-16-e2-claim-rendering-and-judge-receipts.md`、`2026-09-17-repair-round-feedback-and-contradiction-shape.md`。
