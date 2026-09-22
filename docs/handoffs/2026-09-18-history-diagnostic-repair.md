# 历史研究返修一：诊断可达，但不绕过事实门

## 背景与当前边界

承接 [真实四题失败快照](2026-09-18-history-market-anatomy-live.md)。第一题把 `stage_day` 放入metrics，finance_query本已有字段角色重试提示，却被严格日期门因空evidence抹成“未取得有日期材料”；市场类比漏`entity_kind`又被笼统“不支持”误导。这里修的是**反馈送达和具体错误定位**，不是放宽范围或替模型猜对象。

本轮运行代码 `a05b3483`，固定完整被测提交 **`58b785421195da707a74e1fe84fb59570f04b91f`**（后者只修遥测测试预期/对照）。四叶通过，**没有重跑真实四题；业务仍沿用fbd8拒收**。未合并、未部署、未改生产行情库/用户画像/每日写入链。代码地图仍empty/refused_empty，不将它作为架构不存在的证据。

## 按发现顺序

1. 先归档fbd8失败原答、原件哈希、调用/引用索引和四叶，提交3ac74ef5；19968cd4补交接，已推WIP #783。原失败没有被润色替换。
2. 以临时库复现strict历史查询的字段错位，发现空evidence同时用于“无可交付事实”和“参数错误”，日期门缺了类型区分。首批夹具复用task_id受query ledger影响，改独立ID，避免把去重缓存当实执行。
3. 新增冻结`ToolDiagnostic`，只从受审定的finance失败生产者生成；普通observation与evidence仍过事实门，诊断在门后添加、不发E号。时间授权、写工具权限和下游预算不变。
4. 进一步检查诊断入口：字段名/dataset或原始异常可带任意正文。新增白名单校验消息与标识符清洗，不把raw异常贴个标签送进可信通道。
5. market参数错误现在指出所选类型、所需精确代码、不兼容与支持特征；`000001.SH`不是sector/stock。没有按代码暗推类型，没有改相似度/接力公式。
6. 新测试真实跑注册表/批工具/ContinuousAgentEpisode/临时DuckDB/RunStore；脚本消费者看见提示后显式改参，非真模型自主研究。早期脚本finish错称single_case而无history原件，按合同改为insufficient_evidence；另一夹具问法未触发历史意图，改成实际目标问题并断言history_intent存在，没为测试改路由。
7. 相关回归808P/12S、Ruff和提交门通过后冻a05b3483。四个进程内变异均抓住，但全量发现两条工具饥饿遥测测试仍期待旧文案，Python11529P/2F，其他三叶绿。保留整个失败节点。
8. 58b78542只更新遥测测试：新诊断标记+无sink/正常sink/写失败sink输出一致、无证据；独立task ID防对照吃缓存。49项定向通过，再冻新SHA完整重跑四叶，11531P/81S/2X/17warnings，全部退出0。
9. 两次全量runner均结束后才归档；4个变异新SHA重验，原件/日志哈希一致。没有因为四叶绿再盲跑真模型。

## 方案对比

| 问题 | 采用 | 被否与原因 |
|---|---|---|
| 诊断被事实门吞 | 显式程序反馈类型、门后渲染、不作证据 | 错误状态或空evidence直接放行prose；会让未知日期事实借报错洗入 |
| 诊断内容 | 审定构造者+白名单消息/schema角色+标识符约束 | `str(exception)`原样入“可信诊断”；外部/模型文本不是可信控制信息 |
| market漏类型 | 拒绝并说明如何显式修正 | 按指数代码推类型、删不兼容特征；两者擅改研究对象/口径 |
| 证明反馈送达 | 真实Episode接线+脚本消费者断言+真实临时查询 | 只断言helper生成提示；中间过滤/预算仍可吞它 |
| 测试强度 | 新进程内单点变异、哈希验证不改源文件 | 在正式树改坏源码再回滚；会污染并行测试/缓存 |
| 全量新失败 | 保留红收据，更新合法接口预期并增强对照，再冻新SHA重跑 | 把两红叫存量、不跑它们、用808定向替全量 |
| 真模型复验 | 等未修业务片完成后原四题新根 | 不改接力/特征就重复抽样；不能修选择偏差 |

## 验证入口

[58b78542验收说明](../verification/history-market-anatomy/58b78542/acceptance.md)、`manifest.json`及四叶原始日志均在同目录；含`previous-a05b3483/`的正常回归失败、`mutations/`的故意反向失败。

- 固定58b78542：Ruff、Python11531P/81S/2X/17warnings（494.49s）；前端107P及lint/typecheck/build；浏览器34P/2S；registry五项0、98存量warning。
- 正式pytest收据 `~/.finance-runtime/test-receipts/20260918T071557Z-58b78542.json`，八项校验通过；前后clean。后续文档提交不能代签新的全量SHA。
- 新/旧工程根：`~/.finance-runtime/history-diagnostic-58b78542-checks/`、`history-diagnostic-a05b3483-checks/`；变异在同前缀`-mutations/`。umask022/清环境/主树venv解释器，非CI容器同环境声明。
- 测试30个新增参数化用例不等于30个真实研究样本。作者脚本Episode、算术第二实现、真实模型和独立人员QC仍分层。

## 下一步与不能做

未修：接力immature误读、各类状态正文消费、异窗rank、成员路径不等于个股启动、同口径启动特征/失败控制、主动读取历史原件与输出模板偏题。

只读旧四轮合同的新索引 `saved-task-contracts.json` 显示：四轮均comparison_analog，必答为直接判断/反证/证据边界；第四轮增加可选量能资格和近5日量能台阶。没有证据支持“required已被公司矩阵覆盖”的强断言；下一小片应追实际提示/输出合同，而不是凭偏题反推根因。

接力公式不动：immature=源峰后不足5个观察交易日，不是失败；源峰不要求先回撤确认；收益同源峰后5日，不是目标启动后5日。不得放宽日期门、从助手旧答授权、换题/换窗制造成功，不得把此轮工程绿记为四题通过。

## 沉淀盘点

- 新增进仓变异工装 `scripts/review_probes/history_diagnostic_mutations.py`；可迁移的是隔离进程/反向不变量/失败分类，不是金融字段或提示。harness自有分支登记 `de8c93c` 已推未合，KIT/TOOLKIT一致；共享BUILD和保护镜像未碰。check_refs缺失0，仍26行数漂移/8未解析/1未核数，分支脚本另用git show/AST核过。
- 反馈门与事实门的分型原则补入既有 `agent-memory/10_knowledge/retry-must-carry-the-last-rejection.md`，不建第二篇同义知识；由vault自动同步b8fafdba。单次研究失败仍在项目验证层，不写成通用金融规律。
- vault_lint仍19错/17警告（含既有元数据/镜像问题），没有顺手修改保护区。一次性工程runner/打包器留runtime，不伪装通用业务判官。
