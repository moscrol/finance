# 行情恢复 GLM 独立质检证据

状态：**HOLD，不是合入或生产批准**。本轮没有业务代码修改。

## 身份与范围

- 固定候选：`50330cf4fa435292bbd555ccc817e62ca5cc45b4`；tree `9b8d5d99baecd1fc6e48307e27ed46f14279e594`。
- 组合基座：`b59d6eed0356ae093b52bd291ab328628de8790e`；另一 parent 为修复分支 `32a7d2031585a7a3dbb1564f87e4ffb483a304c9`。
- 验证引用：`refs/verification/market-recovery-glm-b59-20260923`。
- 全仓运行时 main 已前进到 `f47d464eb`；最终观察到 `e926157d9dfa33336d71150d13fb7d9c387659e2`。报告只签固定候选，不移签这些后继版本。
- 原始运行根：`~/.finance-runtime/reviews/market-recovery-qc-20260923/glm-50330cf/`。候选工作树保留。

## 最终独审

| Claim | 探针来源与结果 | 作者测试 | 选用报告 |
|---|---|---|---|
| F1 | 旧独立探针逐字节重用，5P | 28P | [报告](zhipu-v1/F1-report/delivery/report.json) |
| F2 | GLM 新交付，16P | 75P | [报告](zhipu-v1/F2-report/delivery/report.json) |
| F3 | GLM 新交付，6P | 28P | [澄清报告](zhipu-v1/F3-report-clarified/delivery/report.json) |

三项均为 `PASS_WITH_LIMITS`。对应探针合计 27P，作者测试 131P，三次故意失败阳性对照均检出。作者成绩不替代独立覆盖；F1 的多次重跑不累加成新测试。机械对账见 [validated.json](zhipu-v1/validated.json)。

F2 实测成员及板块外 bar 的 NULL、NaN、正负无穷、零、负 close，以及成员缺 bar；四张派生表都种入目标日和另一日期，比较完整逻辑行。冻结分母的非交易身份有正向对照。F3 的拒绝路径比较两日完整逻辑行，包含缺 policy、三种真值非布尔值和默认旧计划；literal True 替换有正向对照。

F3 原报告有超出证据的描述，原件仍在 [原报告](zhipu-v1/F3-report/delivery/report.json)。澄清版明确：旧计划是手工模拟，事务顺序主要来自源码检查，没有双连接交错、事务边界埋点或部分写入后故障注入；最后一次拒绝只再次比较目标日。SQL 值相等不是物理字节相等。澄清启动器首次参数签名错误发生在请求前，日志和修正版均保留。

## 通道分账

- 初版 `fomo/glm-5.3` 两场本地适配失败：零请求预占，零交付。
- `adapter-v2/` 修正扩展所需字段后，两次连接均失败；配置的 `127.0.0.1:54340` 当时无监听。不是 GLM 全局不可用。
- 依据项目必读记录和现有 launcher，找到智谱直连及既有 Keychain 凭据。未改全局配置、未重启网关或生产服务。
- `zhipu-v1/` 固定 `zhipu/glm-5.3`，真实流式请求、无 temperature，每阶段上限 4 请求/600 秒、无自动重试、并发最多 2。六阶段实际共 12 请求、12 条 HTTP 200、2 份新探针、4 份报告原件，最终选用 3 份 Claim 报告。
- 本轮总请求预占 14，包含 fomo 的 2 次失败连接；澄清启动器本地错误不算模型请求。没有追加 K3 请求。
- 接入与交付门自测分别通过；初版适配回退被新增自测捕获。凭据只在内存读取，fomo 四场 42 文件、智谱六场 100 文件的精确凭据扫描通过，包含 Pi auth/models 文件。零价格字段只是 SDK 必需占位，不是实际计费证明。

## 历史缺陷敏感度

旧探针本轮复跑 20P；五个单文件历史回退检出 20 个行为失败，另 3 个旧 API TypeError 单列排除。见 [旧探针回退](mutations/summary.json)。

新 F2/F3 探针又针对三处历史回退执行，分别检出 13、12、6 个行为失败，共 31，零 collection error、零 API 形状错误。见 [新探针回退](zhipu-v1/mutations/summary.json)。这些是历史版本上的重复试验，不是新增 31 个独立测试。八棵本轮敏感度工作树已清理，验证 refs 保留。

## 全仓门禁：红

[Ruff 与 pytest](full-gate/execution.json)：**14874P / 1F / 85S / 2XFAIL，0 error，14962 collected**。pytest exit 1，门禁耗时 2039.225 秒。唯一失败为 `intelligence/tests/test_finance_query.py::test_timeout_interrupts_connection`，约 1.105 秒超过 0.5 秒断言，见 [失败原文](full-gate/failures.json)。[单次隔离诊断](timeout-diagnostic/execution.json)为 1P，不能替换全仓红收据，也不足以断言是环境原因。

[原始收据](full-gate/gate-UtG3vrT9/pytest.json)使用规定的 Python 3.12.13，依赖指纹 `3328bed61f3e21ea`；目标是候选仓根，没有 -k/-m/ignore/deselect/maxfail 收窄，收集对账、revision、解释器、依赖、干净树检查通过。[收据复核](postflight/receipt-check.stdout)仍因零容忍基座漂移被拒。任一原因都足以阻止合入。

消费/技能注册表、解析和交付门检查通过。相对组合基座无前端差异，未跑 frontend/E2E，不宣称所有 CI 叶子全绿。更早 `257263f` 的全仓绿仅属于那个旧候选。

## 封存与未验证

`manifest.json` 校验 389 个归档条目，连同 manifest 本身共 390 文件；`raw-manifest.json` 记录并复核 417 个原件哈希。README/交接是其后的人工说明，不在该机器清单内。脚本加 `.txt` 防止被 pytest/ruff 当作仓内代码；映射见 `archive-renames.json`。完整 packet、events.stdout、credential.json 和全仓 XML 保留在原始根，归档只留其哈希；不归档 auth/models 凭据配置。

本轮进程已结束。旧漂移候选工作树已清理；本轮 postflight 因全仓红没有删除 pytest scratch，收尾时 `/private/tmp/pytest-of-a77/pytest-1830` 已不存在，删除者未查证，不能记作本轮主动清理。

未验证/未授权：F1 真实子进程与日志落盘；F2 无中间写入的动态证明、默认 daily 路径与其他字段；F3 并发、完整输入指纹和部分写后回滚；真实 nightly/恢复 CLI、staging、换库和生产验收。五问 (a)-(e)、三合同、5553/5565 范围及 53 只公司行动处置仍待用户确认。没有合并、推送、部署或写生产。
