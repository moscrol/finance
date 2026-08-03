# Budget Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用预注册的四臂五题实验确认 Codex headless 超时的首要预算瓶颈，并闭环既有预测，不修改生产默认值。

**Architecture:** `a_control` 同时承担 R-04 的真实 runtime 验证与四臂对照基线；随后只改变预注册 profile，依次执行 `b_floor_ablation`、`c_long_capped`、`d_long_expanded`。原始 artifact 是事实源，归一化 artifact 只负责 L1 九步投影，最终按 M2 的 Evidence → Finding → Path 契约形成标定报告。

**Tech Stack:** Python 3.12 虚拟环境、Codex CLI、JSON benchmark artifact、`jq`、`normalize_harness_trace.py`、Markdown 预测账本。

---

### Task 1: T0 开工前预测闭环

**Files:**
- Modify: `docs/prediction-ledger.md`

- [ ] **Step 1: 在新归因前记录三条 Open 预测的证据状态**

  记录 `R-20260804-02`、`R-20260804-04`、`R-20260804-07` 当前均无足以改变 outcome 的新证据，并保持 `pending`。这是时间顺序收据，不把后续实验结论倒灌为开工前事实。

- [ ] **Step 2: 核对 Open 表的冻结枚举**

  Run:

  ```bash
  rg -n 'R-20260804-02|R-20260804-04|R-20260804-07|本轮开工回填' docs/prediction-ledger.md
  ```

  Expected: 三条预测均可定位，且开工回填明确写出 `pending` 与“本轮暂无新证据”。

- [ ] **Step 3: 提交 T0 收据与执行计划**

  ```bash
  git add docs/prediction-ledger.md docs/superpowers/plans/2026-08-04-budget-calibration.md
  git commit -m "docs(eval): preregister budget calibration execution"
  ```

  Expected: commit 成功，工作树恢复干净，后续 benchmark 的 `source_dirty=false`。

### Task 2: T1 用 a_control 闭环 R-04

**Files:**
- Create: `intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json`
- Modify: `docs/prediction-ledger.md`

- [ ] **Step 1: 运行真实 a_control 五题**

  ```bash
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
    scripts/run_agent_runtime_benchmark.py \
    --backend codex_headless \
    --headless-budget-profile a_control \
    --questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json \
    --finance-root /Users/a77/finance-workspace-private \
    --knowledge-wiki /Users/a77/知识库/wiki \
    --output intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json
  ```

  Expected: 五题均落盘；命令在仓库根执行；不触碰 8792 或生产 tier 默认值。

- [ ] **Step 2: 断言 runtime issues 与 protocol issues 的生效值**

  ```bash
  jq '[.cases[] | . as $case | .arms[] | {
    case_id: $case.id,
    status,
    protocol_issues,
    runtime_issues: ([.diagnostics.events[] | select(.kind == "runtime_result") | .payload.issues] | last)
  }]' intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json
  ```

  Expected: 至少一题 `runtime_issues` 含 `headless_timeout`，同题 `protocol_issues` 不含 `runtime_invalid_actions:*`。

- [ ] **Step 3: 将 R-20260804-04 移入 Closed**

  Evidence 必须写 artifact 路径、case ID、`runtime_result.payload.issues` 实值与 `protocol_issues` 实值；若没有产生 `headless_timeout`，保持 pending 并记录“本轮未触发判据”，不得伪造 confirmed。

### Task 3: T2 完成 b/c/d 并归一化四臂

**Files:**
- Create: `intelligence/eval/measurements/2026-08-04-budget-calibration/b-floor-ablation.json`
- Create: `intelligence/eval/measurements/2026-08-04-budget-calibration/c-long-capped.json`
- Create: `intelligence/eval/measurements/2026-08-04-budget-calibration/d-long-expanded.json`
- Create: `intelligence/eval/measurements/2026-08-04-budget-calibration/*.normalized.json`

- [ ] **Step 1: 依次运行 b_floor_ablation、c_long_capped、d_long_expanded**

  对每个 profile 复用 Task 2 的同一解释器、题面、finance root、wiki root 与 backend，只替换 `--headless-budget-profile` 和输出文件名。

- [ ] **Step 2: 逐臂验证实验变量真实生效**

  从 artifact 断言 `diagnostics.root_budget`、每次 `tool_result.payload.budget`、`latency_seconds` 与预注册 profile 一致；不能只检查脚本里的配置常量。

- [ ] **Step 3: 生成四份 L1 九步归一化收据**

  ```bash
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
    -m intelligence.eval.normalize_harness_trace \
    intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.json \
    --kind runtime-benchmark \
    --output intelligence/eval/measurements/2026-08-04-budget-calibration/a-control.normalized.json
  ```

  Expected: 四份产物均为 `vocabulary=triage-l1-9` 且 `unmapped_count=0`；其余三臂使用同形命令。

- [ ] **Step 4: 提取每臂五题的标定字段**

  必须覆盖 arm status、事件级 `finish.payload.stop_reason`、每次取证后的 `remaining_research_seconds`、`research_stage_closed` 的次数与工具序号、`latency_seconds`、root budget 与最终化间隔。

### Task 4: T3 形成 M2 标定结论

**Files:**
- Create: `docs/verification/2026-08-04-budget-calibration.md`
- Modify: `docs/prediction-ledger.md`
- Modify only if a new field trap is observed: `docs/trace-profile.md`

- [ ] **Step 1: 按 a→b、b→c、c→d 做三组单变量比较**

  先验证 profile 生效，再比较终态和事件序列。M2 分开填写 activation、divergence、failure、surfaced、reconvergence 五个 step；不得用 `first_divergence_step` 填满五槽。

- [ ] **Step 2: 建立至少三条可证伪假设**

  候选依次为关门阈值、总时长、调用数上限；每条用相邻两臂的实际差异判为 `CONFIRMED`、`REJECTED` 或 `INCONCLUSIVE`。

- [ ] **Step 3: 写 Evidence → Finding → Path 报告**

  报告首字符必须是 `# Agent Run Triage Report`。PRIMARY 只能选择第一次有运行时证据的错误变换；建议使用冻结 `fix_type`，带 `verification_prediction`，并明确本轮不改生产默认值。

- [ ] **Step 4: 标定 0.65 与真实收尾时间**

  用 `finalization` 到 `finish` 的事件时间差回答收尾实际需要多少秒。若 artifact 没有足够时间戳，写明 D3 证据边界与最小观测处方，不从配置值反推实测值。

- [ ] **Step 5: 更新 prediction ledger**

  闭环 R-04；R-02/R-07 只在满足原判据时改 outcome；新增本轮修复建议对应的 pending 预测，并更新同类 `fix_type` refuted streak。

### Task 5: 验证、提交与推送

**Files:**
- Verify all changed files

- [ ] **Step 1: 校验报告契约**

  ```bash
  /Users/a77/.grok/skills/agent-run-triage/scripts/validate-report.sh \
    docs/verification/2026-08-04-budget-calibration.md
  ```

  Expected: `RC:0`；这只证明报告结构合约，不替代结论复核。

- [ ] **Step 2: 运行相关测试**

  ```bash
  env -u FORESIGHT_USERS_DIR \
    /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
    intelligence/tests/test_normalize_harness_trace.py \
    intelligence/tests/test_run_agent_runtime_benchmark.py
  ```

  Expected: focused tests 全绿；若出现已知宿主环境泄漏或 flake，单独复现并按 handoff 口径报告。

- [ ] **Step 3: 检查风险文件与提交范围**

  ```bash
  git status --short
  git branch --show-current
  git diff --check
  git diff --name-only --cached
  ```

  Expected: 只包含计划、四臂测量、归一化收据、验证报告、账本，以及确有新字段陷阱时的 trace profile；不含任何密钥、数据库、PDF、压缩包或缓存。

- [ ] **Step 4: 提交并推送任务分支**

  ```bash
  git push -u origin eval/budget-calibration
  ```

  Expected: 分支推送成功；不合并 `main`。
