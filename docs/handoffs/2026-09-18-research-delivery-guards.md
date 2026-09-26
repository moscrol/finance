# 研究交付补闸：结果准入、局部续修与最终投影 · 2026-09-18

## 状态与身份

- 工作树：`/Users/a77/fwp-wt-research-data-readiness`；分支：`feat/research-data-readiness`。
- 本轮业务提交：`a31b572f9a762c6205224d251717472ffa61c530`，接 `2c5f4993`，17文件；包含运行时接线、回归、冻结夹具、撤保护定义与源码生成的工具目录。
- **固定干净版本的工程检查通过；整体自然回答质量仍为 `not_passed`。** 本轮没有新模型会话、没有新取数、没有恢复公告来源，没有将作者写的修正脚本算成模型成功。
- finance 分支未 push、未开 PR、未合 main、未部署；8792未动。旧8907保持停服，工程E2E结束后8908/8909无listener。共享主树与R5/R6/答案保留/runtime并行树未被本轮修改。
- 本轮原件根 `~/.finance-runtime/research-delivery-20260918/`，以下称 **DELIVERY**；旧根 `~/.finance-runtime/research-data-readiness-20260918/` 称 **OUT**。
- 新封印：`docs/verification/2026-09-18-research-delivery/manifest.json`，338个文件，SHA256 `d062be3202714360b9ba7c77a8d35e6710aec5db7aba317d94c6cfbd863d392e`。原件留本机，仓内只有路径/尺寸/hash及结论范围；hash不证明金融正确。
- 旧194份原件逐个重算尺寸/hash一致，旧manifest SHA仍 `d37237b8d2c0bde5503428b2bc92d689c4aa4ea29d80d4d0eae5dda487f091d7`。旧交接 `2026-09-18-research-data-readiness.md` 与旧 `OUT/final-state.json` 只描述当时，未覆盖/重标成本轮状态。

## 背景：为什么不继续加接口

上一轮行情、资金和财报已有可消费数据，真实问答却暴露两类交付失败：

1. `run_20260918_124033_015953` 四次计算报错后退出成功，但脚本把逐期嵌套字典放进只接受标量的summary，展示器忽略该内容；JSON中的1.588又在终稿两处变成1.587。输入hash齐、进程exit0、文件存在都没有保证可用产物或正确正文。脚本还手抄数值，没有读取结构化输入。
2. `run_20260918_121115_094979` 来源查询不完整，进度已诚实披露，但成功答卷仍写“窗口内无新公告即无新增官方信息差”和“返回空白可坐实无公告”。错误没有只发生在异常出口。

这两份原件已冻结；本轮不重新抓数据、不绕cninfo403，也不借新一轮模型采样覆盖失败。与并行R5对照时只借其已提交 `dfd7b4ff` 的业务失败投影形状，**没有整合**R5财报选期、必答槽/预算修复、同bind缓存或其祖先runtime改动，验收数字不拼票。

## 按发现顺序：实现与接缝

### 1. 成功铸证据之前检查结果协议

`derived_calculation_artifacts.result_contract_errors()` 检查v1摘要标量、表格列/行宽、图序列、有限数、合法字段，以及至少一项可展示内容。稳定错误码不携带私有值。沙箱exit0后仍可能返回可改脚本重试的 `invalid_result_contract`，不生成派生证据或成功telemetry。

- 旧 `normalize_result()` 不改：旧嵌套summary继续呈现其真实“空展示”失败，不把历史原件迁成成功。
- 无schema的非空legacy `emit(dict)`仍兼容，不外推已按v1全面严验。
- 提示写真实 `table(name, columns, rows)` / chart签名，不新增title别名，也不改沙箱prelude掩盖模型误用。
- `CalculationError`把失败送进gap与telemetry；`ToolObservation.result_status_fields()`、harness投影把真实 `ok=False/error/status` 送到模型和审计。合法empty与失败分开，不只在日志里诚实。
- 首次提交被源码目录保鲜门拦截；运行既有 `scripts/gen_runtime_catalog.py` 更新 `docs/runtime/tools.md` 后提交成功，不跳过hook。

### 2. 实际公开文本上的有限检查

新 `research_delivery_checks.py` 无IO、无模型调用：

- 有L3公告查询trace时，拒绝明确的“查询失败/空白/不完整 → 没有公告/无信息差/尚未兑现”推断。成功查询也不是全集完整证明。合法免责声明、独立公司原文和条件假设不一概删除。
- 对**单公司、明确报告期、绝对OCF/归母净利比率**，逐期逐列比对真实派生产物。不能用另一报告期或营收列出现相同数字支持本格；行报告期优先于表名中的年份。按正文精度允许明确舍入及百分比换算。
- Markdown坏格只标“待核对”，保同一行现金流/净利；坏推断局部移除，不删整答、不静默代写正确数字。
- 明确要求计算工具或出现计算编号时，缺/冲突产物留缺口，不把词面有数字认证成核算完成。
- 合法“含金量同比增速：2026中报449.8% vs 2025中报28.9%”曾被误当绝对比率；隐式标签分支补增长率前缀排除，先红再绿。

`episode_semantic_verifier._recheck_research_delivery()` 在统一语义出口以及材料短路前检查实际public文本。judge off或注入全过判官也不能绕过。只重新打开相关required槽，保私有原稿/证据、公开明确缺口，继续经 `session_projection.view()` 唯一出口。

### 3. 原预算内同会话续修，不是“检出缺口就有权再跑”

真实Adapter/运行器接线测试最初只有一次请求：问题不是检测缺席，而是夹具没有表达真正的续修许可。未为测试调大生产预算、未改admission算法；分别构造研究工具关窗、root交付期限尚有余量、原预算预留/耗尽以及首次语义核验前root到期。

37个脚本SDK用例覆盖：公告/计算 × judge off/llm注入 × 改对/重复错稿/超时 × 预留/耗尽/root到期，外加最后投影接缝注错一例。

- 只一次取数；同episode、同证据hash；续修 `tools == ()`、remaining_calls=0，原调用帽不变。
- 预留且改对才completed；未改对、修复超时或预算耗尽，保已核实部分并partial，不恢复错稿。
- root在首次语义核验前已到期时，不存在可信前稿：degraded并说明“核验未完成”，保私有候选证据，而非把未核验首稿认证成保留事实。
- 关键请求断言放在运行器退出后。把assert写在会被吞异常的callback内，会把测试错误误读成provider失败。

### 4. 两个额外遗漏：错因与引用卡

新增承重断言后暴露：原修复请求只有槽位名，没有具体错因；可信句保留了 `[E1]`，但该槽降成缺口时卡片被整批移除。

- `delivery_repair_notes`用固定错因，经Adapter原 `rejected_claims` → `REPAIR_GOAL.unsupported_claims` 送达，不新增工具权限、预算或模型调用。
- `delivery_retained_evidence_hashes`只从**此前fulfilled、未被既有gap撤销、原本已有绑定**的证据里，保留修后正文仍显式引用的卡。无绑定E2、已gapped槽不复活。保卡不把缺口槽改回成功。
- 最终投影删除编号后再过滤retained集合，不残留过时卡片。

### 5. 最后一次公开投影也要检查

Adapter的日历披露/公开提示之后，`recheck_material_public_delivery(semantic, projected=answer)` 不再仅对材料题执行。最终非材料文本混入坏推断也会局部删除、更新缺口/引用、completed降partial。最后接缝不私自另开新修复循环。

第37例是**故意在最终接缝注错**，证明最终出口有保护，不是宣称日历函数自然生成过这句话。

## 决策与被否方案

| 选用 | 否掉 | 理由与边界 |
|---|---|---|
| 新结果成功前准入 | 改旧归一化器让历史产物看似成功 | 保留失败史；新格式门仅证可展示，不证公式 |
| 失败状态同时进模型与审计 | 只修telemetry/外层一律ok | 模型必须知道需改脚本，而不只管理员知道 |
| 公开文本有限确定性检查 | 只堆prompt或再加一个全能判官 | 已知有限性质可复现、无额外外呼；未知语义不认证 |
| 期别+指标+单位对账 | 数字词袋、purpose标题、计算ID充证 | 同数不等于同一事实，任务名不等于产物 |
| 错格留缺口、可信邻句保留 | 全删答案或直接改成正确值 | 不连坐已得事实，也不替模型静默编写 |
| 原许可/预算/期限内续修 | 有缺口就加资源，耗尽就取消必答 | 执行许可与完成义务独立 |
| 原绑定且仍引用的卡片保留 | 放开全部证据或把槽恢复成功 | 引用身份与任务完整性不是一件事 |
| 最终投影再核 | 验过草稿就信任后来所有拼接 | 凭据只适用于被验文本，不能借给新稿 |
| 冻结失败、独立Decimal、真实展示、输入扰动分层验 | hash/exit0/文件存在/作者脚本冒充模型成功 | 每层只证明本层，不跨层代签 |
| 固定提交独占临时树拆保护 | dirty源码、无匹配替换、collection error算反证 | 量具先可用，再看真实行为断言 |

## 验证账：不同版本与重叠用例不累加

### 固定clean `a31b572f`

| 检查 | 结果 | 收据 |
|---|---|---|
| Python全仓 | **11635 passed / 83 skipped / 2 xfailed / 17 warnings**；522.71秒 | `DELIVERY/candidate-a31b572f/pytest.log` |
| Ruff | 通过 | 同目录 `ruff.log` |
| 前端lint/typecheck/test/build | 全通过，**107 tests / 8 files** | `frontend-*.log` |
| 浏览器E2E | **34 passed / 2 skipped**，固定夹具，不是34次provider会话 | `e2e.log` |
| registry四项 + 台账crosswalk | 全通过 | `parseability/registry/tables/views/ledger-crosswalk*.log` |
| 工程编排前后身份 | 同一SHA、status均空，candidate_unchanged=true | `result.json` |

权威Python收据 `~/.finance-runtime/test-receipts/20260918T122214Z-a31b572f.json`：Python3.12.13、主树`.venv-workbench`、dependency_fingerprint=`3328bed61f3e21ea`、dirty=false、未绕依赖门。
`check_test_receipt.py --expect-revision <完整SHA> --require-target <本树>` exit0，见 `DELIVERY/receipt-check.log`。同SHA较早的0项收据不替代此份。全量前后净环境/umask022，Keychain=0，不继承正式launcher。

### 新撤保护13组：真实执行、断言红、逐项恢复绿

运行器与定义均来自固定提交；每项唯一锚点、修改后可编译、测试非空、0 collection errors/0skip，最终字节还原，临时树成功移除。基线/最终完整目标均107P。

| 拆的保护 | 执行数 / 红断言数 |
|---|---:|
| 结果成功准入 | 2 / 2 |
| 表格行宽 | 16 / 1 |
| domain错误状态 | 1 / 1 |
| harness状态送达 | 1 / 1 |
| 公告公开检查 | 10 / 10 |
| 计算公开检查 | 4 / 4 |
| 按期别而非数字并集 | 7 / 3 |
| 按指标列而非表名用途 | 6 / 3 |
| 错格局部保留 | 3 / 3 |
| 同会话具体修复意见 | 36 / 12 |
| 非材料最终投影 | 1 / 1 |
| 原绑定引用卡保留 | 37 / 13 |
| 缺产物不认证 | 3 / 3 |

原件 `DELIVERY/mutations-a31b572f/{results.json,definitions.json,*.diff,*.xml,*.log}`。
注意两个数字归属变异会造成冲突/误拒，证明测试对边界敏感，不宣称每个变异都表现成错误数被放行。

共享runner升级后，**不传--suite**另跑旧extraction默认入口：35组按原判据全部红→绿，基线/恢复165P，0收集错误，树字节恢复并移除。这里只证明默认兼容：旧红项中含变异造成的KeyError/UnicodeDecodeError，不把它们统称本轮新增“全为AssertionError”的13组。分账见 `seal-prerequisites.json`，原件 `extraction-default-a31b572f/`。

### 冻结重放的有限证据

`intelligence/tests/fixtures/research_delivery_20260918.json`带旧产物/正文来源SHA，未重取。真实沙箱现在拒绝旧嵌套summary脚本。**作者修正脚本**用series/ratio_series读取同批数据，六期比率与独立Decimal参照一致；真实CSV/HTML含最新行：

`2026-06-30,2026-08-15,706.91,445.17,1.588`

将最新OCF从706.91扰动到800，实际结果随输入改变；这证明该作者脚本真消费输入，不证明任意模型脚本。规范产物下旧正文仍检出错误格与比较句；旧空产物不能认证所称工具核算。公告原件两坏推断移除、ROE等邻句保留，不因此认证保留句所有金融事实。

dirty阶段548P/1S、Adapter37P等日志保留，仅记开发轨迹，不与clean全量相加。此前19F/2P、9F/22P、增长率误伤及续修夹具调试原件均未覆盖。

## 未验证与不要外推

- 没有新自然模型通过证据：新模型是否自然写规范结果、会不会按错因修正、整篇数字/来源是否正确，仍需真入口验收。作者脚本、SDK替身、全过lambda判官、工程E2E都不代替它。
- 有限guard不是通用语义裁判：多公司、隐含报告期、未覆盖句式、复杂否定、来源归属、同比/累计/单季金融口径、公式及任意脚本实际输入使用另验。跳过不是认证；格式门不证明数学。
- 未整合R5全套；本轮没有修历史解禁弱先验/路由扩题、event_daily筛选日期被泛称整库新鲜度、根预算生命周期或旧call-provenance偶发问题。后续未重现不是根因已修。
- cninfo403、互动易字段异常仍是外部缺口；空/失败/部分/未尝试均不能推出公司无公告。历史解禁缺披露时点，不用当前滚动日程回填。
- 本枝工程收据不是main批次合流门。并行owner已经继续推进，合流前按最新已提交revision审diff，不能从dirty树复制。
- 独立QC、真人视觉、新固定自然题集、稳定日更/全股覆盖、港美宏观扩展均未由本轮签收。
- 原运行选择仍为gpt-5.6-sol/Keychain；旧GLM答卷不重标GPT。下一次live需重新核实际provider/model/执行壳与凭证，不能照搬旧GLM launcher，也不能因凭证缺失偷换模型。

## 工具归位与共享记忆

- 手工检查已落仓：结果准入/有限检查模块、四个正式测试文件、冻结fixture、共享撤保护runner的新suite；未另建第二套取数、循环或写事实链。
- `DELIVERY/run_candidate_checks.py`复用旧工程编排；`seal_delivery.py`为一次性归档选择器，已一起封印，不是新生产入口。能力逻辑留正式源码，报告性的拼装不冒充通用工具。
- `docs/agent-product-door.md`与业务同提交，`docs/runtime/tools.md`由源码生成；`.claude/lessons_learned.md`记录本轮接缝/夹具教训。
- memory方法写入 `10_knowledge/contract-vs-delivery-mismatch.md`；项目仅一行交接索引与blocked看板；能力图谱更新现有条目，不另建清单。graph审计当时80行/192断言、141在途；PENDING不表示已上线。
- code_map重新build/query为ready，但本次长中文query的doors/structure/narrative都missing、vault unavailable、recall untested；不据此断言不存在架构。
- harness主树有他人BUILD.md，未触碰。从已fetch的gitea/main另开 `~/hr-wt-research-delivery-0918`，分支 `docs/research-delivery-0918`；`48635c4af090df2c07775cf76656f595f9cb8e06` 已push Gitea，仅BUILD/KIT/TOOLKIT三份文档，未合main。跨仓引用核对235条、缺失0、既有行数漂移26、未解析8/未核数1；不借exit0声称全部漂移清零。候选专有源码显式带ref，另由finance图谱/本次固定树核实。

## 下一步与准入

1. 独立审阅有限检查、保留引用及最终投影边界；需要扩支持域时，先有负例/合法反例，再改源码并固定新revision重验。不要把工程绿变成“任意财务计算已可靠”。
2. 用户授权自然验收后，先固定新题集、模型/壳、预算、judge设置、只读范围、真实端点和失败判据。走 `POST /api/conversations`，绑定本次run/message取终稿；首发失败不重发挑绿，留health/episode/trace/计算产物/公开正文。
3. R5/R6/runtime/答案保留整合是独立动作；新main批次门须签合流后的SHA，不能借a31工程数字。合并/部署仍需用户确认，8792不提前切。
4. 既往local恢复、L2、生成双根装机及主动launchd验证不重跑；自然20:40调度、方法新协议、KB received→apply、旧分支收敛继续分案。
