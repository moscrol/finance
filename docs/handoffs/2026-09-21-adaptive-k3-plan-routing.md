# K3 写手单次验收：漏 PLAN 标签误催终局及离线返修

## 身份与结论

- 分支 `feat/adaptive-research-loop`，工作树 `~/finance-worktrees/adaptive-research-loop`。
- 真实验收 revision：干净 `129e6cbeaa452b8d38e1272a3a6410b2752acf83`；它与已全门禁通过的 `be6602934` 仅文档差异。
- 新业务补丁：`4c33e0d458be9cd171c4bb2f7de39b6ccb62d119`。完整旧门禁**不能移签**该补丁。
- **K3 可以当写手。本次 n=1 交付未通过，但不是网关 400、也不是 K3 角色不可用。** 故障在更早的计划类型识别：遗漏 kind 后被要求交最终答案，未查数据就停。
- 返修已获离线定向验证；**未跑修复版自然模型，不宣称真实研究质量通过**。未 push、开 PR、合回 main 或部署。

## 背景：为什么是这一题

此前东阳光原题曾出现“修正后的稿 B 自报 partial，却公开未经新核验的旧稿 A”。`continuous_turn_adapter` 的变稿重核、来不及则旧稿+partial+公开提示已修；后续 GLM 自然复跑都自报 completed，缺的是特定路径样本，不是 K3 写手能力。

用户纠正后授权“执行”：K3 写手，判官保留原 GLM，隔离 Workbench 真会话入口，同题单次，观察实际交付，不为碰到状态词无限刷。

## 发现顺序

### 1. 本地数据在，权限和服务隔离

- 原题逐字复用：“只用本地已有资料，不联网：东阳光(600673.SH)9月以来的量价表现如何，与所属板块相比强弱如何？给出具体数值、日期和数据来源；本地没有的部分单独列出，不要补。”
- 现有 `probe_tool.py finance_query` 前置只读：`stock_daily` 09-01～09-18 返回14条；`sector_stock_daily` 返回25条且被上下文行数预算截断。后者不能证明其它日期本地缺失。
- 没改生产 8792：旁车8797，既有 `compare_adaptive_research.py --arms off`，会话提交一次。单臂、数据未冻结，不是 A/B。
- K3凭证通过 pi auth 在内存获得，remember=false、Keychain禁用；判官另固定 `glm-5.3-flash` / coding 端点 / `ASK_SEMANTIC_JUDGE=llm`。配置成功不等于实际调用。
- 8797已关闭。生产前后快照均 `adcda94b5e40`，未切换；密钥扫描无命中。

### 2. 入口 completed，不等于回答了问题

run `run_20260921_192812_245529`，conversation `conv_cf4eeb0667d3422e85990defa8a9cbe3`。

探针94.73秒、外层97.35秒/exit0；但原件是2模型轮、0工具、1无效动作，input/output tokens 31996/742。公开稿只有“现有证据不足，暂不能可靠回答”，无量价/板块分析。

原件 `probe/off/raw-run/continuous-episode.json`：

| seq | 事件 | 可断言事实 |
|---|---|---|
| 6 | model_turn | 八项必需计划体字段齐全，只漏顶层 `kind=PLAN`；无工具调用 |
| 7 | invalid_action | parser说“非PLAN”，终局门报 `bad_status` / `invalid_model_finish` |
| 8 | model_input | `steering_invalid_finish` 要求“修复后只输出 FINAL_JSON” |
| 11 | model_turn | 模型返回无证据 partial；尚未取得数据被写成“本地暂缺” |
| 13 | finish | partial，最终发布不足证据的短兜底 |

两模型轮各 provider_attempts=1，无本次400。`metrics.judge_usage.calls=0`，`repair_attempts=repair_cycles=backfill_turns=0`。`phase_trace` 出现 repair 转换只是阶段投影，不是实际执行修复；不可拿它补签目标路径。

判官配置未变，但零有用输出被 `EpisodeSemanticVerifier._verify_inner` 提前短路，`judge_status=unavailable` 不证明判官服务故障。未见推理过程泄漏到短兜底，不能外推正常长答安全。

### 3. 修类型分流，不宽松接纳

`research_plan.parse_plan_candidate` 在研究尚未收口时把“完整计划体缺kind且无终局字段”的对象交回 `parse_research_plan`，生成严格缺字段错误。沿既有一次 PLAN 纠错，模型可保留当前会话修计划或直接选授权工具。

不补标签、不接纳计划、不执行 candidate_actions。顶层 status/draft/gaps/bindings/render_from_claims 任一出现，即使值无效，无标签对象仍走终局路径；部分形状不猜。已收口阶段仍跳过计划识别，不能重开研究。没有修改全局400重试、预算、授权、进度门、证据准入或公开稿手术。

| 方案 | 评价 | 结果 |
|---|---|---|
| 补窄候选识别，仍让严格解析器拒收 | 错误按真实工作类型回灌，不放宽准入 | 采用 |
| 自动补 kind 并接纳 | 静默改变模型输出，混淆识别与授权边界 | 不采用 |
| 所有坏 JSON 都提示继续研究 | 终局与已收口也会被反向打开 | 不采用 |
| 只强化开场提示词 | 不能修复已经发生的错误分流 | 不采用 |
| 再发模型直到碰到目标路径 | 成本增加且验收被选样，不能解决确定性断点 | 不采用 |
| 把本次失败写成 K3 不可用 | 两次正常返回已反证该归因，角色能力与路径覆盖不同 | 不采用 |

## 验证与收据

1. 原始seq6逐字节进 `intelligence/tests/fixtures/k3_missing_plan_kind.json`：1138 bytes，SHA256 `d643acc7ff9e913e7e4cc4744ae680b597f2aaefdbb1ad4b02b0a0149a7ff009`。不是重写后的理想样本。
2. 先红：新钉子9F/5P；修后四文件264P。这两轮开发树脏，只有红绿复现资格，不按129e6cbea冒签新代码。
3. 四项进程内变异，不改磁盘源文件：baseline24P；撤候选识别9F、终局误路由6F、部分形状推断4F、自动接纳漏标6F。失败exit1为断言，不是导入/采集异常；源码首尾hash同一。
4. **固定干净4c33e0d45：相关10测试文件748P/0F/0E/0S；Ruff全仓通过**。含原发布重核/partial上限、研究回路、协议、GLM装配与目录合同。测试前后SHA与工作树完全一致。
5. 精确收据 `~/.finance-runtime/test-receipts/20260921T114433Z-4c33e0d4.json`；副本 `offline/fixed-regression-receipt.json`。`check_test_receipt.py --expect-revision 4c33e0d45` 通过解释器/依赖/干净树/精确SHA；未声称当前主线合流准入。
6. 旧 `be6602934` 的12698P、前端110P/E2E34P2S等仍仅签旧版。新补丁没跑全量/前端/registry叶子，不是完整合入结论。

脚本化续轮会修PLAN或直接调用工具，只证明修复指令与执行通道保持，不是 K3 对新提示的自然反应。此次未新增真实会话。

### 私有证据包

根 `~/.finance-runtime/adaptive-k3-writer-live-20260921/`：README、execution身份、preflight、完整probe/inspection、原始稿/公开稿、offline红绿/变异/固定收据。

- `SHA256SUMS`：71件，逐项回读一致；独占pytest scratch不纳入正式包。
- 清单SHA256：`c7537ce4bb85b3f6dc107efb363814bf0eb75e78b1497fe1632ee54fd147870f`。
- 外部回执：`~/.finance-runtime/adaptive-k3-writer-live-20260921-verification.json`。
- FWP_TEST_RECEIPT在该版本只支持0禁写，不能指定输出文件；复制来自每次日志打印的固定路径，未读共享latest.json。

## 后续与不要做的事

- 若继续，授权下固定修复版做一次真实验收，先看工具取证/量价交付是否发生；再看目标“无工具修订+self partial”是否自然出现，未出现如实留缺口。
- “修后自然继续取证”“改稿重新核验并发布”“正常长答不泄漏”均未签；独立Spec/Quality也未做。
- 最新只观察到本地gitea/main已为79b11d4268a3，未fetch/追合；最终待合SHA变化后取对应完整门禁，不移签748P或be660全量。
- 不把缺某一验收样本泛化成“等K3可用”；不放宽HTTP400重试，不追加正文剥离，不自动猜股票后缀。
- push/PR/合main/部署另待授权。

## 沉淀盘点

本次不是建新编排框架：在既有PLAN识别接缝修了确定性分类，永久钉子落两个测试文件，原始响应进仓内小夹具。一次性进程内变异驱动随私有证据包封存，不新增公共工具入口；它不是跨项目通用工具，换协议字段后不可直接复用。

可迁移的是“纠错理由必须匹配输出类型/阶段，候选识别不等于接纳”：补入共享记忆 `retry-must-carry-the-last-rejection.md`，能力现状更新既有图谱行，不另建能力清单。共享memory树存在其它会话改动，只精确改本任务行/方法段，不提交他人的文件内容；harness-reference树脏，本轮不动。
