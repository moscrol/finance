# Knevo 材料吸收处置报告（2026-09-23）

## 结论

**材料处置、可复用代码与揭盲回归接线已交付；真实入口验收未通过，不能称“全部炼化”。**
本轮只做可逆的研究侧收口：不合 main、不部署 8792、不回补生产行情、不写生产画像。状态以[吸收清单](absorption-plan-2026-09-11.md#2026-09-23-执行决定与当前状态覆盖下文历史建议)为准；本报告只串起来源、决定、产物和证据。

## 09-23 后续入口修复

代码 `f1fd8aa1a16bea4f3dd4e2ba0e5fd92114aea2c6` 已修复材料范围/虚构身份、编号题漏识别和材料型Q14题型投递；真实 `run_turn` 装配探针覆盖12题，干净定向580P/4S，均不代表答案语义验收。新隔离live首两题仍因判官无效工具报告降级，G1c仍有逐句来源核验缺口。新完整终态以 `~/.finance-runtime/knevo-absorption-20260923/material-repair-f1fd8aa1a/observations.json` 为准，缺文件不算通过；[修复快照](../../handoffs/2026-09-23-knevo-material-entry-repair.md)记范围和证据身份。下文第3节与旧observations继续作为修复前原件，不改判、不覆盖。后续文档固定候选工程结果单独见同根 `material-repair-closeout/current.json`，不移签旧全仓收据。

## 1. 材料 → 决定 → 实现/回归 → 证据

| 材料 | 吸收决定 | 实现或回归 | 已知边界 |
|---|---|---|---|
| Q14 小作文 | 只吸收事实/解读/情绪的结构；不吸收现场数值权重、情绪溢价公式或交易窗口 | `research_workflow_guidance.py` 的 `news_impact` / `fact_check`，两条生成引擎共用；Q14 揭盲题纳入回归 | 旧live落general_finance_qa；f1fd已补真实入口装配投递并离线验证，后续live另记，不证明方法增益 |
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
