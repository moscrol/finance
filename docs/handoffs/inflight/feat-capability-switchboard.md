# feat/capability-switchboard

## 这个分支做什么
从今日 `gitea/main` 抽出开关板 + 谓词缝，不搬超集树 `76ee1e89` 已漂文件。

## 当前状态
树 `/Users/a77/fwp-wt-capability-switchboard-main` @ `feat/capability-switchboard`，基线 `gitea/main@3fc47e91`。台账 `R-20260824-11` pending。本提交落地第 1 步文件。

已落：登记表、faces、词汇、离线 runner/生成脚本、第 0 步读表测试、`dual_red_counts` 最小 `faces()` 接线。`reading-baseline` 标 `pending-other-branch`。

## 未验证 / 已知边界
- 路由/说明书面未接线（`query_understanding` / `foresight` / `ask_blocks` 不读 faces）。
- 超集 960 行夹具、复印件棘轮、runner 正控未搬。
- `run_capability_switchboard.py` 会 import `reading_baseline`，#343 未合时不要强行绿 reading 臂。
- 未开 PR、未合、未切 8792/8796。

## 下一步
1. push 后开 Gitea PR。合 main / 切端口等用户。
2. 同 SHA 是 `R-20260824-09`，等本单进同一 main 且用户明示切端口。

## 踩过的坑
不要 `git checkout 76ee1e89 --` 已漂路径。不要复用 `/Users/a77/fwp-wt-capability-switchboard`（那是 `1c52e19f` 的 docs 树）。不要把 D3 空池树和本树混改。

## 已验证
`test_capability_switchboard.py` 20 绿；连带 `test_asof_prefetch_dual_red.py` 共 28 绿。ruff 绿。serving 路径无 `import capability_switchboard`。
