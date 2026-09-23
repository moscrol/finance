## 这个分支做什么
#84：从 main@626d8a508 前向 #812 看板加固，与 #876 共用只读安全采样；ownership 12 树只盘点不删除。

## 当前状态
源码 `18bfc3af96731d2df1d172c3047c189f5a6303a0` 已推；WIP PR #895。#812 评论6514已回读，含12行处置表与#895接替指针；#895评论6522记录验证边界。未合并、部署、关闭旧PR或删真实树。#64附表、INDEX已改。

## 决策与被否方案
- 采用 `scripts/worktree_safety.py` 共用状态/进程/plist/祖先采样；否仅改“不可删”文案，文案不能消除重复判据。
- 撤 #876 对整个 `.code-review-graph` 的豁免；真实未提交文件也会被那条过滤吞掉。
- 取#812两处代码增量而非整枝合入；旧组合含#813/#814及历史审查，不移签。
- 详见 `docs/handoffs/2026-09-23-worktree-board-hardening.md` 与 `docs/verification/2026-09-23-worktree-board/README.md`。

## 已验证
源码18bfc3af干净树48P；registry五项exit0且首尾同SHA/dirty=false；全仓ruff、pre-commit、merge-tree对626d8a508通过。旧main九反例9F；内存撤dirty保护1F。
树外收据根 `~/.finance-runtime/reviews/worktree-board-hardening-20260923/`；定向收据 `focused-receipts/20260923T140129Z-18bfc3af-fee7bf2202e4.json`，registry.json。这些只签源码提交，后续文档尖不移签。
12树实为6 baseline+1 ops+5 detached；全部两个tracked删除，且非基准祖先。HEAD均有分支保留（ops那棵无baseline精确锚点）；证据目录均在。原始采样 ownership.json。

## 未验证 / 已知边界
BLOCKED_RESOURCE：磁盘约9.4GiB、多轮他人全量pytest并发，未启动本单全量Python/frontend/E2E。四叶未齐，不可合入。整仓看板120s/900s超时；低预算JSON返回trees=null未知；成功JSON契约已用隔离仓CLI测试验，未取得真实整仓成功收据。
#64完整mtime/ignored/reflog/授权未验；命中dirty/非祖先即保留。未重开K3。

## 下一步
协调空间与独占资源窗口；fetch后复核main漂移/merge-tree，在最终干净head跑全量Python、frontend、E2E、registry；重取完整看板JSON。合入仍等用户确认，拆树仅#64另行确认名单。

## 踩过的坑
所有命令先cd本隔离树，默认工具cwd仍是脏主树。Gitea本机请求用 `NO_PROXY=127.0.0.1,localhost`；超时POST可能已生效，先回读marker勿盲重发。只读Git显式GIT_OPTIONAL_LOCKS=0；本树一把无人持有的空index.lock已核验移除，未动其他树锁。
