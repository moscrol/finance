# fix/gate-partial-release

## 这个分支做什么
按「门禁只设在最关键证据」原则拆掉三道叠杀：G7 类型白名单改剔除式（剔非法哈希、留合法）、G11 语义放行名单加入类型缺口、残差 prime_quote/prime_news 改可选。起因 run_20260819_130854：SPT 视角问答检索齐全、稿已写完，prime_quote 混绑一条 finance_query 就整篇换成「现有证据不足」。

## 当前状态
**已合已部署（2026-08-19 14:41）+ 轨道 A live 已过（15:28）**。用户确认后经 PR #224 squash 合入 `gitea/main` = `441c60f2`；8792 快照 `~/.finance-runtime/finance-workspace-441c60f27cc2`。读数 `docs/verification/2026-08-19-gate-partial-release-live.md`。**轨道 B 可以链切**（先确认当时无 in-flight）。

## 已验证
- 定向 181 passed（verifier/semantic/residual 三文件）；全量 5604 passed / 16 failed / 12 skipped @ 本分支。
- 16 个失败 = 三个 ceiling fixture 文件的权限位/写一次审计（环境耦合），stash 后在干净 main 逐一复现 = 零回归。
- ruff 全绿；两笔提交过全部 pre-commit 门禁。
- **生产 live 原题重放** `run_20260819_152316_348138`：SPT 单视角打 8792=`441c60f27cc2`，公开稿放出结构判断（非「现有证据不足」），结构核验 completed / issues=[]，prime_quote 8 条全是 market_data。对照病灶 `130854`。
- **估值题仍 fail-closed** `run_20260819_152635_937314`：缺口模板；精确 `missing required evidence type` 未发出（零绑定），靠「无一槽 fulfilled」挡住。

## 未验证 / 已知边界
- 一周 telemetry 只开了 T+0：今日 `stripped unsupported evidence type` = 0。不能据此决定 A3。
- 精确财务锚 floor 文案仍只靠单测；live 估值题没绑错类型，floor 函数没跑到。
- A3/A4 错配未动：finance_query 仍不在 prime_quote 白名单（现在只被剔除+留痕，不再致命）。若一周后 stripped 痕迹高频，再问用户要不要加白名单。
- 重放语义层有 `semantic judge transient provider error`（R-06，与 15:06 长电同形），不是 #224 回归。

## 下一步
1. ~~原题重放~~ 已过，见 verification。
2. ~~估值 fail-closed~~ 已过（路径见 verification，不是 floor 前缀命中）。
3. **继续观察一周** telemetry 里 `stripped unsupported evidence type` 频率，再决定 A3。
4. 与 feat/reading-rules-baseline-batch1（同域，未合）的合并顺序无冲突：本分支不碰 reading_baseline。

## 踩过的坑
- 贴文分析里的槽位名是真的：`prime_quote` 只在 main（#222 后）存在，老基线树 rg 不到——查行为要对着**部署树的 revision**，不是自己检出的树。
- 真实 run 产物在 `~/.local/share/finance-workbench/users/<id>/runs/`，比读代码猜行为快得多。
- 放行名单是前缀匹配：`stripped …` 不以 `unsupported …` 开头，两个前缀都要列，漏一个就白改。

## 工具沉淀盘点
可迁移模式已提炼进 `~/harness-reference/BUILD.md`（校验器爆炸半径要匹配违规单元：剔除违规项而非作废整批；放行名单按「缺口能否诚实呈现」划界而非按结构/语义层）。无新脚本——本轮排查全部一次性 rg/jq 即可复现，不够格进 TOOLKIT。
