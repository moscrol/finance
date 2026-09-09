# docs/closeout-0909

## 这个分支做什么
09-07 13:00 → 09-09 13:00 两日质检的文档收尾（A 组 1–5 + B 组 8）：INDEX #21 / #27–#30 回写已合、三张运行底座工单落地记录、slice1 头部、6 份已合交接归档、#44 部署账本占位单。纯文档，零代码。

## 决策与被否方案
- 选：#30 范围第 5 条 CLI `steer` 标 ❌ 未做。否：按 §12 第 4 题豁免——那题只豁免 Workbench 端点，CLI 在推荐范围内。
- 选：#21 写「#661 已合（v3）；v3 旁路库重建 + 重跑后才能当结论候选」。否：直接改成可当结论——重跑没人做过。
- 选：不碰母单 `runtime-base-endstate-design.md` 头部。否：改掉「草稿待审」——§12 五题确实未拍，且 P4 分支正在改该文件。
- 选：新单取 #44。否：#33——#33–#43 全在未合分支上，#41 被两棵各占一次。
- 选：删 6 棵已合 worktree + 本地分支（干净、cherry 0、远端已无）。否：留着——记忆「合并完直接删」。

## 当前状态
`ad23762c`（13 文件）+ 本交接已提交，基线 `gitea/main@f90af450`。**PR #686 已开，等用户确认合入。**

## 已验证
- 干净树全量 8300P / 0F / 77 skip / 1 xfail，336 s，收据 `~/.finance-runtime/test-receipts/20260909T053922Z-ad23762c.json`；ruff 0；pre-commit 11 道过。
- `audit_ledger_spec_crosswalk.py` 那 1 个缺号（R-20260831-02）在 gitea/main 临时干净树上逐字相同：存量。
- 六张 PR 的合入时刻 / sha 逐条对 `git log gitea/main` 核过。

## 未验证 / 已知边界
- #30 落地记录里的验收读数（单元 8 / conformance 14 / runtime 428）引自原交接，没重跑。
- 8792 未切流、09-08 主库零数据、北交所轮询已停：只记录，未处理（运行面）。
- INDEX #32 行仍写轮询在跑，未改（不在 A 组范围）。

## 下一步
- 用户：拍 §12 五题；决定夜跑 `--plan local` 重启用；确认 #686。
- **#686 先合最省事**：7 棵动过 INDEX 的分支（closeout-workorders-0908 / workorder-33 / knevo-tool-parity / methodology-promotion-certification / river-pit-strict-gate / runtime-base-p4 / sandbox-derived-calculation）前向合并 main 时各解自己那行，全是「取双方」；#21 行与 closeout-0908 同行双改，也取双方。
- CLI `steer` 小单并进 P4 #684 或单开；#44 待派。

## 踩过的坑
- INDEX 相邻行改动 git 也判冲突：对每棵分支跑 `merge-tree` 本枝 vs main 两次取差集，才分得清哪些冲突是自己新造的。取号 / 冲突扫描没沉淀成脚本（本单不带代码），手法记在 `.claude` 记忆，下一张带代码的 INDEX 单落 `scripts/`。
