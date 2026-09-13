# feat/extraction-first-p0 · 2026-09-14 · 工单 #53 提取前置 P0

## 这个分支做什么

把「提取」放到「给答案」之前：带读披露之前先收**用户自己写的**观察剧本，再展示字段差异
（只列「你写了系统未列 / 系统列了你未写」，**不评分、不算收敛**）。用户可显式跳过，跳过不计失败。

工单 `docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`（本分支新建）。
收据 `docs/verification/2026-09-14-extraction-first-p0.md`。
设计依据 `~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` rev.4（金融仓外，未改）。

基线 `gitea/main@d7e5380551ba92758935d268fdd0e6fbfdd51ce8`（= 开工时 `gitea/main`，与工单冻结号一致）。
干净新树 `.claude/worktrees/feat-extraction-first-p0`，解释器 `.venv-workbench/bin/python`。

## 决策与被否方案

- **成功事件随剧本行一次写入**（`action_event` 字段 + 读时 `projected_events` 投影）／
  否了「保存剧本后再追加一条事件行」／因为两次写会留下「剧本在、事件不在」的窗口，
  而那种断裂事后无法与「根本没提交」区分。
- **顺序门放在 `guided_reading.build` 之前**，且「先记跳过、再生成骨架」的顺序由
  `gated(on_skip=...)` 在共用门内部保证／否了「各调用方自己按顺序写两行」／
  因为靠约定维持的顺序总有一个入口会写反，写反了从输出上看不出来。
- **尝试/事件寄存在 `observation_scripts.jsonl`，用 `record_kind` 分型**／
  否了新建台账文件、否了写 `interactions.jsonl`／后者是「新用户 / 老用户」默认开关的
  判据台账，往里写任何一行都会翻转带读默认值——记录过程反而改变了被观测的行为。
- **`daily_section()` 新接缝 + `build_for_daily_review` 保留为 2 元组视图**／
  否了把 `build_for_daily_review` 改成 3 元组／因为那会打断既有调用方与四条回归。
- **关联键里的 `scope` 由身份推导**（`extraction.scope_for`，两侧共用同一函数）／
  否了读用户 `--scope` 填的值／因为「填 index、系统推 theme」会把同一个阅读目标劈成
  两个键，表现是「昨天写的草稿凭空消失」而不是报错。
- **提取门未过时退出码 0**（JSON 里 `blocked` / `code` 供机器判定）／
  否了非零／与既有「带读未开启 → 0」同档，且夜跑不能因为用户没作答而失败。

## 当前状态

- **未提交、未推送、未合 main**（合并需用户确认）。工作树上是完整实现 + 测试 + 三份文档。
- 改动：新增 `intelligence/services/observation_extraction.py`（354 行，纯判定）与
  `intelligence/tests/test_observation_extraction_first.py`（1009 行 / 76 条）；
  改 `observation_script.py` / `guided_reading.py` / `cli.py` / `personal_export.py`；
  `docs/learning/ledger-map.md` 与工单 INDEX 各 +1 行；
  `test_guided_reading_daily_seam.py` 的接线断言改指 `daily_section` 并**加强**（只加不减）。
- 新命令：`observation draft` / `observation close --attempt-id` / `observation list --events`；
  `read` / `confirm --from-slice` / `skip` 新增 `--skip-draft` / `--attempt-id`；
  `confirm` 新增 `--from-draft`。

## 已验证

- 干净基线（改动前，同树同解释器）：`9554 passed, 77 skipped, 2 xfailed, 526.44s, exit 0` —— **全绿**，
  所以任何失败都不能推给存量红。
- 最终全量：见收据 §6.1；相对基线 **0 新增失败**。
- 八条门禁叶子全绿：ruff / pytest / frontend lint·typecheck·test·build / e2e（15 passed）/ registry-check。
- A1–A15 逐条验收见收据 §3；A13 五个变异逐条 RED→GREEN（`/tmp/xfp0/mutations.txt`），还原后 76 全绿、无残留。

## 未验证 / 已知边界

- **真人效果完全未验证。** 工单 §7 三项阈值（观察周期 / 可接受额外耗时 / 撤回条件）**未填**，
  真人实验**未开跑**。`read_completed` 只证明系统成功交付，不证明人读完；`pending` 不等于离开。
- **真库路径上的身份解析本次没跑过**：全部用例都对 `river.slice_river` 与
  `resolve_identity` 打桩。它复用现有 `river.resolve_entity`，但没有本单的真库证据。
- `--from-draft` 与 `--from-slice` 同时给时后者胜（按代码顺序），未做互斥拒绝，无测试。
- 关联键里的 `scope` 是**冗余项**（由 `canonical_entity_id` 唯一决定）。按工单口径实现，
  将来若精简键，这是可以去掉的那一位。

## 下一步

1. 用户评审代码与收据；**要合并请明说**（本分支不自行合 main、不推）。
2. 合并前若 `gitea/main` 已前移：按「送审的比较基准是目标分支，不是快照」重新 diff，
   注意 `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` 是热文件——开 PR 前
   `git merge-tree` 列一遍新造冲突（#53 这一行是追加到表尾的，冲突面小但不是零）。
3. 真人实验要开跑，先由用户填 §7 三项阈值并写进工单，不得事后补。

## 踩过的坑

- **全量 pytest 跑到一半改了 `cli.py`**：那次读数的条件不自洽（部分模块按旧版收集、
  部分按新版导入），已杀掉重跑。定稿前不要碰被测代码。
- **变异测试要防 `.pyc` 缓存**：同长度改动 + 秒内还原会被 `(mtime, size)` 缓存掩盖，
  伪造出「有牙」的假象。harness 每次运行前清 `__pycache__` 且 `PYTHONDONTWRITEBYTECODE=1`。
- **变异锚点必须唯一**：`if gate.guided is None:\n        return _print_gate_block(gate, aid, args.json)`
  在 `read` 与 `skip` 里各出现一次，第一版 M4 命中两处被 harness 拒了（幸好它自己检查了计数）。
- **新树跑前端叶子前要先 `pnpm --dir intelligence/webapp install --frozen-lockfile`**：
  不装 `node_modules` 时 `eslint: command not found` 的退出码与「真红」一模一样，
  那是**无结论**不是红。e2e 还要把 `.venv-workbench/bin` 放进 `PATH`，否则
  playwright 的 webServer 回落宿主 `python3`（无 uvicorn），在任何测试跑起来前就死。
- **`registry-check` 在 `market_feature_store.cli` 下，不在 `intelligence.cli`**；
  用错入口拿到的是 argparse 的 `invalid choice`，而 `echo $?` 若前面隔了一个 `tail`
  会显示 0——两个错凑在一起能拼出一个自洽的假绿。退出码要在任何别的命令之前就存下来。
- **A14 的第一版用全文关键词扫描**，被自己模块 docstring 里「不评分 / 不相似度」这类
  **声明红线的文案**判红。改成结构判据（差异载荷里没有数 / 收据只有来源关联 /
  别的台账零写入），并先拿已知坏样本证明探针会红。顺带抓出一处真问题：
  初版把 `diff_field_count` 写进了 read 收据，违反「只持久化必要来源关联」——已删。
