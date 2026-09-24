# 历史表达边界与测试生命周期返修验收

## 裁决与适用范围

**固定 `672abcc504b3466a2ddd24dfa450c55703265c70` 的作者侧四项工程检查通过。真实历史研究四题没有重跑，最近业务裁决仍为 [fbd8f2a6 整组失败](../fbd8f2a6/acceptance.md)。WIP #783 未合并、未部署。**

表达修复提交为 `f9afb4a0029224ed13dd3b3bb16d0a76e7c0f2e8`；其正式全量先出现一条真实回归失败，随后 `672abcc5` 仅修测试夹具拥有的后台任务生命周期。不能把后者的绿灯追溯签给前者，也不能把工程通过写成模型理解正确。

本目录 [manifest.json](manifest.json) 登记 **95 份源/副本、34 份冻结源码哈希、8 份未改动旧 live 原件身份**。长日志按证明范围分组；原始数据/答案仍在原 live 根，不迁移、不重封印。

## 1. 本片修了什么

- 可信 `HistoryIntent`（历史任务用途）传到提示装配、表达缺项修复、终态收据、自动观察项登记。历史窗口内强弱排名/路径追踪，不自动要求面向未来的公司优先级矩阵、长期跟踪或改判登记。
- 只移除不适用的前向表达义务；真实证据缺口、历史 finish/publication 门、授权与信息截止保持不变。助手正文自称“历史研究”不能降合同。
- 普通前向题、其中的历史类比、用户显式停止历史研究后的正常模板仍保留。
- 两个共享合同的 `history_intent` 可选、默认 `None` 保兼容。Workbench 两路收尾已接线；**未传任务状态的 standalone legacy CLI 仍是旧行为**。
- quota/credits/admission 三个测试夹具先放行受控任务，再等待执行器与完成回调结束，最后撤销替身。只改测试基础设施，未改变生产 `RunSupervisor.shutdown()`、模型重试、预算或收据算法。

**没有修**同窗板块/个股/成员排名、各自启动特征与控制组、跨轮主动读取原件；更没有认证完整 SPT/风远方法。

## 2. 冲突来自实际输入，不只是标签推测

[saved-template-conflict.json](saved-template-conflict.json) 对旧 fbd8 四轮 `prompt_assembled` 的 system/user 文本与保存收据逐份核哈希。第二题的实际提示含：

- `【跟踪表达契约】`：上期基线、复核期限、下期关注；
- `【排序与情景表达契约】`：公司优先级矩阵、收入利润传导、改判表；
- 终态结构检查仍追讨 `track_next_watch`、`ranking_flip_conditions`。

这是**已发生的冲突指令/检查路径**，不是整组失败的唯一因果解释。原先板块与股票使用异窗等缺陷仍独立存在。

[candidate-contracts.json](candidate-contracts.json) 使用原四题、真实 controller 用户链与 Harness 装配离线核查：四题没有前向表达标题，真正证据缺口保留；清除历史状态的反事实对照恢复前向要求。该快照的 registry 为空、答复为脚本缺证据稿，**不是模型实际新收到的请求，也不是新业务验收**。共享 writer、真实 `run_turn` 和 adapter 的消费者回归见 `tests/test_history_expression_contract_boundary.py`。

## 3. 固定代码工程结果

运行根：`~/.finance-runtime/history-expression-672abcc5-checks/`。驱动固定 SHA/干净树、白名单环境、umask 022，各叶独立记录退出码且不 fail-fast。运行前后 revision 一致、dirty 为空、`gitea/main=d32b8966` 无漂移；这不是合流后 main 验收。

| 检查 | 结果 / 原始输出 |
|---|---|
| Python | Ruff 通过；**11579 passed / 81 skipped / 2 xfailed / 17 warnings，890.75s**；[日志](python.txt) |
| 前端 | lint/typecheck/test/build 全部退出 0；8 个测试文件、107 测试通过；[日志](frontend.txt) |
| 浏览器 | 34 passed / 2 skipped；隔离夹具和空模型密钥，非真实金融研究浏览器验收；[日志](e2e.txt) |
| 注册表 | 五项检查全部退出 0；反向台账 98 条存量 warning；[日志](registry.txt) |

[四叶收据](ci-receipt.json)、[pytest 收据](python-receipt.json)、[八项条件校验](receipt-check.txt)。pytest 原收据为 `20260918T125515Z-672abcc5.json`，Python 3.12.13、依赖指纹 `3328bed61f3e21ea`、正确 workbench venv、未绕过依赖门。两个 xfailed 不计普通失败；跳过项和 warning 未隐藏。并行检查和诊断影响用时，**不拿单次耗时作性能结论**。

四叶与原序诊断进程均已结束，检查时 18891/18894 无监听。未启动新 live 服务、未切换生产端口。

## 4. 保留 f9 全量红，定位而非刷绿

[previous-f9afb4a0/ci-receipt.json](previous-f9afb4a0/ci-receipt.json) 保存 f9 干净全量：**11575 passed / 1 failed / 81 skipped / 2 xfailed / 17 warnings，544.89s**；其他三叶绿。

唯一失败：`intelligence/tests/test_ask_call_provenance.py::test_receipt_covers_calls_and_reuses_outer_budget`。HTTP 替身原定第二次调用抛 503，却被上一测试尚未结束的 Workbench 线程抢走调用序号；**不是 503 重试策略错误**，未修改受害测试的计数或生产 LLM 逻辑。

归因链分账：

1. [单独跑 1P](diagnosis-before/provenance-isolated.txt) 只是定位对照，不抹掉全套红。
2. [保持收集/执行顺序到目标的前缀](diagnosis-before/provenance-prefix-probe.txt) 复现同一失败；[请求身份记录](diagnosis-before/provenance-transport-events.jsonl) 保存线程、endpoint、栈，不记录 body/header/key/query。
3. [后台任务归属插桩](diagnosis-before/late-runner-events.jsonl) 捕获 3 次逃逸真实 runner：quota 一次、admission 两次；credits 等多个 teardown 仍有 active。插桩阻止逃逸进入 provider/DB，因此其 1331P **不是正式全量**。
4. 修复后同类 [诊断前缀](diagnosis-after/late-runners-prefix.txt) 为 1334P/3S/1X，10324 未选；[事件](diagnosis-after/late-runner-events.jsonl) 无逃逸事件、probe_end exit 0。这只覆盖该前缀；正式结论仍取上面的**未插桩**四叶。

生产 shutdown 不等待慢 I/O 是既有策略；测试对自己拥有的有界 fake 执行 wait-join，两个语义分开。新增确定性屏障测试不依赖加长 sleep 碰调度。

## 5. 反向证据与开发读数

变异测试是“故意拆掉保护，要求原回归真的失败”，不是正常源码红：

| 套件 | 结果与范围 |
|---|---|
| [expression](mutations-expression/receipt.json) | 8 个变体，覆盖提示、修复、收据、上下文传递、外层写门、两个共享 parser，全部 caught |
| [succession](mutations-succession/receipt.json) | 7 个变体，状态限定同卡与原数学边界，全部 caught |
| [diagnostics](mutations-diagnostics/receipt.json) | 4 个变体，反馈可达与事实日期门双向边界，全部 caught |
| [fixture join](fixture-mutation-receipt.json) | 一个删 join 变体，quota/credits/admission 三个参数化用例均以生命周期断言失败；失败清理仍回收线程 |

均在新进程内替换，不改源码；`FWP_TEST_RECEIPT=0`，不用故意失败覆盖通用 pytest 收据。源码/日志哈希已核。认预期 `FAILED` 且无 `ERROR`，不强求裸 assert 输出字面 `AssertionError`；f9 的同 19 项 clean 反证也保留在 `previous-f9afb4a0/`。

开发记录不冒充冻结检查：

- `development/expression/`：初版 baseline-red 是设置问题；v2 的 3F 命中实际模板消费断言。随后 142P、244P、1041P/4S；均 b6f9cbc2 + dirty。
- `development/fixture/`：84P/7.46s，f9 + 五文件 dirty。第一次缺 join 变异丢失延迟注解，`NameError: TestClient is not defined`，**不计 caught**；v2 恢复 future annotations 后三个 owner 行为断言红。
- 一次人工二次检查器因要求日志必须有字面 `AssertionError` 而误红；真实 `E assert True is False` 是有效失败，不据此改产品或丢原日志。
- 既有 pytest 秒级命名覆盖问题未修，上一接力开发 854P 的缺失 JSON 仍未补造，见 [ba281381](../ba281381/acceptance.md)。本片按明确路径核收据，不使用全局 latest。

## 6. 仍然不能断言什么

数据存在、计算可用、工具可达、实际调用、信息送达、正文正确、方法有效是不同证明层。这里没有新的真实模型自主纠错、接力正确解释、消除偏题或完整四题交付证据；旧 semantic passed/repaired、transport completed 不能代替这些结论。

后续先修已知业务片，再用原题/原窗、新隔离 user/conversation/instance 与显式 EpisodeStore，保存 health 前后，逐层核菜单→调用→原件→引用→正文。合并和部署分别等用户授权。

非显然决策、被否方案、可迁移原则及跨仓沉淀见 [日期快照](../../../handoffs/2026-09-18-history-expression-and-fixture-lifetime.md)。
