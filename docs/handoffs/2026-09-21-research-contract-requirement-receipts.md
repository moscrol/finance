# 研究清单逐项核验回执：实现与离线验收

## 背景与范围
本记录是 `fix/research-contract-citations-0921` 在已有研究清单、排名意图和公开引用身份修复之后的续作。目标是把“要求已送达模型”推进为“最终答案逐项有回执、公开稿仍保留回答见证、缺项进入有界修复”。

本轮仍是离线修复：没有重跑 09-21 三道冻结半导体题，没有调用模型或消耗 Knevo 名额，没有操作生产 `8792`，没有修改冻结首答、数据库事实、生产配置或运行记录。三方对照仍等待用户提供本批 Knevo 原答，本轮不作优胜判断。

## 按发现顺序

1. 现有 `MaterialContract.questions` 已经是原始题目合同和 `qN` 身份；新增要求协议复用它，不再建立第二套 checklist ID。清单识别继续保持窄门：研究引导语、独立要求标题、连续顶层编号必须同时满足，材料、引用列表和普通编号不获得控制权。
2. `explicit_requirements` 只能证明题面被投递给写手/判官，不能证明模型真的完成了题目。新增 `requirement_checks`，要求覆盖每个 `qN` 和显式子项，并返回状态、实际回答句号、理由和缺项。
3. 程序对回执做结构校验：缺题、重复题、未知题、漏项、重复项、未知项、非法布尔值、缺 witness、未知 witness、空理由、错误状态和额外字段都 fail-closed。对象数量、公司集合、信号数量、正反关系、第三解释、分母和期间仍交语义判官，不由字符串计数冒充证明。
4. 漏答与事实拒绝拆开。清单缺项只降低覆盖度并尝试既有有限修复，不删除正确事实，也不伪造 `rejected_sentence_indexes`；判官报告事实失败但没有可执行句号时，继续保持 fail-closed。
5. 最终公开文本会再次检查 witness。公开投影删除、改写或拆分原回答句后，旧回执失效，防止草稿阶段的 completed 状态被 stale receipt 抬回通过。
6. `requirement_qN` 只被 repair coordinator 视为契约表达缺口，复用已有 `contract_rewrite` admission。清单补写不增加工具权限、调用次数、时间预算或 cycle 上限，也不授予零证据编造公司、事实或阈值的权限。
7. verifier 的正常终局、事实题短路、tool judge、注入式 judge 和 adapter 的最终 publication projection 都统一执行回执复核，避免不同出口产生不同完成语义。

## 方案决策与被否方案

| 选择 | 被否方案 | 原因 |
|---|---|---|
| 复用 `MaterialContract.questions/qN` | 新造要求身份 | 防止写手、判官、修复和存储之间出现两套编号 |
| 结构化 `requirement_checks` + 程序校验 | 只看 `explicit_requirements` 或模型自报 completed | 送达不等于完成，自报不能成为状态机事实 |
| witness 在最终公开稿上复核 | 沿用旧草稿回执 | 公开清洗可能删句或改句，旧证据会过期 |
| 漏答降级并走既有 repair admission | 漏答触发新检索或零证据补写 | 保持读取权限、预算和证据不变量 |
| 事实拒绝与清单漏项独立 | 用缺项结果覆盖事实失败 | 不能因为“还漏一项”就把错误事实放行 |
| 完整账本先定 E 号再过滤 | 用公开列表位置重新编号 | 过滤后的位置不能恢复原证据身份 |

## 验证与收据

最终代码提交为 `ba18395ce229872e60cd80ebffb82577a3f65a67`，工作树 `dirty=false`。

- 固定范围定向回归：`1787 passed / 4 skipped / 0 failed`，收据 `/Users/a77/.finance-runtime/test-receipts/20260921T163733Z-ba18395c.json`，JUnit `/Users/a77/.finance-runtime/reviews/research-contract-citations-0921/requirements-fixed-ba18395ce.xml`。
- 范围覆盖研究请求边界、公开引用身份、连续适配器、Episode 协议与语义判官、材料权限、TaskFrame、检索/前置引用序号、会话投影、研究 harness、修复协调及清单协议测试。4 个 skip 是既有嵌套材料边界用例，不是本轮新增跳过。
- 反向验证产物 `/Users/a77/.finance-runtime/reviews/research-contract-citations-0921/requirements-fixed-ba18395ce-mutations/results.json`：`complete=true`、`source_unchanged=true`；基线和恢复各 77 项通过，清单识别、非公司排序保护、引用序号/存储身份、回执、覆盖度、最终投影、repair notes 与 repair budget 等十组变异均按预期让断言失败。
- 修复重入 conformance：`4 passed / 1 xfailed`，收据 `~/.finance-runtime/test-receipts/20260921T163455Z-ba18395c.json`；测试进程只自建 loopback 临时服务，未访问生产 8792。既有 `xfailed` 是 Codex 后端不支持 resume 却缺少显式不支持回执，未修复且不算通过。
- 定向与变异子测试在 Python 进程内拒绝 `socket.connect`；重入测试仅放行本进程自建临时服务。这不是对子进程或任意外呼的通用网络沙箱认证。
- 假完成专项相关回归：`414 passed`，收据 `/Users/a77/.finance-runtime/test-receipts/20260921T171122Z-a5cb2e9f.json`；覆盖 fulfilled 无 witness、被拒 witness、公开稿改写/删除、补写后仍缺项等路径。
- `scripts/review_probes/check_research_contract_boundaries.py` 的专项产物 `/Users/a77/.finance-runtime/reviews/research-contract-citations-0921/false-completion-ba18395ce/results.json`：基线与恢复各 77 项通过，十组反向保护均有效，`complete=true`、`source_unchanged=true`。
- `ruff check .`、`git diff --check` 与提交前 pre-commit 门禁通过。

## 这些收据不能证明什么

固定替身和结构测试只能证明协议、状态传递、公开投影撤销、修复入口和预算边界。它们不能证明真实模型能正确识别候选公司集合、`2+2+1` 结构、A/B 各至少三条信号、每条正反结果和第三解释、分母/时间窗或无来源阈值，也不能证明自然答案的金融事实正确。

本轮没有全仓 pytest、前端/E2E、跨仓 registry 或独立审查；没有生产装配、部署、真实行情日期一致性或运行效果结论。生产 revision `adcda94b5e40` 不等于本候选提交，分支未 push、未合并、未部署。

## 后续与禁止动作

后续可在用户授权后进入金融分支合并验收；如用户提供本批 Knevo 原答，可做三方材料与答案对照，但不把任何一方自动设为金标。真实模型验证应使用另行授权的新样本并保留旧冻结失败，不重跑原首答。

在此之前不自动写 `reading_baseline`、视角、经验卡，不升级研究规则，不切生产，不动 8792，也不把本轮工程测试收据写成真实语义质量证明。

## 工具沉淀盘点

重复验证已扩入正式脚本 `scripts/review_probes/check_research_contract_boundaries.py`，没有只留临时命令。五个新增保护点分别撤销回执校验、覆盖度、公开投影复核、修复提示和预算约束，要求实际断言失败，收集/夹具错误不算成功反证。

跨项目原则沿用共享记忆 `gate-covers-only-its-return-value` 中的“成功凭证必须绑定输入”和“删错不能替任务补齐”：审核后正文改变，旧回执不能继续认证交付。程序保护已进入真实消费者和正式回归，不另造第二套人工清单；数量/对象关系的语义判断尚不能由字符串计数可靠替代，故仍需独立语义验收。`harness-reference` 有他人在途，本轮不改，通用工具索引补登待该树归属澄清。
