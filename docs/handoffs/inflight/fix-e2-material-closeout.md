# E2 材料整合在途

## 这个分支做什么 / 当前状态
整合 P5/P6：单份正文、逐句来源回执；无 D6/P7 结论。
树 `/Users/a77/fwp-wt-e2-material-closeout`。代码尖 `df74042c`（= `04d3c397` QC 修正 + forward-merge `gitea/main@18859d37`），
已推 gitea（远端=本地实读）；本文档提交在其上，PR head 以 `git rev-parse gitea/fix/e2-material-closeout` 为准。
PR #770 open、WIP，未合 main、未部署；合并与切 8792 等用户。8826 已停；8792 实读 healthy/`ce009718`/clean，本轮未碰。

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

## 已验证（全部对 df74042c 干净树）
python 11586P/0F/83S（`20260917T021523Z-df74042c.json`，`check_test_receipt.py --expect-revision df74042c --base-drift-max 5` 8/8 可采信）；
ruff 过；前端 lint/typecheck/107P/build（产物与已跟踪文件一致）；E2E 34P/2S（`WORKBENCH_PYTHON` 指 venv-workbench）；
registry check/parseability/views/path-literals 全过。日志与收据指针：`~/.finance-runtime/e2-material-closeout-df74042c/`。

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

## 踩过的坑
工件根 `~/.finance-runtime/e2-material-closeout-{8f6e6eaa,d8ba0fb2,df74042c}/`。不设 FWP_TEST_RECEIPT_DIR，按时间戳收据取数，别读 latest.json。
探针 sidecar 的 episode 状态落在主树 `state/episodes/`（episode_store 按 FINANCE_WS 解析，gitignored）。
版本史 `docs/handoffs/2026-09-16-e2-claim-rendering-and-judge-receipts.md`、`2026-09-17-repair-round-feedback-and-contradiction-shape.md`。
