# 视角请求离线贯通

本地日期 2026-09-25，UTC 仍为 09-24。接续前日 perspective-reconciliation，不替代阶段 B 的真实消费和质量验收。

## 结论

| 项目 | 结果 | 有效边界 |
|---|---|---|
| 风远当前画像到首次 GLM 请求 | PASS | 原文片段和当前上下文 13,449 字完整到达 provider 回调前；四字段147/147仍装配 |
| SPT 当前画像到首次 GLM 请求 | PASS | 当前上下文10,531字完整到达同一边界；四字段92/92仍装配 |
| 两视角的 neutral 对照 | PASS | 请求不含 perspective_context / perspective_context_rule；0个工具暴露 |
| 编排器至请求边界的回归 | PASS | 临时 alice/bob、固定 controller 的合成测试；不是真实 HTTP 入口 |
| 风远历史批准和既有考卷 | FAIL / PASS | 原值95/105，十条替代关系未闭合；旧考卷2+1通过，两者不抵消 |
| SPT 既有考卷 | FAIL | 缺卷。当前 honest_boundaries 字段为空，不能替它自动决定边题金标 |
| 生产 readiness | BLOCKED | 09-24 16:11:08Z 发起 GET，HTTP503，market_data_consistency=false |
| 真实采用、答案质量、Workbench/CLI 对照 | UNKNOWN | 本轮未发送网络请求、未生成答案、未做新自然验收 |

两个画像审计命令均预期 exit 1：请求子项 PASS 不吞掉原有 FAIL。输入文件哈希与 patch 集前后不变，未写用户目录。

## 到底检验了什么

`scripts/verify_perspective_consumption.py --check-delivery` 调用同仓辅助模块 `scripts/perspective_request_capture.py`：

`active_runtime_prompt -> project_turn_decision -> ContinuousTurnAdapter -> build_episode_context -> GLMAgentRuntime / ContinuousAgentEpisode -> build_episode_input -> complete_fn`

除空工具注册表、本地 provider 回调及禁止执行的判官外，保留真实执行和序列化代码。回调记录消息到内存后抛专用 BaseException，越过普通重试/降级处理立即结束，不伪造答案或完成状态。只输出长度、哈希、结构字段和调用数，完整请求不落盘。检查前后再次验画像、原文、patch 和考卷，避免离线检查过程读到混合版本。

真实画像检查使用固定 market_forecast 框架、quick 档位、探针当天日期、无市场事实；日期不是历史截止证明。绕过 API、路由、会话选角、真实工具及网络，停止在首次请求，未覆盖续轮、压缩、模型理解和外部 token 计费。synthetic 编排器测试补到 TurnOrchestrator 的连接，但不能代替真实用户请求。

反例涵盖：adapter 丢视角、协议序列化丢字段、边界说明字段消失、neutral 泄漏、无回调、其他用户画像混入、检查中 patch 改变及缺卷在请求阶段被创建。边界说明只检查存在，不签语义充分性。

## 历史 SPT 记录

在真实用户空间找到 `run_20260819_152316_348138`，只读摘录见 `historical-spt-run.json`。它确实保存 completed 运行、SPT 答案署名和40项 evidence，不应说“从未用过”。但 research_context 只存日期/trace字段，没有完整视角输入；semantic=partial，judge=unavailable。因此既不能签这次完整画像的实际输入，也不能签独立质量，更不能当成当前发布验收。未重新执行这道历史题或复制私人问题/答案。

## 重跑

在本审计树，以主树解释器执行。以下两个命令的总退出码都应为1，查看 offline_request_delivery 子项为 PASS：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
USERS=/Users/a77/.local/share/finance-workbench/users
$PY scripts/verify_perspective_consumption.py --users-root "$USERS" --user linxiaoqi5111 --perspective fengyuan --query '风远如何判断行情退潮和亏钱效应，什么条件下应降低仓位？' --check-exam --check-delivery
$PY scripts/verify_perspective_consumption.py --users-root "$USERS" --user linxiaoqi5111 --perspective sptfei --query 'SPT如何判断主线强度和分歧转一致，出现什么信号应证伪？' --check-exam --check-delivery
```

实现 `507872eed`；两份画像报告绑定该 revision 和源码哈希。冻结证据后的 `663cce791ed0e9bdb571a825157d05811a2e593a` 干净树定向487P/0F/0S，exit0、dirty=false，无忽略/筛选；完整目标见 `clean-targeted-receipt.json`。覆盖原审计器、视角/考卷/用户空间、编排器、adapter、GLM和协议，共12个测试文件。不是全量Python/前端/E2E/registry发布收据。

研发中一个反例最初替换错了构造器默认函数，改为实际 context_factory 注入后才检出断链；另一次新增测试漏模块限定名，由ruff/pytest检出并修正。保留机器原始红收据，不将这些红值归因生产或基线。最终ruff、diff-check和提交钩子通过。

## 后续责任

1. Perspective owner 与用户冻结 SPT 至少2道已知题、1道边题及适用边界；答案由原文和用户确认，不从当前画像倒推金标。已学文章保真与未见题泛化分开。
2. 同 owner 补风远十条替代/撤回关系、剩余42条和人工框架的审批来源；不自动恢复旧阈值，不另造 Q-002 队列。
3. #61与KB/#87先关闭数据/发布阻塞，再按#76预算和真入口规范验收。阶段C跨日稳定与D配对优化仍未完成。

未推送、合并、部署、补行情、换库、建索引、恢复采集或触发新模型。工具沉淀复用项目审计脚本；通用原则沿用“门禁只覆盖实际经过的路径”，不另建审批器或通用网络代理。
