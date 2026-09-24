# feat/pi-research-loop

## 这个分支做什么
兑现 8792 的 Pi 式研究行为；本轮总 spec + P0 离线机制验收，不换生产 Loop。

## 决策与被否方案
- 复用 ContinuousAgentEpisode + FinanceResearchHarness；否掉参考 Loop 直接转生产、宿主 Shell 放权、重复改 #868。
- 原 owner 的 #72/#75/#76 承接自主视角/截止/改稿验收；不自动增加其模型额度。
- 背景与收据：`../2026-09-24-pi-research-p0.md`；spec 为 `docs/superpowers/specs/2026-09-24-pi-style-research-delivery-design.md`。

## 当前状态
P0 已提交 `03453614b`：spec + test_research_chain.py。本交接/日期快照为文档收尾，不改受测代码。独立树 `~/fwp-wt-pi-research`，基线 `4cc15e703f81`。未push/合main/部署，生产运行逻辑未改。
#868 原交接131/152已过期。最新读 `~/.finance-runtime/reviews/pr868-glm-qc-20260924-1405/STATE.md`：候选ce2a2713121a，工程四叶绿；spec/execute漏complete字段被拒收并封存，累计166/209、余43，不足完整新批78。未分类探针不算产品缺陷；额度/方案归原owner，旧批不续。

## 已验证
新增12项：观察驱动追查、空/异常换路、越权后恢复、假引用拒绝、额度/取消停止、4个变异对照。真实Runtime/Harness，假模型/数据源，零外呼。
干净提交03453614b定向回归175P/3S/1X，collected179；ruff与提交钩子过。精确revision收据校验过：`~/.finance-runtime/test-receipts/20260924T131215Z-03453614-66f9369f56b2.json`。范围conformance + test_glm_agent_runtime + test_research_progress，非全仓门禁。X是已有codex_headless修复缺席基线。

## 未验证 / 已知边界
未经过HTTP门、真实数据/子研究链、自然模型改向/反证/修稿与公开稿一致性。未跑前端/全仓门禁或独审。未审8792活进程；runtime软链3b7e473575b0不能代替能力验收。

## 下一步
1. 跟原owner确认#868最新候选及独审预算/协议；不读旧树交接就开跑。
2. 组合候选重跑P0；独审通过后按#76授权做真实Workbench研究，原件与生产身份分账。
3. 完整门禁及用户确认后才合入/部署。本支只含合同和测试，不等于研究效果已改善。

## 踩过的坑
初始变异碰到更早的授权快照校验；菜单泄露应在菜单投影点注入。额度测试需区分已授额度与hard cap，否则另一道帽掩盖漏扣账。工具已定义/离线可调不等于生产授权可达。
