# E2 P3d 小片：先验生产者在读取前让路

## 身份与背景

代码 `1f6ebc5de9e906ccedf70c0377d45919fb5f7b34`，`fix/e2-boundary-closeout`；基底 `dcd57d60` 为P3b/P3c+返修独立报告归档。未推/合/部署；**P3d待独立复核**。

前片解决registry消费者及Scope绑定，不能撤销上游IO。源码定位发现 `TurnOrchestrator._run_turn_ledgered` 已取得TaskFrame后，仍先读取旧答案产物、stance pack、研究项目先验、视角，然后Episode工厂才丢弃这些字段。因此选这一可独立证伪的小片，不把controller早读和可信继承一起做成未经审查的大包。

## 发现顺序与取舍

1. 新增真实`run_turn`测试，临时ConversationStore/RunStore，canonical/legacy两种controller、四种scope、项目先验正常/抛错，共16例；在adapter入口用专属BaseException停止，不让收尾流程掩盖前置读取。
2. 初始16F全部因测试TurnDecision漏`needs_template`，根本没到目标。只修夹具后得到**4F/12P**：material_only四组合各调用全部四类先验；正例正常。初始日志保留，不当产品失败。
3. frame确立后从同一`material_contract.data_scope`派生本地布尔，分别在四个生产者调用前短路。未改合同/题目/路由/超时；full/local_only/普通路径保持。
4. 16例及相邻五文件210P。隔离变异树`/tmp/e2-p3d-guard-mutations`基于dcd57d60，复制当前代码/测试后分别去掉四处闸，每处均**4F/12P**，最后还原。这不是四次全新覆盖，而是四个单因素证伪。
5. 提交1f6ebc5d，干净复跑210P；全仓首跑被工具240秒限时杀掉（约53%，无pytest终态）。原日志保留，增加的是宿主命令执行窗口，不是产品/测试timeout；同一干净代码完整复跑**9797P/83skip/2xfail/17warnings，exit0**。

| 方案 | 决定 | 为什么 |
|---|---|---|
| 只依赖Episode工厂清空字段 | 否 | 读取已经发生 |
| material_only禁止所有会话IO | 否 | 会话身份/用户消息/持久化本来就需要本地store，且D7允许特定同题上下文 |
| 四个未分型事实先验生产者读取前拦 | 采用 | 同源scope、局部清晰、能逐项证伪；不宣称全部来源纯度 |
| 同时给local_only关掉先验 | 否 | 本片未审其实际IO，不以全拒绝假绿破坏允许本地读合同 |
| 把所有“继续”一律澄清 | 否 | 既有普通追问会回归；必须与可信基底恢复一起接线 |
| 因全测绿跳过独立审查 | 否 | 作者测试不替独立反例；下片之前先审本片 |

## 收据

目录 `docs/verification/e2-boundary-closeout/p3d-1f6ebc5d/`，14项原件SHA256 manifest：

- `e2-p3d-before-tests.txt` 初始夹具错误16F；`before-v2`有效修前4F/12P。原夹具缺失可由当前测试删除`needs_template=True`复现，无产品改动。
- `e2-p3d-focused-tests.txt` 工作区210P；`frozen-1f6ebc5d`干净210P，收据`20260914T155711Z-1f6ebc5d.json`。
- 四份mutation日志+JSON；逐项删answer_spec条件、stance条件、project_prior条件、perspective条件，实际计数增加，均4F/12P。
- `e2-p3d-full-1f6ebc5d-tests.txt`工具超时中断，**无最终pytest exit，不计失败数**。
- `e2-p3d-full-rerun-1f6ebc5d-tests.txt`全仓9797P；真实exit文件、干净收据`20260914T160955Z-1f6ebc5d.json`。
- 全仓Ruff、代码diff、提交钩子通过；地图ready@1f6ebc5d。

新16例计数四生产者及socket，禁止网络0；资源为临时源/脚本化生产者。**不将相邻/全仓绿测写成全部IO审计**。前端/E2E/registry-check完整叶子未运行，不是合并收据。

## 下一步与范围外

独立范围提示已存同目录`qc-prompt.txt`，**本轮仅准备，尚未启动独立审查**。固定1f6ebc5d分审，本片通过才继续余P3。

controller前history/context与QueryResolver早读、歧义/基底不可恢复预取前澄清、全部四组九类来源过滤、可信继承/历史身份、压缩/恢复/子研究/非工具provider事实、确定性/legacy回落及交付后读取、local_only原题槽及更多runner、P4–P7仍未完成。测试显式保留controller看到旧历史的事实，不把此片假写为整轮零读取。原T2→T3不得改题/重贴禁令。

## 沉淀

新行为探针已进正式`intelligence/tests/test_e2_turn_prior_reads.py`；变异只是现有测试的单因素反证，不建新通用CLI。原失败和执行日志归档；跨项目“先过滤输出无法撤销生产者副作用”“迟到完成不等于deadline后新调用”回写已有知识条目，不改脏harness-reference或新建能力清单。
