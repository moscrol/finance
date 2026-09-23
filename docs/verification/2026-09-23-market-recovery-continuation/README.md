# 行情恢复 QC 续跑：全仓绿，独审仍受 504 阻塞

**整体 HOLD。** 新组合的完整 Python 门禁通过，旧独立探针原样复跑 20 项通过；五个单文件历史回退版本均被识别出行为错误。本轮 K3 新探针、新正式报告均为 0，不能用复跑或作者测试代替独审报告。没有修改行情业务源码，没有合并、推送、部署、staging、换库或生产写入。

## 固定身份

| 项目 | 值 |
|---|---|
| main，结束后 fetch 再核对无漂移 | `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e` |
| 修复分支输入 | `f3c99ab5b`，业务仍为 `4fa70046f` / `981c4d629` / `3abb7a4d3` |
| 组合 revision | `257263f63f526035a27724ffb2e7777ff2a9ee50` |
| 组合 tree | `dd731224eaea1d609f6ef5327d75bf3695687ddd` |
| 验证引用 | `refs/verification/market-recovery-continuation-20260923` |
| 运行根 | `~/.finance-runtime/reviews/market-recovery-qc-20260923/continuation-257263f/` |

`git merge-tree --write-tree <main> <fix>` 无冲突，使用独占 detached worktree `candidate/`。全仓执行前后及封存时干净。行情模块和相关作者测试相对旧组合 `4dd5e6660` 无差异，但不据此移动旧收据或旧 reviewer 报告的 revision。本次文档提交同样不在这份测试身份内。

## 完整 Python 门禁

- `bash scripts/run_main_gate.sh`，pytest 参数仅 `-q -p no:cacheprovider --junitxml=<产物> --durations=20`，未指定目录、用例或筛选条件。
- **14874 passed / 85 skipped / 2 xfailed / 0 failed / 0 error**，收集 **14961**，结果总数一致；17 warnings；pytest 2385.43 秒，整个 runner 2390.465 秒。
- Ruff、消费注册表、技能注册表、技能 frontmatter 解析、交付门 5 项自测通过。
- 解释器为主树 `.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`；无依赖门绕过、脏树豁免或 baseline 红集豁免。
- `--expect-revision 257263f63f526035a27724ffb2e7777ff2a9ee50 --base-drift-max 0 --require-full-scope` 在测试结束时及最后 fetch 后均 exit 0。
- 前端 / E2E 未运行：`git diff --name-only 2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e 257263f63f526035a27724ffb2e7777ff2a9ee50 -- intelligence/webapp` 为空，本行情补丁没有前端变更。

原始收据：`full-gate/gate-fbkayBkJ/pytest.json`。最后核验：`postflight/receipt-check.stdout`、`postflight/execution.json`。完整收集不意味着 opt-in live 用例都执行了；保留 pytest 自己报告的 skip / xfail 状态。

**target 口径：** 原始收据把全仓运行的 target 记成候选仓根绝对路径，而非空字符串。因此 `full-gate/execution.json` 的诊断字段 `receipt_target_empty=false` 不代表收窄；该原件不改写，`postflight` 另核对 target 等于仓根、完整 scope 与总数。不能把上轮 `target=tests/` 与本轮混淆。

## 探针复跑与通道失败

| 主张 | 原独立探针，在新组合复跑 | 作者相关测试 | 新 reviewer 交付 |
|---|---:|---:|---|
| F1 | 5P | 28P | report：`BLOCKED_PROVIDER_504` |
| F2 | 9P | 75P | 补强 explore：`BLOCKED_PROVIDER_504` |
| F3 | 6P | 28P | 通道失败后未启动补强会话 |

探针由上一轮 K3 编写，本轮校验其原 manifest 后逐字节复制；`F1-explore/provenance.json`、`replay/*-explore/provenance.json` 记录来源。执行由确定性控制器在禁网络、限写入、拒绝生产读取的 OS 沙箱中完成。三项 `assert 1 == 2` 阳性对照均 1F，和上述测试分账。

K3 固定 `mirasim-kimi/kimi-k3`，真实流式请求，剥除 temperature，并发最多 2。本轮共 **3 次请求预占**：F2 第一请求约 123.64 秒后 504；F1 第一请求 HTTP 200 并读包，第二请求 504，会话约 241.685 秒。响应钩子仅记录 **1 次 200**，两条 504 在原始 `model_errors` 中。两次 Pi exit 0 都不构成交付。未自动重试、换模型或重启网关，未触 600 秒帽。

新控制器把 `review.py` 及配置也纳入模型阶段输入哈希监测，结果 `inputs_unchanged=true`。旧轮 `run-v2.py` 未被监听的限制仍是旧证据的事实，不追溯改写。

## 历史缺陷敏感度

控制器用独立 Git 索引，从同一新组合仅恢复一个历史源码文件，生成另外的临时 revision；从未改动正在全仓运行的候选，也未改独立探针。每个回退版本的完整身份、源码 blob、探针哈希和失败原件在 `mutations/<名称>/`。

| 回退版本 | 来源 | 原始结果 | 可采用的行为失败 |
|---|---|---|---:|
| F1 接线前 | `4fa70046f^` 的 `run_review_sync.py` | 5F | 2；另 3 项仅旧接口参数不兼容，不计 |
| F1 重试记录修复前 | `981c4d629^` 的同文件 | 4P / 1F | 1，attempts 只剩最后一次 |
| F2 成员 guard 前 | `4fa70046f^` 的 `compute_local_stats.py` | 3P / 6F | 6，缺成员及坏价未拒绝 |
| F2 close guard 前 | `3abb7a4d3^` 的同文件 | 4P / 5F | 5，坏价未拒绝 |
| F3 apply guard 前 | `4fa70046f^` 的桥文件 | 6F | 6，拒绝覆盖断言未触发 |

合计 20 次行为失败、3 次旧 API 参数错误，零收集错误。这是同一批用例的重复运行，不是新增 23 个独立用例，也不是当前候选的 23 个缺陷。F2 最早版本同时缺两层 guard；F3 最后一例是在允许 True 覆盖之后再检查默认拒绝，不得解释成 True 覆盖失败。

这补充了针对五个已知历史版本的敏感度证据，不认证所有可能变异或未执行分支。五棵临时树已移除，保留 `refs/verification/market-recovery-sensitivity-20260923/<名称>`；当前候选仍保留。

## 封存与仍未闭合

`summary.json` 为控制方汇总，不是 reviewer verdict。`manifest.json` 校验本轮机器产物；人工 README / 交接不在该 manifest 中。`archive-renames.json` 记录代码和 launch 日志改名 `.txt` 的映射，内容不变。完整 JUnit XML、模型事件正文和输入包保留运行根，SHA-256 进 `raw-manifest.json`；不把大 XML 或会被测试发现器执行的代码副本加入仓库。原始红断言日志的尾空白可能使全目录 `git diff --check` 报警，保留原字节，不称该检查全绿。

所有本轮模型、探针及全仓测试进程已退出。仅清理经活动 PID `.lock`、inode、进程退出和成功收据共同核实归属的 `pytest-1804` 临时目录，没有清理其他 agent 的文件。

1. F1 正式报告仍缺；F2/F3 旧 `PASS_WITH_LIMITS` 只属于旧组合 `4dd5e6660`，未移签。
2. F2 的 -inf / 成员自身坏 close / 其他日期独立覆盖，F3 的全列及缺 policy 时其他日期独立覆盖，仍未补齐；并发、完整指纹、部分写后回滚也未认证。
3. 五问、三合同、5553/5565 范围及 53 只除权送转处置仍待用户裁决，见 `docs/handoffs/2026-09-22-market-recovery-decision-page.md`。真实 nightly、恢复 CLI、staging / 发布和生产验收未运行。
4. 之后 main 或实现再变，须重新判定收据适用性；未经授权不合并、推送、部署或写生产。
