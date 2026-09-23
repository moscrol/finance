# #83 / #813 门禁续跑与容量阻塞

## 当前结论

2026-09-24 收尾时仍为 **BLOCKED_RESOURCE / WIP**，不是 PR 就绪。候选 `fd6d8cc5be24c6f3a85af5c960be7766f88deaa7` 已推至 #813 的 `fix/backfill-main-ready-0921`；基线为 `gitea/main@3bb81b9638f97b4773ce0f338df3a505b7c0162f`。本次没有合 main、执行生产回填、重启 8792、修改 launchd 或停止他人的任务。

证据根为 `~/.finance-runtime/reviews/backfill-302132-0923/`，下文路径均相对它。动态状态只读 `CURRENT.json`。固定候选树为该目录下的 `candidate/`；后续交接文档只提交到 `fix/backfill-302132-0923`，不再推进 #813，文档提交不能冒充被验源码。

## 发现顺序

1. 前向得到 `c2ecc1273fedeb4dcb69e2801e6b670ca8c9994a` 后，前端、E2E、注册表清单检查及整库副本演练通过。`continue-01/rehearsal/` 包含 37 项验收、异常成交额对照、恢复核验及生产身份不变的证据，仅对应 c2。
2. c2 首轮 Python 全量为 14965 通过、1 失败、85 跳过、2 预期失败。唯一失败的临时数据库路径含 `302132`，路径随来源信息进入带读文本，被 `E_STOCK_SCOPE` 当成个股代码。原目录单文件 29P/1F，中性目录同文件 30P；未改业务文字检查规则。原红收据与失败夹具保留。
3. 中性目录全量 `continue-02` 因磁盘跌破 4 GiB 中断。只清理本轮已退出进程的临时目录，保留中断记录和最后夹具。
4. pytest 8.3.5 的 `tmp_path_retention_policy=failed` 能在成功用例结束后清理其 `tmp_path`。30 项对照通过、目录归零。c2 完整再跑得到 14966P/0F/1E：全局 `os.open` 模拟仍作用于 pytest 目录清理，因不支持 `dir_fd` 在 teardown 报错。这不是绿收据。
5. 前向 main 到 `3bb81b96`，提交 `fd6d8cc5b`：三处系统调用模拟改用 `monkeypatch.context()` 限定于被测调用，原拒收和文件保留断言不变；另加系统函数恢复断言。原测试在清理策略下复现红，三处定向转绿；冻结提交后相关 118 项全绿。仓外复制真实测试并撤掉作用域，在默认保留策略下恰好被新增恢复断言击杀，正式候选未改。
6. fd6 的前端与 E2E 完整通过。核对 `.github/workflows/registry-check.yml` 后补齐五个子检查，均退出 0；之前单独的 `build_registry.py check` 不能代表整片叶。
7. fd6 整库演练在复制前因不足 8 GiB 被拒绝。Python 完整门禁运行 307.12 秒后，共享磁盘降至 4293124096 字节，低于 4 GiB 停止线；守护仅终止本轮 shell、pytest 和其子进程，三者均已退出。临停前本任务临时目录约 112 KiB，未取得完整 Python 收据。不能把部分输出、旧版本数据演练或定向绿拼成新版本全绿。

## 本候选证据

| 检查 | 结果 | 证据 |
|---|---|---|
| 回填及演练定向 | 干净树 118P | `continue-04/focused.command.json`、`focused-receipts/` |
| 前端 | install/lint/typecheck/120 项单测/build 全 0 | `continue-04/frontend/frontend.json` |
| E2E | 34P、2 个既有跳过，超时标准未放宽 | 同一前端收据及 `continue-04/e2e-results/` |
| 注册表 CI | 五项全 0；与 CI 一样仅本仓，缺席跨仓项明确跳过 | `continue-04/registry-complete/receipt.json` |
| Python 全量 | ruff 通过；pytest 容量保护中断，没有完整收据 | `continue-04/python.command.json`、`python.log.txt` |
| 整库演练 | 空间预检拒绝，没有复制或发布 | `continue-04/rehearsal/summary.json` |
| 系统调用模拟变异 | 仓外旧写法 1F，命中恢复断言 | `continue-04/osmock-mutant.log.txt` |
| 合并预览 | main `3bb81b96` 与 fd6 无冲突，树 `3e508e515641eea0ce4df52a47d2504b45da615a` | `continue-04/merge-tree.txt` |

本 PR 相对上述 main 的增量没有命中 `data-quality-check.yml` 的路径条件。Gitea 显示的 mergeable 不是本地预览或门禁的替代。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 中性临时路径，保留原红 | 放宽业务文字检查 | 暴露的是来源路径参与扫描的边界；改业务检查超出本单，不能靠删闸凑绿 |
| pytest 原生成功清理、失败保留 | 筛用例或删除正在使用的目录 | 不缩小收集范围，不破坏失败现场与运行中的文件 |
| 限定系统函数模拟作用域并加恢复断言 | 只让假的 open 接受 dir_fd | 后者仍会让模拟污染框架清理；恢复断言让默认配置也能抓回归 |
| 对 fd6 重新出工程和数据证据 | 将 c2 绿收据移签 | revision 已变化，且本轮前向包含 main 的 CLI/部署检查更新 |
| 维持 4 GiB 停止线与演练 8 GiB 预检 | 降线、抢占别人进程或清他人数据 | 当前是整机容量约束，不能把风险转给其它工作或生产 |
| 状态文档单独推任务分支 | 为更新交接继续改变 #813 head | 保留固定被验版本，下一轮只需补缺失项 |

## 留证与工具盘点

旧 c2 的完整状态已封在 `continue-03/final-status-c2.json`。旧 39 候选的 `trace.zip` 未成功保留，只有旧前端日志和收据，不能声称旧 trace 可回放。本轮先归档 c2 输出到 `continue-01/e2e-results-complete/`，fd6 输出另存 `continue-04/e2e-results/`，没有跨轮覆盖。

c2 的 cleanup 失败夹具保留在 `continue-03/failing-osmock-fixture/`，该轮其余已结束的临时目录已清理。fd6 中断现场很小，保留；没有后台验收进程继续运行。

正式量具仍为 `scripts/review_probes/rehearse_302132_backfill.py` 及其测试、`run_main_gate.sh`、`run_frontend_gate.py` 和 CI 声明的注册表命令。证据目录的固定 SHA 启动器是本次命令附件，不是第二套产品门禁；临时文件寿命直接用 pytest 内置机制，不另造框架。系统模拟缺陷已用源码测试和撤作用域对照封住。可迁移经验见 agent-memory 的 `pytest-temp-paths-and-mock-lifetime.md`；单次样本不用于推断速度提升。

## 下一步与授权边界

1. 先协调稳定的磁盘余量和重测试窗口。整库演练至少要 8 GiB 可用空间；全量过程仍保留 4 GiB 停止线。
2. 核对 `CURRENT.json`、#813 head、候选树干净状态及 main 漂移。保持 fd6 时，使用新输出目录和不含业务代码的中性 basetemp 补完整 Python 门禁；保持 `tmp_path_retention_policy=failed`，不加筛选。随后执行 `check_test_receipt.py <明确收据> --expect-revision fd6d8cc5be24c6f3a85af5c960be7766f88deaa7 --require-full-scope`。源码变了就重验，不能消费旧收据。
3. 用已有副本量具在新目录重跑本候选整库发布、37 项验收、异常金额拒收、恢复与生产身份核验。全部工程与数据证据齐后更新 #75、解除 WIP，再请用户决定合入。
4. #802 已关闭且评论 6446 指向 #813，历史分支保留。独立 QC 尚未签字，不能以作者检查替代。
5. 生产与合入分开授权。最新待授权稿在证据根 `production-authorization-draft.md`，已绑定固定候选树并标明当前未过门。只有本轮真实父收据的 backup 路径/SHA 才能成为回滚点；不能用演练备份或“最新一个备份”。CLI 没有 `--record`，用户逐字授权另存 JSON；出现 WAL 或后续业务写入先停下，不自行重启 8792、调整 launchd 或扩到其他股票。
