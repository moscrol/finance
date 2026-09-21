## 这个分支做什么
修复旧部署脚本帮助误执行事故。最新进展见 `docs/handoffs/2026-09-21-pr831-merge-gate-and-846-review.md`；原事故/门禁见同目录deploy-help-incident与deploy-help-gates快照。

## 决策与被否方案
- 帮助先退出；写入需apply/显式源/完整SHA/干净树，Git目标及intelligence软链拒绝覆盖。
- 恢复同版新快照，否决部署含已回滚K3的最新main；#831不需重启生产。
- 独立审查无结论不当通过；原报告适用范围按源码blob核验，不移签整树。

## 当前状态
#846源码4f9a2af56+8a82ec780，9be77af53已推，之后仅交接文档。仍WIP、未合未部署。新复审300秒无输出后终止exit143，评论5471已回读；两次旧失败保留，不自动再试。
#831原head ea5c3a94，main028a251a合流候选d97fdf77在 `~/fwp-wt-831-merge-gate-0921` 全叶通过，评论5478已回读；原分支/main未动，仍WIP，待明确合并授权。
8792仍同版adcda94 recovery；旧adcda94目录是受损事故现场，不作回滚目标。

## 未验证 / 已知边界
- #846仍NO INDEPENDENT SIGNOFF；显式既有认证/网关/模型的工具禁用静态审查超时，原因未明，不称认证坏。
- standalone真实部署成功链、并发换链/写锁未验；旧主检出脚本危险，禁帮助探测。
- #831仅继承原两项离线PASS_WITH_LIMITS适用性，未新做独立合流审查或真实图谱后端动态验收，不外推领域功能。
- 生产healthy/clean且代码一致；readiness503仍数据库09-18/快照09-21，数据线另管。

## 下一步
#846由可用独立会话审固定base/head及临时目标反例，无结论不解除WIP。#831工程缺口已补，合并另需用户明确确认；实际合并身份另验。测试末磁盘低于7GiB，收尾观察回升约13GiB；不重复全量、不删他人树或事故材料。本轮进程均结束，候选树保留。

## 已验证
#846 d3d27bce全量12528P/85S/2X及Ruff、前端/registry过；9be77af53干净定向59P。#831 d97fdf77全量12510P/85S/2X、Ruff0、前端110P/E2E34P2S、registry五项0。收据 `~/.finance-runtime/test-receipts/20260921T152141Z-d97fdf77.json`校验0/漂移0；证据 `~/.finance-runtime/reviews/831-merge-gate-20260921/`。七改动文件及app.py与原独立受审版blob相同，旧probe操作员回放过。

## 踩过的坑
help非天然只读；收据路径以stdout为准。健康/就绪/问答分账。共享审查队列绑定另一任务链，不能硬塞请求。harness-reference有他人改动不碰；本轮无新通用抽象，复用原门禁。
