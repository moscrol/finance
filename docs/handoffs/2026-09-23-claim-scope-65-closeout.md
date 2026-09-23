# docs/claim-scope-65-design · #65 口径越界 lint（#850/#854）已合入 · 2026-09-23 凌晨（S5）

**口径说明**：运行时接入点一行未改；本批仍有离线判据模块、CLI 和测试改动；零 live；未动 8792；未翻 `ASK_SEMANTIC_JUDGE`。

## 状态

- **已合入主干**：#850 → `a696c5e1d`（`gitea_pr.py merge --record`，回读三项全过）；#854（先 `PATCH` base → 主干）→ `6fc6bfa94`（POST 客户端超时但服务端已合：tip 树 == 预览树、`^2` == head；PR 对象滞后且 `manually-merged` 不允许，已关闭留指针评论）。记录 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/merge-85{0,4}.json`，含授权原话与出处（用户 16:11:39Z / 16:34:51Z 两条）。
- 合前四叶（#854 head `5f5ce2d1`）：python 12576P/0F（`20260922T170400Z-5f5ce2d1.json`，可采信，漂移 4，带 `--ignore=scripts/archive`）；frontend+e2e exit 0（e2e 34P）；registry 5/5；预览树定向 240P；#850 head 定向 31P。
- 合后：两冻结 run 在 `6fc6bfa94` 重放逐字段一致（`replay-on-main/`）。
- 文档 PR **#869**（本分支，base 主干；#866 已关闭指向它）：接入点设计、`docs/verification/2026-09-22-claim-scope-merge-65/`（README / L5 条件卡已填候选 SHA / QC 候选包改事后审 / 第二方审查）。INDEX #65 行仍在开放 PR **#858** 的 `docs/closeout-workorders-0922` 分支，尚不能视为已落入主干。
- 远端分支 `fix/answer-claim-scope-0922`、`fix/claim-scope-hardening-0922` 已删；本地同名已 `-d`；两 PR 的 worktree 与三棵门禁树已清。`fwp-gate-65-main` 是供 #75 事后审的只读 detached 审计树；本轮质检确认其 HEAD 为 `da761024e`（#878 后），不是旧文档所写的 `bd2290c86`，也不代表之后的 `gitea/main` tip。

## 未做 / 留给后续

1. **主干 tip 全量批次门禁未跑**：合入时机器磁盘 <1 GB、swap 10.6/12 G、9 套 pytest 并发（#69 告警），新起会假红。下一轮主干批次门禁（#59 形态）补。
2. **后续单（判据缺陷）**：`check_answer_claims._ledger_has_fund_flow` 不辨否定语境（「未取得净流入数据」让资金流规则静默，fail-open，中）；`_LATEST_DAY_NEGATION` 缺「无法确认 / 无法核验」（误报，低）。夹具句在 `second-party-review.md`。L5 条件卡已加人工缓解。
3. #75 K3 审查对合后主干事后审（候选包已改）；#76 L5 用条件卡（候选 SHA `6fc6bfa94…`）。
4. 接入实施（advisory 档）需用户单独授权 + 另立单，按设计稿 §5 六条验收。
5. 本地分支 `docs/claim-scope-merge-65`（#866 旧版）未删（`-d` 拒绝、内容已在 #869）。

## 接手怎么做

#869 已合；INDEX #65 行目前仍由开放 PR #858 承载。#858 合入后，复核该行是否与最新主干和本收尾事实一致，再把“已合入”从分支事实升级为主干事实。
