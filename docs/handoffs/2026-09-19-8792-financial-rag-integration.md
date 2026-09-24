# 8792 金融候选：RAG 分帧与代码身份接缝整合

## 收尾结论与身份

用户先要求“继续”，随后授权“按照最优方案推进直至可以收尾”。本轮只接可单独验证的已提交读取片，完成代码提交、固定工程检查、反证、原件回放、证据封存和临时资源清理；**不扩大到新真实模型验收、push、合 main、部署或切生产8792**。

- 树：`~/fwp-wt-8792-financial-r6-repair`，分支 `fix/8792-financial-r6-repair`。
- 新业务：**`d8d6196baebdb1108a81ae01466e9df6397dc4fc`**，父为文档 `f70b939918aee0d9b11dd3656c88a39f855bf2c4`；前一业务 `d06dc1e8d1adf6ba8b39bd02333af6299416dc1d`。
- 仅整合 `20939b18bcb4a00f1eec9098dc52887ab1f71c02` 的 RAG（检索增强生成）响应读取片，并增加金融底座的代码身份/换代接缝测试。既有 a31 交付片、49fd 发布片不重复搬；不接整枝答案保留、runtime 或资金/历史数据祖先。
- **可作为带限制的离线整合交接收尾，不能签无保留全绿或可直接合入。** Python/前端/固定三仓原生检查有新SHA收据；六套撤保护都有完成的执行，但原发布套件并发基线180秒超时仍未归因，后续串行通过不翻该结果。宿主 registry 红与 `engineering.all_passed=false` 保留。
- 旧 R6/R3 自然验收仍 **0/4、not_passed**；本候选新 live=0、独立QC未跑。运输 completed、发布 published、金融 partial、整题正确各自分账。
- 本文及封存包是后续文档提交，不把业务成绩迁绑文档tip。旧三包与旧原件均只读。

新外置证据根：`~/.finance-runtime/reviews/8792-financial-rag-integration-20260919/`（下文 `R/`）。
仓内包：`docs/verification/2026-09-19-8792-financial-rag-integration/`。

## 按发现顺序

### 1. 选片：不能覆盖一整份较旧 worker

从干净 f70 开始，重新核并行树和代码地图。邻枝有已提交20939读取修复，也有他人的候选保留/证据审查WIP；只从提交取读取逻辑、测试与诊断器，不复制邻枝工作树。金融基座已经具备检索代码内容身份和私有空 pycache（Python字节码缓存）隔离，邻枝版本不能直接覆盖。

旧循环先用 `select` 等内核管道可读，再用 `TextIOWrapper.readline()` 读行。后者会预读：旧、新两条响应一次进入管道，读旧行时新行也被放进Python缓冲；丢弃旧响应后再次等内核，会把已收齐的当前响应误判超时。半行又会让阻塞式readline越过deadline（绝对截止时刻）。

采用一个stdout消费者：非阻塞 `os.read` 批量读取＋显式字节缓冲，先排缓存整行再等内核；整行才解UTF-8，半字符不提前解码。所有旧帧/碎片共用原绝对deadline，不续时。首次暖查询放弃保留半行；冷启动/连续第二次超时仍杀进程。没有增加超时或另造CLI取数链。

### 2. 先红、再改、再接真实消费者

生产代码修改前，新测试定向 **6F/0收集错误**：一条TimeoutError、一条UnicodeDecodeError、三条WorkerRequestAbandoned、一条AssertionError，不能统称六个断言失败。旧探针 `--expect failure` exit0复现“当前回复困在Python缓冲”，当时新测试/探针未提交，属于开发基线，不是干净f70完整成绩。

修改后读取/换代/保活三文件 **78P**；扩大到KB回执、retrieve、金融交付/发布及公开出口相关回归 **196P/3S**。后者含前者，不相加。全仓Ruff和diff检查通过，随后显式pathspec提交d8。

新增金融接缝：

- 当前帧即使已在缓冲中，仍核精确请求ID、响应代码身份与磁盘代码内容身份；缺失/错误身份及响应期间代码改变均拒绝。
- 真实子进程的崩溃/代码变更 × 恢复/冷启动超时四用例，不继承旧半行、放弃ID、连续超时及暖计数；原同mtime/size代码变化与私有pycache保护保持。`_ensure_process` AST与整合前相同，记录在 `integration-inputs.json`。
- 真 `kb_rag.retrieve`＋真实管道消费者：首次半UTF-8超时保活，第二次只交当前fresh hit，排旧响应，不另起CLI、不重复加载模型。不是mock一个TimeoutError便称接缝通过。
- 新传输测试拒绝socket连接；这些证据不证明在线索引质量或真实模型行为。`FORESIGHT_LLM_KEYCHAIN=0`自身也不等于全量零网络认证。

### 3. 固定d8全仓与跨仓检查

候选前后均 `{revision: d8完整SHA, status: ""}`，未绕依赖门禁：

| 检查 | 新提交执行结果 |
|---|---|
| Python | **12220P / 0F / 86S / 2X**，17 warnings，pytest 1169.70秒 |
| Ruff | exit0 |
| 前端lint/typecheck/test/build | 全exit0，8文件115P |
| 浏览器E2E | 34P/2S，隔离8931/8934，约2.4分钟 |
| 宿主parseability/tables/views/crosswalk | 全0 |
| 宿主registry | **exit1**，旧KB的rag-query声明不匹配；不scan倒退登记 |
| 固定三仓原生五项 | 全0，三仓身份/状态前后不变 |

精确pytest收据由本次 `pytest.log` 中唯一 `读数收据:` 指针取得：
`~/.finance-runtime/test-receipts/20260918T181016Z-d8d6196b.json`。
Python3.12.13，依赖指纹 `3328bed61f3e21ea`，dirty=false，passed=12220，exit0；八项条件校验通过，基座漂移0≤5。没有按“同SHA/最新文件”猜收据。wrapper完成于UTC `2026-09-18T18:10:18.118097+00:00`。

固定三仓：金融d8完整SHA；KB **`91725ea9ba0252a43665f9e3130142f946c289ae`**；site **`9f60bef076749cdba13cf228ffa6f22141876eb8`**。运行原生check-parseability/check/backfill-tables --check/generate-views --check/audit_ledger_spec_crosswalk，没有重扫注册表。Python/前端在原干净候选树运行；固定三仓检查不把宿主红改绿，也不签后续main版本。

### 4. 六套撤保护及一次未归因超时

继续复用 `scripts/review_probes/run_extraction_mutations.py`，新增 `--suite rag-transport`，不造第二套执行框架。每项从固定提交开独占树，唯一锚点、编译、实际非空执行、无收集错误、逐项恢复及最终整套恢复检查保留。

| 套件 | 组数 | 基线/恢复 | 红的真实分类 |
|---|---:|---:|---|
| rag-transport | 9 | 78P/78P | 6组含断言，2组期待异常未抛，1组仅测试体异常；合计10条断言、6条DID NOT RAISE、10条运行期异常 |
| publication（限定串行） | 8 | 150P/150P | 每组含断言，共24条；另1条ValueError |
| financial-delivery | 6 | 20P/20P | 21条断言 |
| financial-r6 | 13 | 91P/91P | 82条断言 |
| research-delivery | 13 | 107P/107P | 57条断言 |
| extraction | 35 | 165P/165P | 28组含断言、7组仅异常；43断言/18 KeyError/4 UnicodeDecodeError |

各分母不相加，不代签前端或浏览器。分类器逐条读JUnit message/pytest assert，不把 `<failure>` 一律当AssertionError；`pytest.raises` 的 `Failed: DID NOT RAISE` 单列，不冒充测试体RuntimeError；未知形状硬失败。原XML不改。

**原发布执行未完成，不能藏掉：**

1. `publication-mutations-d8d6196b/` 与其他检查并行时，在baseline达到既有180秒上限，外层TimeoutExpired。`complete=false, runs=[]`。runner只在subprocess返回后写日志，故原时刻没有保存baseline stdout/XML/栈；`runs=[]`是没有完成记录，**不是已证明零执行**，也没有可分类的测试断言。
2. 这没有让门误通过，runner是fail-closed；缺的是超时现场可观测性。没有改生产代码、放宽时限、判成机器慢或拿全量绿抵消。
3. 全部既有并发检查结束后，在保留的原干净树做一次详细诊断：同180秒帽，加verbose、45秒faulthandler、durations，**150P、51.19秒**。它没有复现原超时，不能给原事件归因。
4. 预先写 `publication-serial-protocol.json`，只准再做一次串行完整撤保护对照，原代码/定义/180秒帽不变，不试到绿。`publication-serial-d8d6196b/` 完成8组及恢复，基线42.50秒、恢复43.96秒；原失败目录和总wrapper中的publication exit1不改。
5. **结论仍有未归因验证限制，不签无保留全绿或可合入。** 若后续要解决它，应先为runner补持久逐步日志/超时栈证据，再冻结新运行协议做归因；不是再把本提交按同样方式重跑一次。旧事件缺失的现场无法事后补造。

### 5. 双向探针与旧R6原件

d8干净树中 `replay_rag_buffered_late_response.py --expect repaired` exit0；反向 `--expect failure` exit1，证明探针不是永远exit0。两种reader输入均只返回current、排1条stale、不杀进程。读取器标签描述装配的输入包装，不代表修复后仍调用TextIO.readline；生产实际用os.read。只是合成管道/代码身份，不调用真实KB模型。

`archive-replay-d8d6196b.json` 在新SHA重新只读R6四份原答案，12输入SHA256不变、连接尝试0；目标矛盾检出、正确计算件无误判，临时登记0/0/0/1，授权due仍2026-10-22。F2仍缺报告原文绑定。`retained_for_mechanical_inspection_only` 不是新可发布终稿，不认证自然补查、因果、来源真实性或整题正确；旧0/4不变。

## 非显然决定

| 方案 | 评价 | 结论 |
|---|---|---|
| 整枝cherry-pick/覆盖邻枝worker | 会带入未授权保稿/runtime改动，或抹金融代码身份/私有缓存保护 | 否 |
| 加长超时、sleep后再readline | 未解决内核/应用缓冲分层错配，半行仍可能越deadline | 否 |
| 直接搬逐字节诊断reader进生产 | 诊断对照有价值，不是合理批量读取实现 | 否 |
| 单消费者非阻塞分帧＋既有身份/换代 | 小范围修真实消费者；请求、代码版本、进程生命周期合同共同成立 | 采用 |
| 全量绿或后续串行绿覆盖初次超时 | 原现场证据不足，后绿不能证明首红原因或修复 | 否；保未完成限制 |
| 修改registry扫描迎合旧宿主KB | 会倒退已经确认的新登记，不是本候选代码修复 | 否；固定跨仓复验另列 |
| published自动清金融债 | 交付可见性不等于业务完整性 | 否；既有partial/view/引用/拒句账接缝重验 |

## 沉淀与清理

- 正式量具/定义已随d8入库；执行包装、分类和封存脚本仅服务这一批路径与收据，不声称通用产品框架。
- 工具包独立树 `~/harness-wt-financial-r6-repair`，核对最新gitea/main为4 ahead/0 behind后，仅改KIT/TOOLKIT，提交 **`3858a6c717f3c4c6fb03611c4f57743f189e649b`**。共享BUILD及受保护镜像未动，未push/合main。
- refs exit0，但235引用仍有26行数漂移、8未解析、1未核数，另有缺仓8/3条跳过；不称零警告。
- 方法补既有 `contract-vs-delivery-mismatch.md`，由vault自动同步 `ae4f196c`；图谱/本项目看板和一行索引为 **`7a1f53af`**。无手工push，不排除既有自动同步。
- graph audit前后exit0，只证路径/符号。vault lint前后仍20E/17W、exit1；ERROR集合一致，仅金融项目笔记420840→421890、KB笔记89155→89490的既有超长警告变化（vault也有并行作者），不签vault通过，不顺修他人条目。
- 工程、撤保护、诊断进程均已结束；8931/8934无listener。核clean后正常移除本轮固定finance/site和原超时保留的诊断树；复用KB树不动。原失败日志/收据保留，旧三包checksum均复核有效。
- 封存前只读并行身份：答案保留 **ce673a9f**、runtime **a7f5cc06**、数据 **b4757709**，均clean。它们相对开工时已有新提交；本轮未审/移入新片，不借其收据签d8。具体身份见 `closeout-state.json`。

## 后续与不要做的事

1. **本轮实现与证据已收尾，无测试仍在后台。** 保留原发布超时的未知原因、宿主registry红和自然质量失败；不能写成“已全面通过，可以合入”。
2. 如继续合入准入，先补超时现场可观测性并制定有证据的归因方案；涉及runner源码变化需新SHA和新收据。缺失旧现场不能伪造，不把资源争用当已知原因，不重试挑绿。
3. 完整保稿/有限证据诊断/runtime新片需另审最小已提交diff；不搬WIP、不重复接a31/49fd/20939。扩大组合必须另冻SHA与跨仓输入，不能拼旧枝绿灯。
4. F2真实报告取回未修；自然模型沿原预算补查复算、根预算全链、跨进程恢复/永久缺发布事件仍未验。排锁/请求写入预算、消息大小策略也不在本读取片。
5. 新live、独立QC、push、合main和部署分别确认。旧题不重发挑绿，生产8792继续不切；不改旧sealed目录、日志或本文快照。
