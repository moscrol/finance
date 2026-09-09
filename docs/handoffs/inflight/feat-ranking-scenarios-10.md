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

已实现 ✅（44 新单测绿；ruff 0；层门禁无新增）｜已进默认入口 ✅（双引擎注入，hybrid 真实 run 收据在 `continuous-episode.json`）｜真实验收 ⏳（第一轮 Q1 差分：候选 matrix=4/flip=3/缺件=0、1473 字 vs 基线 812 字无结构；六题配对批跑**在等网关**）｜生产生效 ❌（按合同不合 main）

## 批跑状态（接手先看）

- 批跑 pid 39647、双臂 8815/8816（pid 39218/39219）均存活，环境已核对（双链+判官修复）。
- 20:07–20:12 探针：8080 单次 200 但 502/503 抖动态，episode（12+ 调用/题）必撞回——等连续 3 次探针通过的门槛是对的，继续等。57244 兜底链两把 key 恒 401（blocked/10.md 第 6 行），恢复只看 8080。
- `/tmp/ticket10/paired/base/q1.json`（18:18 残留）是降级空壳，批跑重跑会覆写，不计入差分。

## 下一步

1. 盯 `/tmp/ticket10/paired/paired.log`；网关恢复后批跑自动开跑。
2. `python3 /tmp/ticket10/summarize.py /tmp/ticket10/paired --md` → 填验证文档 §4.2/§6 四项报告 → 按 `10-frozen-questions.md` 判卷点逐题打分，Q6 查 `rerank_consistent`。
3. 合 main 等用户确认；合后能力图谱去 `@branch`。
4. `blocked/10.md`（判官两处 + 网关退避 + 57244 key）转运行底座负责人。

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
