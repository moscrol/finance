# 8792 板块/历史同题诊断

## 这个分支做什么
用同版组件独立作答，对照8792答案和trace，冻结可复现缺陷，不改生产。

## 决策与被否方案
- 选独立文档树，否改脏主仓；基线gitea/main@0a1cb8c4。
- 选证据核验，否把“推荐PCB”写成金标准：模型/预算/prefetch未配平，n=1不能判胜负。
- 选局部修引用解析，否关数字门：E27被误读成数量；其他新阈值仍须约束。
- 展开见 `docs/handoffs/2026-09-17-8792-sector-history-diag.md`；完整报告在 `docs/verification/2026-09-17-sector-history-comparison/README.md`。

## 当前状态
主要报告、双答案、摘录、原件manifest及离线复现脚本已提交5a2b45de；此交接另作收尾提交。未push、未合main、未修复/重启/切8792。发布版仍bf662e9310ff。原主仓改动均非本轮。

## 未验证 / 已知边界
- 首轮manual运行失败：mappingproxy不可JSON序列化，4次provider attempt/0工具；未找到栈，不断言模式因果。
- hybrid run_20260917_203230_060027传输完成、业务partial；数据到09-15，不是09-17实时。
- 本轮没有修复后live、全仓/前端/浏览器验收；API探针不冒称浏览器点击。
- 组件独立稿17调用，产品8调用，不能比较预算效率；组件历史79窗仅8可比。
- 原件只在本机 `~/.local/share/finance-workbench/diagnostics/20260917-sector-history-2030/`，勿只保留/tmp。

## 下一步
另开修复切片：①引用ID不当数量；②错误查询有界修正；③题材集合去重、历史距离忠实排序；④规则与当日观测分离；⑤扩板块比较合同而非套公司表头。先冻结证据离线回归，再同设置真实入口复验。manual崩溃另线定位。

## 踩过的坑
- 9+10+7是标签成员数；去重15/32=46.875%，非81%，更非上涨原因归属。
- PCB与PCB概念代码不同；最强历史表现不等于未来收益最大。
- tool_result.ok=true可包内部parse_error；judge repaired可仍漏核心错误。
- 重复手工核验已归scripts/replay_sector_history_diagnostic.py；exit0只是复现成功。一次性components.py预算不公平，仅留原件不升通用工具。
- 本轮只诊断，门禁漏洞未补；harness-reference树脏未碰。单题样本留项目文档，不灌共享记忆为稳定结论。

## 已验证
脚本Ruff、8项基线断言、61原件SHA-256、双答案逐字节一致、提交钩子通过。E27含引用拒句20，去引用同句不拒；ranking_intent=false离线复现。生产前后版本/加载/依赖指纹一致。
