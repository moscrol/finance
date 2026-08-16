# 2026-08-17 视角快照/留出分支不合

roadmap_ref: 无（决策收口，不立项）

一句话：P0（triple-gate / contradictions / honest_boundaries）留在 main；`feat/perspective-snapshot-holdout` 整包扔掉。

## 已核实（2026-08-17）

- `gitea/main` tip `dd28e4d8`。`01fb1cf0` / `9431fa57` 是祖先。holdout 提交 `5a4517db` **不是**祖先。
- `git grep` 在 main 上无 `verify_holdout` / `SNAPSHOT_KEEP` / 「第 5.5 步」。
- 远程 `feat/perspective-snapshot-holdout` 已删，无 PR。
- 对照一手源：https://github.com/titanwings/colleague-skill `tools/version_manager.py`、`prompts/celebrity/budget_unfriendly/validation.md`、`SKILL.md` triple-gate 段。

## 决策

对方 validation 是 known-answer + edge-case + 口吻/版权，**不是**词元回声。本仓回声 ≥50% 门禁是借词不借法，不当验收。快照「改前留底」合理但非必须，不单独留。

## 不要做

- 不要复活该分支或把回声 50% 当门禁。
- 不要修那条分支上的三个实现坑（尺子不该存在）。
- 真要验收：另开分支做已知题/边题/盲测，不要从 `5a4517db` 续。

## 本地

废稿树 `/Users/a77/fwp-wt-perspective-gates` 收尾时拆除。远端 `research/perspective-gates` 仍在（已合 P0 的旧名），不是本决策范围。
