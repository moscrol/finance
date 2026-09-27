# #81 / #75 机械加固与新批停止

## 背景与授权

产品#832固定 `d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c`，基线 `626d8a508c1c988ff094110b371987e6afdcdd15`。工程结论仍为ENGINEERING_PASS_WITH_E2E_TIMING_LIMITS；旧两轮E2E红、n=1对照限制和后来main集成未验均不变。文档单独在#892，不把文档头当产品头。

用户在49请求旧批交付后回复「执行」，授权先加固真实退出、结构报告和实际pytest/SQLite准入，再开一批有限#75。归档时用户「继续」承接文档收口，不扩成自动新模型批。#76、合并、部署8792及生产写入均不在授权内。

## 发现顺序

1. 新建 `~/.finance-runtime/reviews/pr832-glm-qc-20260923-2355/`，独立clean候选；只继承公开主张/差分/工装，不复制旧审查探针或结论。旧2255批不可变。
2. 取消模型自由bash，inspect仅rg/ls直接argv、拒rg进程预处理；run_tests固定解释器/参数/七作者文件/独占tmp，记录OS真实exit、输入哈希和JUnit。模型可新建探针，不能覆盖旧探针、改正式回归或自选pytest跳过参数。
3. 用pi终止工具submit_report及结构约束替自由文本JSON；宿主绑定身份、生成必需文档，缺探针或缺执行不得续阶段。阶段能力双检查，工具串行，22请求或450秒触发唯一提交专用请求；每阶段24/600秒、请求120秒、重试0、全批152。
4. 两轴实际准入均2P，SQLite文件/WAL和嵌套tmp通过；必红exit1、stdout谎报EXIT=0仍exit1，读写/网络/阶段/缺交付拒签对照通过，零模型。只补必要父目录metadata，不放开内容或网络。38件最终工装锁定；Ruff初次F401后移除未用导入再通过，未支持的toolExecutionMode设置封存前移除，真正串行靠Promise队列。
5. 新批实际UTC16:09:24至16:16:43（CST09-24）：gateway4请求通过；Spec explore22普通请求后1次强制submit_report，约412.453秒。总27请求，全部完成/对账，无HTTP失败、自动重试或墙钟超时。controller按缺探针交付停止整批。
6. 报告JSON合法，REPORT.md/EXPLORE.md确实落盘，终止工具没有多发下一请求；但零探针、零产品测试，六项全not_verified，Spec execute/report与Quality全NOT_STARTED。execution中的report_structural=false代表完整交付不满足，不是JSON语法错误。根QC为BLOCKED_EXPLORE_NO_PROBES，不是产品失败或供应商不可用。
7. 进度日志第21请求自报「用了16次」，实际账本22后准时切收尾。硬预算能阻止超额，不能保证有效产出。未实现权威剩余额度逐轮提示，也未强制较早首探针检查点；不再靠一句「记得留时间」或直接加帽重跑。
8. 宿主核证另发现read先由文件助手分页，再被公共命令输出尾截断；400短行仅显示51-400。长UTF-8页还被底层48000字节切断，而尾标仍标原选择终点。模型「完整读1050行diff」不采信。独立副本v1保留初步修正，v2完整修正read不再二次截尾、完整行限字节、实际next_offset、超长单行显式拒绝；短400行一读、长400行两读均完整无缺重，零模型。封存spec/quality文件和旧失败未改，不把此修正补成审查通过，也未证明它造成全部读数消耗。
9. 112个阶段产物哈希、38封存输入及候选/作者首尾clean同头均核实。模型/controller退出，19899无监听。原44工程+371旧批件不变；新342件/1246030字节入独立子清单，字节按源码/日志原样封存，不美化空白。main已到5bf47a5ae9aa，未追逐它重取产品身份。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 在旧失败会话补文件/继续剩余预算 | 追溯改写失败且混合工具版本 | 否；新授权新批，旧原件完整保留 |
| 继续提示bash勿包装退出 | 模型已实际违反提示 | 否；直接argv目标exit与stdout分账 |
| 正则从自由终稿抢救JSON | 运输成功可能冒充交付 | 否；typed终止工具，缺项只交BLOCKED |
| import/touch准入 | 未触达真实pytest/数据库需求 | 否；真实收集、文件库/WAL及反向控制 |
| 合法报告就放行 | 空探针的BLOCKED同样可合法 | 否；结构、交付、行为结论分开检查 |
| 立即扩大帽并恢复新批 | 不能解决误计额度/零产物，且违背失败即停 | 否；先补进度里程碑，后另授权 |
| 原地修本批read工具 | 破坏执行时输入哈希 | 否；独立副本零模型前后对照 |

## 证据与后续

仓内入口 `docs/verification/2026-09-23-react-trace-chain/README.md`；新包 `receipts/independent-qc-hardened/`：SUMMARY/MANIFEST、host-review.json、PREPARATION、两轴准入、spec/explore原件、read-delivery-control-v2。原始流式events留外部并由execution.json哈希绑定；不提交凭据或库。固定解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

下一批先将 `read-delivery-control-v2/after/{review.mjs,file_tool.py}` 的读取修正并入新配方，增加宿主权威预算/产物计数及早期可运行探针里程碑，并离线验证缺产物不能继续纯阅读；重做两轴准入与封存，再取得新的有限模型授权。旧批不可恢复，也不能复制旧作者夹具当新独立证据。C6真实出口、幸存定义无条件断言、恢复顺序及N条豁免仍待真正独立执行。

工具盘点：执行硬检查、结构交付、准入和读取反例均有可运行源码及原件，不仅是方法提醒；仍是绑定本候选的私有运行器，不宣称通用组件或全阶段真实模型验收。共享harness-reference主树领先且BUILD.md他人未提交，未修改它；跨任务方法补既有证据卫生知识卡。产品保持WIP，不合main、不启动#76、不部署、不写生产、不干预他人工作树/进程。
