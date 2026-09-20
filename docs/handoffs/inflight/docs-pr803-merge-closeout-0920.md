# 在途交接 · #803合入与清树封存

## 这个分支做什么
承接用户执行授权，封存#803合main、#789接替评论与安全清树结果；不部署。

## 决策与被否方案
- 最终728f3271重新全叶后fast-forward-only合入；否借d95旧收据/新造未测merge身份。
- 看板仅初筛；否status干净就force删。逐blob、reflog、ignored、进程/launchd引用及回滚锚必须过。
- 只删已证安全树，未知数据保留；否把用户库当缓存。日期快照 `../2026-09-20-pr803-merge-cleanup.md`。

## 当前状态
封存提交d2a72bb6已推gitea，文档PR #804已开、未合；#803收尾评论5056链接固定证据，#789指针评论5050已补。#803合入身份728f3271，来源分支保留。清理时移除44棵旧树（28开发+16快照），另拆本轮前端树，收尾293棵；未再删树。本枝仅文档，main和生产不随本枝推进。树 `~/.finance-runtime/reviews/pr803-merge-cleanup-20260920/python/finance-workspace-private`。

## 已验证
728f3271两独占树全叶：Python11913P/85S/2X、前端110P、E2E34P/2S，Ruff/registry五项0；合前后严格收据revision/解释器/依赖相符、漂移0。80旧原件+2事件流hash全符。两清树批次refs和剩余注册项不变、精确删除差集；44份元数据可核、抽树恢复3549文件。8792前后及发布时healthy/bf662e93/dirty=false/code_matches_repo=true。文档提交前39扫描文件927P、Ruff通过，d2a提交钩子无失败（不适用项跳过）；41份封存原件hash全符。记忆81e2a9a2已同步gitea。证据 `docs/verification/2026-09-20-pr803-merge-cleanup/README.md`。

## 未验证 / 已知边界
本枝新文档不继承728f3271全量签字。R2跨午夜/原夜跑全链/生产真实采集/下一夜时钟触发未验；未动8792/L2/索引/launchd。74棵候选有未知ignored，23棵已合开发树有脏内容，全保留；acceptance-tests的reflog未被main覆盖拒删。剩21生产快照含当前/回滚/数据，不全是垃圾。

## 下一步
1. #804保持待审；后续合文档须用户确认、核最终身份与适用门禁，不能借728f全量签字。
2. 继续清树先认领数据/脏改动，禁止直接重跑冻结删除器。
3. R2与#802、#797/#798/#800独立推进；生产部署另授权。

## 踩过的坑
通用basename finance-workspace-private会误报进程引用；本轮自建前端树首次0删除，改完整路径匹配后执行。旧树独特basename判据未改。status不保ignored/reflog安全。无交互提交须-m及明确pathspec；超时遗锁先核持锁进程，不盲删。
