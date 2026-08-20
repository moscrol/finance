# refactor/ask-block-flags

## 这个分支做什么
画出产品门/两条引擎/积木，并收掉 AskOptions 的 include_*_block。

## 当前状态
两笔已提交、未推：`ccbab9dd` 拓扑正文；`880be769` 块开关收敛。树 `/Users/a77/fwp-wt-product-door-depth`。主仓脏树没动。

## 未验证 / 已知边界
- 定向 314 passed @ `6da1fe34` dirty 时跑的；提交后未再全量。
- 未 live。表达层 `include_scenario_guidance` / `include_track_guidance` 和 `force_moneyflow_block` 有意留下。
- 能力图谱在途行 `docs/agent-product-door.md@refactor/ask-block-flags`，合 main 后去掉 `@branch`。

## 下一步
合 main 等用户点头。不要在 `feat/reading-rules-baseline-batch1` 上叠。

## 踩过的坑
`git commit -- files -m` 会把 `-m` 当成路径；`-m` 必须写在 `--` 前面。
