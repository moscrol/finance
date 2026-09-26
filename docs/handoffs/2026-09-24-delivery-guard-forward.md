# #71 结构绑定守卫前向组合

## 身份与结论

受验代码 `2749f2d25b63eac8091e28e1311689101f3a82ad`，双亲为 `4cc15e703f81bce8abadee00f68caacdb0c72b4d` 与 `5de303619711995ff6f864487336b7538e6031da`。分支 `fix/delivery-guard-forward-0924`，本地树 `~/fwp-wt-delivery-guard-forward-0924`。

**本地工程检查已齐；独立审查和新真实金融验收未完成，未推送、未开本轮 PR、未合 main、未部署。** 本文之后的文档提交不继承或改签代码收据。原真实 K3 输出将 0.7474 抄成 0.7473，且自选列名曾绕过旧词表；冻结原件保留，新工程绿不能翻案旧真实失败。

## 发现与处理顺序

1. 以固定 main 4cc 合入候选 5de，出现十二文件冲突。没有接管旧作者树，也没有整文件选边。
2. 保留候选的算术结构绑定、期间限定、局部替换/未定位标记和本回合披露证据身份；同时保留主线的基点/百分点约束、金融拒句、引用资格及修复债务。
3. 初始对照 26 项失败。跨枝整合先修单位语义，再对齐通知、旧格式断言和资金工具 I/O 声明；没有靠撤掉原保护取绿。
4. 新增真实计算产物的 14 个交叉用例。基点/百分点即便数值恰好相等也不认证绝对比率；同报告期有效产物不能掩盖另一个已知不适用产物。
5. 变异定义由 61 组扩至 65 组，修复合流后的旧锚点；保留主线 runner 的超时、日志、JUnit 和进程组证据合同。移除了初次误列的不存在测试文件，原 no-tests/exit4 仍留档。
6. 提交首轮超时遗留 index.lock。单独路径扫描通过，lsof/ps 确认锁无持有者后移到外部证据目录保留；第二次提交因锁 exit128，第三次完整门禁提交 exit0，未跳 hook。
7. 固定 2749 后复跑定向、65 组撤保护及恢复、完整 Python、前端/浏览器和注册表。所有收据均绑定本候选，不移用 #813 或 #73 的结果。

## 决策对照

| 采用 | 否决 | 理由 |
| --- | --- | --- |
| 结构识别之后仍检查单位与期间 | 算术吻合即认证 | 结构只回答对应哪个量，不能把 bp/百分点认证成绝对比率 |
| 空集合表示已知但不适用的产物 | 与没有产物合并处理 | 同期有效产物不能静默覆盖不适用产物 |
| 单位不可比记 unverified，可比数值错误记 mismatch | 所有拒绝归同一原因 | 影响公开通知及后续修复动作，不只是测试文案 |
| 保留 capital_data 的 external_or_mixed 声明 | 默认 unknown 替代主线声明 | 不能因合流弱化 I/O 权限边界 |
| 真实产物交叉用例和逐保护红绿对照 | 只拼两枝既有绿测试 | 新入口可能绕过旧单位规则，必须验证交集 |
| 固定树跑完整 Python，同 SHA 另检出跑前端 | 在 Python 受验树同时生成前端产物 | 防止 ignored 构建文件改变测试现场 |

## 验证与收据

统一证据根：`~/.finance-runtime/reviews/pi-closeout-execution-20260924/delivery-forward/`。

| 检查 | 结果 | 入口 |
| --- | --- | --- |
| 固定定向 | 1106 passed，0 failed/error/skipped | `fixed-2749f2d.xml`；标准收据 `~/.finance-runtime/test-receipts/20260924T141048Z-2749f2d2-1130cdff034d.json` |
| 研究交付变异 | 基线758P；65组有效断言红/恢复绿；最终758P；132次子运行，无收集错误/超时/跳过，文件哈希逐个恢复 | `mutations-2749f2d/results.json` 与每次 JUnit/日志；外层 `mutations-01.process.json` exit0 |
| 完整 Python + Ruff | 16049 passed / 85 skipped / 2 xfailed，collected16136，0 failed/error，无过滤，干净树 | `full-python-receipts/gate-eQJ5cUWh/pytest.json`、`full-python.xml`、原始 pytest.log.txt |
| 原门禁进程 | exit0，1046秒，未超时，进程组已退出；自己的显式 basetemp 由全绿门禁清理 | `full-python-01.process.json`、`full-python-01.log` |
| 正式范围/身份/漂移 | `--expect-revision 2749... --require-full-scope --base-drift-max 5` exit0 | `full-receipt-check.log.txt` |
| 前端及浏览器 | 六项命令exit0；120单测；34 E2E通过、2跳过；前后同SHA且clean | `frontend/frontend.json` 及六份日志；树为证据根内 `frontend-tree`，端口19951/19954已退出 |
| 注册表/台账 | 按当前CI工作流的五项检查全部exit0 | `registry-complete/receipt.json` 及各项原始日志 |

解释器为主树 `.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`。22:12完整门禁启动前 load1=6.93，预计pytest=2；22:29结束。末次远端main核验仍4cc，不放宽漂移阈值。完整测试的17项 warning 原样保留，未扩大范围修它们。

工程结论只对上述固定 SHA 和这次环境成立。变异外层 process JSON 未解析 JUnit，测试分母必须读取内层 results/JUnit，不能把 null 当零执行。

## 其他队列与记忆

- #813 原执行者 3c5/continue-08 四叶和整库演练完成；本轮在正确固定树上正式校验其收据 exit0。首次从协调树检查被身份门拒收，不记成产品失败，也未重复跑其测试。
- 能力图把本交付链与 #81 测试引用改指当前本地候选。graph_audit 第二次exit0；305条断言中254条为在途/未校验提示，不代表全图能力验收。全库 vault_lint 的其他旧错误仍未解决。
- 方法补入 `agent-memory/10_knowledge/validator-bound-to-producer-chosen-labels.md`：结构识别不能代替量纲检查。

## 下一步与禁区

1. 对固定2749或明确的新组合完成所需独审。新增模型预算未获本轮授权，不能借“继续”扩大额度。
2. 新自然验收须从真实 Workbench 入口复核模型自选比率列名、抄数、当期/同期，以及披露负面断言与本回合证据绑定；离线冻结稿与作者测试不代替它。
3. 合入和生产仍分别确认。主线再移动时先复核组合身份/漂移，不自动循环追主线重跑。
4. 其余14项队列见协调树 `docs/handoffs/2026-09-24-pi-closeout-TODO.md`；#877仍是真实八问失败，#61仍欠生产前置，不把本单工程绿横向借用。

工具盘点：业务与测试进入现有模块，65组变异、前端门禁、注册表均复用既有工具。外部 run_logged.py 只是现有 `_run_logged_command` 的本轮参数包装；Git冲突与业务单位归属仍需语义判断，不新增自动批准器。harness-reference/BUILD.md有他人改动，本轮不覆盖。
