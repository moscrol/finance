# Harness 前向组合：固定版本工程验收完成，真实质量待验

日期：2026-10-04。任务 `FINANCEWORKS-3`，PR [#30](https://github.com/moscrol/finance/pull/30)。
本快照只签固定候选的工程与静态审查，不签回答质量、合入或部署。
继续真实实验前先读第六节；质疑版本、预算或工具去向时读第三、七节。
本轮收尾回读：验收接手方已将 `FINANCEWORKS-3` 置为 `in_review`（version 11），
并以 `arena-takeover-20261004-harness-quality-closeout` 接手 `FINANCEWORKS-6`（in_progress，version 5）
定位旧真实轨迹首错。本分支只回写工程收据与交接，不抢占内容任务；父任务仍 in_progress。

## 一、背景与固定身份

用户要的是较弱模型答得更准、较强模型复杂任务发挥更好，不是单纯减少模板或获得更多自主动作。
上一批 `25de6994` 的工程与独审已经完成，但主线随后纳入记忆具体纠偏、个人回顾失败出口、
前端日历时序和评测状态隔离。旧收据不能为这组新组合背书。

| 身份 | 固定值 |
|---|---|
| 本轮产品候选 | `51b66d52fd7ea8970dfab163f1c24704b298ac58` |
| 合入候选的 main | `04799bc6fb60472e5207275720f09d2ab0935c0c` |
| 原 PR 头 | `1811ed903934185dc0b85da1a5c00bd9e3131e27` |
| 上一批产品 | `25de6994bdb79b57e9cf06fcb81f6f5796c67079` |
| 本轮最后观察的 main | `ae02f420d2da6aebefe066b86f5c4f3d91532023` |

候选在独占 detached worktree（按提交检出的临时工作树）内无文本冲突合成；随后在同一 SHA 上完成
新门禁、变异和双轴复审。本人分支 `feat/harness-integration-1003` 已快进至候选并推送两端，
origin/Gitea 回读均一致。后续交接提交只有文档增量，产品收据仍属于 `51b66d52`，文档头与其 CI 单列。

最后观察的 main 相比 `04799bc6` 仅多 PR #37 的三份 `docs/handoffs/` 文件（四个提交）；
没有产品源码差异。本轮不追逐主线漂移，不把这段观察写成已合入最新 main 的证明。

证据根，下文简称 `B`：

```text
~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/forward-20261004T1256/
```

入口：`B/engineering-closeout.json`；逐项复算脚本 `B/summarize-closeout.py`，退出码 0，绑定 52 份输入哈希。
这是作者侧收据核对，不是第三份独立批准。

## 二、按发现顺序的推进

1. **先纠正模型与工具的概念混淆。** Workbench 已有 `SessionLLMSettings`、按用户隔离的 BYOK
   （用户自带凭证）以及自定义地址/模型能力。`continuous_glm` / `GLMModelClient` 是兼容命名，
   不是“只能 GLM”。Claude Code 只是临时代码复审客户端，没有成为产品依赖，也没有修改生产模型配置。
2. **固定 main 后独占树验组合。** 首次 doctor 选到了主树环境，依赖锁不符；改为显式指定已锁定解释器后通过，
   没有改共享环境。代码地图为空，不据此下架构结论。无文本冲突只表示合成成功，随后重新跑工程与审查。
3. **真实 HTTP 到假运输。** 六组配置经 conversation/messages API 进入真实提供商解析与运行器。
   假上游返回 401，仍会有作者以外的终结/恢复尝试；首轮“一次 401 只应一次调用”的假设失败保留，
   后续按全部调用及产品账本对账。六组共 18 次假运输，运行终态可以 completed，但报告为 partial、`llm.used=false`。
4. **新组合工程门与独审完成。** 新快照包含变异脚本，避免重演旧快照漏 `scripts/` 的盲点。
   两轴顺序执行、互不读取对方输出、仅 Read/Grep/Glob；不运行产品测试，不读取用户金融资料。
5. **推送候选、收齐远端 CI。** 先前的进行中状态原样保留，终态另写新目录；`51b66d52` 五项全部成功。
6. **另做零模型预算原型。** 仓外 SQLite 事务账本加真实 HTTP/运行器假运输接缝，先验并发预占和失败保留，
   不把原型悄悄并入固定产品。真实标准 API 仍未启动。
7. **回收本轮门禁树。** 两棵临时树进程已结束、无未提交源码，先保全残留与数据库克隆、归档引用推 Gitea，
   再按点名计划拆除。原活动分支、生产、回滚及其它活动树未动。

## 三、关键选择与被否方案

| 问题 | 选择 | 被否方案及原因 |
|---|---|---|
| 新 main 到来 | 固定 `04799bc6` 合成 `51b66d52`，重新绑定门禁与两轴 | 直接转签 `25de`：不能覆盖组合；每次 main 变化都重定正在执行的批次：实验身份漂移 |
| Workbench 多模型 | 复用现有会话提供商注入，六组离线核对 | 把 Claude Code 装进产品：混淆复审客户端与产品能力；凭 GLM 类名判断单模型：源码不支持 |
| 套餐调用 | 官方支持用途内按需做代码复审，不设人为人民币/批次总帽 | 沿用旧 50 元限制卡复审：已被新授权覆盖；挪给 Workbench 或自动切现金：越过用途/授权边界 |
| 标准 API 成本控制 | 先持久预占，再准入每次实际发包；已发包缺 usage 留 unknown | 只做事后费用汇总：并发与重试可先超支；断线即退款：不能证明上游没处理/没计费 |
| 独审非阻塞建议 | 查真实消费者与可达路径，记录边界，不扩大四片 | 为统一主 origin 标签或修既有排序等建议扩改产品：没有确定 P1/P2，且会改变受验身份 |
| 真实验收隔离 | 核对实际启动入口及全部可写路径，另加只读沙箱 | 只换 users；用 live_probe 测试代签旧 shell launcher：后者还缺三个状态覆盖 |
| 留出输入 | 逐轮只送完整 `turns[i]`，评分与后续材料留外部 | 直接复用读 `question` 的旧预检：会漏材料；统一拼汇总材料：会提前泄漏后续轮 |
| 下一道门 | 标准 API 准入和预注册后做至多 12 格预验 | 工程全绿就上线：不能证明金融答案正确；12 格即宣称两档收益：样本与检验不足 |

S1 仍遵循原决定：解释经注入的 `ResearchHarness.admit_interpretation` 接纳；loop 保留取消、
截止、PLAN 次数、工具同包、持久化与根预算。合并语义/交付反馈文字，不把旧裸 claim 索引绑到新稿。
canonical 因果义务保留，表达建议不获得权限或补写许可。

## 四、固定 `51b66d52` 验证

### 本机工程与变异

| 项目 | 本轮结果 |
|---|---|
| Python/Ruff | 20639 passed / 76 skipped / 2 xfailed / 0 failed/error/xpassed；collected 20717 |
| Python 身份 | Python 3.12.13，依赖指纹 `66726d345bf37ce5`；clean、完整收集面、未绕依赖门，收据审计 exit 0 |
| 前端六步 | 安装、lint、typecheck、test、build、E2E 全部 exit 0；首尾 SHA 一致、树干净；6 份日志哈希复核通过 |
| 前端读数 | 210 unit tests / 22 files；E2E 52 passed / 2 skipped |
| Registry | 五项 exit 0；当前只有 ws 仓，缺失跨仓项按工具规则跳过；101 条台账反向 warning 原文保留 |
| 四片变异 | PLAN 9、解释 15、来源 13、表达 14，共 51；每条有效失败且恢复绿 |
| baseline/restored | PLAN 321/321；解释 56/56；来源 54/54；表达 287/287 |
| 其它变异 | history 8，boundary 16；红绿与恢复审计通过 |

Python 固定解释器：
`/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`。
原件：`B/gates-51b66d52/`、`B/mutations-51b66d52/audit-final.json` 及各组原始日志。
不能把采集错误当成有效行为变异红灯。

### GitHub CI（持续集成自动检查）

2026-10-04 15:04 后回读，`python/frontend/e2e/registry-check/workbench-check` 五项均 completed/success，
每项 head SHA 精确为 `51b66d52`。

- [workbench run 37181781227](https://github.com/moscrol/finance/actions/runs/37181781227)
- [registry run 37181781251](https://github.com/moscrol/finance/actions/runs/37181781251)
- 原件：`B/readback-20261004T1504/candidate-*.json`；更早进度在 `B/promote-candidate/`。

### 独立 Spec / Standards 静态复审

| 轴 | 物理请求 | 回包模型 | 裁决 |
|---|---:|---|---|
| Spec | 91 | 全部 `glm-5.3` | 未发现确定 P1/P2 阻塞 |
| Standards | 73 | 全部 `glm-5.3` | 未发现确定 P1/P2 阻塞 |

真实客户端 Claude Code 2.1.282；合计 164 次 admitted/dispatched/completed，failed/cancelled/active 均 0，
全部有回包身份与 usage，shutdown 完整，后台已退出。两轴是同一模型的隔离会话，不是两个不同模型互证。
5 次 count_tokens 路由在本地拒绝，未送供应商，不混进 164 次。
Standards 有两次读取错误（大文件限制与路径写错），修正读取后完成；不能称全部工具操作零错误。

原件：`B/review/{spec,standards}/live/{report.md,audit.json}`。
输入未被修改，报告哈希再次复核。审查者没有执行任何测试或变异；工程红绿在上一表单独计账。
CLI 美元估价不是现金账单，推理 token 未单独返回，现金实付及 V2 配额折算仍未知。

### 建议处置与保留盲点

- origin 平手取 incoming：`required` 与 `merged_origins` 保留，已核 `task_fulfillment` 真消费者，未升级为硬义务丢失。
- 冻结表达槽名以 unknown_output/integrity 拒绝：这是本轮预期合同，现有产品门文档已描述模板名不能获可信绑定；不恢复旧补写语义。
- 纠偏摄入先于 controller 仲裁：源码顺序已核，纠偏属于上一轮用户授权；未增造“失败轮零副作用”的承诺，真实副作用仍需实验核对。
- 旧 `scripts/launch_workbench_sidecar.sh` 仅隔离用户与 Episode；未覆盖 `FINANCE_DEPLOY_LEDGER`、
  `FINANCE_REJUDGE_PENDING_INDEX`、`FINANCE_MEMORY_VECTOR_CACHE_DIR`。不是本轮新增缺陷，但不得直接拿它做本轮 live 验收。
- 纠偏检索键保留 `original` 可能带来排序偏向；交付文本不含 original，本轮计划不改排序。
  标签任一空/重复键导致全局 ambiguous/exit 2，以及 eval 严格读损坏台账而 CLI 返回 gap，均为保守准入设计。
- `_check_cancelled()` 至失败终局认领间仍有既有微小竞态；不宣称所有时序下取消均胜出，不借此扩大四片。
- 真实 SDK provider 时序、存储故障/重启恢复、逐句 claim 对齐、最终内容质量仍有动态盲点。
  Spec 对部分非交叠单父系代码仅看 diff；Standards 对 harness-vs-main 约九成 hunk 通读，余下夹具/文档抽查，
  不夸称独审逐字覆盖全仓。

## 五、预算原型与真实调用分账

`B/workbench-preflight/` 的四个 Python 文件是仓外验证原型，不是产品提交：
`shared_budget.py`、`test_shared_budget.py`、`check_budget_mutations.py`、`probe_budget_http.py`。

- 18 个离线测试通过；6 个行为变异均 exit 1 / 有测试失败 / 无收集错误，恢复 exit 0；Ruff 通过。
- HTTP/runtime 探针六组共模拟首发 1 次，401 缺 usage 后保留全部预占，其余 68 次尝试在本地拒绝。
  合成费率下 held=64000 micro-CNY（0.064 元等值），不是实付，不是报价。
- 所有作者、终结/恢复及跨 case 共享同一 SQLite 文件；事务预占防并发超额，已发包断线/崩溃/缺 usage 不释放。
- Controller 与开场预取被 mock；全部凭证为占位、socket 禁止，合成数据根只测接线，**没有真实金融问答请求**。
- 起初 red 是模块未实现导致的 `ModuleNotFoundError` / exit 2，保留为开发记录，不计行为变异。

这套原型尚未覆盖真实供应商输入/输出/推理 token 上界、完整运输/取消/旁路或独立安全复核，`live_ready=false`。
不因为离线账本通过就启动标准 API，也不把 68 次本地拒绝写成供应商请求或有效答案。

## 六、下一步准入及禁止误读

详细执行条件见树外 `B/workbench-preflight/admission-status.md`。当前尚未冻结新实验，未领取新 claim 号。

1. 另核合规标准 API 及有限现金边界；套餐无限制授权不等于套餐外无限现金。此前预算批准不证明充值到账，
   本轮没有充值/续订/改订阅，不索取明文凭证，不启用现金 fallback。
2. 真实运输必须每次发包前共享持久预占，覆盖作者/controller/核验/修复/子研究/判卷/重试；
   供应商 token 与推理计费上界须有一手合同。缺 usage 留 unknown，关闭 socket 不能证明上游停止计费。
3. 新建隔离 A/B 树与输出根，核所有写路径及只读沙箱；行情来自真实冻结只读数据，不能沿用离线合成 finance 根。
   `live_probe.sidecar_zsh` 的隔离修复与旧 shell launcher、旧 conversation 预检是不同入口，逐入口验。
4. 固定 A/B 真实 SHA、3 题完整多轮、数据、模型分档依据、6 对 AB/BA 各三对顺序、相同权限/资源、串行间隔、
   匿名全文双评及停止规则，经 `claim_ledger_id.py` 预注册。留出只发完整当轮 `turns[i]`；
   旧 `preflight_model_harness_conversation.py` 读 `question`，不能未经适配拿来执行留出集。
5. 最多 12 格仅预验，每格一次、失败计分，不补跑择优、不自动扩样；正式两档收益、最小效应/不确定性、
   一般题非退化和来源/对象/日期/单位/算术等金融严重错误门另验。
6. 质量门满足后再谈合入/部署与回滚。PR 仍 Draft/OPEN，无 auto-merge；Knevo 模型/源码/trace 未知，不能按型号认定强弱。

R17/R19/240、剩余 P1b、共享 Memory、其它活动树和生产配置均保持原边界。

## 七、生产观察、归档与工具去向

2026-10-04 14:02:49 的只读响应：8792 health=healthy、readiness=ready，source_revision=`04799bc6`，
source_dirty=false、code_matches_repo=true。是其它流程部署的主线，不是本轮 Harness 候选。
其 readiness 报告存在 4 个历史 open episodes；本轮未恢复/关闭它们。配置中的模型名也不是本轮供应商回包身份证明。
原件 `B/readback-20261004T1400/production-{health,readiness}.json`。本助手没有切链或重启生产。

两棵 `B/trees/{frontend,product}` 已拆。`B/tree-closeout/apply-20261004T151412.json`：2 removed / 0 skipped / 0 failed；
两份残留归档、4 个本地数据库克隆哈希与两条 Gitea 归档引用回读通过。它们不是生产数据库备份。
第一次 apply 从家目录运行且未给 `--repo`，exit 4、一棵未动；指定仓根后才成功，失败日志保留。
以后重跑在新输出根按固定 SHA 建树，不能覆盖本轮原件。

工具盘点：已有 gate/review/mutation/closeout 工具负责通用动作；本轮不再造通用框架。
预算与 HTTP 脚本故意保留为封存原型，尚缺真实运输合同与独审，不能现在提升为可生产复用的预算能力。
若推广，另立工具范围并补旁路/取消/故障/隔离验证；不能继承 `51b66d52` 的静态审查收据。
本轮也不写共享 `harness-reference` 或用户 Memory。

历史 sealed 根 `harness-integration-20261003/`、`harness-release-20261004/`、
`plan-review-20261004T1025/` 不覆盖。哈希只证明相对本机清单的完整性，不证明内容质量或密码学来源认证。
