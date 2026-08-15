# Round 6 · 批 #3 执行 handoff（新执行方）

- 日期：2026-08-15 · 角色：执行方（单轨，live-lock 归你）· 检阅方：本文作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  末三段（Round 4 收口批注、Round 5 两轨小结、检阅方勘探）。
- 你可能是第一次进这个循环：**先读母本再动手**，本文只含你这一轮的增量。

## 0. 现状快照（开工前自查，全部应为真）

| 项 | 应读到 | 自查命令 |
|---|---|---|
| 生产身份 | `source_revision=fdb231148c0e`、`source_dirty=false`、pid 70403 | `curl -s http://127.0.0.1:8792/api/health \| jq '.runtime \| {source_revision, source_dirty}'` |
| main tip | `fdb23114`（含 #24 序号契约、#27 探针+并行字段、#28 detail 修复） | `git fetch gitea && git log --oneline -1 gitea/main` |
| 数据层 | `market_feature_store.duckdb` 无写者 | `lsof ~/finance-workspace-private/db/market_feature_store.duckdb`（空输出） |
| 同步管道 | 未在跑（批 #2 塌方根因＝日频同步持写锁 11:0x–11:16，见母本勘探段） | 同上 + `ps aux \| rg -i 'market_feature\|sync_'` |

任何一项不符：**停，报检阅方**，不要自行修。

## 1. 红线（母本 §1 之外本轮特别强调）

1. 独立 worktree（`git worktree add ~/fwp-wt-r6-batch3 gitea/main`）+
   独立分支；**禁止**动主 checkout `~/finance-workspace-private`。
2. 本轮**零代码改动**——所有量具已就位，你只跑批、读数、写报告。
   发现新缺陷登记账本，不修（Stop-the-Line）。
3. 多条 `kind=finish` 取**末条**；case 终态读 `execution_state_aggregate`
   （已写死 `last_turn`）。取首条会把 slips>0 窗口全读成 0（trace-profile §2）。
4. 合并/评论 PR 一律用**创建响应返回的编号**，不得手写常量（母本事故披露③）。
5. `validate-report.sh` 在 `~/.claude/skills/agent-run-triage/scripts/`（仓内没有）。

## 2. 任务：批 #3 + 六项读数

### 2.1 开批

```bash
# worktree 内、venv 解释器（宿主 python3 没有依赖）
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m intelligence.eval.acceptance run \
  --output intelligence/eval/runs/<UTCstamp>-r5-clean-baseline-3.json
```

- qc28 全集、默认预算（同批 #1/#2）；产物 sha256 记进报告并随 PR 进 git。
- 探针（R-12）自动跑：确认产物 `preflight_detail` 含
  `data_probe: finance_query=ok`。若探针失败：**照跑**（策略已写死
  `run_and_flag`），产物顶层必须出现 `window_contamination="finance_query"`，
  A 组读数按污染窗口标注，R-10/R-23 收口照常（B 组不依赖该数据源）。
- R-08 已部署：users 目录错配会响亮失败，遇到即报检阅方，不要 --force。

### 2.2 六项读数（判据全部预注册，事后不改口）

| # | 靶 | 判据（原文见账本对应行） | 归属 |
|---|---|---|---|
| 1 | **R-23**（序号契约 after） | 修复轮携证据收尾的同形 case（批 #1 B1/B7、批 #2 B5/C7 形）：`invalid_action.reason` 不再出现 `unknown/truncated evidence hash`，且修复终局解析出绑定、`evidence_bound>0` → confirmed；再现誊抄拒收 → refuted。零同形窗口 = unobserved，保持 pending 不扩批 | 判归 A 行，你出数 |
| 2 | **R-25**（detail 非空 live 臂） | 批内新的 `tool_error` 且 `error=tool_exception` 事件，`detail` 非空、形如 `ClassName: first line`、不含 `/Users/`。再现 `detail=""` → refuted。**数据层健康时可能零 tool_exception：零样本 = unobserved，保持 pending，明写不改口** | 判归 A 行，你出数 |
| 3 | **R-12**（探针 live 臂） | 产物探针字段在场（ok 或 fail 均可）；fail 而无顶层污染标注 → refuted | 你的行，可收口 |
| 4 | **R-10**（N=3 收口） | B 组按题出 3 批交付率表（冻结口径 `evidence_bound>0`），按该行判据结案，outcome 引三批 sha256。并行列 `episode_fulfilled_hashed` 供对照，但**结案只用冻结口径** | 你的行，收口 |
| 5 | **R-09**（回填) | 新快照 finish 带 `rejection_code`/`rejection_reason`（无拒收=none/空）；字段在场性 + 有拒收时非空 → 回填 outcome | 你的行，可收口 |
| 6 | **RU-3 / E-007 观测** | 统计 `episode_fulfilled_hashed ≠ evidence_bound` 的 case 数及其 `gap_output_ids`。**R-24 未实现**（裁决：下个部署窗），B3#2 同形可能再现——记录、不修、不开 L0（根因已钉死在 `_marker_loss_partial_public`，见 `docs/verification/2026-08-15-trka-r5-e007-split.md`） | 观测行，只记录 |

### 2.3 读数纪律

- A 组若再塌方：先看 `data_probe` 与 `window_contamination`，探针 ok 而 A 组
  仍 no_evidence 才是新缺陷（登记，不修）。
- 每条读数给 source_ref（产物路径 + jq 路径或 run 目录 + seq），
  检阅方会独立复核，抽不中原文即打回（母本 §6）。

## 3. 边界

- 可写：`docs/verification/`、账本你的段与 R-12/R-10/R-09 行、
  产物 JSON（新增，不改冻结批）、母本「轮次记录」追加。
- 不可写：`intelligence/` 任何代码、`docs/handoffs/round5-*`、A 的账本行
  （R-23/R-24/R-25 你只出数，outcome 由 A 或检阅方落）。
- 8792 服务、启动器、软链：**只读**。

## 4. 交付四样（不变）

1. 报告 `docs/verification/2026-08-15-r6-clean-baseline-3.md`
   （validate-report.sh RC:0）；
2. 账本 diff（只动你的行）；
3. PR（gitea，分支 `fix/r6-batch3-readings`）；
4. 轮次小结 ≤10 行追加母本「轮次记录」。
