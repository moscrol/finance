# Knevo 材料吸收处置报告（2026-09-23）

## 结论

**材料处置、可复用代码与揭盲回归接线已交付；真实入口验收未通过，不能称“全部炼化”。**
本轮只做可逆的研究侧收口：不合 main、不部署 8792、不回补生产行情、不写生产画像。状态以[吸收清单](absorption-plan-2026-09-11.md#2026-09-23-执行决定与当前状态覆盖下文历史建议)为准；本报告只串起来源、决定、产物和证据。

## 09-24 本地候选复核：完整工程绿不等于可部署

当时的主干`3bb81b963`已合入本枝为`6d721fdaa`；`7343cfc34`修复补写失败覆盖历史审查的问题，私有尝试与最终裁决分离，inspect只出脱敏摘要，不改变生成或审稿合同。两项提交只留本地，未推、未合回main、未部署。

6d完整Python15062P/85S/2X；7343首次完整15054P/8F/87S/2X，8红在RAG保活，原因未定；同revision独立检出完整复跑15064P/85S/2X/0F，收集15151。保留两次收据，不以复跑绿解释旧红。两revision前端六步通过，7343为120单测、34E2E/2跳过；Ruff/注册表通过，审计定向267P、撤保护4F/恢复4P。

GLM完整版隔离探针确认served_model=glm-5.3，但写手仍错；高思考75秒超时，低思考约42秒非法JSON，先锚点实验也未解决分句/语义。旧固定稿判官三次两阶段合法返回却均passed=false，不签长期稳定性；请求关闭思考仍有非零思考计数。真实原八问run_20260924_015153_765303在6d上仍repair_model_unavailable/failed、最终judge unavailable、作者not_passed。新审计修复未再跑自然live，也不能补造旧审查原件。

原题/七份原件/八问/来源/预算/判官不变；旧0/12及G1b、包3、Q14、真实Q18等反例不翻案。完整状态与取舍见[本轮快照](../../handoffs/2026-09-24-knevo-deploy-readiness.md)，证据`~/.finance-runtime/knevo-deploy-readiness-20260924/current.json`。**仍不可部署。**

## 09-24 逐句输入指引：送达已验，生成与判官仍未通过

`86692c7b5`在首轮/修复共用提示补齐全输入锚点、比较主体与期间、收入/利润和库存水平边界。实际首轮仅两处material_grounding规则变化，19035→19415字符；系统、原题、八问、来源和终局模板均相同，接收schema、预算/重试及审稿规则不变。这是指引增强，不是已验证的质量修复。

原入口`run_20260923_235628_399142`三轮写手63.967/35.279/38.691秒，先分句失败、再缺evidence_boundary，最后44条声明结构完成。q6仍把厂商125→110写量增；q7库存60写远超消耗100，事实标reasoning无锚点仍在。判官两次约75秒超时，首层150.011秒无报告、未到复核。请求/结构completed、语义partial、作者not_passed、driver not_evaluated。

旧冻结稿同输入重放150.031秒首层超时，两次请求哈希均与历史成功首审`5d091c4f…`相同；历史一次两层合法但未通过报告不代表稳定性。无额外写手重试、未提高预算。

干净定向**2154P/2S/1X/0F/0E**，收集2157，Ruff/收据验签通过；相关302P、有效撤保护5F/恢复5P。最初测试路径笔误与变异脚本NameError保留，不计作产品缺陷或有效反证。原题保真/material_only/0 Episode工具请求，七份原件不变，进程已停，未合/部署。证据`~/.finance-runtime/knevo-absorption-20260923/claim-inputs-20260923/current.json`；[本轮快照](../../handoffs/2026-09-24-knevo-claim-inputs.md)。不签全仓、前端、main组合或语义验收，旧反例保留。

## 09-23 写手实包与提示归属：冲突已修，交付仍未通过

`34902599f`修复确定性提示冲突：已确认编号材料合同不再叠加关键词触发的跟踪/公司排序/互斥假说等旧模板；保留专项纪律与原题、全部8问、来源和接收规则。实际首轮messages仅`question_type_rules`变化，用户载荷21195→19035字符；不把减少字符解释成稳定提速。

原入口`run_20260923_230143_763221`首稿60.061秒、格式续轮42.547秒（均原75秒上限），后者62条声明形成结构完整稿；判官两个约75秒尝试超时，未到非事实复核。请求/结构completed、语义partial、judge unavailable，作者not_passed、driver not_evaluated。厂商出货/终端消耗、比较基期、无锚点reasoning及盈利方向仍有错误，原八问语义交付未过。

旧代码f2101ad51的实包基线还发现stop后仍含`.replace(...)`表达式的非法JSON；隔离JSON模式实验随后两轮合法JSON并成稿，但判官仍超时。这是单次诊断，不认证网关强制约束，JSON模式未加进仓内传输层或生产配置。三次原入口题面一致/material_only/0 Episode工具请求，非全IO零，七份原件不变。

34902599f干净扩大定向**2151P/2S/1X/0F/0E**，收集2154，Ruff/收据验签通过；相关338P、撤提示保护4F。非全仓/前端/main组合，PR仍WIP，服务已停、未部署。证据`~/.finance-runtime/knevo-absorption-20260923/writer-wire-20260923/current.json`；[本轮快照](../../handoffs/2026-09-23-knevo-writer-prompt-owner.md)。下文旧反例与收据均保留。

## 09-23 去重续修：两层判官单次完整返回，原入口仍未交稿

运行代码`984e53588`明确空draft下全部claims.text的精简目标，完整子问、计算与本句输入优先，不截断或新增接收门槛；判官发送层把完全相同的绑定换为claim_ids引用，原私有请求、来源归属、预算/重试和回执schema不变。冻结输入26468→21543字符，减少约18.6%，44条声明/8问仍在且可逆。

同一冻结稿的low两层重放：材料首审70.228秒、非事实复核54.082秒，总124.323秒，报告合法但passed=false。单次返回不证明稳定提速、语义正确或Workbench通过，原同hash超时反例保留。

新原入口包1`run_20260923_215601_143892`仍failed/repair_model_unavailable：写手75.221秒、既有补写40.013秒超时，无完整稿、未到判官。作者not_passed、driver not_evaluated；原题逐字一致/material_only/0 Episode工具请求，非全部IO零。七份原件未改，服务已停、生产未动。

扩大回归曾1885P/2F，原红保留；`48ad099af`只将两项毫秒计时测试改为可控时钟，不改运行预算，之后干净定向**1887P/2S/1X/0F**，Ruff及收据验签通过。撤去重3F、撤正文说明1F、坏预算时钟2F。live签984e535，绿色收据签48ad099，两者不冒签同revision；仍非全仓/前端/main组合门禁。

证据`~/.finance-runtime/knevo-absorption-20260923/compact-review-20260923/current.json`；[本轮快照](../../handoffs/2026-09-23-knevo-compact-review.md)。下一步仍是原窗口写手完整生成、判官回执重复性及逐句语义核验，下文均保留历史。

## 09-23 思考强度隔离：单次报告返回，不证明修复

`6d472c523b963a33f2f8fd1519aca422f2a8b3b5` 新增默认不启用的 `LLM_JUDGE_REASONING_EFFORT`，只覆盖judge调用作用域，写手、提示、schema、接收规则及预算/重试不变，生产启动器未改。干净定向 **1874P/2S/1X/0F**、Ruff/收据验签通过；局部58P、撤作用域2F，不是全仓/前端/main组合。

冻结旧包1首审输入，显式enabled+low单次64.478秒返回合法报告（passed=false），原配置75.208秒超时。随后真实判官阶段重放，两次low请求与成功调用完整hash相同，却仍75.007/74.994秒超时，仅收推理片段，150秒首层耗尽、未进非事实复核。因此low不是已验证修复，报告合法也不证明判得正确；诊断不是Workbench验收或新盲测。

原入口仅新跑包1一次 `run_20260923_204255_417562`：写手75.014秒与既有补写39.870秒均到期，failed / repair_model_unavailable，未到判官、无完整八问稿。作者not_passed、driver not_evaluated；原题逐字保真、material_only、Episode工具请求0，非全部IO零。七份原件及旧失败保留，服务已停，PR仍WIP、未部署。

证据 `~/.finance-runtime/knevo-absorption-20260923/judge-effort-20260923/current.json`；[本轮快照](../../handoffs/2026-09-23-knevo-judge-effort.md)。下一步仍是原窗口内写手完整生成与判官稳定报告，随后核非事实复查和输入/主体/基期；下文均为历史快照。

## 09-23 调用诊断续修：八问已成稿，判官仍超时

`5beeeef3c8e3d4330a6011b635f92dca5b734750` 修补连续入口提前结束绕过LLM台账落盘，并增加仅含时间/字符数的流式进度；inspect继续白名单导出，不保存隐藏推理正文。写手/判官提示、预算、重试及接收规则未改。干净定向 **1869P/2S/1X/0F**、Ruff/收据验签通过；撤落盘4F、撤计数2F、恢复6P，不是全仓/前端/组合main认证。

原入口包1单次隔离复验 `run_20260923_193125_229673`：首稿74.930秒、既有格式修复32.776秒，八问结构齐；材料判官两次75.008/74.990秒超时，分别收到6054/8933个reasoning_content字符，均没有报告正文或工具参数，未到非事实复核。阶段150.008秒包含已有重试，不与最后一次75秒窗口混比。请求completed / 报告partial / judge unavailable / 作者not_passed / driver not_evaluated分账；只改诊断不能解释为生成质量提升。

作者仍拒收：A/B厂商出货均低于本季度125，原稿却以量增推盈利向好；成本未知、库存基线缺失，不能签盈利方向或“风险解除”；计算及研究卡重复数字仍缺本句输入锚点。原题逐字保真、material_only、Episode工具请求0，非全部IO零；七份原件未改，旧失败不翻案。服务已停、PR仍WIP、生产未动。

新证据 `~/.finance-runtime/knevo-absorption-20260923/writer-diagnostics-20260923/current.json`；[决策与续接](../../handoffs/2026-09-23-knevo-writer-diagnostics.md)。下一步须在原窗口内完成有效判官报告，同时修全输入绑定和主体/基期核对；低思考量、换模型或强制解码尚不是已验证方案。

## 09-23 响应时限续修：工程通过，交付仍失败

`7cfc51d524681e2b9a8740e6b16e064a32006ed1` 修复工具聊天响应体读取只受网络空闲超时限制的问题：沿本次调用绝对时限中断连接、拒收晚稿，不增加预算或重试；材料判官首层失败也保存阶段耗时，inspect仅导出摘要。干净定向 **1768P/2S/1X/0F**、Ruff/收据验签通过，撤响应保护与撤阶段记录各2F，恢复正向72P。这不是全仓/前端/组合main认证。

原入口新隔离包1、包3均 **failed**，写手首发约75秒、既有终局补写约40秒后流式失败，未进入材料判官、无有效八问稿。原题与八问未改；两题不是新盲测，驱动仍not_evaluated。事件时长符合给定窗口，但底层异常已扁平，不能单凭时长确定故障原因，更不能签判官线上窗口或语义通过。此修复不主动中断DNS/建连/响应头，不能称全网络硬截止。

服务已停，生产未动，PR仍WIP。新证据 `~/.finance-runtime/knevo-absorption-20260923/response-window-7cfc51d52/current.json`；[决策与续接](../../handoffs/2026-09-23-knevo-response-window.md)。旧包1的14句无锚点与2句不全、盈利判断矛盾仍需语义续修，历史失败及下文快照全部保留。

## 09-23 再续修：诊断可定位，语义仍未通过

`8eceac0f217628b6ea76a64400bf60e0c3de4269` 增加私有判官原返回/哈希/原因码与批量格式反馈；六题新live捕获 G1b 的 `nonfactual + anchors=[1]` 非法组合，三包转为来源绑定拒绝。`58f28c2373328a7b5f87f3d5c87ed0a0ba3e3b14` 对齐生成schema与原严格规则、明确逐字引文和材料ID，再跑 G1b/G2b/三包五题：G1b结构通过但仍认领未核实历史，G2b文本基本满足材料代理判据；三包进入审稿却分别预算耗尽、报告非法、复核超时，整体仍不接纳。包2再次返回 `unsupported + anchors=[1]`，直接反证“schema已发出等于模型会遵守”。两个非法返回原样离线重放均拒收，不自动改报告或放宽接收端。

两轮服务已停，原题/八问/审稿闸不改，旧0/12不翻案；六题加五题是11次执行、6个不同题目，不是新11题分母。驱动均保持 `not_evaluated`，作者意见另存。G2b不代签真实台账/字段传播/权限/身份/跨轮，Q14漏判仍未修。

离线量具 `798ccefb7289b36a88f478e2cb3414fe5f1dc0b0` 已将格式错误码、协议失败元数据与逐阶段预算归入 `inspect_run`，不输出私有原文。固定干净树统一定向 **1519P/2S/1X/0F**，Ruff及收据验签通过，两条撤保护反证见红；这是定向集合，不是本版本全仓、前端或组合main认证。旧工程收据仍只签各自SHA，PR WIP、未合未部署。

[本轮快照](../../handoffs/2026-09-23-knevo-protocol-repair.md)记逐题事实、被否方案和续接顺序；统一索引 `~/.finance-runtime/knevo-absorption-20260923/protocol-repair-closeout/current.json`，两组原件分别封存100/88文件。下文入口修复和旧最终快照保留历史，不覆盖失败。

## 09-23 后续入口修复（历史快照）

代码 `f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6` 已修复材料范围/虚构身份、编号题漏识别和材料型Q14题型投递；真实 `run_turn` 装配探针覆盖12题，干净定向580P/4S。新隔离live现已全部结束：12题私有原题保真、均material_only、0工具请求，三包八问完整进入合同；Q14为news_impact，离线重建提示hash与运行事件精确匹配，三层指导确已送达。受测入口证据不等于整轮全部IO认证。

**新live仍9 completed/3 failed，端到端0/12**：判官协议失败3、来源核验拒绝3、无效出稿/漏答5、实质越界1。Q14内部judge passed，却无充分依据称订单小额、情绪很可能主导和大概率回吐，作者复核不接纳；条件措辞不是证据豁免。隔离服务已停，生产8792未动。逐题事实和作者意见见 `~/.finance-runtime/knevo-absorption-20260923/material-repair-f1fd8aa1a/observations.json`；179文件manifest已验哈希，驱动semantic_verdict仍为not_evaluated，不冒充独立验收。

工程固定候选 `8aadc23d4873251ffb3b0ecf4f9355f111ba6253`：全仓14664P/85S/2X/0F，完整收集面14751，Ruff/收据验签通过；前端120P、E2E34P/2S及其余四步、registry五项通过。PR diff-check仍因冻结原件空行exit2（七份hash一致），附加共享vault lint仍exit1，不宣称所有检查全绿。索引在同根 `material-repair-closeout/current.json`，只签实际测试SHA，不代签本次后续文档提交。

[最终快照](../../handoffs/2026-09-23-knevo-material-repair-closeout.md)记录逐题分桶、Q14漏判、完整收据及主干漂移；[阶段快照](../../handoffs/2026-09-23-knevo-material-entry-repair.md)保留修复过程。下文第3节与旧observations仍为修复前原件，不改判、不覆盖；新旧两轮都不能证明质量增益。

## 1. 材料 → 决定 → 实现/回归 → 证据

| 材料 | 吸收决定 | 实现或回归 | 已知边界 |
|---|---|---|---|
| Q14 小作文 | 只吸收事实/解读/情绪的结构；不吸收现场数值权重、情绪溢价公式或交易窗口 | `research_workflow_guidance.py` 的 `news_impact` / `fact_check`，两条生成引擎共用；Q14 揭盲题纳入回归 | 旧live落general_finance_qa；f1fd新live为news_impact且提示hash确认送达，但Q14判官漏判、作者不接纳，不证明方法增益 |
| Q18 三组 | 吸收为揭盲材料代理题，不升级为真实存储/检索能力 | 8 个材料代理题 + `knevo_regression.py` + `workbench_probe.py` | 不验真实台账、空集、权限、身份隔离、跨轮继承；不改冻结 28 题 |
| 09-17 三包 | 保留冻结原题及 7 个候选映射；三包是 3 个完整题包，不拆成 24 个样本 | `K260917-pack1/2/3` 回归题和 reviewer-only 判据 | 揭盲、单侧、A/B 同包，不是基准或独立盲测；原答不是金标 |
| 44 轮早期问答 | 按自述、UI、工具回执分证据层；补第 1–14 轮处置 | `rounds01-14-disposition-2026-09-23.md` | 外部后端真相仍未知；`finance_memory_write` 单次回执不能证明所有写入都无审批 |
| 风远原料 | 恢复 ZIP、66 卡、40–44 轮切片和定位索引；不重复灌入画像 | runtime `source-recovery/`、来源恢复文档 | `/tmp` 临时筛选稿原字节仍丢失；未重验全部成熟度/效果；未确认当前 UI 用户或生产挂载 |
| R6/Q15/B线 | R6 停研究检查表，Q15 留观察词表，B 线暂停新增但保留红样本 | `position-framework.md`、`ab-ledger.md` | 无收益回测、无干净成对样本，不报胜率/top3，不启用 `RELIABILITY_DOWNWEIGHT_THRESHOLD` |
| knevo28/宽基 | 只恢复入口和接替指针，不搬未审 WIP、不重造 compiler | knevo28 spec、#815/#821 来源说明 | 今日生产覆盖、完整消融和旧矿重放未由代码存在补签 |

## 2. 代码与确定性验证

- 揭盲套件状态固定为 `revealed_regression_not_benchmark`；每题有题面哈希、pass/fail/not-tested。`prepare` 只导出题面和 reviewer-only 判据，规则不进模型；`inspect_run` 校验 run/题面/工件哈希、frame 来源、工具轨迹和内部状态，缺 Episode audit 记 **unknown**，不记零调用，也不自动语义评分。
- Q14 的生成指导新增消息三层；它仍是生成指导，不是权限器、路由器或语义审稿器。`RELIABILITY_DOWNWEIGHT_THRESHOLD=None` 保持关闭。
- 固定提交 `85bff632610d0b0861d6afae7f410cc498392f11`：
  - 定向 Python 回归：**325 passed**，收据 `~/.finance-runtime/test-receipts/20260922T180913Z-85bff632.json`，`dirty=false`，revision 一致；
  - 全仓 Python：**12567 passed, 85 skipped, 2 xfailed, 0 failed**，收据 `~/.finance-runtime/test-receipts/20260922T183622Z-85bff632.json`，`dirty=false`；
  - Ruff：exit 0，日志 `~/.finance-runtime/knevo-absorption-20260923/ruff-85bff6326.log`；`git diff --check`：exit 0；
  - 前端独占树同 revision：`pnpm install --frozen-lockfile`、lint、typecheck、组件 **110 passed**、build、E2E **34 passed/2 skipped** 全部 exit 0；收据 `~/.finance-runtime/knevo-absorption-20260923/frontend-gate-85bff6326/frontend.json`。
- 这些是工程门禁，不是研究质量、工具权限或用户语义验收。前端收据中的 build 只证明构建成功，不证明本报告的真实入口结论。

## 3. 12 题真实入口逐题结果

证据根：`~/.finance-runtime/knevo-absorption-20260923/`，后 8 题在 `remaining/`；机器可读汇总为 [observations.json](batches/2026-09-23-regression/observations.json)。两批服务均 dirty-tree、`continuous_glm / glm-5.3-flash`，用户/episode/data 写根隔离，但共享知识库仍可读；因此不是 OS 级沙箱，也没有 before/after 因果对照。两批均已停止，未自动重试。

| 用例 | run 尾号 | 交付/题型 | 工具与范围 | 作者侧结论 |
|---|---|---|---|---|
| G1a 有记录 | `003624_945344` | completed / general_finance_qa | material_only；Episode audit 有，0 tool request；judge unavailable | 只剩复核不可用提示，未回答 |
| G1b 检索空集 | `003847_513700` | failed / general_finance_qa | material_only；audit 有，0 tool request；缺 direct_answer/evidence_boundary | 未交付，`invalid_repair_finish` |
| G1c 读取失败 | `003932_899615` | completed / general_finance_qa | material_only；audit 有，0 tool request；权限边界写对但内部 partial/rejected | 文本满足代理规则，但整链不通过 |
| G2a 新价旧档 | `004458_152606` | completed / general_finance_qa | material_only；audit 有，0 tool request；静态 PE/日期边界写对但身份编成 real | 文本满足代理规则，但整链不通过 |
| G2b 间歇字段 | `004751_005392` | failed / general_finance_qa | material_only；audit 有，0 tool request | `invalid_repair_finish`，NULL 解释未交付 |
| G3a 原排序失效 | `004842_736035` | completed / general_finance_qa | `material_contract` 为空；audit 有，0 tool request | 只剩证据不足模板，未回答失效前提 |
| G3b 窗口冲突 | `005128_701521` | completed / general_finance_qa | `material_contract` 为空；调用 `kb_search` 1 次 | 文本选 B 有对，但违反“不查库”并带入真实公司，范围不通过 |
| G3c 异机制 | `005651_631859` | failed / general_finance_qa | material_only；audit 有，0 tool request | `invalid_repair_finish`，未交付 |
| Q14 消息三层 | `004200_900107` | completed / general_finance_qa | `material_contract` 为空；audit 有，0 tool request | 最终通用题型，专项纪律未送达，未回答三层 |
| pack1 景气 | `005843_816502` | completed / kol_review | local_only；audit 有，0 tool request | 未答八问，证据不足模板 |
| pack2 利润/估值 | `010000_266528` | completed / valuation_estimate | local_only/real；`evidence_lookup`、`memory_lookup` 各 1 次 | 越过“仅用材料”范围，未答八问 |
| pack3 来源/改判 | `010139_417143` | completed / clarify | 无 Episode audit；只澄清材料/指令边界 | 未答八问；不能把无轨迹记成零 IO |

汇总：**9 completed、3 failed；作者文本层只有 G1c/G2a 两题有限满足代理规则；端到端接纳 0/12。** 驱动条目的 `semantic_verdict` 均保持 `not_evaluated`。这不是模型错误率、Knevo 胜率或 top3，也没有完整消融。

### 题面、路由和公开 frame 的证据边界

- 12 个 `run.json.question` 都与冻结 suite 原题逐字匹配（pack3 也匹配）。前 11 题有私有 Episode frame；pack3 只有公开 `report.json` frame。`inspect_run` 与当前 `observations.json` 均标出 `frame_source=private_episode` 或 `public_report`；pack3 的 `frame_source=public_report` 不能把公开缺字段倒推为真实输入缺失。
- pack1/2 私有 frame 与原题只出现末尾换行差异；pack3 的公开 frame 缺 D0/D2/D3/D4。离线复现 `sanitize_user_visible_artifact_text()` 会吞这些日期标签，`conversation_orchestrator._redact_object()` 会递归清洗公开 report。因此已确认的是**公开工件保真/脱敏问题**；实际控制器或模型输入是否完整仍未知，需清洗前私有记录或控制器级审计。
- Q14 离线 `plan_answer_question → ask` 合成路径可得到 `news_impact`，但真实材料入口最终是 `general_finance_qa`；单测名称不能被解读成 Workbench 完整材料入口验收。

## 4. 根因分诊与重开条件

1. **材料范围编译/执行**：G3b 明示不查库却 `kb_search`；pack2 明示仅用材料却 `local_only` 并调工具。先复现 `split_user_message → compile_material_contract → task_frame → registry` 及早期预取；接替现有 E2 边界线，不新建第二权限器。修后原题不改，需证明工具尝试为 0、约束到达执行者。
2. **路由/题型**：Q14 的纪律只到专门 ask 合成路径，Workbench 材料入口换成通用题型。修后需同一正门证据证明最终题型和指导均到达，不用 planner 单测代签。
3. **出稿/复核**：G1a/G1b/G2b/G3a/G3c/Q14/pack1/pack2 有 invalid finish、缺 required output、judge unavailable 或降级模板。先按 artifact 的 `invalid_action`、finish、missing output 分桶，不能把运行故障归因于研究方法，也不能关审稿闸凑绿。
4. **Q18 真前置**：代理题之后仍须真实台账存在/空集/权限失败、字段缺失传播、身份隔离、跨轮改判；这些未验不能升级 `candidate_not_wired`。
5. **风远**：若重开画像，先经当前 userspace/launcher 确认身份，再做内容级去重、跨语境复现、生成力、独占性和人工审批；恢复索引本身不触发写入。

## 5. 明确暂缓 / 不吸收

- 不把 Q14 的数值信源权重、情绪溢价减法、反向交易窗口写成规则。
- 不把 R6/Q15 的阈值、仓位动作、止损或“必然回升”写入策略；不照搬未经回测的数字。
- B 线暂停新增而非废弃；干净成对样本仍为 0，不报胜率/top3。
- W3、E-002、E-006、T-001 暂缓；无完整消融、独立样本、成本质量前沿或审稿盲测证据。
- 不把公开 report 缺字段写成模型输入被删；不把 completed、非空消息或内部 `completed` 写成语义通过。

## 6. 交付界线

本轮交付的是“材料 → 吸收决定 → 实现或回归 → 失败证据”的可追溯闭环。它没有证明研究能力提升、Knevo 胜率、top3、真实权限/身份/跨轮闭环或完整语义验收。PR 保持 WIP；材料范围/路由已补入口回归，出稿/判官缺口及新同题真实入口结果另记，不能凭入口测试关闭语义验收；合 main、生产切换和画像写入仍需另行确认。
