# docs/claim-scope-65-design · #65 口径越界 lint（#850/#854）已合入 · 2026-09-23 凌晨（S5）

**口径说明**：运行时接入点一行未改；本批仍有离线判据模块、CLI 和测试改动；零 live；未动 8792；未翻 `ASK_SEMANTIC_JUDGE`。

## 状态

- **已合入主干**：#850 → `a696c5e1d`（`gitea_pr.py merge --record`，回读三项全过）；#854（先 `PATCH` base → 主干）→ `6fc6bfa94`（POST 客户端超时但服务端已合：tip 树 == 预览树、`^2` == head；PR 对象滞后且 `manually-merged` 不允许，已关闭留指针评论）。记录 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/merge-85{0,4}.json`，含授权原话与出处（用户 16:11:39Z / 16:34:51Z 两条）。
- 合前四叶（#854 head `5f5ce2d1`）：python 12576P/0F（`20260922T170400Z-5f5ce2d1.json`，可采信，漂移 4，带 `--ignore=scripts/archive`）；frontend+e2e exit 0（e2e 34P）；registry 5/5；预览树定向 240P；#850 head 定向 31P。
- 合后：两冻结 run 在 `6fc6bfa94` 重放逐字段一致（`replay-on-main/`）。
- 文档 PR **#869**（本分支，base 主干；#866 已关闭指向它）：接入点设计、`docs/verification/2026-09-22-claim-scope-merge-65/`（README / L5 条件卡已填候选 SHA / QC 候选包改事后审 / 第二方审查）。INDEX #65 行已随 PR **#858** 合入主干，合并提交为 `86d3e558e3b1`。
- 远端分支 `fix/answer-claim-scope-0922`、`fix/claim-scope-hardening-0922` 已删；本地同名已 `-d`；两 PR 的 worktree 与三棵门禁树已清。`fwp-gate-65-main` 是供 #75 事后审的只读 detached 审计树；本轮质检确认其 HEAD 为 `da761024e`（#878 后），不是旧文档所写的 `bd2290c86`，也不代表之后的 `gitea/main` tip。

- **判据缺陷已修复**：台账否定语境 fail-open 与「无法确认 / 无法核验」免责误报已由 #872 修复并合入 `bd2290c86`，不再是待修项。有效门禁对应 head `0a258a098`，不是漂移超限的首轮 `b058a0a1`；详见 `2026-09-23-claim-scope-ledger-negation-closeout.md`。

## 未做 / 留给后续

1. **合入当时未跑主干 tip 全量批次门禁**：机器磁盘 <1 GB、swap 10.6/12 G、9 套 pytest 并发。本段保留历史条件；09-23 后续补验状态见 `2026-09-23-claim-scope-final-state.md`，不得把旧 head 收据当作新 tip 收据。
2. #75 K3 事后审仍待执行（审计树绑定 `da761024e`）；#76 L5 条件卡最低修复基线已提升到 #872 合并提交 `bd2290c86`，开跑前另行冻结获批候选。
3. 接入实施（advisory 档）需用户单独授权 + 另立单，按设计稿 §5 六条验收。
4. 本地分支 `docs/claim-scope-merge-65`（#866 旧版）未删（`-d` 拒绝、内容已在 #869）。

## 接手怎么做

#869、#858 均已合；INDEX #65 行现在已在主干。后续只需保持本收尾文档中的门禁、#75 审查和运行时接入未完成边界，不要把文档入主干误写成运行时接入完成。
