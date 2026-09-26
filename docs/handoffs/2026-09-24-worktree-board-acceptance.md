# #84 / #895 固定候选全量验收

## 身份与裁决

用户本轮要求「继续全量验收」。受测候选始终为 `fix/worktree-board-hardening-0923@b26b8711a4826521a43a5a24fb488bdf53aa389e`，代码树 `/Users/a77/fwp-wt-board-hardening-0923`。本轮不改源码或测试断言。

**候选四叶通过；不等于最新 main 的集成验收。** 结束时 fetch 得 `gitea/main@5bf47a5ae9aa16768c0ef2df614177253764aeb6`，候选落后 28 个提交、8 张合并。`--base-drift-max 5` 明确 exit 1，仍禁止放行。未合并、未部署、未重开 K3、未关闭 #812、未删除任何真实 worktree；12 棵 ownership 证据树保留，拆除仍归 #64 重算与逐树授权。

报告独立放在 `docs/worktree-board-acceptance-0924`（底为上述 main），保持 #895 的受测 head 不变。本分支只载文档，复查实现须用上述候选树，不能运行本文档分支的旧看板来代替受测实现。此处收据也不签本文档分支。

## 四叶结果

| 检查 | 实际读数 | 身份与范围 |
|---|---|---|
| Python | Ruff exit 0；pytest 14665P / 0F / 0E / 85S / 2X，1729.15 秒 | `collected=14752` 对平；仓根 target；无 ignore/deselect/keyword/markexpr/maxfail/last-failed 收窄；依赖门禁未绕过；首尾同 SHA、干净 |
| frontend | frozen install、lint、typecheck、test、build 全部 exit 0；组件测试 120P | 同 SHA 的独立 detached 树，避开 node_modules 对 Python 仓扫描的影响；正式 runner 首尾身份一致、干净、complete=true |
| E2E | 34P / 2S，exit 0 | 与 frontend 同一正式收据；binding 用例只跑 desktop，tablet/mobile 按既有条件跳过；端口 19081/19084 已无监听 |
| registry | 五项全部 exit 0 | check-parseability、check、backfill-tables --check、generate-views --check、audit_ledger_spec_crosswalk；首尾同 SHA、干净 |

解释器为主树 `.venv-workbench/bin/python`，Python 3.12.13；本机 Node 26.0.0、pnpm 10.12.1，CI 配置要求 Node 22，未把本机结果称为 Node 22 环境验收。Python 的 85 项跳过主要为真实数据库、未提交脚本、显式跨仓/真实模型探针；没有新增 skip，没有接生产库或开启收费模型探针。

独立 `check_test_receipt.py --expect-revision <b26完整SHA> --require-full-scope` exit 0。错误 SHA 阳性对照（要求 main SHA）exit 1；加 `--base-drift-max 5` exit 1，原因仅为基座漂移超限。`merge-tree --write-tree <main> <候选>` exit 0，预览树 `6b32e81fc12d0cc512765b4b5be40114845bf0e9`，只证明无文本冲突，不代集成测试。

## 首轮红灯与复跑

1. 首轮全量 14664P / 1F / 85S / 2X，唯一失败 `tests/test_main_gate_receipt.py::test_green_gate_removes_explicit_basetemp`。本单三组回归在该全量内为 34+7+7=48P。
2. 根因是本轮运行器为保留临时证据设置了全局 `GATE_KEEP_BASETEMP=1`。`gate_env()` 会继承它，子门禁因此不清目录，与用例要求默认清理相反。是验收调用参数干扰，不是据此认定看板回归。
3. 同 SHA 下，显式保留变量的单例再次 1F，去掉后 1P；去掉变量的整个门禁模块 56P。两种读数单独保留，不能拼成全量绿。
4. 第二轮保持同一源码，白名单环境不含该变量，直接跑 Ruff、全量 pytest，再由现有 `main_gate_receipt.py` 校验退出码和身份；不经外层自动清临时目录的执行分支。完整新收据 14665P / 0F / 85S / 2X，三步 exit 0，首尾身份稳定。
5. 首轮原始红收据、两轮日志和临时目录均未覆盖或删除。第二轮有 3 GiB 磁盘止损和 3600 秒预算，均未触发；并发会话的进程、产物未干预。

## 实机看板

`worktree_board.py --json --timeout 10` 在 288.76 秒内 exit 0，得到 335 棵树的完整 JSON；采样基线固定为 `c9dd71dfd678855b61662100ec74625b92ad1f1b`。所有行的 `unknown_reason` 为字符串、`blockers` 为数组，Git 查询未出现负值失败占位。

**335 行均带全局引用未知**：`launcher unreadable: /Users/a77/Library/LaunchAgents/com.kb.disclosure-scout.plist (ExpatError)`。直接 plistlib 复核为第 12 行第 91 列 invalid token，macOS `plutil -lint` 却通过；因此记录解析器结果不一致，不断言 launchd 配置不可用，也不擅改仓外文件。该文件 SHA256 为 `0e872c88c3599e75188bfb69aba7923d056aab5d47fe3b7571d8e2e6204e39e5`。

这证明扫描完成并明确暴露未知，不证明树可拆。12 棵 ownership 树仍各有两个 tracked deletion：`.code-review-graph/.gitignore`、`.code-review-graph/wiki-steering.json`。本轮未重算 #64 的完整 mtime、ignored、reflog、引用授权链。

`--this` 另行冒烟成功，显示 `cherry+3 / cherry-0` 与采样时落后 26 个提交；不拿后续 main 漂移修改该历史读数。此前 120/900 秒超时、低预算 `trees:null` 记录仍保留，未改写为成功。

## 证据入口

共同前缀为 `/Users/a77/.finance-runtime/reviews/worktree-board-hardening-20260923/`：

| 相对路径 | 内容 |
|---|---|
| `full-20260923T2346/python-receipts/gate-Kjrc6cNR/pytest.json` | 首轮全量原红收据 |
| `full-20260923T2346/keep-positive-control.log`、`diagnostic-keep-receipts/` | 保留变量的 1F 阳性对照（后者也在 full-20260923T2346 下） |
| `full-20260923T2346/diagnostic-receipts/`、`gate-module-receipts/` | 去变量 1P、模块 56P（两者均在 full-20260923T2346 下） |
| `full-20260924T0024/run.json`、`pytest.json`、`python.xml` | 第二轮运行、正式 pytest 收据、JUnit；三者均在 full-20260924T0024 下 |
| `full-20260924T0024/full-scope-check.log` | 独立未收窄范围与身份核验 exit 0 |
| `full-20260924T0024/base-drift-check.log`、`wrong-revision-control.log` | 漂移拒绝与错 SHA 拒绝；后者也在 full-20260924T0024 下 |
| `full-20260923T2346/frontend/frontend.json` | frontend 与 E2E 六步、逐日志哈希、首尾身份 |
| `full-20260923T2346/registry-run.json` | registry 五项及日志哈希 |
| `full-20260923T2346/board-run.json`、`board-0.log` | 看板扫描收据与 JSON（后者也在 full-20260923T2346 下） |

各 runner 收据含命令、日志 SHA256、自身 SHA256、退出码和首尾身份。看板 JSON SHA256 为 `c082a558517eb9cee01f8f0a66361e47a54d4df7de0c4087fd21629a46717e1e`。一次性运行器存于上述持久证据目录，不在 /tmp；复用现有 pytest 收据与校验器，不另设官方验收入口。本轮仅修正运行参数，未发现需要给生产门禁删断言或放宽判据的理由；环境隔离教训进入既有 lessons，不新增 harness 能力清单。

## 后续与被否方案

| 决定 | 未选方案 | 理由 |
|---|---|---|
| 同 SHA 在修正环境后完整重跑 | 单例/模块绿覆盖全量红，或改测试断言 | 不同覆盖面不能拼签，首轮失败有可证伪原因 |
| 文档另枝，#895 保持受测提交 | 验完又向 #895 追加文档提交 | 避免收据 revision 与 PR head 失配 |
| 保留全局引用未知 | 用 plutil 一条绿替代标准库失败，或擅修启动文件 | 解析器语义差异尚未设计和验证，仓外配置不属本轮授权 |
| 保持 WIP | 将四叶绿或 merge-tree 干净当合入许可 | 基座漂移门红，且用户未授权合并 |

下一步先协调资源，在新的集成候选上前向最新 main，再跑针对该提交的必要门禁，取得用户确认后才可合入。当前候选收据不可移签新集成提交；#812 只在接替提交实际合入后按原规则留指针处理。文档分支也未获合并授权。#64 拆树与任何启动器修复另行办理，本轮不替它们放行。
