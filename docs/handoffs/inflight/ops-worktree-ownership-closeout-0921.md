# 工作树归属与接管

## 这个分支做什么
协调#812看板/#813回填/#814收据，固定对象复审、保护他人现场。

## 决策与被否方案
- 用户K3不限预算仍有效；否把本次50准入误称新帽。无自动重试/增开会话/付费fallback。
- 固定6eb12候选；否部分绿补签、跟main移签、删他人文件腾空间。
- Quality同刻退出但空stderr，不凭时间接近确证同因。
- 展开：`docs/handoffs/2026-09-21-ownership-k3-v4-interrupted.md`。

## 当前状态
2026-09-21双轴已异常结束，不再运行：Quality08:40:37.949Z、Spec08:40:39.231Z，均exit1，各50准入/49完整消息，无REPORT/verdict/completion。Spec明确ENOSPC（磁盘写满）；Quality原因未知。结论BLOCKED_INFRASTRUCTURE，独立未签字。
原件`~/.finance-runtime/reviews/ownership-k3-v4-20260921/`；别重跑launch.py/run_k3.py。新归档`docs/verification/2026-09-21-ownership-k3-v4/`819文件/33,027,503字节（含README、不含manifest），原失败保留，operator QC单列。
三v4树`~/fwp-wt-ownership-{gates,spec,quality}-v4-0921`固定6eb12c1b8（c615基线）。没有重启、合并、部署、生产回填、删真实树；Arena另线。

## 已验证
首尾及复核时净同SHA/tree/十二源哈希，冻结输入/原输出哈希一致；75份shell记录完整。七旧档30/30/86/26/450/115/82与旧v3三树不变。审计设施六项离线测试/Ruff通过。
Quality现有定向测试210P/1S、真实pytest exit0，receipt关闭；独立same-target重入探针外层2P正确。作者6eb12工程12461P/85S/2X，前端110P/E2E34P2S仍仅作者证据。

## 未验证 / 已知边界
两轴独立动态backfill均未完成；Quality独立board未做；signal控制未全过。共享磁盘波动未归因：08:44余3.5GiB，后来回升不是本任务清理。保留夹具约1GiB，不足解释全机跌幅。
探针曾覆盖旧fixture，Quality曾宽泛pkill后改owned child；无全机旁伤审计。shell无OS沙箱，首尾净不证明中途无改还原。后来main/真实完整副本302132发布恢复未签。

## 下一步
先确认容量和路径归属，清理/迁移与恢复审查另确认；无预算不等于允许重开会话。新会话不得覆盖本轮。最新main集成/合并/部署/回填/删树分别确认，三单与组合不可重复合。

## 踩过的坑
latest只导航；tail后$?不是pytest/driver退出。保留失败每一版，信号只发本次创建PID；模型未终审不能由operator代填PASS。
