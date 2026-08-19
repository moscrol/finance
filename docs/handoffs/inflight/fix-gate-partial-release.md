# fix/gate-partial-release

## 这个分支做什么
按「门禁只设在最关键证据」原则拆掉三道叠杀：G7 类型白名单改剔除式（剔非法哈希、留合法）、G11 语义放行名单加入类型缺口、残差 prime_quote/prime_news 改可选。起因 run_20260819_130854：SPT 视角问答检索齐全、稿已写完，prime_quote 混绑一条 finance_query 就整篇换成「现有证据不足」。

## 当前状态
**已合已部署（2026-08-19 14:41）**。用户确认后经 PR #224 squash 合入 `gitea/main` = `441c60f2`；按 R-24 规范流程部署 8792：新快照 worktree `~/.finance-runtime/finance-workspace-441c60f27cc2`（detached、porcelain 干净）→ `ln -sfn` 链切 `~/finance-workspace-runtime` → kickstart。验收三读数 `source_revision=441c60f27cc2 / source_dirty=false / code_matches_repo=true`，`/api/health/ready` 全绿（13 项含 rag_worker，`missing_critical=[]`，起动约 18s 未撞预热窗）。旧快照 `finance-workspace-a7e2d74f7789` 保留作回滚锚。远端分支已删，本地分支与树 `~/fwp-wt-gate-release` 留作取证。

## 已验证
- 定向 181 passed（verifier/semantic/residual 三文件）；全量 5604 passed / 16 failed / 12 skipped @ 本分支。
- 16 个失败 = 三个 ceiling fixture 文件的权限位/写一次审计（环境耦合），stash 后在干净 main 逐一复现 = 零回归。
- ruff 全绿；两笔提交过全部 pre-commit 门禁。

## 未验证 / 已知边界
- 未跑 live：8792 没切代码，SPT 原题未真机复测。合并部署后拿原题（用 SPT 视角看 2026-08-18 盘面）重放，预期 verified=completed、issues 只剩 stripped 痕迹。
- 财务锚硬门有测试钉住（floor 不进放行名单），但没在 live 估值题上验过。
- A3/A4 错配未动：finance_query 仍不在 prime_quote 白名单（现在只被剔除+留痕，不再致命）。若 stripped 痕迹高频出现，可考虑把 finance_query 加进 prime_quote 白名单——那是数据口径决定，留给用户。

## 下一步（归 live 验证 agent）
1. 原题重放（用 SPT 视角看 2026-08-18 盘面）打 8792：预期 verified=completed 或 partial 放行正文，issues 至多剩 `stripped unsupported evidence type` 痕迹，不再出「现有证据不足」模板。run 产物在 `~/.local/share/finance-workbench/users/<id>/runs/`。
2. 顺手验一条估值/财务题：财务锚 floor（`missing required evidence type`）必须仍 fail-closed。
3. 观察一周 telemetry 里 `stripped unsupported evidence type` 频率，决定要不要把 finance_query 加进 prime_quote 白名单（A3，数据口径决定，留给用户）。
4. 与 feat/reading-rules-baseline-batch1（同域，未合）的合并顺序无冲突：本分支不碰 reading_baseline。

## 踩过的坑
- 贴文分析里的槽位名是真的：`prime_quote` 只在 main（#222 后）存在，老基线树 rg 不到——查行为要对着**部署树的 revision**，不是自己检出的树。
- 真实 run 产物在 `~/.local/share/finance-workbench/users/<id>/runs/`，比读代码猜行为快得多。
- 放行名单是前缀匹配：`stripped …` 不以 `unsupported …` 开头，两个前缀都要列，漏一个就白改。

## 工具沉淀盘点
可迁移模式已提炼进 `~/harness-reference/BUILD.md`（校验器爆炸半径要匹配违规单元：剔除违规项而非作废整批；放行名单按「缺口能否诚实呈现」划界而非按结构/语义层）。无新脚本——本轮排查全部一次性 rg/jq 即可复现，不够格进 TOOLKIT。
