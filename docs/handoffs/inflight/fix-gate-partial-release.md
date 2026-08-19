# fix/gate-partial-release

## 这个分支做什么
按「门禁只设在最关键证据」原则拆掉三道叠杀：G7 类型白名单改剔除式（剔非法哈希、留合法）、G11 语义放行名单加入类型缺口、残差 prime_quote/prime_news 改可选。起因 run_20260819_130854：SPT 视角问答检索齐全、稿已写完，prime_quote 混绑一条 finance_query 就整篇换成「现有证据不足」。

## 当前状态
两笔已提交已推 gitea：`53bb4d9d`（G7+G11+测试）、`a87f21bd`（prime 槽可选）。工作树干净。**未合 main、未部署**——8792 仍跑旧 main（`a7e2d74f`，部署树 `~/.finance-runtime/finance-workspace-a7e2d74f7789`），合并需用户确认，合并后要更新部署树并重启才生效。

## 已验证
- 定向 181 passed（verifier/semantic/residual 三文件）；全量 5604 passed / 16 failed / 12 skipped @ 本分支。
- 16 个失败 = 三个 ceiling fixture 文件的权限位/写一次审计（环境耦合），stash 后在干净 main 逐一复现 = 零回归。
- ruff 全绿；两笔提交过全部 pre-commit 门禁。

## 未验证 / 已知边界
- 未跑 live：8792 没切代码，SPT 原题未真机复测。合并部署后拿原题（用 SPT 视角看 2026-08-18 盘面）重放，预期 verified=completed、issues 只剩 stripped 痕迹。
- 财务锚硬门有测试钉住（floor 不进放行名单），但没在 live 估值题上验过。
- A3/A4 错配未动：finance_query 仍不在 prime_quote 白名单（现在只被剔除+留痕，不再致命）。若 stripped 痕迹高频出现，可考虑把 finance_query 加进 prime_quote 白名单——那是数据口径决定，留给用户。

## 下一步
1. 用户确认后合 main → 更新部署树 → 重启 8792 → 原题重放。
2. 观察一周 telemetry 里 `stripped unsupported evidence type` 频率，决定要不要动 A3 白名单。
3. 与 feat/reading-rules-baseline-batch1（同域，未合）的合并顺序无冲突：本分支不碰 reading_baseline。

## 踩过的坑
- 贴文分析里的槽位名是真的：`prime_quote` 只在 main（#222 后）存在，老基线树 rg 不到——查行为要对着**部署树的 revision**，不是自己检出的树。
- 真实 run 产物在 `~/.local/share/finance-workbench/users/<id>/runs/`，比读代码猜行为快得多。
- 放行名单是前缀匹配：`stripped …` 不以 `unsupported …` 开头，两个前缀都要列，漏一个就白改。

## 工具沉淀盘点
可迁移模式已提炼进 `~/harness-reference/BUILD.md`（校验器爆炸半径要匹配违规单元：剔除违规项而非作废整批；放行名单按「缺口能否诚实呈现」划界而非按结构/语义层）。无新脚本——本轮排查全部一次性 rg/jq 即可复现，不够格进 TOOLKIT。
