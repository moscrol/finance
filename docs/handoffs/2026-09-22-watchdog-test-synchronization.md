# 2026-09-22 Watchdog 测试时序隔离

## 背景与授权边界

用户“执行”本轮落实为定位、修复正式 main watchdog 测试红灯。基线 `e82717d9a7c3dfa811a4538bd44985b61258355a` 已包含 #831；#831 已合入的事实不变。此前正式 main 的完整 pytest 为 12509 passed / 1 failed / 85 skipped / 2 xfailed，不能用单例或模块绿覆盖。

本轮在独占 `/Users/a77/fwp-wt-watchdog-test-0922` / `fix/watchdog-test-synchronization-0922` 工作，不碰主检出的他人修改、不合并、不部署、不重启。#846 未解除 WIP；8792 最新 main 整体部署禁令继续。未修改行情或删除任何工作树、事故现场。

## 按发现顺序

1. 核对 runtime：`run_turn` 在前置编排前创建绝对 `ResearchDeadline`，watchdog 进入时发现已过期就返回结构化部分结果，trace 明确 `worker_started=false`。这是一条合法路径。
2. 原测试把整轮预算设为 0.2s，却无条件断言回答线程已启动。对原 main 代码与测试不作文件修改，用树外 pytest 插件在 watchdog 入口前延迟 0.25s，稳定得到相同断言失败。剩余预算从约 0.1506s 降至 0，trace 为 `ask_root_timeout` / `worker_started=false`。
3. 原正式全量失败的临时目录早已丢失，所以这里只证明失败形状可由前置预算耗尽触发，不宣称历史事故的唯一根因，更不以该实验排除集成交互。
4. 改动只在 `intelligence/tests/test_conversation_orchestrator.py`：替换 `research_contract` 模块自身的 `time` 绑定，不修改全局 `time.monotonic`；仍用真实 ResearchDeadline、真实 Thread/Event/Future。回答线程记录 started 后将局部时钟推进到原绝对截止点，才触发真实 watchdog 的运行中超时分支。
5. 原 0.2s 业务预算不改。0.8s 检查明确改为“到期事件到 watchdog 返回”，不再量整轮前置编排及结束后的落盘。这是计量边界调整，不是原端到端耗时保证。Event 的 5s 等待是测试死锁上限，不是生产授时。
6. 新增前置编排消耗 0.25s 的回归，要求回答函数调用数为零且 trace 为未启动。原测试直接记录转发的文本回调、核对 trace 不增长，并在 finally 释放、join 自己的回答线程。
7. 六个负向变异均能被测试抓到，正常及延迟启动对照通过。源码文件不作 mutation；探针只改测试进程中装载的函数。
8. 代码提交 `eb23f84015a0d48da996b98af1d906a6b6ce9d0f` 已推送。干净提交的模块/合同测试 107P、全仓 Ruff0。磁盘一度约 4.5 GiB，未启动完整 Python/前端/registry 门禁。
9. 创建 PR 两次客户端 30s 超时，第一次后回读 open 无该 head，第二次后回读 all 无该 head。截至该次回读没有 PR 编号，不把分支已推送写成已创建 PR。不再写请求，不重启 Gitea。PR 正文草稿保留在证据目录；后续先回读再决定创建，避免迟到请求造成重复。

## 方案取舍

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 增加根预算、放宽耗时断言 | 仍依赖冷暖/调度，掩盖启动前到期路径 | 不选 |
| 删除 worker_started 或迟到输出检查 | 会失去 watchdog 行为覆盖 | 不选 |
| 改 runtime 强制启动已经过期的回答 | 违背副作用前预算检查合同 | 不选 |
| 冻结全局 time.monotonic | 影响无关计时和线程等待，容易假绿 | 不选 |
| 局部时钟、真实线程、分开启动前后截止 | 控制业务事件顺序，同时保留真实等待与回调实现 | 采用 |
| 用定向结果覆盖原 main 全量失败 | 收据范围、revision 均不匹配 | 不选 |

## 验证与收据

统一证据根：`/Users/a77/.finance-runtime/reviews/watchdog-sync-20260922/`。所有 pytest 使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`、`env -i`、`umask 022`，`--basetemp` 放在持久树外目录。

- 原版复现：`delayed_preparation_probe.py`、`delayed-pytest.log`、`delayed-junit.xml`、`delayed-observation.json`、`delayed-basetemp/`。1F，断言正是 `worker_started.is_set()`，原文件未改。
- 脏树开发验证：2P，随后模块105P；只支持开发阶段，不移签干净提交。
- 固定代码提交107P：`committed-pytest.log`、`committed-junit.xml`。原生收据 `/Users/a77/.finance-runtime/test-receipts/20260921T164752Z-eb23f840.json`，Python 3.12.13、依赖指纹 `3328bed61f3e21ea`、clean、exit0。
- `committed-receipt-check.log`：完整 revision、解释器、指纹、干净状态与基座漂移0校验通过。校验的是来源；107P/0F/exit0另从收据正文与 JUnit 确认。
- 全仓 Ruff：`ruff.log` exit0。提交钩子的层级、字段、路径、dataset、工具可达性、runtime目录检查通过，不冒称完整 registry 发布叶子。
- 固定提交八个控制实验：`committed-controls/execution.json`，首尾 identity 相同、干净，日志/JUnit 哈希、原生收据独立副本齐全。正常2P，前置/线程启动各延迟0.25s的对照2P；下表六项各1F/1P，零 setup/error。

| 进程内撤保护 | 被抓住的检查 |
| --- | --- |
| 允许到期后启动 | 回答调用必须为零 / timeout trace |
| 移除两层进度检查 | 完成后 trace 不得增长 |
| 移除文本检查 | forwarded_deltas 必须为空 |
| 移除取消门控 | 回答线程无法完成约定的迟到回调路径，测试失败 |
| 忽略运行中截止 | watchdog 未按期限返回，测试失败 |
| 重建根 deadline | 前置耗尽后仍启动回答，测试失败 |

取消/运行中截止变异有 worker 内断言，runtime 将异常封入 Future，外层测试据失败结果/等待断言变红；不是测试加载错误，也不据此认证所有异常传播路径。

`git merge-tree --write-tree e82717d9... eb23f840...` exit0，预览树 `7be70f6106f2cf3489849b2195d626411aa9d7be`。这仅是合流可行性，不是独立批准或全叶验收。

## 探针失败与工具沉淀

早期两项探针因匹配旧函数文本报 UsageError，未进入测试。之后只撤进度内层检查仍为2P，因为外层保护仍在；最终 v3 撤两层后按预期1F。历史日志均保留。

早期三探针并发运行，同 revision 同秒生成的原生收据 `20260921T164035Z-e82717d9.json` 发生同名覆盖；该文件只保留最后一个写者结果，不能证明三次运行。各次独立日志仍在。后续用顺序运行、唯一输出目录、JUnit、每次原生收据即时副本，避免再依赖共享 latest/秒级名字。收据基础设施修复已有独立候选 #814，本轮不跨边界重写 conftest。

重复控制实验固化为证据目录内 `run_controls.py` 与 `watchdog_controls_v3.py`，绑定具体 watchdog 源码用于审查复演，不是通用发布工具，也不得执行部署。正式长期保障是仓内两条回归测试。通用方法补入 Agent Memory 的 `wall-clock-derived-values-in-equality-asserts`；`harness-reference/BUILD.md` 有他人未提交修改，未触碰。

## 后续与禁止事项

- 先确认 Gitea 中该 head 是否出现迟到 PR，再创建 WIP PR，不重复 POST。
- 独立审查固定完整 base/head，确认局部时钟没有掩盖要验证的合同；本轮没有独立签字。
- 空间与并发任务允许后，在固定合流候选跑完整门禁，取得授权后才合；实际 merge commit 仍需自身 main 收据，不可移签候选或文档前驱。
- 代码收据绑定 eb23f840，后续文档提交不改签这份107P；源码零差只是范围说明。
- 原 main `20260921T160947Z-e82717d9.json` 仍为红色完整收据。#831已合并与发布门禁红同时成立。
- 不整体部署含K3的main，不为测试修复重启8792，不解除#846 WIP，不清理别人或事故证据。
