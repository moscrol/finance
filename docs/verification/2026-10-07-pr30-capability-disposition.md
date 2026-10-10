# PR #30 能力接替对照：不能按「#54 已替代」直接关闭

## 结论与适用版本

**建议保留 #30 为草稿；不整枝直接合入，也不以 #54 为接替指针关闭。**
四片能力仍有独立价值，按下表保留意图，在发布运行时批次落定后重新合成、验收。
本页完成的是去留证据与建议；关闭/合并由用户拍板，不替代 FINANCEWORKS-14 的质量依赖。

- 当前主干：`ea217633ceeaceeb41d3b3f30fa58708fe14ecc9`。
- #30 固定 head：`bffc675daef6318cdacb1bf2b18ae0e740ecac63`。
- #54：合并提交 `f3b97499aaff267d34bc69a1ea2bfe09b609ae85`，产品 head `9556f6e35e0da5bb5eac6b936347a74207b3c2ca`。
- 旧 owner-output 候选：`4cba44a63950a5671e4be8d2d40f71e5ef3c2e50`。
- 本轮只读源码和离线函数对照；零模型请求，未合并/关闭 #30，未改其活动树。

`git cherry` 仍有 14 个独立提交，包含文档，不等于 14 项独立功能。
本轮 `merge-tree --write-tree --name-only` 对上述准确两端只报告一个文本冲突：
`intelligence/tests/test_episode_protocol.py`。旧文档中的“五个交叠文件”不是本轮冲突数；
自动合上的产品文件仍须审语义，不能只修这一个测试冲突就签集成通过。

## 能力 / 消费者 / 接替矩阵

下表的 main 和 #30 都指上述固定版本。源码路径可分别用 `git show <SHA>:<路径>` 复核。

| 能力 | main / #54 实际状态 | #30 独立变化与消费者 | 处置建议 |
|---|---|---|---|
| 模型撤回自拟研究计划 | `research_plan.validate_plan_revision` 拒绝删 answer_elements、branch_goals、perspectives；#54 未改此文件 | 显式 `base_revision` + 撤回理由，版本串行接纳；legacy 保旧义。`adaptive_research`、Episode/参考loop/SDK与协议同步消费 | **保留**，不把模型自拟计划当用户义务；不撤授权/预算/已发生费用 |
| 可选项贯穿完成、补写、失败投影 | `RequiredOutput.required` 已存在，但 `FulfillmentItem` 不带它；`missing_required` 返回全部未完成项 | item 记录 required/origin，missing_required 只含必需项；终稿/补写/失败投影同源 | **保留**，这是消费者丢字段，不是再加一张槽名白名单 |
| 输出来源身份 | main 的 RequiredOutput 没有 origin/merged_origins；TaskFrame 只有ID列表 | `output_requirement.py` 共享身份；TaskFrame、factory、owner别名合流、授权快照与履约序列化保真；同名合流 required OR + 来源并集 | **保留**，但标签不是自然语言解释正确性的证明，legacy默认槽也未全部迁移 |
| 稳定原请求与可变目标解释 | main 无对应 `RootRequest` / `TaskInterpretation` 对象；#54 改Controller路由，不提供这个协议 | `request_interpretation.py` 冻结原件，PLAN提案单独版本化goal；`ResearchHarness.admit_interpretation` 由三条loop消费，注入harness也拥有反馈 | **保留有限范围**：只改goal，不改题型/主体/时间窗/权限/输出/根预算，不宣传为完整在线题意重编译 |
| 跟踪/排序方法建议化 | main adapter 的 `_with_track_contract_gaps` 仍合入模板缺项，收据 `missing_outputs` 表示模板缺件；#54 未替换该链 | 从Episode完成/修复出口撤模板追加权，保可选提示及诊断；v2收据 `authority=advisory`、模板缺件另列 | **保留**，只迁Episode；旧CLI、解析/登记不因此获得新合同 |
| 无效PLAN与同包工具 | main与#30存在不同接纳逻辑；不能由“字段解析支持”推定派发安全 | #30在两条loop闭合每个call回执，未接纳计划不借deadline flush派发；版本/提示/工具副作用共同验 | 作为计划片的**强制回归**保留，不独立扩新重试框架 |
| 真实核验诊断的修订机会 | main有语义修复，但模板缺项与拒绝反馈仍会混入分类 | #30将可行动 `review_feedback` 与事实 `rejected_claims` 分开；delivery机会耗尽不降格成progress再开工具 | 作为建议化片的**消费者接缝**保留，额外调用不能超预算 |
| 模型路由与资源上限 | #54已将更多市场研究交Episode，调整上下文/工具结果截断、子研究权限等；已在main | #30旧基线不包含后来的全部修复；两端直接diff中的“删除”有些只是主线后增内容 | **保留main**；重合成时不能以旧#30文件覆盖最新源，更不能把两端diff当可直接应用补丁 |

主要定位：
- `intelligence/services/research_plan.py::validate_plan_revision`
- `intelligence/services/task_fulfillment.py::{FulfillmentItem,FulfillmentVerdict,evaluate_task_fulfillment}`
- `intelligence/services/output_requirement.py::{RequiredOutput,merge_output_requirement}`（#30）
- `intelligence/services/task_frame.py::{TaskFrame,rebase_task_frame}`
- `intelligence/services/episode_factory.py::_initial_output_requirements`（#30）
- `intelligence/runtime/conversation_orchestrator.py::{_merge_frame_outputs,_specialized_owner_required_outputs}`
- `intelligence/services/request_interpretation.py::{RootRequest,TaskInterpretation,accept_interpretation}`（#30）
- `intelligence/services/research_harness.py::admit_interpretation`（#30）及三条loop的同名调用
- `intelligence/runtime/continuous_turn_adapter.py::_with_track_contract_gaps`（main）、`track_contract.contract_receipt`、`ranking_contract.ranking_receipt`

## 本轮可复核的离线对照

用生产解释器 `.venv-workbench/bin/python` 在两个干净checkout导入真实函数；阻断socket连接，
用户态指向本轮临时目录。主干侧使用review树 `3e6aba9b3`，逐文件SHA-256及Git对象比较确认
本次受测的8个运行时代码文件与 `main@ea21763` 逐字节一致。候选树为准确#30 head。
前后HEAD/干净状态不变，零网络尝试。退出0表示取证成功，不等于产品正确。

| 相同输入 / 场景 | main | #30 | 能证明什么 |
|---|---|---|---|
| 从PLAN撤去一个自拟研究项 | legacy拒绝，未实现显式base协议 | legacy仍拒绝；给准确base及理由后接纳 | 候选不是简单放松所有旧计划 |
| 一个必需项和一个可选项都未完成 | `missing_required` 同时列两者 | 只列必需项 | 必需性在真实履约消费者上的差异 |
| 普通自然段，询问跟踪 | 收据列3个模板缺项 | 相同3项进 `missing_template_elements`，missing_outputs为空 | 收据权责改变；单独看空列表不证明任务完成 |
| 同一段正文，询问排序 | 收据列4个模板缺项 | 相同4项进建议性诊断 | 同上；不证明该正文是好的排序答案 |
| 构建/重建同时含direct_answer和direct_assessment的TaskFrame | 两个ID都保留 | 两个ID也都保留 | #30没有做旧owner候选的前置身份去重 |
| 只公开证据边界，但内部仍带直接回答claim | direct_assessment错误地为fulfilled | 仍错误地为fulfilled | 历史语义覆盖反例两边仍在；不是#30新引入，也不能以新身份字段宣称已修 |

原件：`~/.finance-runtime/reviews/release-resume-20261007/`
- `pr30-seams-main-v2.json` / `pr30-seams-candidate-v2.json`：源码哈希、实际输出、身份和范围。
- `probe_pr30_seams.py`：一次性多revision取证包装，不另造判卷器。
- `owner-output-identity-test-source.py`：从准确 `4cba44a63` 导出的历史反例及构造器，未改测试去翻案；SHA-256在收据内。
- 第一版观察另存，不覆盖。没有在此借用旧全量绿或真实金融成绩。

## `4cba44a63` 是否已被 `output_requirement` 替代

**没有完全替代；两者在不同位置解决不同问题。**

旧候选在 `task_frame._clean_outputs` 编译阶段，当目标已存在时将 `direct_answer` 身份并入
`direct_assessment`，让生成、持久化与核验看同一ID。它明确不把 evidence_boundary/counterpoint
等独立要求当全局别名，也不静默重签旧frame。

#30的 `merge_output_requirement` 则在运行时已有执行槽的合流点保留强义务和全部来源；
它没有进入 `_clean_outputs`，本轮 build/rebase 实跑也仍得到两个ID。不能据类名相似关闭旧枝。

建议：
1. 保留旧候选和失败证据，不整枝合入；其提交消息自身就声明非release-ready。
2. 将**前置身份归一**作为#30后续接缝单独承接，设计时同时迁移ID与origin并集；不能直接删ID却留下来源元数据。
3. 将“边界正文冒充直接回答”的反例独立列为内容覆盖问题；不能靠放宽门禁、删除反例或整句词表过滤取得绿灯。
4. 有已落地的接替提交及相同反例验收后，才可用该指针关闭旧候选。#30当前本身不是有效替代凭证。

## 后续决策门

| 方案 | 本轮评价 |
|---|---|
| 现在按#54已替代关闭#30 | 否：上表多项未被替代，有实际函数差异 |
| 只解一个文本冲突，凭旧CI合#30 | 否：组合身份改变，语义消费者/金融质量未验 |
| 原样搁置且无接替表 | 否：继续制造重复工作；本页钉住保留项与缺口 |
| main运行时批次稳定后重新合成，保留四片意图并重新验收 | **推荐**：保最新主线修复，按交叠消费者逐项验，不扩无关产品范围 |

重新合成至少覆盖：最新协议测试冲突的双边意图、#54路由/上限、#55工具结果状态、#57正文
保留及#64/#65/#66核验器/数据消费者接缝；最后一项按实际合入集合调整，不默认draft已准入。
重跑准确组合的全量与前端/端到端，再按新留出和同模型预算做真实质量验收。
旧12题取消批次不得重开；本轮函数对照不是自然模型提升证据，也不启动模型实验。
