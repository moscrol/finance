# Harness 四片主线集成：发现、裁决与验收边界

本快照记到 `46d9875c60fcdbec75a0366ded453d2d49f33971`，不是最终发布批准。工程验收按固定提交留收据；本快照之后的完整门禁结果在下述树外证据根与 Draft PR #30 更新，不把旧读数移签。

## 目标与授权

从 GitHub `origin/main@06198093eb7d4cf57ff20e26a2fa7a7df9df8726` 集成 PLAN 归属、冻结根请求/解释、输出义务来源与可选跟踪/排序表达四片。独立树 `~/fwp-wt-harness-integration-1003`，分支 `feat/harness-integration-1003`。

用户只授权集成与工程验收、推送 Draft PR；未授权合入 main、部署、真实 Workbench 配对或继续扩建剩余 P1b。共享主目录有他人工作，旧候选 `~/fwp-wt-harness-output-provenance-1003` 及旧收据均保留。

证据根：`~/.finance-runtime/reviews/harness-integration-20261003/`，以下收据路径均相对它。PR：<https://github.com/moscrol/finance/pull/30>。

## 按发现顺序

### 1. 主线冲突与自动合并接缝

`episode_protocol.py` 采用主线冻结材料引用预检、来源/身份检查和纠错分类顺序，再叠加根请求与解释投影。主线抽出的绑定验证对陌生 output 统一拒为 `unknown_output`；模板名字不能获得绑定身份或修复豁免。

自动合并后发现 `turn_controller.py` 改路由只更新 `required_outputs`，与新增来源元数据不一致。修复 `_rebase_frame_for_decision` 和历史路由重建，同步 ID 与 `output_requirements`；quick_fact 退休旧研究提示，保留当前可信 `user_request` 及别名合并见证。新增 `test_harness_main_integration.py`。

生产集成提交 `74638aa5835042b5fb4ba04fe93912f2d38cb2f7`。迭代的 976 passed 不是全量结论。

### 2. 变异定义失配

三处探针仍锚在旧源码，不能证明集成版测试有牙。先复现 3 failed，再迁移锚点，新增 `tests/test_harness_mutation_definitions.py` 检查唯一匹配、目标存在与 Python AST 可编译。提交 `df3a1421ea28af8fa102453d2c13f4c2608fae73` 仅改定义/测试。

四组 9/12/13/13 个变异、历史表达 8 个、交付边界 16 个均在该 pin 重新执行并审计。它们证明指定破坏能被测试捕获，不证明模型回答改善。

### 3. 因果任务的 24 个失败

主线 `test_causal_request_scope.py` 75 passed；集成版 24 failed、51 passed。最初按可能的用户义务丢失排查，不能直接删断言。

逐级核对发现：`market_cause` 题型的 canonical `causal_chain` 与 `counterpoint` 仍必需；`cause_attribution` 是 envelope 的额外算子提示，来源为 heuristic。本片要求提示可选，不应因名字再立一套硬义务。

更新断言以同时钉住必需因果答案、可选算子来源与否定语义；新增反例证明缺少因果答案时履约仍缺 `causal_chain`，FINISH 仍拒绝 `completed`。未改生产代码。提交 `5266b5f8159d59def2f496b16cd88a65f7ec82f6`；定向 165 passed。

旧 `df3a1421e` 完整结果为 24 failed / 20,531 passed / 76 skipped / 2 xfailed，不覆盖、不改写为绿色。`5266b5f8` 全量与收据检查通过，见下表。

### 4. 独立静态审查与身份纠正

原 Codex 规格/代码会话因额度耗尽退出 1，没有审查结论。之后两个新的只读会话（仅 Read/Grep/Glob）通过 `claude` CLI 启动，受审对象为 `5266b5f8`。

**工具名不是模型身份**：启动前未显式固定模型，日志中的模型实际为 `glm-5.2`；不能称作 Claude 模型审查或权重身份认证。两会话均完成，但不再追加调用。工具报告费用分别为 $3.802314 / $4.533796，合计 $8.336110；`costBasis=unknown`，不是实际账单证明。编码审查与产品实验分账，不能把所有外部模型调用说成 0；金融 Workbench 对照新增调用仍为 0。

原件：`review-claude-{spec,code}-events.jsonl`、对应 `*-result.json`、`*-result.md` 与 `.exit`。规格审查无 P1，提出一个 P2；代码审查未发现确定高/中严重度 bug，但对同一处反馈保真给出不同解释。两者都是静态检查，不是执行或金融质量证明。

### 5. 审查分歧复现：交付说明被替换

`classify_repair_need` 用 `review_feedback or rejected_claims` 选择阶段化反馈，避免旧 claim index 对缩短后草稿失去归属。但 adapter 的 `review_feedback` 原来只含句子核验反馈，另一组 `delivery_repair_notes` 只在旧输入中；两者并存时交付说明消失。

源码复查否定了“`rejected_claim_notes` 已携带全部说明”的解释：该字段只投影逐句判据，不包含交付检查说明。

新增离线真实 adapter/核验器/同会话 resume 反例：错误比率 + 无证据数值条件同时出现，在研究窗已关且无工具额度时，已有的一次文字修复应同时接收两组诊断。首版夹具仍开研究窗、0 resume，保留 `review-f1-red.log`；修正夹具后 `review-f1-red2.log` 精确失败于缺失比率修复说明。

最小修复放在 adapter 的语义已知处：阶段化反馈与独立交付说明去重合并，保留旧 `rejected_claims` 用于事实拒绝/材料许可分类；不把过时裸 index 混回阶段化反馈，不改预算、权限或修复次数。新增对应变异，提交 `46d9875c6`。`review-f1-green.log` 为 411 passed，属于迭代脏树定向测试，不冒充该提交完整门禁。此补丁尚未另作独立复审。

## 方案对比与裁决

| 决策 | 被否方案 | 理由 |
|---|---|---|
| 主线材料预检优先，功能叠加 | 直接采用候选旧函数 | 旧版会丢冻结来源与拒绝顺序；不是普通文本冲突 |
| 路由同步义务 ID 与来源 | 删除全部来源或只改 ID | 会丢用户见证或造成契约不一致 |
| 因果答案必需、额外提示可选 | 恢复 cause_attribution 硬槽；删除整组测试 | 前者违背提示可选的规格，后者失去用户义务和否定语义保护 |
| adapter 合并两类诊断 | 在 coordinator 无差别并集裸 index | 原句索引属于核验阶段，不能重新当成当前稿坐标；adapter 知道两组来源 |
| 固定每版独立验收 | 用旧候选或源码相同来转签 | 测试定义、版本身份、主线组合都发生变化 |
| 停在 Draft 与证据 | 扩建 P1b、合并、真实模型补跑 | 超过授权；机制验证不回答内容质量问题 |

## 已验证的版本账（不转签）

| 版本 | 证据与结论 |
|---|---|
| `df3a1421e` | `final-df3a1421/python-receipts/gate-Osaxq98A/pytest.log.txt`：24F，完整门禁红 |
| `5266b5f8` | `final-5266b5f8-r2/python-receipts/gate-UjZxOL8X/pytest.json`：20,556P / 76S / 2X；collected=20,634；完整范围/解释器/依赖/干净树审计 exit 0 |
| 同上 | `final-5266b5f8-r2/frontend/frontend.json`：frozen install、lint、typecheck、209 个 unit、build、E2E 52P/2S，首尾身份稳定且干净 |
| 同上 | 同目录 registry 五项 exit 0；ledger 102 行反向引用 warning 保留，不称零警告 |
| 同上 | `final-5266b5f8-mutations/audit.json`：四组 9/12/13/13，历史 8、边界 16；还原哈希一致 |
| 同上 | GitHub `workbench-check` run 37130902893 的 python/frontend/e2e/聚合与 `registry-check` run 37130902904 全绿，PR 仍 Draft |
| `46d9875c6` 及其后 | 重新 pin 全量门禁与 14 项表达变异；最终结果读证据根的 `closeout.json` 和 PR，不借上行读数 |

## 接手边界与工具沉淀

- 验收解释器固定 `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`；`env -i`、`umask 022`、`FORESIGHT_LLM_KEYCHAIN=0`、树外新收据目录。Node 22.23.3 为独立安装。共享依赖和生产数据不改。
- 重用 `run_main_gate.sh`、`run_frontend_gate.py` 与三类既有变异运行器；本轮补入仓内的是失配定义的自动检查和混合诊断反例，不新建第二套验收框架。树外批次 shell/审计器只作固定 pin 的重放清单。
- `frontend/index.lock` 曾残留：先确认无 Git 进程/文件占用，再归档锁文件；首次启动失败保留，另起 r2 目录，不覆盖证据。
- 后续先核最终 pin 收据与独审补丁覆盖，再由用户决定下一步。12 格草案在 `live-comparison-approval-draft.md`，尚未预注册；实际模型、配置、物理调用帽、费用和盲审须先确认。
- R17/R19、正式 240 格封存。CLI、脚本模型、E2E、`completed` 与工具次数均不能替代真实 Workbench 入口、完整响应身份或回答质量判断。
