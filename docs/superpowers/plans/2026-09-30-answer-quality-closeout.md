# 8792 回答质量接续 Implementation Plan

> For agentic workers: execute the accepted stages in this session; use the code-review skill for independent Standards and Spec checks. The user explicitly assigned this continuation on 2026-09-30.

**Goal:** 在最新 GitHub 主干上接回有效回答能力修复，定位并验证尚未通过的材料时点、财务推理和纠错追问，交付有明确质量边界的合入候选。

**Architecture:** 复用 Controller、TaskFrame、Episode、来源合同和已有 sidecar/probe。先完成已有设计的依赖集成，再通过固定输入的有限实验检验语义机制；结构通过、内容正确、运行上线分别记账。

**Tech Stack:** Python 3.12.13、项目锁定依赖、pytest、现有 GLM 接口、真实 Workbench conversations/messages。

## 固定身份与授权

- 起点：GitHub `origin/main=7569327143a9a40ff44da32d723865b062d856e6`。
- 有效旧工程候选：`d9eeb69b7d82b159d6635ca7664ee77b0be43653`；祖先基线 `4de44009af6de4619573a3e35984d3477228a9df`。
- 既有设计：上述候选中的 `2026-09-28-answer-capability-design.md`、`2026-09-28-answer-authoring-design.md`；本次用户已确认接手，并明确先审失败原件、固定模型/材料/版本验证根因修复。
- Claude 独立负责 GitHub #6 的测试隔离/CI；本枝不重做它。
- 当前授权覆盖开发、隔离真实验收、评审和开 PR；新 PR 合入及生产切换在形成可审查包之后按仓规确认。

## 1. 复现并接回有效工程行为

责任文件：`intelligence/services/{turn_controller,route_table,user_task,conversation_materials,task_frame,episode_factory,research_harness,episode_protocol,material_contract,material_grounding,material_answer_authoring,judgment_delta,research_tool_registry}.py`，旧候选对应的 runtime 接线及测试。

- [x] 将旧候选的 `test_quick_fact_routing.py` 放入本枝，运行 `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_quick_fact_routing.py`，保存旧主干红灯及具体断言。
- [x] 以 `git diff 4de44009a d9eeb69b7 -- intelligence scripts/material_claim_support_probe.py tests/test_verify_perspective_consumption.py` 的净变化作依赖完整补丁，使用 `git apply --3way`；不复制旧整树或旧收据。
- [x] 保留 main 对 `research_tool_registry.py` 的 high_status/partial/缺值合同，只接候选 `prompt_block` hunk；核对所有冲突和文件差异。
- [x] 运行上述回归和全部变更测试，原权限、截止、取消、来源硬拒、普通查数/研究/个人回顾对照均保留。
- [x] 同步 `docs/agent-product-door.md` 中这组有效接线；不带入 FA-01、v2 摘录选择或输入删减实验。

首次集成：快查回归主干 6F/16P；18 条纠错承接回归由红转绿；25 个变更及邻近测试文件 1072P/1X。
独立审查发现并修复了旧工具证据上下文的简化格式准入不一致：真实 validator 先红后绿，84 条相关测试通过。
记忆截止/数量测试曾在组合运行出现 0/5：可控延迟重现其与一秒异步预取预算耦合，不能反推原失败必定超时。
该语义测试改用同一注册表的显式读取；保留生产预取时限及其独立超时测试，相关 105P。上述是工作树定向验证，尚非最终版本全量门禁。

## 2. 原件分诊与有界内容验收

- [x] 固定原题哈希和历史原件；分别记录首个偏离：输入丢失、表示错误、模型已产生的语义错误。原答/原裁决只读保留。
- [x] 核对纠错承接 `563d52622`、JSON wire `97d54cc8`、quantity hints `e86dc6af` 的实际依赖与已有结果。工程接线可以复用，语义收益必须另证；被否决的变化不因曾有全量绿而复活。
- [x] 真实试验前固定服务代码、实际模型优先序、推理参数、原题/材料、用户与 Episode 根、零生产写入边界、预算及判官模式；不能保证身份则不提交题目。
- [x] 先形成单变量假设及事前保留条件，再运行原题与邻近正常/反向对照。每次调用编号、失败、超时、模型回退和完整答卷均保留，不补抽以替换旧失败。
- [ ] 内容判据：新闻不外推旧否定到新时点、不把预计写成已确定；财务分开净利润、已给 CFO、现金 CapEx、余额变动、净借款和条件股权估值；纠正后必须改掉错误推理，同时保留原题和来源范围。
- [ ] 接续失败时只在同一授权预算内修复；不以扩大预算、默认新增判官、放松来源或编造缺失财务数据换通过。

固定 8 份首答为 1 usable / 5 partial / 2 unusable，财务纠错核心仍失败。既有判官及一次通用逻辑提示对照均未形成可采用修复，未改生产设置。详见 [原件、结果及被否方案](../../handoffs/2026-09-30-answer-quality-integration.md)。此处内容验收保持未完成。

## 3. 独立复核与交付

- [x] 对工程差异做 Standards/Spec 两轴独审；正文按匿名答卷、完整原题与固定规则复核，机械哈希准入不能替代语义判断。
- [ ] 最终干净提交运行完整 Python/Ruff、frontend/E2E、registry，检查收据完整收集面和精确版本；GitHub Actions 同样必须通过。
- [ ] GitHub PR 说明最终实际改动、内容结果、成本和限制，附本会话。被拒候选留证，不发布为已改善。
- [ ] 呈交合并/部署包后再按已有授权边界执行；实际 health/readiness、真实入口及交接齐备才能称上线完成。

## 完成定义

工程合格不能覆盖内容失败。原题质量、相邻任务无新增回归及身份一致性共同决定采用。若固定试验没有支持改善，保留失败并继续定位实际原因；不把全部金融语义正确或稳定追平外部系统列为本轮可由小样本证明的结论。
