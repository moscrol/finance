# 双索引v4与Workbench交付验收 · 2026-09-19

## 结论

**隔离候选工程门禁、实际索引覆盖和检索接线通过；没有合并或上线。**
生产8792仍 `bf662e9310ff751a4c31763815ee78fb7d6d5122`；原双索引两个目录及24文件防写、
三个post-*的maintenance-skip仍保留。没有自动解锁、提升、切换或远端发布任务。
14页正文冲突未解，health仍degraded，不能宣布“全库无问题”或“生产检索恢复”。

用户此前“执行/你来协调”支持本轮运维协调与修复，不代替新增代码合并确认。
写者协调已经完成，不再要求用户寻找或关闭Cursor；旧归因纠错见
[协调快照](2026-09-18-kb-index-writer-coordination.md)。

## 固定身份与证据入口

| 对象 | 身份 |
|---|---|
| 金融工程/消费者候选 | `99fb9304ae9611178274293de30a117d5d504566`，分支 `fix/kb-dual-index-deploy` |
| 部署根绑定 | `c0fa49cf` + `d95d4921`（代码/wiki/普通/全文根显式分离） |
| Workbench交付修复 | `e9bb34c37101a21b0dfab80393bda1d5b8b4f548` |
| 实际前端构建物 | `058f76a3bb7eb19ec2b0d67127aa698bc8b23518` |
| 测试夹具回收 | `99fb9304`，原样复用 `672abcc504b3466a2ddd24dfa450c55703265c70` 的五文件补丁 |
| KB解析候选 | `23b4f5e4e1ace932fcc741197bf4892c272bf541`，分支 `fix/rag-frontmatter-body` |
| 冻结KB代码 | `$HOME/.finance-runtime/kb-code-23b4f5e4e1ac` |
| 操作根 OP | `$HOME/.finance-runtime/kb-dual-index-20260918` |
| 冻结资料 / 新索引 | `OP/source/{wiki,raw}` / `OP/staging-v4/{.rag_index,.rag_index_full}` |
| 新干净工程树 | `OP/gate-99fb9304/finance-workspace-private`，同级KB链接指向固定23b |

本页与随后文档提交不冒用99的收据为另一个HEAD代签。合并前/合并后最终身份仍需按
[验收规程](../workflows/acceptance-workflow.md)重新判定；不以“只改文档”伪造SHA匹配。

可携带归档：[`../verification/2026-09-19-kb-v4-acceptance/`](../verification/2026-09-19-kb-v4-acceptance/)，
内有 `manifest.json`、`SHA256SUMS`、新旧门禁、因果回归、消费者逐条出参及现场脚本的只读文本快照。
索引、raw、原始大资料清单不进Git；完整现场留OP。源清单SHA见manifest。
归档281份文件的哈希全部匹配；另有SHA256SUMS本身。原始失败输出保留行尾空格，
所以全路径 `git diff --cached --check` 返回2（原件见OP/evidence/finance-docs-raw-diff-check.txt），
不是格式全绿；手写文档检查exit0。未格式化原件或修改哈希求绿，原有pre-commit照常执行。

## 按发现顺序：为什么没有直接切生产

### 1. v3退出成功，实际全文缺四页

普通迁移覆盖闭合；全文update退出0、生成268,641块，但独立从允许源文件集合对账发现
四篇非空原文没有入库块。原 `verify-after-coordination.log` 因缺口4而终止，后续源差分/防写
检查当时没有执行；不得补写它们已完成。

旧解析器把页首Markdown水平线之间的正文当YAML，非法或非mapping也丢正文。
KB23b只在mapping或真正空/纯注释页头时去掉页头；否则保留原文。覆盖false/0/null/[]/空字符串、
CRLF及未闭合边界。切块版本升v4，使旧profile不能因源未变而继续自称fresh。

### 2. Workbench E2E红不是加长等待能解决

d95固定门禁31P/3F/2S：desktop首轮和mobile第二轮缺结构化报告按钮，tablet新追问被旧快照覆盖。
trace显示run的completed仲裁先于report.json交付，前端已停止刷新；同会话迟到加载又没被换会话保护覆盖。

- `RunSupervisor.is_active()`在锁内检查future；`delivered_run_payload()`**先看writer活性，再读run/artifacts**，
  只在completed且worker仍收尾时投影 `delivery_pending=true`。
- 列表/单run/SSE统一消费该投影；SSE先排空尾部事件再交终态。UI交付中继续轮询/接流，恢复会话亦然。
- `loadConversationData()`返回它实际读到的messages/bundles；新提交先增加代际号，同会话旧加载也失效。
- `_claim_terminal_run()`和取消仲裁没挪；失败/取消不等不合作worker。**这是单进程future协议，不是多worker协议。**

后端两个受控回归修前断言红；前端交付等待/同会话覆盖修前两红，另补恢复会话重连。
修后API定向110P、前端110P，原E2E断言和超时不变。

### 3. e9所有测试叶子绿，整批仍因构建产物失败

e9后端11,488P、前端110P、E2E34P/2S、KB837P及其他叶子均exit0，
但 `pnpm build` 删除旧JS、新增 `index-DH207EFA.js` 并改index.html，使候选树变脏。
`python-receipt.json`明确dirty=true，`all.exit=1`；不能拿它证明可交付提交。

058提交实际静态文件，再在新干净树重建，产物SHA相同且不再使树变脏。

### 4. 058全量暴露测试生命周期缺口

058前端/E2E/KB及所有其他叶子绿，后端 **11,487P/1F**，唯一红为
`test_ask_call_provenance.py::test_receipt_covers_calls_and_reuses_outer_budget`。
请求替身期望第二调用503，却拿到body。该窗口没有线程身份插桩，不把另一窗口归因冒充这里的完整trace。

检索现有知识卡后找到同名失败已在历史研究分支定位：旧API测试后台线程越过替身撤销，抢用后续HTTP替身。
本候选三个fixture与既有672补丁的父版本逐字节相同。新受控屏障在本候选上证实quota/credits/admission
均未join（3个断言红），故原样复用五文件test-only修复。定向67P；内存撤销join再3个断言红，失败清理也回收线程。
不改受害测试计数、LLM重试/预算或生产非阻塞shutdown。最终99全量是**未插桩**的一次完整验收，不用旧绿代签。

### 5. 消费者探针也会设错判据

| 窗口 | 实际结果 | 错误预期与处理 |
|---|---|---|
| R1（e9） | 普通“液冷+L3”合法空回执 | 错误要求有命中；保留失败 |
| R2（058） | 海鸥股份L3候选合法空回执 | 源明确review_required=true，不是合格正例；保留失败 |
| R3（058） | 普通7例通过，全文L3返回3条 | 错把没有完整字面词等同无词法posting；保留失败 |
| 全文补验（058） | 全文7例+恢复原文通过 | 明确前三名只匹配“液”，不签相关性/答案质量 |
| 最终固定99组 | 两索引14个service用例+恢复原文CLI通过 | 预先核资格与token交集；实际路径/回执/身份/只读性通过 |

普通虽有12块L3标签，但全部被待复核策略排除，合格L3=0。全文合格L3=551，
其中22块与分词结果 `{液, 冷, 液冷}` 有交集；前三名电解液/注射溶液仅含“液”。
**过滤执行正确不等于材料相关，更不等于答案质量通过。** 没改模型、排序、过滤、预算或超时凑绿。
合格正例用现有L2 baseline（GQY视讯2025年报，as_of=2026-07-02），两份各4块符合资格；
待复核候选、1900截止为确定空负例。未知元数据仍未知。

## 方案对比与可复用判据

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 修解析器、保原文、升切块版本 | 改raw/缩分母/只修parser不失效旧索引 | 内容保全与旧索引失效是两道边界 |
| 单进程交付投影+代际保护 | 后移终态仲裁/延长sleep/仅靠会话ID | 保取消合同，同时封交付与同会话迟到两类竞态 |
| 提交真实静态产物再验新候选 | 忽略dirty/用源码绿代签 | 产品由实际源码和构建文件共同决定 |
| 复用fixture join补丁及反证 | 改受害断言/改生产关闭/重跑碰绿 | 资源生命周期必须位于替身生命周期内 |
| 正负例先验资格与token | 用L3标签或字面词猜输出 | 过滤资格、词法候选、相关性是三个判据 |
| 新代隔离、最后切消费者 | 原地双目录依次覆盖/仅停hook | 两目录非原子事务，direct writer仍会绕过hook |

## v4覆盖与只读验收

| 索引 | 应选页 | 入库页 | 冲突隔离 | 未解释缺口 | 全部向量行 |
|---|---:|---:|---:|---:|---:|
| 普通 | 14,448 | 14,434 | 14 | 0 | 168,862 |
| 全文 | 17,988 | 17,974 | 14 | 0 | 268,791 |

BGE-M3、1024维、max_files=0；证据元数据版本1、切块v4；两份include_raw合同保持。
全部向量finite/非零/归一，实际证据字段计数见两份verification.json，不只看版本标记。
全文raw覆盖selected=indexed：根raw906、disclosures1463、sellside1068、briefings103。

四篇原文SHA未动，v3零块→v4：毫米波雷达24、海上风电21、超级钻石20、超聚变23。
两份已入库冲突0，源冲突14，不删除marker、不擅自解决内容。

冻结资料21,819文件，2026-09-18T16:05:36Z再核新增/删除/变化0；实时源同数量，仅
`wiki/relations/access_log.jsonl`变化。新鲜度有观察窗口，切换前必须重新核，不永久继承fresh。
同一窗口核生产26项flags/device/inode和24文件SHA不变；无截断/创建的写意图打开全部被拒。
8792 health healthy、源码干净且身份匹配旧bf662e93。

## 最终99消费者实际验收范围

`consumer-v4-99/summary.json`：14个服务查询均过，另一个全文直接CLI命中
`raw/毫米波雷达-演讲稿.md`且fresh。显式KB代码/wiki/双索引根，故意错误ambient KB_VAULT未生效。
所有retrieve要求fresh，检查实际mode、无fallback、封套applied_filters/版本、作用域绑定。

有过滤请求实际走CLI；真正热worker使用无过滤hybrid，两次查询各自验证同PID、同代码身份、
model_load_count=1、queries_served逐次+1。换wiki根生成不同且未启动worker，不复用旧资料根。
两份worker已关闭，PID6048/6842的退出已复核；两索引前后全文件SHA一致。

这不是LLM答案质量、rerank、生产时延、生产入口或长期维护链验收。

## 最终99工程门禁

统一 `env -i`、`umask 022`；测试解释器
`$HOME/finance-workspace-private/.venv-workbench/bin/python`（3.12.13），依赖指纹
`3328bed61f3e21ea`；真实BGE更新/检索子进程用 `$HOME/knowledge-base-private/.rag_venv/bin/python`。

| 叶子 | 结果 |
|---|---|
| 金融pytest | **11,491P/0F/73S/2xf**，17 warnings |
| Ruff + registry五项 | 全部exit0 |
| 前端install/lint/typecheck/test/build | 全部exit0；**110P**；构建后树干净 |
| Playwright E2E | **34P/2S**，独立18971/18974端口 |
| 固定KB23b pytest | **837P/0F**，1 warning |
| KB relations/sizes/quality/log/index | 全部exit0 |
| 批次总结果/两仓最终状态 | **all.exit=0 / 均干净** |

正式金融收据 `20260918T161257Z-99fb9304.json`（归档为
`gate-99fb9304-receipts/python-receipt.json`），dirty=false、dependency_gate_bypassed=false。
`check_test_receipt.py <receipt> --expect-revision <完整99SHA> --require-target <固定树>` exit0。
不是全机的latest收据；同SHA另有非全量收据也不能替代它。

历史失败完整留存：原生产漂移、d95 E2E三红、v3全文缺四页、e9构建脏、058全量一红、
消费者R1/R2/R3错误判据。新窗口通过不修改旧all.exit、不删除失败原件。

## 后续与禁止事项

1. **长期维护仍缺**：接线审计与备选方案在
   [维护/切换计划](2026-09-18-kb-guarded-maintenance-plan.md)。每批固定资料与代码、生成完整双索引代、
   验证后用单一manifest切路径是目标，未实现。需覆盖hook/ingest/手动update/build/fetch/publish，
   验故障注入、旧代保读与回滚；不能把临时uchg当永久维护。
2. **取得用户合并确认**，再在最终main做完整门禁、重新验鲜，备份启动器/运行链接与部署台账。
   执行8792切换还必须另验真实Workbench Episode入口；本次只读消费者探针不能代替它。
3. 未完成受控写者与切换方案前，不解除防写。需要解除只走OP的日记绑定恢复器；
   不递归清flags、不恢复旧无保护hook、不上传覆盖远端旧发布、不覆盖他人正文。
4. 原旧索引/旧代码/失败staging均保留。新文档不声明持续运行中的任务：本轮迁移、消费者、门禁均已结束。

工具沉淀：交付和解析边界固化在正式回归；fixture helper复用现有实现。
现场脚本有冻结身份与特定目录，作为归档可复核样本而非通用维护器，避免误复跑写旧收据。
可迁移原则回写既有知识卡；harness-reference主树BUILD.md有他人在途修改，未覆盖/认领。
