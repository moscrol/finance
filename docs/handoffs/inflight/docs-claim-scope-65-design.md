# docs/claim-scope-65-design · #65 口径越界 lint（#850/#854）合入准备 · 2026-09-23 凌晨（S5）

**红线**：运行时一行不改；零 live；不动 8792。

## 状态

- 文档 PR 见分支 `docs/claim-scope-65-design`（base 主干；INDEX #65 行已直接推到 `docs/closeout-workorders-0922`＝#858 分支，同姊妹会话惯例）：接入点设计 `docs/superpowers/specs/2026-09-22-claim-scope-runtime-integration-design.md`；`docs/verification/2026-09-22-claim-scope-merge-65/`（README、#76 L5 条件卡、#75 候选包、第二方审查）。
- 候选：#850 `1cf35f5167ed`（base main）、#854 `5f5ce2d114b2`（叠 #850，+8 提交）。对 `gitea/main@f24a61a8a` `merge-tree` 均 clean；main 漂移 9 文件与 #854 32 文件零重叠；drift 1 张合并。
- 已取读数：registry 五条在隔离检出 `/Users/a77/fwp-gate-65/finance-workspace-private`（@5f5ce2d1，kb/site 软链在场）5/5 exit 0；#850 head 定向 31P 干净收据 `20260922T154730Z-1cf35f51.json`；阳性对照：删日期规则行情题命中 3→2、删单位规则材料题退出 1→0，还原后回原值。夹具四反例 + 正例 #854 已含。
- **已授权**：用户 2026-09-22T16:11:39Z「继续按照最优路径推进，然后可以合并的就合并」→ 案 A（先 #850 再 #854），决定 + 出处已评在两 PR。
- **第二方审查**（S5 确定性探针）`PASS_WITH_LIMITS`：台账正则不辨否定语境 → 资金流规则可被「未取得净流入数据」静默（fail-open，**后续单**，L5 条件卡已加人工缓解）；「无法确认」免责句误报（低）。#75 K3 审查未开队列，合入不等它。
- **待**：#854 head python 全量 + frontend/e2e 两叶。`~/.finance-runtime/reviews/claim-scope-merge-65-20260922/gate-runner.sh` 轮询准入；00:35 用户再授权后放弃等准入、带负载起跑；python 叶带 `--ignore=scripts/archive`（#58 未合）。

## 接手怎么做

1. `tail …/gate-runner.log`。收据按 revision + `counts.passed>0` 取 `<stamp>-5f5ce2d1.json`，`check_test_receipt.py <收据> --expect-revision 5f5ce2d114b2… --base-drift-max 5`；`frontend/frontend.json` 要 `exit_code=0 / complete / identity_stable / dirty=false`。红按 #59 分诊（单跑 ×3 + 低负载整文件 ×1）。
2. 合前 `git fetch gitea` 重探 `merge-tree`；`gitea_pr.py merge 850 --yes --expect-head 1cf35f5167ed --expect-base <gitea/main> --record …`（`--authorized-by` 用上面原话，`--authorization-source` 写会话 5e0708f1 第 2 条用户消息）→ `PATCH` #854 base→main → `merge 854 --expect-head 5f5ce2d114b2 --record …`。
3. 合后：在新 main 检出重放两冻结 run（材料 1 / 行情 3，`--scope-total 20`）逐字段不变；条件卡填合后 SHA；读数补 README / INDEX #65 / 本文；清 `fwp-gate-65` 与两 PR 的 worktree（`git worktree remove`，不 --force）。

## 不做

不修写手缺陷；不给召回率；不接 Episode 实时路径；不部署 K3、不翻 `ASK_SEMANTIC_JUDGE`；不合 #849/#840（#77）。
