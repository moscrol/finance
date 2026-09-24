# 2026-09-21 两参表格家族收口：#815 合入 main、#821 真值化、#805/#806/#808 关闭

## 身份

- 被测候选 `06f74ef14dbe246cf8d9330b43711ffacb12284f`（`fix/fincalc-row-snapshot-0921`）= 三 PR 组合 `5b27fc6b`（#806 `5d46e626` → #805 `4aa80540` → #808 `89e6217a`，普通合并，基底 `728f3271`）+ 行值快照修复 `78898065` + 交接提交。
- 树外证据根 `~/.finance-runtime/reviews/stale-closeout-k3-20260921/`，入口 `CURRENT.md`；同目录 `README.md` / `handoff.md` 是冻结时的 BLOCKED 快照，已封存，不改写。

## 合入与验证（2026-09-21）

| 步骤 | 读数 |
|---|---|
| 合入前置 | base `728f3271` 未动；`git merge-tree --write-tree` 干净；作者门禁收据 `20260920T193322Z-06f74ef1.json` 从 06f74ef1 候选树用 `.venv-workbench` 重验 9/9 可采信（11944P / 0F / 85S，基座漂移 0）；封存清单 29/29、944/944 OK |
| #815 合入 | merge commit `8aff6ebc3f0ea681a80179fbca8e1f39a815f103`，11:42，用户回复「合并」；parents = 728f3271 + 06f74ef1；main 的树 `0af60538` 与 merge-tree 预览、与 06f74ef1 的树三者相同，即 main 就是收据所测的那棵树 |
| #821 合入 | merge commit `602ec8b751c5e84bf078ae15ad8500fa8c7ac39d`，11:55，用户回复「合并」；inflight 真值化，docs-only 单文件；pre-commit 11 道过，扫 handoffs 的四个测试文件 74P/1S |
| #805 / #806 / #808 | 合入前先加 `WIP:` 守卫：三张 head 都是 06f74ef1 的祖先但都不含 `78898065`，单独合入任一张会把缺修复的版本落进 main。合入后贴接替指针（评论 5219 / 5223 / 5227，指向 #815 / 8aff6ebc 与本文入口）关闭，远端分支删除；本地分支与证据树未动 |
| 独立验收 | Spec 根 QC 接受 13 项 / 93 个实际断言；Quality 首轮 40 请求触顶 exit 75 为 BLOCKED（原件保留），`quality-followup-01` 为 PASS_WITH_LIMITS。非完全盲审，不覆盖真实指数覆盖、真实回答质量、下载端点与全仓 / 前端测试 |

## 出册

本提交移除五份已合分支的 inflight 交接：`fix-fincalc-row-snapshot-0921`、`fix-fincalc-table-closeout-0921`、`fix-generation-degrade-closeout-0920`、`fix-broad-index-closeout-0920`、`baseline-stale-closeout-integration-0921`。它们各自的日期快照（`2026-09-21-fincalc-row-snapshot-k3`、`2026-09-21-fincalc-table-closeout`、`2026-09-20-generation-degrade-closeout`、`2026-09-20-stale-broad-index-closeout`、`2026-09-21-stale-closeout-integration`）保持冻结；其中「未合 / 待用户确认 / 不关闭原 PR」是当时状态，现状以本文为准。

## 仍在途、未做

- #770 材料来源 / 权限 / 冻结 / 重算，#804 / #807 文档语义复核：独立处理，不因本次合入视为已吸收。
- 未部署、未切换 8792、未生产采集或回填。
- 未删旧证据树 / 数据 / 恢复锚：`stale-closeout-k3-20260921/`、`stale-work-closeout-20260920/`、`stale-integration-20260921/` 各树仍在；分支 `baseline/stale-closeout-integration-0921` 远端仍在（无 PR，内容已在 main）。
- 真实行情、真实金融回答质量、生产数据均未验证。

## 踩过的坑

- #815 建 PR 时带 `WIP:`，06:35 前缀被去掉（时间线可见，操作者未记录），到 10:50 才重新加回；这四个多小时里它在平台层可合。给「组合件」加守卫不等于给「零件」加了守卫，兄弟 PR 要逐个罩住。
- 收据校验从主检出树用宿主 python 跑，得到 4 项「不符」；换到候选树 + `.venv-workbench` 后 9/9 一致。不符的是运行环境，不是收据。
- 主检出树是停住的运维叠加层，`git branch -d` 按上游判断已合并，要在 `fetch --prune` 之前删本地分支，否则退回按 HEAD 判断会拒绝。

## 记录

树外 `wip-guard-0921.json`、`merge-815-record.json`、`merge-821-record.json`、`close-siblings-0921.json`，每份都带授权来源：长效指令的文件路径、实时用户原话及其出处。
