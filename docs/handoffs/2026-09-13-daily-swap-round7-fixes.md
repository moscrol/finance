# daily-swap 七轮修补：existing→missing 不再降为首次建库

日期：2026-09-13 晚 · 施工分支 `fix/daily-swap-lock-all-callers` · 基线 dfb6ce87
输入：七轮独立审查 `docs/qc-daily-swap-dfb6ce87`（报告 @ e8ad314b，
`docs/handoffs/2026-09-13-daily-swap-round7-qc.md`；探针 @ 同分支
`scripts/review_daily_swap_round7.py`）。**生产库未动、未合并。**

## 修了哪一刀（P2：已见旧库后消失被静默降为首次建库）

**遗漏窗口**（审查方实测复现，旧代码同样复现，非六轮回归）：
`probe_no_active_writer(target)` 成功打开过旧库之后、
`source_exists = target.exists()` 之前，目标被第三方删除 → 第二次 exists
得 False → 本轮被重新归类为首次建库 → 子进程建出缺历史的新库 → os.link
发布成功 → rc=0 / swapped=True，读回只剩当天行（旧库 2026-08-14/10000
被删后，库里只剩 2026-08-15/12345）。

**修补**（按审查建议的最小形态：钉死分类，不是再加一次 stat）：
`sync_daily_full.py::_run_daily_full_staged_locked` 开工闸处，
`source_exists = target.exists()` 提到探针**之前**——existing/absent 分类
钉死在本轮首次观察，之后不再就分类重新观察。已见旧库的轮次后来缺失只剩
两条拒绝路径，都是 rc=2：

- 消失在探针窗口内（探针的 exists→connect 之间）→ 探针抛
  `SwapTargetReplacedError`（六轮已有），本轮起在编排侧单独给措辞
  （与「有活跃写者」分开，reason 可指认）；
- 消失在探针之后 → `hold_swap_lock` 开锁失败抛 `SwapTargetReplacedError`
  → 「基线窗口失败」拒绝，子进程从未启动。

反向（钉为 absent 后第三方新建）仍由发布前守卫 + os.link EEXIST 原子拒绝
（六轮 P1），不受影响。声明边界照审查口径：钉死只覆盖本轮首次观察**之后**
的消失；观察之前就被删的，本轮无从知道它存在过。

**连带修订**（审查报告点名的小项）：

- `db.py` 顶部威胁模型补一段：分类钉死首次观察，声明边界如上（单一口径仍
  只在那一处）。
- `remove_stale_staging` docstring 改掉「收据从未写入、生产库未动」——
  与「已发布但删名失败」的合法残留不符；行为没变，只同步说明。
- `_run_daily_full_staged_locked` 概览补全两条发布路径（replace + link）。
- `docs/handoffs/2026-09-13-daily-swap-round6-fixes.md` 删掉「三份文件零
  漂移 → 门禁可外推到合并后」断言（七轮 P2 裁定不成立：main 侧改了 48 个
  路径，文本可组合 ≠ 行为正确），改写为「收据只对被测快照成立，整合候选
  须重新跑门禁」。
- `.claude/lessons_learned.md` 补两条：「已观察为既有的对象，其消失不能
  被重新解释为首次初始化」+「我改的文件对面没动 ≠ 合并后测试还过」。

**测试**（`tests/test_market_feature_store_staging_swap.py` 新增 4 条）：

- `test_target_deleted_after_opening_probe_is_not_bootstrapped`——审查红探针
  迁回常规回归：探针返回后真删除 → rc=2 / swapped=False / copy=None /
  子进程从未启动 / reason 含「已不存在」/ target 不被重建。
- `test_bootstrap_link_io_failure_refused_without_replace_fallback`
  （EPERM/ENOSPC/EOPNOTSUPP 三参数）——审查建议迁移：link syscall 失败
  结构化拒绝、不回退 os.replace、target 不创建、staging 留证。（这三条在
  修复前也绿：它们钉的是六轮 P1 已修的行为，防将来放宽。）

## 收据

统一解释器 `.venv-workbench/bin/python`，施工树干净检出 + 本刀改动。

- **反向证伪**：新探针测试对 dfb6ce87 旧代码真红（`rc=0` 而非 2，与审查
  实测一致）；link 三码测试对旧代码绿（符合预期，钉的是六轮行为）。
- **审查方原始探针 9/9 转绿**（拷入本树跑，含原红项
  `test_target_deleted_after_successful_opening_probe_is_not_bootstrapped`；
  首次在 QC 树内直接跑会误 import QC 树的旧代码——QC 树自带 conftest 把
  它自己 prepend 进 sys.path，复跑时注意）。
- **定向三文件 75 passed**（71 + 新增 4，数目对账严丝合缝）。
- `ruff check .` 全仓通过。
- 全量口径（**八轮复审更正**）：本刀提交前跑的一轮是 9,521 passed / 0 failed /
  77 skipped / 1 xfailed（437s，exit 0），但收据 JSON 绑定的是
  `dfb6ce87 + 未提交修补` 的脏树（dirty=true，dirty_paths 即本刀三文件），
  不是干净提交收据——本节原先写「干净工作区」不准确。八轮在干净 c20abf7d
  重跑：**9,518 passed / 1 failed / 79 skipped / 1 xfailed**（收据
  `20260913T104506Z-c20abf7d.json`）；唯一红
  `test_installed_codex_sandbox_denies_network_and_unix_socket` 在父提交
  2d16a7f7 全量同红（非本刀引入），本树单独复跑绿——与四~六轮记录的已知
  抖动一致，保留为 baseline exception，不伪装全绿。无论哪份收据都只
  对**被测快照**成立——合并候选须按七轮裁定重新跑门禁，不得外推。

## 明确没做的事

- **一般 clone IO 裸抛**（cp/copy2 的 EPERM/ENOSPC 逃出编排）：审查裁定为
  错误出口旧债、另开小提交，本刀不夹带。target 字节实测不变，不是数据
  覆盖问题；后续应在编排边界返回 rc=2 + 异常类型/errno/阶段，不得伪装成
  「目标被替换」。
- **合并范围裁定**：本分支携带整个 hithink 重建（15 文件、3723 插入），
  合并不凭本刀复审放行；整合候选须重新组装干净树、重跑适用门禁，合并与
  生产换库仍须分别授权。
- 未做数据端到端对账（本刀不动数据）。
