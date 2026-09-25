# 同会话审查反馈：工程验证与公开保真边界

## 背景与范围

分支 `feat/adaptive-research-loop`，工作树 `~/finance-worktrees/adaptive-research-loop`。
前片 `0cd4de57` 修复判官查询身份，不解决公开稿删掉前件后只剩转折后件、重要限制只留在私有 gaps 的问题。前片记录见 [查询身份交接](2026-09-21-adaptive-query-identity.md)。

本片继续本会话原任务：把审查发现送回原 Episode（同一研究会话），让模型有机会完整重写受影响推理。用户后续明确继续这条任务，不转去外审或 K3 调用。没有新真实模型实验、push/PR、合 main、部署或生产删除；自主视角仍默认 off。共用修订接线不由该视角开关单独控制。

业务提交：

- `b29f2ad60e347154c39f884970730e62e5f5f47d`：阶段绑定审查反馈、私有 gaps 判官输入、同会话修订提示与回归。
- `affe6bdd0a38fde45277a53e58502f67f8ace6a0`：分离诊断内容和续修预算分类，修正首轮全量发现的材料重写退化。

最终收据只绑定干净 affe6bdd。后续产品门补充、此快照和 inflight 是文档改动，不把旧收据移绑到文档 tip。

## 按发现顺序

1. 既有 `sentence_verdicts` 已保留审查阶段、原句和理由；旧反馈只用当前句索引，删句后容易错指。`semantic_repair_feedback()` 沿原账提取结构化字符串，旧 `claim_index` 仅作兼容回退。语义解除不能清除独立机械拒绝。
2. 判官输入新增 `declared_gaps`，要求核对公开结论是否缺少必要限定。声明只是原稿的私有诊断，不是事实、指令，也不算公开披露。
3. Adapter 将这些发现交给原 `REPAIR_GOAL`，harness 要求模型重写完整判断和转折、保留证据绑定、不自动恢复拒句。沿原历史、权限、预算与进度门，没有新增状态真本或续修额度。
4. 定向验证通过后提交 b29f2ad6。首轮完整 Python 回归却出现1项真实退化：`test_judge_rejected_gap_can_rewrite_without_tools_or_stale_revocation` 不再 resume。新诊断同时进入既有 `rejected_claims` 预算分类，错误阻止了原来允许的零工具材料重写。
5. 在隔离临时树复现并修复：`classify_repair_need` 仍接受旧 rejected_claim_indexes 转换值；分类完成后才用独立 `review_feedback` 丰富修订目标，保持 shape/work_units 不变。材料测试增加原句、judge阶段与零工具额度断言。没有删除分类条件或加反馈专用豁免。
6. 首轮全量结束后，把补丁移回正式树并提交 affe6bdd。重跑完整 Python、最终版五项撤线、前端/浏览器和注册表检查。测试与临时服务均结束，隔离工作树已正常移除。
7. 作者侧覆盖核对发现 SDK 仍有诊断裁剪和提示接线差异，未扩写成所有后端已完成。细节进入产品门与证据范围审计。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 原句、审查阶段、理由随既有拒句账回传 | 不依赖删句后变化的编号，可追溯原审查 | 采用；旧索引只兼容回退 |
| 按当前句索引重建原拒句 | 可能把问题指向别的句子 | 否 |
| 把私有 gaps 当判官上下文 | 可检查结论是否过强，但声明仍待证实 | 采用；明确不是证据或指令 |
| 自动把 gaps 拼成公开段落 | 私有诊断可能未核验或与正文冲突 | 否；应由模型结合证据完整重写 |
| judge lifted 就撤销全部拒绝 | 会误清独立机械问题 | 否；分账保留 |
| 诊断同时参与原预算分类 | 已被全量证明会误挡零工具材料重写 | 否；分类输入与诊断内容分离 |
| 为新反馈放宽预算/进度门 | 把“知道问题更多”误当成更多授权 | 否；使用原剩余额度和进度合同 |
| 自动恢复原被拒句 | 能恢复语法但也恢复未获支持断言 | 否；只保留原稿用于模型修订和审计 |
| 因脚本模型能重写就宣称保真完成 | 测试替身按预设返回答案，不证明真实判断能力 | 否；只认可工程通路 |
| 顺手覆盖 SDK 与所有降级路径 | 其裁剪、提示和预算合同需要单独压测 | 本轮不推广，明确列为后续 |

## 工程验证

解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

| 项目 | 结果与边界 |
|---|---|
| b29f2ad6 首轮完整 Python | 12047P/1F；实际材料重写退化，失败收据保留 |
| 修复定向 / 扩展 / 提交前 | 216P / 529P+1X / 227P；误指定不存在路径的 exit4 零执行不算红测 |
| affe6bdd 完整 Python | 12048P/85S/2X，17warnings，1355.96秒；dirty=false、exit0，依赖和精确revision校验通过 |
| 最终五项作者侧撤线 | 去adapter反馈、去declared_gaps、误清机械问题、去原句、让诊断影响分类，五组均实红；基线/恢复各12P，无collection error/skip |
| 前端干净临时树 | 安装、lint、typecheck、110单测、build通过；Playwright浏览器34P/2S；首尾干净和六份日志哈希校验通过 |
| Ruff / 提交门禁 | 通过；最终全仓Ruff另留日志 |
| Registry五项 | exit0；ledger crosswalk有98条既有反向warning，不宣称零警告 |
| 能力图定位审计 | exit0，92行/243断言，192条在途或未核验；不是功能验收 |
| 旧证据完整性 | 四题395、本地边界46、查询身份73文件，全部哈希通过 |

完整 Python 的17项warning来自玩具模型数值运算与 datetime.utcnow 弃用，不是“零警告”。本分支工程绿不是最新基线合流后的验收。

真实离线 Episode 回归包含 GLMAgentRuntime + FinanceResearchHarness + ContinuousTurnAdapter：原稿、工具观察、证据仍留在同一历史；判官 llm/off 两种模式都验证机械反馈重入。模型是预设替身，不是自然模型。关闭判官不等于关闭机械检查；也不等于 gaps 会接受语义审查。

## 证据封存

根目录 `~/.finance-runtime/adaptive-repair-feedback-20260921/`，104文件已封存，`SHA256SUMS` 全部校验通过。

清单 SHA-256：`9febe9ab60496bc73ed2e4c6f5d930579a7048fde5a071b7820ff07bc80f9878`。
目录外校验日志 `~/.finance-runtime/adaptive-repair-feedback-20260921-verification.log`。

关键文件：

- `README.md`、`scope-audit.md`：发现顺序、原件索引与适用边界。
- `20260920T190232Z-b29f2ad6.json` 和对应全量日志：首轮真实失败。
- `20260920T192743Z-affe6bdd.json`、`full-pytest-affe6bdd.log`、`receipt-check.log`：最终收据与核对。
- `mutations/` 是原始四项；`mutations-final/` 是最终五项，保留定义、diff、结果、log/XML。
- `frontend-final/frontend.json`、六份日志与 `frontend-verification.log`；`frontend-fixture-results.tgz` 是隔离假用户和假市场数据，不是生产数据。
- `changes.patch` 是两个工程提交；`previous-*-verification.log` 保留旧档核对。

复验另建目录和临时树，不能原地重跑覆盖封存包。`collection.log` 仅收集节点；进行中的零执行收据、不存在路径导致的 exit4，都不能当验证通过或承重红测。

## 未验收与下一步

1. 自然模型能否保留完整推理、公开重要来源/估值/专项风险限制，仍未验收。旧四题失败样本不翻案，n=1、未冻数据也不能拿来判断速度或趋势。
2. 无预算或数字补证无进展时，既有合同仍可能不准续修，删句残片仍可能被交付。下一步先核验不增加额度的反馈时机和诚实降级，不能靠额外调用绕过合同。
3. `OpenAIAgentsRuntime._bounded_repair_goal` 仍取前20项、每项前500字符，可能截断 JSON 诊断；SDK 直接使用该投影，没有调用新增完整重写提示。本轮未做 SDK 原句/诊断完整性端到端验证。
4. 生产判官 off 不执行 gaps 的语义检查，工程接线不能代替开启判官的效果验证或开启授权。
5. 请求范围不等于实际覆盖；前片裸代码300308与300308.SZ口径风险未修。其他工具自由文本范围、子研究逐轮、自主视角持续改向也未验证。
6. 独立 Spec/Quality 与合流后的行为未验收。本轮没有付费外审或新模型调用；合 main、部署、付费外审、生产删除仍须先停。

下一次新模型验证应保留实际公开稿、原稿、事件、审查与修订历史，并分开判断事实支持、表达完整性和关键限制披露。不得补固定股票池、必查清单或代写答案来使样例通过。

## 工具与共享记忆

运行和变异判定复用仓内 `scripts/review_probes/run_extraction_mutations.py`，前端复用 `scripts/run_frontend_gate.py`。两份一次性驱动在证据目录保存的是本次revision、变异配置和调度，不另造通用执行器；没有仅留在 /tmp 或聊天中的工具。真实漏洞已修生产代码并有定向回归与撤线承重检查，不是只写一条经验。

“诊断信息与行动许可必须分开”已进入共享闭环原则笔记；能力图更新实际函数定位及限制，项目笔记仅放日期快照索引。此模式的可执行保证落在预算分类不变和零工具材料回归中，不以方法论笔记替代测试。未改他人脏工作树或 harness-reference/BUILD.md。
