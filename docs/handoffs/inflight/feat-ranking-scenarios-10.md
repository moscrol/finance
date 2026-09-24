# feat/ranking-scenarios-10 · 能力升级 10 号单（排序与情景）· 2026-09-09

## 这个分支做什么

多对象排序题此前落 theme_analysis / news_impact，名单加形容词就能过门。本分支加 `intelligence/services/ranking_contract.py`（沿 track_contract 表达层惯例，零新数据源）：固定表头公司矩阵 + 财务传导 + 竞争解释（≥2+区分变量）+ 改判条件表（↑/↓）+ 下一步；两条引擎注入；缺件以 `ranking_*` id 走 contract_rewrite；`apply_scenario` 按箭头机械再排序（↑=上移一位）；改判条件登记 `checkpoints.jsonl`、`foresight` 渲染——输出成为 07 回检 / 09 续研的输入。

提交 `444e520e`（基 gitea/main 5eb24515），已推 Gitea，**未合 main、未切生产**。合同/冻结题/进度/范围外：`docs/superpowers/plans/2026-09-09-capability-upgrade/` 下 10-*、progress/10.md、blocked/10.md；验证 `docs/verification/2026-09-09-ticket10-ranking-scenarios.md`（附录存档验收脚本）。

## 决策与被否方案

- 表达层契约 / 否 改 route_table 加题型——契约按词面注入，非排序题零改动；Q3 路由成 news_impact 也拿到契约。
- 机械再排序 / 否 模型自由重排——反向验证要求「只换文案不能改推导」，机械基线让 Q6 可程序判定。
- 缺件并入 `missing_outputs` / 否 进 verifier issues——#224 放行门吃 issue 前缀。
- 改判条件进既有 `checkpoints.jsonl` / 否 新台账——新增台账须先登记，07/foresight 已消费它。

## 当前状态（四项）

已实现 ✅（44 新单测绿；ruff 0；层门禁无新增）｜已进默认入口 ✅（双引擎注入，hybrid 真实 run `run_20260910_011137_336558` 四件全交付、缺件=0）｜真实验收 **部分**（3/6 题：Q1 完整对照——候选四件全交付 vs 基线散文全缺；Q2/Q6 基线 clean 读数；Q2 候选+Q3/Q4/Q5 双臂**卡死在上游故障**，见下）｜生产生效 ❌（按合同不合 main）

## 批跑状态（接手先看 · 09-10 13:20 更新）

- **Cockpit 57244 深题会打冷却（blocked/10.md 新增一行）**：q2 候选臂 turn1 于 13:10 clean 完（390.8s、1528 字、finish=completed、判官过），随即 sol 429 `model_cooldown reset_seconds≈8401`（≈15:34 解冷）、luna 同账号池用量限额同步受限、terra 连接超时——**三模型同时不可聊到 15:3x**。driver pid 46965 读 reset_seconds 睡到解冷自动续跑 q2 cand turn2（Q6 追问）→ q3/q4/q5 双臂，预计全部跑完要到深夜。
- 已完成（clean 可作证据）：q1 双臂、q2 基线 turn1+turn2、q2 候选 turn1。剩余：q2 候选 turn2、q3/q4/q5 双臂。
- 打脏作废的 run 都有收据可循（model_error>0 即重试）：q2 base turn1 一次（10:34 TimeoutError 打水漂）、turn2 一次（3× TimeoutError）。
- 15:49–18:48 sol 503 server_is_overloaded 持续 3h，期间四次「探针过→episode 429 打脏」循环（q2 cand turn2 attempt 2–5 全废）。**18:52 起 sol 回稳**：18:56 q2 cand turn2（Q6）clean 落盘（1434 字、0 错），19:06 q3 base clean 落盘；19:14 q3 cand turn1 一次被 1 个 model_error 打脏，正重试。q4/q5 双臂未开始。
- 已完成（clean）：q1 双臂、q2 双臂两轮、q3 base。剩余：q3 cand、q4/q5 双臂。
- 现挂 **20:41 一次性 cron** 继续盯；若仍 503 循环，cron 指令自排下一小时接力，不碰进程。

## 下一步

1. 批跑完成后 `python3 /tmp/ticket10/summarize.py /tmp/ticket10/paired --md` 更新 §4.2 → 按 `10-frozen-questions.md` 判卷点补打 Q2 候选/Q3/Q4/Q5，Q6 查 `rerank_consistent`。
2. 合 main 等用户确认；合后能力图谱去 `@branch`。
3. `blocked/10.md`（判官两处 + 57244 key + **Mirasim relay mint 401**）转运行底座负责人。

## 未验证 / 已知边界

- 契约是引导非硬闸：模型不写矩阵走修复轮，预算耗尽仍可能发无矩阵稿（`missing_outputs` 非空可见）。
- `apply_scenario` 1.5 位次步长是确定性规则非校准量；两箭头同向叠加未在真实题验证。
- 基线臂离线复用候选树解析器（同尺），但基线无 `ranking_contract` 收据，dump 层不对称（汇总脚本已注明）。
- 「独立评审看匿名前后答案」未执行（等批跑完成）。

## 已验证

- 全量 pytest 干净绿（18:38，提交态 1ba0bd8b）：8343P/77S/1X，收据 `~/.finance-runtime/test-receipts/20260909T103809Z-1ba0bd8b.json`，check_test_receipt 可采信。相邻测试 138 条过。

## 踩过的坑

- 判官二进制钉版本号路径会被自动更新清掉；1.0.24 需 `LLM_JUDGE_GROK_SANDBOX=off`（本机 read-only 因 docker.sock 符号链接拒启）。诊断用 `complete_grok_cli` 同款 argv 手跑，别烧 episode。
- 网关探活用 `max_tokens≥3`（=1 会被当 availability probe 拒）；429 正文有 `reset_seconds`，睡它不盲重试。
- 一道深题 ≈12+ 模型调用可打冷却整模型——批跑按题间隔、跑前重探。
- bash 3.2 下 `. <(grep export)` 只加载一半——用 `eval "$(grep …)"` 且 exec 前断言非空。
