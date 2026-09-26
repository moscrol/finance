# 自主研究反馈：原留出题诊断与计划约束修补

日期：2026-09-20/21；分支 `feat/adaptive-research-loop`；工作树 `~/finance-worktrees/adaptive-research-loop`。

## 结论与版本边界

**两个协议问题已修、软件回归通过；真实研究质量未验收，材料授权样本明确失败，不可上线。**

- 原四道留出题全部在 `ced8203c`、原业务 `469ba766` 上完成，共八次真实 Workbench 会话。完成之前没有改业务源码。
- 业务修补 `1205ee7c`：回传真实计划修订约束；允许证据足够的单一事实在检查点直接 FINAL_JSON。
- 测试补充 `000a7ca4`：非法修订、无证据收口、合法重排及真实反馈路径。此提交未改业务源码。
- 新版本没有重跑完整八次会话。两个冻结前缀实验只改变检查点内容，不能替代整轮研究质量验收。
- 默认 `WORKBENCH_ADAPTIVE_RESEARCH=off`；未 push、PR、合 main 或部署。8792 健康，仍为 `bf662e9310ff751a4c31763815ee78fb7d6d5122`，生产默认模型仍是 glm-5.3-flash；本轮实验模型是 kimi-k3。

## 背景

此前开发题经历了不提 PLAN、代码框拒收、引用超限、尾部说明拒收。最后单臂接通五个视角，但只有一份已接收计划，尚不能证明随观察改变研究。此次目标是用不同问题暴露通用失效点，而不是继续为十只股票题补名单或指定视角。

题面、顺序、模型和旧 fixture 哈希在外部原件 `protocol.json`。`reviewer_checks` 没有发给研究模型；匿名审查另行调用、与研究上下文隔离。四题在用来诊断之后已成为回归题，不能继续声称是未见样本。fixture 保留原 split 标签，同时修正说明。

## 按发现顺序

### 1. 同版本八次会话

所有题的 off/on 检查均为同加载指纹、同初始配置；加载指纹为 `0cfe85248dd84c0ff111405bd3868fabd82a2f29c0faba4b1eb34b8f7b077d45`。交替采用 off/on、on/off。实时数据未冻结，每臂每题仅 n=1。

| 题目 | off 模型/工具/非法 | on 模型/工具/非法 | off/on 秒 | on 父会话已接收计划 |
| --- | --- | --- | --- | --- |
| 降息事件推演 | 3/8/0 | 6/10/0 | 176.76/295.12 | 1 份，revision=1，6 视角 |
| 长电/通富比较 | 6/13/0 | 15/19/2 | 337.27/411.87 | 1 份，revision=1，0 视角 |
| 上证最新完整日涨幅 | 2/1/0 | 4/1/3 | 78.43/60.30 | 0 份 |
| 中际旭创本地风险 | 5/12/0 | 8/12/0 | 305.57/500.16 | 1 份，revision=2，6 视角 |

探针 exit=0 只证明运行与导出完成，不代表行为验收通过；简单事实两臂的 structural_status 均为 partial。

模型/工具数来自公开工件的 `outcome.usage`，不是父 durable `model_turn` 或全部 provider 请求数。公司 on reported 模型调用含支路，为 15；父会话只有 5 轮；provider_attempts 为 22。off reported 为 6，但父 durable 有 8 轮、provider_attempts 为 13。不可混用这些分母，也不能据单次耗时作快慢结论。

本地题第一次接收就标 revision=2，**数字大于 1 不等于发生过已接收视角计划之间的修订**。这四题的父会话没有展示两份连续接收的视角计划；支路未做完整逐轮复核，不能将该断言扩展到所有内部研究。

### 2. 两个协议失效点

公司比较：seq6 接受无视角 revision=1。seq40 的 revision=2 有八个视角，但改写原 answer_elements、遗漏 branch_goals；首次报错是不能移除原输出项。seq45 revision=3 修正输出项但仍漏两个分支目标，继续拒收。`reproduce_revision_rejections.py` 以原始模型输出重现两次错误。

简单事实：一次无工具检查点引发无效计划链，依次出现 `PLAN must be one valid JSON object`、未知字段 `perspectives_note`、非法 finish status。两臂核心日期和涨幅相同，但 on 多写了盘面背景。问题不是缺少一份固定视角清单，而是模型为解释“不需要视角”仍被要求造计划。

外部 `test_plan_revision_feedback.py` 先红后绿；正式测试覆盖同一失效形状。

### 3. 材料授权与公开答案仍失败

“只用本地已有资料”题的**两臂都调用 financial_data**；off 还调用 news_search。`episode_tools.financial_data_runner` 经 `ask_blocks._financials_bundle_for_llm` 调 `market_financials.fetch_financials_bundle`，默认真实链会用 urllib 联网取财报，不能因工具名像数据查询就判作本地读取。两臂答案仍以本地范围开头，故本题材料授权验收失败。这个失败不只发生在 on，不能归因为本补丁新添了联网权限；本片也没有修复它。

on 内部 gaps 记了财务数据不是本地知识库原文、估值现值未知、专项风险未回填，但公开稿没有完整列出。公开稿还出现缺少前件的“但同季净利……”转折，派生发现无法完整复核。off 单列了较多缺口，但将价格证据 E39 挂到监管空结果上，且在公告主通道缺口很大时仍给出“中等偏强”。

其余题也没有通过独立事实验收：事件题有来源层级及公开缺口问题；公司题两臂都有无日期公司答复、财务/估值时点混用风险，off 还混淆了 AMD 总营收与数据中心增速，on 数字较准确但有引用/主宾口径问题。更多视角或资料不能自动抵消这些缺陷。

### 4. 审查模型本身也要复核

四题已做隔离的匿名 A/B K3 审查，原请求、映射、来源哈希及原响应全部保留。不是人工验收，也不是独立来源核验。

人工复核没有照抄以下判断：

- 事件题审查把内部 gaps 当成已公开，实际公开稿仍漏重要边界。
- 简单事实审查把可按日历计算的星期也要求外部引用，不能据此判核心回答错误。
- 本地风险审查因为证据列表里没有监管项，就断言查询不存在。私有事件中确有指定窗口查询及“结构化查询无结果”；空结果没有 E 编号，原审查包漏了这类观察。这不撤销 off 的错引用，也不让“查不到”变成“不存在”。on 查询使用裸代码，是否完整匹配标识还需核验。

全分支 Spec 审查曾被 Codex 配额限制、K3 HTTPStatusError 和 ReadTimeout 阻断，失败原件不改判。修补之后又完成一次限定摘录的独立 K3 补丁审查，但这不是全分支 Spec/Quality 验收。

## 选择与被否方案

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 从当前已接收 PLAN 派生 plan_revision_constraints | 让模型知道校验器要求保留什么，没有第二份真本 | 采用；检查点与常规反馈共用 |
| 放松不可删输出项/分支目标校验 | 会让研究修订悄悄丢掉已承诺输出 | 拒绝，旧校验不变 |
| 宿主自动补回被模型删掉的字段 | 掩盖模型未遵守合同，trace 不再忠实 | 拒绝 |
| 按股票名/题面关键词固定视角或必查工具 | 把诊断题过拟合成生产流程 | 拒绝 |
| 证据足够的单一事实可直接 FINAL_JSON | 不为“不需要计划”制造另一份计划；仍经原终态校验 | 采用；不是承诺所有简单题零开销 |
| 把新指令返回 FINAL 当作修订成功 | 返回收口对象没有产生新的 PLAN | 拒绝，分别记录 |
| 本次顺便重做材料权限及公开稿投影 | 涉及不同所有权与验收面，不能用小补丁宣称已修 | 未做，保留明确阻断项 |
| 用匿名审查的偏好当上线结论 | 审查包不全、审查模型也会误判 | 拒绝，保留原审查及作者异议 |

约束内容只有 minimum_revision、preserve_answer_elements、preserve_branch_goals、preserve_perspective_ids。逐字保留指条目内容，不锁定排列顺序。检查点仅在无视角时进入，故其中保留的视角 ID 必为空；常规反馈才覆盖已有视角，正式真实循环测试已分别断言。

## 冻结前缀实验

`replay_checkpoint.py` 从原 durable events 经 derive_messages/to_provider 重建输入，断言消息数量相同且只有 checkpoint.content 改变；没有执行工具、没有增补证据。每个 old/new 仍是 n=1；旧的初始指令和常规反馈也保持不变，因此它不是完整新版本回放。

| 冻结前缀 | old | new | 能说明什么 |
| --- | --- | --- | --- |
| 简单事实 | 再次因 perspectives_note 被拒 | 返回可解析的 finish 对象 | 本次未再造非法计划；没有做最终语义验证 |
| 公司比较 | 再次因移除原输出项拒收 revision=2 | 选择返回 finish，不提交修订 | 不能声称真实模型修订被接收，更不能声称研究质量改善 |

两个结果文件均保留 `finish_semantically_validated=false`。没有补写模型计划、代写回答、补名单或覆盖旧失败。

## 验证与收据

- 干净业务 `1205ee7c` 全量 Python：**11975 passed / 85 skipped / 2 xfailed**，620.81 秒；17 条 warning 位于市场阶段玩具模型数值运算及 datetime.utcnow 弃用，不属于本补丁。收据 `~/.finance-runtime/test-receipts/20260920T163233Z-1205ee7c.json`，dirty=false、exit_status=0。
- 独立补丁审查之后只补测试。干净 `000a7ca4` 定向回归 **211 passed**；收据 `~/.finance-runtime/test-receipts/20260920T163502Z-000a7ca4.json`。services/runtime 与全量测试业务提交无差异。未把此测试提交冒充另一次完整全仓运行。
- 新增真实循环负向：删输出项、删分支目标、不递增 revision 均拒收且原计划不替换；无证据不能声明 completed，随后可以带缺口 partial；原条目重排合法。
- 全仓 Ruff、diff check、pre-commit、层级/路径/未读字段/注册与运行时目录门禁通过。
- 补丁审查提到的“检查点带已有视角”只属共享构造函数可接收但当前主循环不会到达的状态，已把检查点测试改为真实无视角状态，另在常规反馈真实回路验证非空 ID。未采纳“逐字保留等于顺序锁死”的推断，增加重排正例。
- 前端/E2E、最终合流门禁、完整独立 Spec/Quality 和新版本完整真实研究重复均未完成。已知材料授权失败，不可合并。

## 原件与收尾

根目录 `~/.finance-runtime/adaptive-holdouts-20260920/`：

- `protocol.json` / `results.json`：冻结题面与运行结果；各题 `protocol.json` 与 `inspection/` 给出配置、加载身份与计数。
- `<case>/<arm>/answer.md`：实际交付原答；`raw-run/continuous-episode.json`：公开完整工件；`episode-stores/`：私有事件。
- `revision-rejections.json`、红/绿测试日志、`frozen-checkpoint-replay-*/`：失败复现与协议实验。
- `blind-quality/`、`spec-review.jsonl`、`independent-spec-k3*/`、`independent-checkpoint-fix/`：审查与失败原件。
- `test-receipts/` 保存两个干净版本收据，完整测试日志保留。

**395 个非缓存文件已封存并逐项验 SHA256**；清单 `SHA256SUMS` 的 SHA256 为 `66431f27e3cfe132ed629209160906b45af71838afff96350d48b71da3618545`。校验日志在根目录同级 `adaptive-holdouts-20260920-verification.log`。原件和私有事件不提交 Git。

所有本轮 runner、审查、重放、pytest 进程已结束；8797 与代理 56232 无监听。主服务未动，其他工作树与 ingest 产物未清理。

工具沉淀：通用双臂控制/检查仍复用已入仓的 compare_adaptive_research.py 与 inspect_adaptive_research.py。本轮 runner/重放/审查脚本与原件一同封存，没有另立通用研究入口：它们绑定这批事件前缀、审查包尚漏空观察、样本太少，暂不适合推广成验收器。下一步完善审查包时优先并入现有 inspect，而非复制另一条管线。共享方法与能力图已回写；harness-reference 的 BUILD.md 有他人脏改动，本轮不触碰，通用搭建底座回写待干净窗口。

## 下一步与不要做的事

1. 先让“仅本地材料”真正进入工具执行授权并用阻断外呼的测试验证；同时修公开稿对重要缺口、推理前件及引用的保真。两者均需各自范围与真实入口回归。
2. 审查包补完整工具观察、空结果、失败状态和查询条件，不能只交 E 列表；再复验上述争议，不覆盖原判。
3. 在新版本上另取未见问题并重复对照，验真实判断/取证改向及公开答案。不要以 PLAN 数量、revision 数字、资料量或工具次数代替质量。
4. 补齐独立验收与所有合流门禁，再由用户决定是否合并和更新 8792。不得拿本报告的软件绿灯抵消已失败的行为验收。
