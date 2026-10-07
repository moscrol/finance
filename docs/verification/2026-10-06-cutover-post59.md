# 切流回执 · 2026-10-06（post59）：8792 `e33021db023d → d5d7c5f6017e`

执行者：Cursor 本机会话。
授权：用户 10-06 先选「一路到上线：本机门禁和 CI 都绿就合并并切 8792，任何一步红就停」。main 推送后的汇总检查因账单问题未启动、显示为红，用户再次确认「继续切 8792：这个红是账单问题，不是测试失败」。
前一次切流：账本 switch 行 `2026-10-06T05:23:54Z`，rev `e33021db023d`（PR #58 合入后）。

## 1. 合入了什么

| PR | 内容 | head |
|---|---|---|
| #59 | 研究工具结果与派生计算的准入规则落在正式入口 `ResearchToolRegistry`，撤回未接线的 `finance_harness` 原型 | `3826f011a35a` |

- 分支原本基于 `09f53a731`，落后 main 32 个提交。用合并提交并入 `e33021db0`，没有改写历史，也没有强推。
  - `git merge-tree` 无冲突；合并树为 `a426c9acdeb4`。
  - 合并树上静态核对了 20 处 `ToolRunResult` 构造点：带证据时状态都在白名单内，失败状态都不带证据。
  - 相关测试 62 个文件、2412 项全部通过，ruff 通过。
- 合并前本机门禁（PR 头 `3826f011a`，干净环境 `env -i` 加 `umask 022`）：
  - ruff 0；pytest 20693 过 / 0 挂 / 0 错 / 75 跳过 / 2 xfail；
  - `collected=20770` 对得上，`--require-full-scope` 通过；
  - 收据 `gate-eTAV73Tp`。
- PR CI（`3826f011a`）：python、frontend、e2e、registry-check、workbench-check 五项全绿。
- 合入命令 `gh pr merge 59 --merge --match-head-commit 3826f011a…`。
  - 合入时间 `06:12:09Z`，main 变为 `d5d7c5f6017e`。
  - 其代码树 `a426c9acdeb4` 与 PR 头逐字节相同。

## 2. 批次门禁（main tip `d5d7c5f6017e`，独立 detached 门禁树，用后已拆）

- python：ruff 0；pytest 20693 / 0 / 0 / 75 / 2，`collected=20770`。
  - 当时解析出的期望 revision 为 `d5d7c5f6017e12ce5be9414abe31cf763c161f50`，`--require-full-scope --base-drift-max 5` exit 0，漂移 0；
    历史收据复核使用这个完整 SHA，当前 main tip 另取新收据。
  - 收据 `gate-AoylKDhl`。
- frontend（Node 22.23.3，取自 `npx node@22` 缓存；pnpm 10.12.1）：
  - install、lint、typecheck、vitest（210 过）、build、e2e（52 过 / 2 跳过）六步全部 exit 0；
  - 首尾 revision 都是 `d5d7c5f6`，`dirty=false`，`identity_stable=true`。
- registry：本机 5 项全部 exit 0（Python 3.12）。
- main 推送触发的 CI：python、frontend、e2e、registry-check 全绿。
  - 汇总任务 `workbench-check` 显示 failure，注解为「The job was not started because recent account payments have failed or your spending limit needs to be increased」。
  - `gh run rerun 37422443444 --failed` 后同样未启动。
  - 结论：账单问题，不是测试失败。

## 3. 8792（14:38:42–14:38:43 CST）

- 切前：在役快照 `e33021db023d` 的 porcelain 为 0；readiness 13/13；workers active 0 / queued 0。
- 按 `acceptance-workflow.md` §4 的准备段和切换段执行：
  - 新建 detached 快照 `~/.finance-runtime/finance-workspace-d5d7c5f6017e` 并加锁；
  - 补 `.venv-workbench` 软链，指向主仓 venv，确认可执行；
  - bootout：2 秒内退出、8792 没有监听 → `ln -sfh` → 用新快照写账本 switch 行（`--port 8792`）→ bootstrap。
- 回滚锚：`~/.finance-runtime/cutover-20261006-post59-rollback-8792.txt`，目标 `finance-workspace-e33021db023d`。该快照干净、保留，本次已加锁。

| 项 | 结果 |
|---|---|
| readiness | 切后约 27 秒 ready，13/13 |
| health（执行记录称三读；本目录未保存原始件） | 记录为 `source_revision=d5d7c5f6017e…`，`source_dirty=false`，`code_matches_repo=true`；监听进程 cwd 为新快照 |
| 部署账本 | `check` ok（`ledger_rev == health_rev == d5d7c5f6017e`，port 8792）；`homes` 只有唯一家，无旧家行 |
| grounded 探针 | 切前 `run_20261006_141511_002688`（`e33021db0`，84.7 秒）和切后 `run_20261006_143935_713864`（`d5d7c5f6`，58.4 秒）都 completed、判官 passed、degrade 0、secret_scan 0；口径 `fact_stock_daily`；模型 `glm-5.3-flash` |
| Gitea 备份 | 手动跑 `runner.py run`：status=success，Gitea 的 `main` = `d5d7c5f6017e` |

- 探针题：长电科技最近一个交易日的收盘、涨跌幅、成交额和近几天走势。
- 切后答案：2026-09-30 收 64.28、-2.16%、约 29.03 亿。
  - 库内 `fact_stock_daily` 为 64.28 / -2.16 / 29.0265 亿；
  - 9/22 72.24 / +0.03、9/23 71.82 / -0.58、9/24 68.78 / -4.17、9/28 65.43 / -4.87、9/29 65.70 / +0.41，逐日一致；
  - 库内 `max(trade_date)=2026-09-30`（国庆休市）。
- 切后整个会话没有出现新准入规则的「工具结果不可作为事实依据」提示。
- 切前、切后各只有 1 个样本。工具调用次数不同（口径计数 20 对 10），不构成快慢或质量判断。

模型身份门另行复核时，完整 run 目录上的命令
`scripts/check_model_admission.py --expect-model glm-5.3-flash <run-dir>` 两次都为 exit 2：
`continuous-episode.json` 能报告匹配的模型，但同目录 `trace.jsonl` 解码失败；只传
`continuous-episode.json` 会得到 exit 0。故这里可以说 Episode 产物自报模型匹配，不能把这两道探针写成完整模型准入已通过。

## 4. 未做 / 边界

- 真实 provider 返回数据的真值，以及自然模型投研答案的质量，仍未验收。探针只证明生产链路跑通、这一道题的数字正确。
- 完整 run 的模型身份准入仍是证据不全（exit 2），需修复或重新生成可解码的 `trace.jsonl` 后再把探针作为身份门结论。
- `reviews/deploy-post59-1006/` 未保留本次切换的原始 switch.log、readiness 和三份 health 读数；2 秒卸载、27 秒恢复及三读次数只能追溯执行者记录。
- 当时 GitHub Actions 因账单受阻；d5 的 main 汇总 run `37422443444` 保留历史 failure。当前 CI 与保护状态见下方 10-07 补查，不能将新提交绿灯移签到旧 run。
- 当时的分支保护说明更正由 #60 处理；#60 已合入，随后规则又有变化，当前配置说明由 #63 接续纠正。

## 2026-10-07 证据补查

- 当前 main `ea217633ceeaceeb41d3b3f30fa58708fe14ecc9` 的 workbench-check（`37443114093`）与 registry-check（`37443114064`）均 success。此前账单导致的旧 PR #61 / #63 检查重跑后已绿；本次文档修订仍须按新的 PR head 检查。
- 保留切前、切后原 run 的 Episode 与 trace，不补造缺失部署读数。用在役 d5 的模型身份检查器读取完整 run 目录，两次均 exit 2；用 PR #66 候选 `05b776e39c47` 的检查器读取同一原件，两次均 exit 0。修复只允许具名进度事件携带纯文本，模型调用账、身份事件和坏 JSON 仍拒收。
- 两次候选复核的 Episode 模型读数分别为 `glm-5.3-flash`×4 / ×3，trace 调用账为 ×5 / ×4；原件哈希前后不变。工程修复尚未部署，这项只证明保留产物的模型身份可解析，不改签历史完整部署验收或答案质量。
- 原始输出和带源码/输入哈希的收据已保存到 [`cutover-post59-identity-recheck-20261007/receipt.json`](cutover-post59-identity-recheck-20261007/receipt.json)。检查命令及精确代码 revision 在该收据中；原部署 readiness、三读 health 和卸载/恢复时序的缺件仍未补证。

## 5. 收据与产物

- python 门禁：`~/.finance-runtime/test-receipts/gate-eTAV73Tp/`（PR 头）、`gate-AoylKDhl/`（main tip）。
- frontend 门禁：`~/.finance-runtime/reviews/deploy-post59-1006/frontend-gate/`。
- 门禁、探针、备份日志，以及合并树定向测试收据：`~/.finance-runtime/reviews/deploy-post59-1006/logs/`。
- 探针收据：`~/.finance-runtime/live-probe-traceability/deploy-post59-pre-e33021db0.json`、`deploy-post59-post-d5d7c5f60.json`。
- 上一轮 e330 切换原始件在 `~/.finance-runtime/model-first-harness-1006/deploy-e33021db023d/`，属于 13:23 的部署，不能替 14:38 本次 d5 切换补证。
- 10-07 模型身份完整目录复核：`docs/verification/cutover-post59-identity-recheck-20261007/`，包含旧解码器失败、候选成功及原件哈希收据。
- 备份 bundle：`~/backups/github-finance/2026-10-06/repository-877c99714764db1fdf94f37b1560cd20b76d25f728532f44c3bc88373a64e79f.bundle`。
