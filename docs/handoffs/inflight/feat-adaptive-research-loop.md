# feat/adaptive-research-loop

## 这个分支做什么
模型自主研究、同会话修订与公开保真；当前补判官诊断及只读成交额均值。

## 决策与被否方案
- 完整计划漏 kind 送严格纠错，不自动接纳/执行。变稿或 bindings 改即重核；不足时旧稿+partial+提示。
- 拒发与上一发失败分账：last_dispatched_failure 脱敏保最近失败，不抬75秒帽/150秒窗/根预算，不猜历史异常。
- 均值复用 finance_query；不开放 derived_calculation。AVG/COUNT 同取有限值含零，只按股票代码+明确窗口，防名称拆组及筛选改分母。
- 请求窗口进入证据哈希；MAX(source_date)不冒覆盖起点。样本数不证明交易日齐全。
- 不刷live追状态词，不手改真实稿。背景/收据：`docs/handoffs/2026-09-21-adaptive-amount-summary.md`。

## 当前状态
诊断00fb5be63、均值60a41f2fa已提交；59464c400为带变异脚本的固定干净候选。随后仅交接文档。未push/PR/合main/部署，未操作8792。
旧72a2ac534单次K3真实复验已取证并生成正文，但判官两发耗尽窗口、公开partial；均值6.55应为6.6153亿，“无涨停”只支持本地未收录。完整交付仍未过，原件不改。

## 已验证
- 59464c400：22模块719P/8S，全仓Ruff/diff检查通过；跳过8项因本树无本地行情库，新36项临时库全执行。
- 固定收据 `~/.finance-runtime/test-receipts/20260921T145131Z-59464c40.json`：dirty=false，精确SHA/解释器/依赖校验通过。
- 五变异均命中断言、还原36P；旧脚本35变异兼容、首尾165P。证据 `~/.finance-runtime/adaptive-stock-amount-20260921/`。
- local_only四能力不变，网络/子进程/计算loader拦截无触发；limit1/25汇总不误报，日期分组与空集保留缺口。

## 未验证 / 已知边界
自然模型选用均值及引用、判官通过/repair/rejudge、无工具改稿+self partial、正常长答无泄漏仍未新增验收。未收录=>未发生另修。当前完整合入叶子与独立审查未跑，旧be660全量不可移签。未fetch/追合新main。旧生产前后健康与后来拒连并存，原因未知。

## 下一步
先做超证据否定窄修复及回归；新隔离真实验收不得选样重试。最终基线整合、完整门禁与独立审查另签；push/PR/合main/部署需明确授权。

## 踩过的坑
pytest/Ruff用主树`.venv-workbench/bin/python`；只取固定收据，FWP_TEST_RECEIPT=0仅禁写。limit1会被旧遥测自然忽略，需limit25反证。入口completed不是研究质量通过；新诊断不补旧异常。
