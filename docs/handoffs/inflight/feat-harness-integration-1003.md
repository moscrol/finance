## 这个分支做什么
四片Harness候选及S1接缝修复；工程、独审、真实质量均过才上线。任务FINANCEWORKS-3。

## 决策与被否方案
- 接纳/反馈统一经ResearchHarness；loop保留取消/截止/预算/持久化，否默认harness回落。
- 用户已批复审+最多12格预验共用50元；否把授权、测试绿或预验当正式质量通过。
- 标准API适用于自建Workbench；否把Coding套餐当免费额度。先核账户、再设共享费用硬帽；否事后超支再停。
- 细节见[本轮预算预检](../2026-10-04-harness-budgeted-preflight.md)及[产品修复](../2026-10-04-harness-interpretation-seam.md)。

## 当前状态
- 产品pin=25de6994bdb79b57e9cf06fcb81f6f5796c67079，含main@108835e27；本轮重新fetch未变。文档HEAD由Git读取。
- PR30仍Draft/OPEN，无auto-merge；生产仍ffe1c60d，未合入/部署。无模型实验运行中。
- 预算已批；账户页需用户Chrome登录。已请登录智谱finance/overview后回复“已登录”，不用发密钥/验证码或充值。
- 新证据根`~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/`，先读approval.md、preflight-findings.md与status/。旧harness-release-20261004及harness-integration-20261003均封存不可覆盖。

## 已验证
25de完整本机与CI已过；dfe文档头CI亦全成功。本轮33项离线预算/运输测试、16项payload断言及Ruff通过，非全量或独审。官方标准价：flash输入/输出0.8/2.8、glm5.3为8/28元每百万token；不等于账户实付已核。

## 未验证 / 已知边界
新版独立Spec/Standards仍缺。真实答题/新独审请求0，质量未知。现有调用帽是每turn，root帽是工具/时间；未建立本批共享CNY/token准入。agent两入口及通用chat默认无max_tokens，合成帽不传播；low effort可启用5.3必需思考。不能据超时断言上游停止收费。

## 下一步
读最新任务version/评论与Git/PR。登录后核账户，补并离线验证全运输尝试发前持久预占，含子调用/重试/独审/判卷；不能保证50元则继续停。再冻3题完整多轮、数据、6对AB/BA顺序、匿名评分和停止规则，经claim_ledger_id预注册。12格不代正式效果；R17/R19/240不动。当前不改生产通道、不碰其它活动树。

## 踩过的坑
目录有依赖先串行建，勿并行重定向竞态。旧glm-5.3*通配价误套flash；CLI模型名/估价不是账单。无usage记未知。封口哈希只证完整性。清理先查ignored数据；Gitea代码ref不等于数据备份。
