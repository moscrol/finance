# refactor/ask-block-flags

## 这个分支做什么
画出产品门/两条引擎/积木，并收掉 AskOptions 的 include_*_block。

## 当前状态
已 rebase 到 `gitea/main`（`a97bfd57` 是祖先）。代码停在 `fa65ead3`：拓扑 `bd9aa875`、块开关 `59d5e86e`、研究通道关记忆锁 `fa65ead3`。树 `/Users/a77/fwp-wt-product-door-depth`。主仓脏树没动。

## 未验证 / 已知边界
- 定向 315 passed @ `fa65ead3` 干净树（收据 `20260820T025948Z-fa65ead3.json`）。其后若只有本文，行为不变。未全量、未 live。
- 表达层 `include_scenario_guidance` / `include_track_guidance` 和 `force_moneyflow_block` 有意留下。
- 能力图谱在途行 `docs/agent-product-door.md@refactor/ask-block-flags`，合 main 后去掉 `@branch`。

## 下一步
合 main 等用户点头。不要在 `feat/reading-rules-baseline-batch1` 上叠。

## 踩过的坑
`git commit -- files -m` 会把 `-m` 当成路径；`-m` 必须写在 `--` 前面。
质检时旧收据是 parent+dirty，不能当收尾证据。
