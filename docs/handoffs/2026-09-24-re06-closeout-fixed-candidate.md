# #73 固定候选验证与主线漂移拒收

## 背景与范围

用户要求将09-23会话尾项列成TODO并依次推进。旧RE06组合b027194f1039692b8c26cacf9310619d633c54b7已落后；本轮新建独立树，将它与开工时main a54fed0d065ffdf025734a69420c1fe530615eb1无冲突合流为8088b4af776125c0ef8dbf8d9c1409e4f8aa7387。只做本地候选就绪检查，沿用原authorization-0924.json：不把readiness请求解释成push、PR、main合并、部署或自然质量验收授权。

## 执行顺序与结果

1. 固定8088定向109P、全仓Ruff通过。定向收据`20260924T124611Z-8088b4af-91a13b278848.json`。
2. 20:46 load1=9.23，高于8，未启动全量；20:51降至5.8662、已有pytest=1、空闲79785345024字节后，启动唯一完整Python门禁，未自动重试。
3. 完整门禁在21:11结束：15387P/85S/2X，collected15474，failed/error/xpassed均0，pytest exit_status=0，固定8088、dirty=false、范围未收窄。JUnit保留；脚本报告门禁绿并删除本轮显式basetemp。旧版run_main_gate只存尾部日志，本轮完整JUnit保留，未伪造完整stdout。后台启动器未直接取得最初shell退出码，launch.json明确original_gate_exit_observed=false，不补造原exit。
4. 同一干净固定版本的registry四项和ledger crosswalk均exit0，独立逐项日志/hash和前后身份保留。
5. 21:09发现其他会话已获用户授权合入#884，远端main变为4cc15e703f81bce8abadee00f68caacdb0c72b4d。其产品runtime/services/api/webapp/market_feature_store无差分，但门禁、测试和证据改变。
6. 使用正式check_test_receipt.py核验本轮收据：解释器、版本、依赖、身份、全量范围、收执对账全部通过；基座漂移6张合并超过上限5，exit1拒收为当前合入凭据。测试通过与当前准入失败分账。
7. 前端六步与E2E未启动：Python结束后负载8.72，随后10.20，高于既定8；当前候选的主线准入也已被拒。没有排自动等待/重试任务，没有本轮后台遗留。

解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
证据根：`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-8088b4/`。
关键件：`launch.json`、`python-gate.log`、`pytest.xml`、`receipts/gate-mGyjhsnG/pytest.json`、`registry/receipt.json`、`receipt-check.json`及`receipt-check.log.txt`。

## 决策与被否方案

| 方案 | 判断 | 结果 |
| --- | --- | --- |
| 独立候选固定后测试 | 身份明确，不污染主检出或原作者树 | 采用 |
| 用b027旧通过替8088签字 | 新组合不等于旧受验对象 | 否 |
| 把“测试绿”写成“可合入” | 正式基座门已拒收，且独审与前端仍缺 | 否 |
| 以无产品代码差分为由调大漂移阈值 | 会绕过当前规则，且测试/门禁对象确已变化 | 否 |
| 自动追最新main再启动全套或扩大模型预算 | 容易形成移动目标重跑，原发布和预算边界没有因此扩大 | 否；先固定后续组合与协调窗口 |

## 下一步与禁止事项

下一执行者先核main是否继续前进，再决定当前合流对象与唯一执行者。固定新提交后重排完整工程四叶；三组独审、C1-C10逐项覆盖、自然验收仍欠。本轮模型请求0，不占用旧readiness账的剩余额度。旧模型失败、旧候选收据均保留，不移签。

不要执行push/PR/生产或拿本文作部署授权；不要把未启动的前端写成测试失败；不要重复使用已清理的pytest临时目录作为证据。新增文档提交只是交接，完整测试仍只绑定8088。

工具盘点：复用run_main_gate、check_test_receipt、registry检查；未新增运行时能力。主线协调与发布授权是流程决策，不靠新增校验器或放宽旧门解决。
