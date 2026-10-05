## 这个分支做什么

PR #52：预算、引用记账、多marker绑定、公司上下文与响应模型准入。用户统一决定合并；不部署8792。

## 决策与被否方案

| 选择 / 被否 | 理由 |
|---|---|
| 完整marker结束绑定 / 不合并整行证据、不猜标点 | 邻句不能借源；所有消费者共用边界 |
| 贪婪公司提取+开头完整引导语 / 不在名字内部切字 | 防复合名称被截短、借旧名证据 |
| trace只认逐尝试reported_model / 不认请求名和配置 | 意图不是响应身份 |
| 累计记录仅完全相同才去重 / 不用后记录覆盖 | 不抹早期错配、未知调用 |
| 目录同时查trace分支证据 / 不被正常Episode遮住 | 发现入口也是准入边界 |

完整发现顺序/被否方案/收据：`docs/handoffs/2026-10-06-company-boundary-model-admission.md`。

## 当前状态

源码`89527d47c`→`b5c3d4fa8`已推送；后续仅交接文档。b5本机完整Python门禁和GitHub五项通过；最终文档HEAD的检查只认PR同头评论，不移签b5。未合并/部署/删真实树。本轮离线修复与复核新增模型请求0。

## 已验证

b5：20602P/77S/2X/0F0E，collected20681；`~/.finance-runtime/test-receipts/gate-rPmLghqp/pytest.json`核revision、target、全scope、解释器、依赖均过。公司/trace变异各8/8捕获，基线38P/49P。9稿冻结重放输入不变；两份旧live响应为glm-5.3-flash×2/×1。

## 未验证 / 已知边界

**回答质量未通过**。D4 live仍有非事实升fact、证据外数字4；D1v23仍有无绑定正文、数字4200。两稿judge off，不能称双模型审核；8796 readiness503、RAG worker关闭、snapshot为09-30，不等价生产。n=1、重放字数和模型身份不证明质量。旧895 CI另有判官回归1F未归因，b5绿不翻案。

## 下一步

核最终HEAD检查并等用户合并决定。本轮停止采样；未来质量实验先冻结题面/模型/代码/RAG与judge/样本量/预算/停止规则。FINANCEWORKS-6维持in_progress、13维持in_review。#51合入后才做invocation目录后续；#53等#49再改base。

## 踩过的坑

证据根`~/.finance-runtime/pi-vs-8792-claude-review-1005/`，本轮文件含`b5c3d4fa8`。895本机门禁因发现trace sibling漏洞中断，不是完整绿；他树门禁不可借。变异须提交后且目标与HEAD字节相同。历史空company_scope只在重放内存归一化，原件不改。磁盘曾仅21GiB可用，重门禁前查并发与磁盘，保留真实树和证据。
