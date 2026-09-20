# ReAct trace 最小修复

## 这个分支做什么
在 PR #809 WIP 上维护 ReAct trace 三个工程修复，并处理真实 8857 run 暴露的删句后条件计数残句；不是 #790-#794 全完成。

## 决策与被否方案
- 条件一致性修复只在本轮确实删掉“升级/降级条件”定义时清理“满足该条件中的 N 条”，保留已核验观察；不重写整段、不放宽数字门。
- 修复放在 Episode 语义验证器的公共删句出口；不只改 grounded composer 影子链，因为真实连续研究答案走 semantic public_answer。
- 保持 WIP；不合 main、不部署 8792、不新增付费外审、不重发同题自然 run。
- 背景与被否候选见 `../2026-09-21-condition-coherence-repair.md` 与 `../2026-09-21-react-trace-closeout.md`。

## 当前状态
HEAD `0729692a4ffee950cad47b29f0e690fdf337b7f9`，提交 `fix(research): remove dangling condition counts after repair`；作者树 clean。前置业务冻结 `dda5895a`，文档证据 tip `780ba6b8`。新提交尚未合入 main；生产 8792 仍 `bf662e93`，8856/8857 服务已停。PR #809 仍 open/WIP。

## 已验证
- 全仓 pytest：`11974 passed / 85 skipped / 2 xfailed / 17 warnings`；收据 `/Users/a77/.finance-runtime/test-receipts/20260920T203638Z-0729692a.json`，revision/解释器/依赖/clean/base drift 0 均核验通过。
- 全仓 Ruff、diff check 通过；语义验证器 182P，相关删句/适配器回归 45P，新增聚焦 3P。
- 9/21 真实原始草稿离线重放：删除句索引 `(14,15)` 后无“升级条件”定义、无“满足升级条件中的2条”，保留“双红各1天…双红连续性尚未确立”。这不是自然模型质量签字。

## 未验证 / 已知边界
真实金融质量仍 `not_passed`：未绑定的 225/25、AI手机PC/MiniLED 数值及相关定性仍需 #794 处理；`ranking_intent=false`，#793 比较合同/假设槽仍未完成。registry `check` 的跨仓 `kb/rag-query` 漂移仍与基线同红。新 run 是 history_query 纠参成功，不代签 #790 finance_query 自然纠参。

## 下一步
先审阅/推送 `0729692a` 到现有 WIP（仅分支更新，不合 main），再独立推进 #793/#794 与答案证据绑定；解决 registry 归属后在实际合流身份重验。任何合 main、部署、付费外审或删生产内容先停并取得授权。

## 踩过的坑
全量测试在未提交树产生的旧收据 dirty=true，不可移签到新 SHA；提交后已重跑并严格验收。共享 worktree 有其他并行 refs，不能声称全局 refs 未变。外部原件根 `~/.finance-runtime/reviews/react-trace-closeout-0921/`。
