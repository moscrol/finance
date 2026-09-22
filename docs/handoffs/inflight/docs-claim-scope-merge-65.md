# docs/claim-scope-merge-65 · #65 口径越界 lint（#850/#854）合入准备 · 2026-09-22 夜（S5）

**红线**：运行时一行不改；合入 main 等用户确认；零 live；不动 8792。

## 状态（写于动作完成之后）

- 文档 PR **#866**（head `650c50eae`，base `docs/closeout-workorders-0922`＝#858，因 INDEX #65 行只在 #858 上）：接入点设计 `docs/superpowers/specs/2026-09-22-claim-scope-runtime-integration-design.md`、`docs/verification/2026-09-22-claim-scope-merge-65/`（README / #76 L5 条件卡 / #75 QC 候选包）、INDEX #65 行改进行中。#858 先合则自动 retarget。
- 候选身份：#850 `1cf35f5167ed`（base main）、#854 `5f5ce2d114b2`（base = #850 分支，多 8 提交）。两者对 `gitea/main@f24a61a8a` `merge-tree` clean；main 漂移 9 文件与 #854 32 文件零重叠；`--base-drift-max 5` 口径漂移 1。
- 已取读数：registry 五条在隔离检出 `/Users/a77/fwp-gate-65/finance-workspace-private`（detached @ 5f5ce2d1，kb/site 软链在场）5/5 exit 0；#850 head 定向 31P 干净收据 `20260922T154730Z-1cf35f51.json`（该 head 无 `tests/test_check_answer_claims.py`）；阳性对照删日期规则行情题命中 3→2、删单位规则材料题退出 1→0，还原后回原值（`~/.finance-runtime/reviews/claim-scope-merge-65-20260922/positive-control/`）。
- 四类反例 + 合法正例夹具 #854 已含（`REAL_*_CLAIM` 原句 + `*_is_clean`），PR head 未动。
- **待**：#854 head python 全量 + frontend/e2e 两叶——`gate-runner.sh` 在等准入（load ≤ 8、pytest ≤ 2；23:55 时 load 26–30、5 套并发），日志 `…/gate-runner.log`；python 叶带 `--ignore=scripts/archive`（#58 未合）。落地后按 revision + counts>0 取 `<stamp>-5f5ce2d1.json`，`check_test_receipt.py <收据> --expect-revision 5f5ce2d1… --base-drift-max 5`。
- **已授权**：用户 2026-09-22T16:11:39Z「继续按照最优路径推进，然后可以合并的就合并」→ 案 A（先 #850 再 #854），决定 + 出处已评在两 PR。两叶绿后：`merge 850 --expect-head 1cf35f5167ed --record` → `PATCH` #854 base→main → `merge 854 --expect-head 5f5ce2d114b2 --record`。
- **第二方审查**（S5 确定性探针，零 live）`PASS_WITH_LIMITS`：台账正则不辨否定语境 → 资金流规则可被「未取得净流入数据」静默（fail-open，后续单）；「无法确认」免责句误报（低）。见 `second-party-review.md`。#75 K3 审查未开队列，合入不等它。

## 接手怎么做

1. `tail ~/.finance-runtime/reviews/claim-scope-merge-65-20260922/gate-runner.log`；两叶红先按 #59 分诊表（单跑 ×3 + 低负载整文件 ×1）。
2. 读数补进 `docs/verification/2026-09-22-claim-scope-merge-65/README.md` 与 INDEX #65 行，pathspec 提交推 `docs/claim-scope-merge-65`。
3. 合入后：条件卡「候选代码 SHA」填合后 main SHA；在合后 main 上重放两冻结 run（材料 1 / 行情 3，`--scope-total 20`）逐字段不变；清 `fwp-gate-65` 与两张 PR 的 worktree（`git worktree remove`，不 --force）。

## 不做

不修四条写手缺陷；不给召回率；不接 Episode 实时路径；不部署 K3、不翻 `ASK_SEMANTIC_JUDGE`；不合 #849/#840（归 #77）。
