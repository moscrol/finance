# 研究尾单前向整合：小片先行、领域分开

## 背景与授权

用户在昨日尾单盘点后要求“你按照最优方案推进”。本轮负责 #797 财务比例、#798 运行时证据、#800 历史研究的前向整合；原分支的末端修复依赖尚未进 main 的大块父实现，不能只摘一两个末端文件。主工作区 detached 且有大量他人改动，未碰。每条线使用独立 worktree，来源现场/失败原件不改。

授权不含合 main、8792部署、夜跑装机、生产回填、删旧树或新增付费外审。ReAct、归属回填、adaptive、Arena、夜跑由原接手线继续，本轮不重开其受阻审核。历史证据绑定孤儿片原样推送到 WIP #829（9fabd688，base=fix/react-trace-closeout-0921），只建立可追踪入口，不塞回 #809、不据此关闭 #793/#794。

## 按发现顺序

1. 抽出两项可独立验收的小片：测试夹具自己拥有的 Timer 生命周期；code-map 原始查询加一次有界别名查询。冻结 ea5c3a946，建立 WIP #831；API创建超时后回读已落库，不重复POST。
2. 历史整合保留主干材料/题设、上一轮复核、市场广度提示与缺输入保护，添加可信历史窗口/截止规则。新增8接缝测试；首次4F是测试误把 MaterialQuestion.premise_marks 写成不存在的 authenticity 字段，未放宽运行时规则。提交时runtime目录新鲜度门拦住一次，重生成后冻结7edfe24e7。
3. 运行时整合首轮出现实质冲突：旧快照字段白名单不认识主干 AgentEvidence.io_effect，保存fail closed。升级schema v3严格绑定IO来源；v1/v2原线格式/摘要不动、缺来源恢复unknown、不猜local_read。同hash展示不能改来源，新字段不能默默降成旧版本。可信上轮原件在首次模型调用前持久化，但不继承旧supports/coverage。冻结cb16cd463。
4. 财务源枝含R6、保稿、发布边界、研究交付、RAG读取，不能当作两个比例模块。逐处保留主干unknown_stock_code、日期/材料保护、发布writer收尾、会话加载代际、RAG内存观察。RAG测试替身补pid并替换RSS观察器，避免去采样任意真实进程；生产RSS检查不削弱。第二轮50模块2041P/4S是改动树，不签父HEAD。
5. 财务前端旧代际测试未适配“精确消息发布”合同，先补publication后仍红：旧测试用run终态单独解锁输入。按真实流补message.complete先于run，保留“旧trace加载仍阻塞、迟到结果不得删新追问”的断言；未改生产逻辑去迁就夹具。前端118P且重新构建静态资产。
6. 新增财务组合反例：坏差值与主干股票代码分区同时成立；绑定短日期标题和引用编号不误杀；financial partial在report前、commit事件前、事件已写但writer未结束三窗口保持补修债/引用。新股票代码用例首红来自引文放在句号之后导致句号分段计数错，修夹具引用位置后通过，不改核验器。冻结d82cb16b5。
7. 历史/运行时全量pytest本身绿，旧门禁包装器却exit1。查出两个问题：FWP_TEST_RECEIPT_DIR只被读方使用、conftest仍写默认目录；查无收据的错误文本 `$LATEST（...` 在macOS Bash+UTF-8中把中文括号识别进变量。原失败不覆盖，按精确文件分别核身份/exit_status，再以修复版只读重放通过。
8. 曾独立构建门禁诊断候选c35f61d37，15回归、六个撤保护反例（每组断言红，基线/还原绿）。进一步读共享方法笔记发现 #814/6eb12已有更强的唯一收据+Config重入所有权+只读身份实现。**停止把c35当正式第二实现，不开替代产品PR、不抢原线**；#814评论5363保留诊断接替。原先未先核在途实现导致重复劳动，此分支只保全故障与反例，不追加复制版到工具包。
9. #831独立审核首场BLOCKED：Codex软链找不到同目录host，关闭host也无命令；实际二进制路径解决组件定位但astra探针at capacity。沿同一ChatGPT订阅gpt-5.6-sol完成正式独立审，原报告Spec/Quality两节PASS；根QC收窄为PASS_WITH_LIMITS。真实事件105P/1S、Ruff0、离线probe过；probe没压满总限额且先release Timer，强边界来自本次独立重跑的正式回归，不冒称probe独立全证。末次identity事件stdout空，操作员另回读固定净树；没有保存CLI exit码，不补造0。一个独立session不冒称两位审核者。
10. 财务全量最终13305P/87S/2X、17 warnings、900.85秒，精确收据20260921T095428Z-d82cb16b.json与前端六步/registry等齐备，已推WIP #835并回贴#797评论5369。收据校验首次误传不存在的--receipt参数exit2，改为位置参数后校验通过；这是操作命令错误，不算测试重跑。#831新审核结果回贴5370。
11. 停止门禁诊断第二路线后，17:53对本轮pytest PID51140发SIGINT；全量未完成，8146P/22S、收据exit2、包装器rc4。中断收尾tmp_path出现KeyError且收据与进程退出码矛盾，门禁拒绝；不借前端绿称整仓绿。原包装器临时完整stdout已自行清掉，只有实际留下的尾部与收据，不虚称完整原件。正式方案仍归#814。
12. 在三个独占detached树分别启动领域独立审核（同订阅sol、不转委派）。三者在约18:41–18:42均因明确at capacity结束exit1、无报告、源码首尾净且同SHA，非触外层时限。runtime部分315P、财务部分240P；历史仅静态。财务先误用不存在的/usr/bin/timeout实际127，改/opt/homebrew/bin/timeout后240P；首条被同名日志覆盖，已从events恢复。三领域均BLOCKED_PROVIDER_CAPACITY，不代填终审、不自动重开。
13. 作者四候选收据与24份前端日志哈希逐项复核，分包归档到 docs/verification/2026-09-21-research-tail-forward/：author-and-small-review 与 domain-reviews-blocked，各含来源清单及完整SHA256清单。脚本/日志加.txt防误执行/忽略，字节不改；提交后用现有check_evidence_archive.py核Git blob。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 小片#831先行，领域#833/#834分别堆叠 | 三枝一次全包冲main | 父实现和新保护重叠大，先压清每个接缝；之后联合组合仍须重验 |
| 保存来源/目标/解析tree，merge --quit后pathspec提交 | 整文件取ours/theirs、裸commit | 防覆盖新主干行为及共享索引夹带，保移植可追溯 |
| v3保存IO来源、旧来源unknown | 删新字段、默认local_read、旧摘要偷变 | 来源参与读取权限，兼容不能偷偷扩权 |
| 精确publication且delivery_pending清除 | 二者互相替代、固定sleep | 消息身份正确、writer结束、业务完整性是不同条件 |
| 测试按真实事件顺序搭夹具 | 降低生产发布门以保旧测试绿 | 测试替身也受接口合同约束；代际防护仍须单独反例 |
| 精确SHA收据、首尾身份、原失败保留 | latest.json、父HEAD、别枝绿或改数洗红 | 读数只对实际运行的树/环境/范围成立 |
| 正式收据修复沿#814；c35停为诊断 | 两套门禁并行长期维护 | #814已含本轮小片缺失的同进程重入/只读身份约束 |
| 不抢邻线、不清树 | 近期无回复当弃单、干净即删除 | 归属与内容保全需证据，活动时间不是授权 |

## 固定身份与验收入口

统一原件根：`~/.finance-runtime/reviews/research-tail-integration-20260921/`。
解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；干净测试壳、umask022，PATH含`~/.local/bin`和`/opt/homebrew/bin`。

| 线 | 固定源码 | 作者已完成工程 | 边界 |
|---|---|---|---|
| #831 小片 | ea5c3a94618a15e37f914c8b1a13e271875e4337 | Python12444P/87S/2X；前端110P、E2E34P/2S；Ruff/registry/crosswalk通过 | 独立报告PASS，根QC有限接受，见operator-qc |
| #833 历史 | 7edfe24e76afbd5c365fbf97dd2414847b086f88 | Python12631P/87S/2X；前端110P、E2E34P/2S；Ruff/registry/crosswalk通过 | 包装器原exit1、精确pytest收据exit0分账；独立/自然题未验 |
| #834 运行时 | cb16cd463db5c19b3187a5137009791082874653 | Python12870P/87S/2X；前端110P、E2E34P/2S；Ruff/registry/crosswalk通过 | 同上包装器缺陷；不签跨进程driver/lease/对账 |
| #835 财务 | d82cb16b5ef31d23339a1bef7084a0dcb8221e15 | Python13305P/87S/2X；前端118P、E2E34P/2S；Ruff/registry/crosswalk通过 | 新独立审容量中断无报告；自然题未验 |
| 门禁诊断 | c35f61d37db3a26916902aeae688f82458591ebd | 精确冻结15P、六撤保护断言红、前端六步通过 | 全量主动中断/门禁rc4，无全量绿；由#814接替 |

历史全量收据 `20260921T091040Z-7edfe24e.json`，运行时 `20260921T092044Z-cb16cd46.json`；同SHA的零计数文件不能当全量。前端机器收据分别在`*-frontend-gates/frontend.json`。crosswalk既有98反向警告未清，不称零债务。

本批四源码基于main f783f19c8；17:23观察main已含#830到f2c3e9e1a24f（K3采样/无判官统计），**新main及三个领域联合树未验**。后续只能在实际新组合树重跑，不能拼接绿收据。

## 后续与禁做

- 财务工程和本轮审核均已收终态，没有本轮待收后台；三领域独立审容量阻塞，下一次审核需明确恢复方式与有界额度，不重复开启求绿。#831一个session双节不冒称两位独立审核者。
- #814正式收据实现继续原归属线，K3异常结束且无报告；本轮诊断不补它的独立签字，不能自行重启。
- 历史旧四道自然题、财务R6/R3真实质量失败未翻案；运行时schema摘要不是用户/代码签名，非exactly-once。
- #817仍open@2f2eb31cc910，17:42回读未见新的答复/完整门禁；不沿#816旧绿外推。#809另有#832质检返修，不抢接。
- #799三份未提交文档/证据、#804/#807归档及知识库#155仍另行处理；本轮未清树、关旧PR、动生产。
- 文档独立树提交，不改冻结源码身份；接手从docs/research-tail-closeout-0921的协调与四源码分支inflight读取。源码树本地没有本轮交接，需用git show或到文档树读取；后续真正改代码再同步本枝交接。保全原件，不能以“重跑成功”删首红。
- 工具沉淀：重复逐文件/提交字节核验直接复用scripts/check_evidence_archive.py，不造新清单工具。run-domain-review.py只是此批外层身份/时限记录，文本合同不是OS隔离；c35撤保护装置与源码patch作为诊断归档，不成为第二门禁实现。正式收据硬化沿#814，harness-reference主树dirty且领先1，未碰；通用证据规则已在evidence-hygiene方法卡，只补实际新例，不复制工具包。
