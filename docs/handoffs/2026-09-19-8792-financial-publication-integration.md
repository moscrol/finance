# R6 财务候选 × 精确发布边界｜2026-09-19

## 背景与结论

继续本地 `fix/8792-financial-r6-repair`，从干净文档提交
`0b16bc037d635fefaea39f42c1202e3f474a9be4` 出发；旧业务为
`d965721553741b7a1267b8541e7806d088083a8f`。前轮已移入数据枝
`a31b572f` 的交付保护，不能重复计为本轮工作，也不是资金/历史整枝合流。

本轮只移入答案保留枝 **`49fd8d726176a1e97eb43ed028bda93edc64f657` 的发布片**：
API、UI、SSE、probe 及配套测试；静态前端在本树重新构建，与该枝 `7a9380bd`
产物逐文件相同。Mapping JSON 边界修复在本金融树已等价存在，没有重复搬入。
没有搬完整答案保留、RAG读取、runtime最新代码或他人WIP。

新业务提交 **`d06dc1e8d1adf6ba8b39bd02333af6299416dc1d`**：
`fix(financial): integrate exact publication barrier without clearing repair debt`。
作者工程在固定三仓输入条件下通过；**宿主 registry 红灯和 engineering.all_passed=false 保留**。
本候选没有新真实模型运行或独立QC，旧R6/R3整题仍 **0/4 not_passed**。
没有push金融/工具包、合main、部署或切换8792。

## 发现顺序与有限修改

1. 重核并行树提交/归属。答案保留最初已干净到RAG修复 `20939b18`，旧交接比代码旧；
   不根据旧文档称其仍未修，也不凭提交标题借用验收。最终只读观察为文档 `ad459ad0`。
2. 只搬发布测试先验红：后端13F/132 deselected，前端8F/107P。
   后端7个缺publication字段的KeyError、1个缺事件的ValueError、5个断言失败，均非收集错误。
   前端原命令 `pnpm test -- --run ... -t ...` 实际跑了整个115项套件，不能写成定向8题。
3. 移入发布代码，不移动 `_claim_terminal_run`：它仲裁完成/失败/取消归属，必须先于发布。
   `publication` 单独表达 pending/published/not_applicable；精确核同用户助手及最后事件的
   run/conversation/message/role/status。报告文件存在不能替代最终事件，失败/取消也不强求报告。
   观察提交事件后重读run，防把旧半成品产物列表标published；SSE两读之间出现的事件要先排空。
4. 新金融组合测试 `test_financial_publication_integration.py` 通过实际有限核验器产生partial，
   再走真实会话编排、存储和API；脚本化runtime，不调真实模型。
   用线程事件固定「report写前」及「message.complete写前」两窗口，正常与可信稿恢复各覆盖。
   安全正文、正确差值、合法复查日及引用保留，坏差值不公开，拒句账/metric补修债仍在；
   run/message虽completed、发布虽published，report/业务/答案仍partial。
   恢复投影直接用本轮已核验稿，不声称新自然异常续修或跨进程恢复。
5. 首次组合4F/145P来自新测试请求漏传必填skill_mode，不是产品缺陷；修夹具后4P。
   相关开发回归417P，前端115P、lint/typecheck/build通过，Ruff通过；开发成绩不代替固定提交。
6. 复用 `run_extraction_mutations.py --suite publication`，新增8条撤保护定义；原四套SUITES保留。
   不另造运行框架。API/UI/probe生产源码与49fd对应片完全一致，业务门/公开view出口未放宽。
7. 固定干净d06后运行完整检查、五套撤保护、固定三仓registry及R6只读回放。
   所有后台已结束，工程PID44817不再运行，8931/8934无listener；临时finance/site检出已正常移除，
   复用KB树未动。工程前后SHA和status相同。

## 方案对比与决定

| 方案 | 评价 | 决定 |
|---|---|---|
| 把run终态claim移到所有产物之后 | 会改变取消/完成竞争归属 | 否 |
| sleep延后前端取货 | 依赖写盘速度，慢IO仍会提前收口 | 否 |
| 只看report.json或任意终态事件 | 文件可能半套；他轮/他消息事件不能授权本轮收口 | 否 |
| 既有最后消息事件＋精确身份＋观察后重读 | 不建第二写入链，保持既有仲裁和写序 | 采用 |
| published升级金融任务完成 | 把运输可见性冒充研究完整性 | 否，保留partial及补修债 |
| 并行枝整包合流 | 会扩大到保稿/RAG/runtime新行为及未签接缝 | 否，仅49fd发布片 |
| 以固定KB检查覆盖宿主registry红 | 依赖输入不同，不可迁绑 | 否，两份结果分账 |

可迁移原则：**终态归属、发布可见性、业务完整性是三份合同**。一个任务“结束了”不表示
结果已经全部可读，更不表示内容正确；发布证明必须绑定最终读取对象，不能装饰旧快照。

## 固定版本验证与原件

原始根：`~/.finance-runtime/reviews/8792-financial-publication-integration-20260919/`。
本轮包：`docs/verification/2026-09-19-8792-financial-publication-integration/`。
原日志、XML和R6封存输入不改写；包内文本只是明确声明的展示副本，双hash/字节数及转换见manifest。

| 检查 | d06dc1e8结果 |
|---|---|
| Python全仓 | **12198P / 0F / 86S / 2X**，17 warnings |
| Ruff | exit0 |
| 前端lint/typecheck/test/build | 全exit0，8文件115P |
| 浏览器E2E | 34P/2S，隔离8931/8934 |
| 宿主原生五项 | registry exit1，其余0；汇总all_passed=false |
| 固定三仓原生五项 | parseability/check/tables/views/crosswalk全0，身份状态前后不变 |
| 收据条件校验 | 精确SHA/解释器/Python/依赖/干净树/未绕门/基座漂移等8项通过，漂移0≤5 |

完整收据：`~/.finance-runtime/test-receipts/20260918T170550Z-d06dc1e8.json`；
Python3.12.13、依赖指纹3328bed61f3e21ea、dirty=false。
同SHA另有 `20260918T165836Z-d06dc1e8.json` 的**0执行**收据，不用它证明覆盖；
选择依据是本次pytest.log中的精确指针，而不是“最新文件”或SHA相同。
首次收据检查把文件秒数误写为170551，exit2未校验；原失败日志保留，随后检查正确文件通过。
这不是重跑pytest，更没有覆盖首次工程结果。

固定跨仓版本：finance=d06dc1e8d1adf6ba8b39bd02333af6299416dc1d；
KB=91725ea9ba0252a43665f9e3130142f946c289ae；site=9f60bef076749cdba13cf228ffa6f22141876eb8。
宿主旧KB与登记不一致，**没有scan倒退登记**。固定目录只跑原生registry/crosswalk，
Python/前端在原干净候选树运行，不把两种环境混称同一全绿。

### 五套撤保护（都签新业务SHA，分母不相加）

| Suite | 组数 | 基线/恢复全套 | 失败类型 |
|---|---:|---:|---|
| publication | 8 | 各150P | 每组有断言失败，共24条；SSE等待组另有1条缺事件ValueError |
| financial-delivery | 6 | 各20P | 每组有断言失败，共21条 |
| financial-r6 | 13 | 各91P | 每组有断言失败，共82条 |
| research-delivery | 13 | 各107P | 每组有断言失败，共57条 |
| extraction | 35 | 各165P | 28组有断言、7组仅异常型；共43断言/18 KeyError/4 UnicodeDecodeError |

均complete=true，非空测试体失败、无收集错误，逐项/全套恢复后通过，临时树干净移除。
默认异常型仍M7/M14/M23/M30/M31/M34/M35，不把JUnit failure一律叫AssertionError。
归档初稿只看failure.type，但本次pytest XML根本无此属性；无效分类稿保留外置并明确invalid。
正式分类看message显式异常前缀或pytest的assert表示，未知形状即拒绝归类。
Python运行器不替代前端测试或浏览器验收。

### R6只读机械回放

四份原答案目标矛盾检出，原正确计算件无误判；12输入SHA256不变、连接尝试0，
临时登记0/0/0/1，授权项due=2026-10-22。剩余文字仅机械检查，不是新最终答案或完整Episode。
F2官方报告实际取回未修；有限门不认证因果、多主体、隐含期别、任意公式或来源真实性。
旧两验证包SHA256SUMS全部复核通过，旧live 0/4不改判。

## 并行观察，不是整合或验收代签

- 答案保留最终只读HEAD=`ad459ad09459ecaa48df2ee97a576d0aa0acbb97`，业务20939b18。
  其新交接记录RAG工程通过及一次GLM已发布，但整体仍not_passed，畸形格式首稿未保留、
  金融质量有错；这是作者的邻枝证据，不是本候选新live，也不把旧“RAG未修”继续当现状。
- runtime最初e20f5c1d/6b70e540，途中存在他人证据恢复WIP；封存前已新提交到
  `89f8d72744a64417fe979561c3c49aa00e1c6bb8` 且干净。
  本轮未审该新片、未搬运、未验证；旧交接仍签6b70，不迁绑到89f8。
- 数据枝b4757709/a31b572f；交付片此前已在，不等于整枝资金/历史已在。
- 这些是只读身份/交接核对，不是跨作者协商一致或完整并行合流。

## 沉淀与清理

工具包独立树提交 `78ec62260359f996b83cefdca2c08ab7759b11af` 更新KIT/TOOLKIT，
沿同一撤保护入口记录发布接缝。check_refs exit0，但235条引用中仍有26行数漂移、8未解析、
1未核数；不是零警告。共享旧树BUILD.md他人改动及vault受保护镜像未碰。

方法补入vault既有 `atomic-name-claim-is-not-complete-publication.md`，自动同步7457f945；
能力图谱与项目看板/一行索引自动同步86eb21ba。本轮未手工push。
图谱审计前后exit0只证路径/符号。vault lint前后仍20E/17W、exit1，错误集合相同；
唯一诊断差异是项目页既有超长WARN字节数420524→420840，原差异保留，不称vault通过。

新JSON收据逐字节复制；文本展示副本仅去行尾空白及EOF多余空行，保原/副本各自指纹。
有限私钥/GitHub token/API key/Bearer模式扫描不等于通用秘密认证；具体数量见manifest。
封存器一次性在证据根，不是产品框架；机械回放/变异定义已正式入库。

## 下一步 / 不要做

1. 审并行最新**已提交最小片**及其实际证据，特别是保稿、RAG、runtime恢复；不重复搬49fd或a31交付片，不碰WIP。
2. 若扩大组合，冻结新业务SHA/跨仓输入后重跑工程及全部相关SUITES，保view唯一出口、安全正文/引用、拒句账和补修责任。
3. 新真实模型验收、独立QC、push、合main与部署分别确认；原预算、题集、首发零重采样规则另冻结。
4. 不拿published/计算正确/注册成功替整题质量，也不拿邻枝新模型结果替本候选验收；生产8792继续不切换。
