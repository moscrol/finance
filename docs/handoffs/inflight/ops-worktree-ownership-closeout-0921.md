# 工作树归属与接管

## 这个分支做什么
协调#812看板/#813回填/#814收据，固定对象复审、保护他人现场。

## 决策与被否方案
- 用户“启动”后又说“不用给k3设置预算，随便用”：取消请求/总时长/强制收尾帽；否只改口头而执行器仍限额。
- 仍用既有Plus K3，不购买/切付费路由/自动重试/增开代理；单命令防卡死超时不是整场预算。
- 固定6eb12候选；否追着main移签，旧v3触帽历史不改。
- 展开：`docs/handoffs/2026-09-21-ownership-k3-v4-launch.md`。

## 当前状态
2026-09-21T08:07:40Z新K3双轴实际启动；Spec runner/Pi 53701/53716，Quality 53702/53717。均Plus READY、有真实请求；仅启动事实，不是终审。
新根`~/.finance-runtime/reviews/ownership-k3-v4-20260921/`：authorization/两轴prompt/runner已去掉40请求、1200秒、报告截止点，凭证内存缓存+临期刷新。execution/admissions/events持续写；别重跑launch.py/run_k3.py。
作者与新spec/quality树`~/fwp-wt-ownership-{gates,spec,quality}-v4-0921`均固定6eb12c1b8（c615基线，含a092修复）。旧三v3树及七档封档不改。无合并/部署/生产回填/删真实树，Arena另线。

## 已验证
不限额设施19项离线通过（模拟121请求/2000秒仍准入），离线Pi stub无真实模型请求；两次设施红日志保留。双轴启动身份净同SHA/tree/源哈希。
6eb12作者工程：Python12461P/85S/2X、Ruff/gate0，前端110P、E2E34P/2S，registry五项0，hooks过。证据c39e5bfd8/82文件，评论5294/5295/5296回读一致；唯一gate-bVVRCApx收据、JUnit12548/终端一致，回读/兼容0。

## 未验证 / 已知边界
新独立报告/QC仍待完成；作者绿不替代独立签字，不签后来main。真实完整副本302132父子发布恢复未演练。
直接文件工具有根约束；shell无OS沙箱。首尾净不证明中途无改还原；收据归属非恶意写者防线；旧shell gate仅留pytest末15行。

## 下一步
先查新根每轴execution.json、admissions、events和PID；若已完成，核对REPORT/verdict/真实exit与覆盖、单独写operator QC、封档发布。不限额授权已生效，不再问旧40/20预算。latest-main新集成/合并/部署/回填/删树分别确认；三单与组合不可重复合。

## 踩过的坑
latest只导航；旧单分支/旧组合/新组合数量不能直接比。文档示例导出与本地Pi不一致，按实际lazy API导入；bash非零退出会throw。原错误保留，不算产品缺陷。
