# 在途交接：#58/#59 门禁证据收口

## 这个分支做什么
PR #886：记录 main 的精确 SHA 验收，历史快照保留；不改运行时代码。

## 当前状态
09-23 16:05 CST，main `27ca084f9ffc` 四叶齐绿并经独立复核。详情 `docs/handoffs/2026-09-23-main-tip-gate-27ca.md`。此前 5f35 / bbd5 只是历史部分结果，不能与它混写。
本分支已前向整合 27ca。PR 候选自己的收据、WIP 与合入状态必须回读 #886 的最新 SHA 和评论；本文件不把 main 的绿移签给文档候选。文档树位于证据根 `trees/finance-workspace-private-5f35`，目录名不是 HEAD。

## 决策与被否方案
- 同 SHA 干净树的完整收据允许独立复核，否决重复启动同一 full pytest 加重争用；不用共享 latest。
- 文档按时间 + SHA 冻结，否决为文档自身 merge SHA 反复追开 PR。
- #881 Git 已合但 API 残留 open，已留评论 6183 与接替 #882 后关闭，不再合一次。

## 已验证
- main 27ca：Python 14618P/0F/0E/85S/2X，collected=14705；仓根 target、scope 无筛选，JUnit 对平；ruff 与 runner exit 0。
- 完整覆盖面/精确 revision/依赖校验 exit 0，错误 SHA exit 1。
- frontend 正式六步全绿（Vitest 120P，E2E 34P/2S），起止身份和六份日志哈希独立复核通过。
- reviewer 重跑 registry 5/5、守卫 11P；归档探针先红、删除后绿。
- 证据根 `~/.finance-runtime/reviews/gate-closeout-qc-20260923/`，本批 `main-27ca/`。

## 未验证 / 已知边界
以上只覆盖 main 27ca，不覆盖其后提交或未带自身收据的 PR；资源争用下单次通过不证明低负载性能。未部署、未写生产库。

## 下一步
先回读 #886 候选身份与评论中的四叶状态；齐绿才能解除 WIP/合并。合入时锁 head/base，记录双亲和 merge tree；main 若再推进则判断冲突与漂移，不改历史收据。

## 踩过的坑
`main-4315/targeted-guards.log` 的 11P 实属 2439ca8a。5f35 手工前端摘要无效，只认正式 runner。PR #856 的同 SHA 原始收据只读，副本保留原身份；不清理他人的现场。本轮复用既有 runner 和校验器，未新增通用工具。
