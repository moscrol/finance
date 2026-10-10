# worktree_safety：指向祖先目录的启动器引用不再挡住嵌套树（PR #49）

## 背景与发现顺序

`scripts/worktree_safety.py::context_blockers` 是 `worktree_closeout.py`、`worktree_board.py`、`cleanup_gate_trees.sh`（经 `worktree_safety.py check`）三个消费者共用的「这棵树有没有被进程 / 启动器引用」判据。10-05 上午的收口轮（`docs/handoffs/2026-10-05-delegated-merge-and-tree-closeout.md` 第 17、36–37 行）把 `/private/tmp` 下与嵌在主检出下的树记为「误报挡住，暂留，已开独立任务修」；本分支就是那个任务。

1. 读收据 `~/.finance-runtime/reviews/harness-followthrough-20261004/closeout-survey-1005/dry-20261005T040409.json`：`arena-harness-release-1002`、`pr10-gates-1002` 各被 29 份 `com.a77.ima-*` plist 挡（目标 `/private/tmp`），`.worktrees/capture-quotes-0929` 被 39 个启动器挡（目标主检出根），三棵都只有这一类阻塞。
2. 追来历：双向匹配出自 `11eb5ba6f`（09-23「make cleanup guards fail closed」，shell 版 `is_referenced` 两个方向都查），同日 `18bfc3af9` 原样移植进 Python。两处提交和测试都没写需要「祖先方向」的场景；现存测试也没有一条断言祖先引用要挡。09-25 的 `70832304c` 遇到同一缺陷（`WorkingDirectory=$HOME` 挡 37 棵），只在采样端丢弃 `$HOME` 及其上层的引用。
3. 改代码前先对本机实况回放（只读：全部 launchd plist、`~/.local/bin`、runtime 软链 × `git worktree list` 30 棵）：按「只认树本身或树里」算，15 棵由挡变放，全部只因祖先引用；主检出、`finance-s7-sync`、生产快照、`ffe1c60d84da`、`40fd5a847c65` 照挡。
4. 新规则唯一可能放过真实使用的形状，是「cd 到祖先目录 + 用相对路径跑嵌套树里的代码」。对那些只经祖先引用触及 15 棵树的启动器全文查树名与容器目录名：535 对 0 命中；正对照（同一读取器找祖先目录名）29/29、39/39 命中，说明不是读取器坏了。plist 里指向祖先的键：ima 那 29 份全是 `WorkingDirectory`；主检出根是 10 份 plist 的 `EnvironmentVariables` / `WorkingDirectory` 和 29 个 shell 启动器。
5. 回放顺带看见两件与本改动无关的事（见「不在本 PR」）：`_shell_paths` 把 `${VAR:-…}` 的结尾 `}` 吃进路径；`finance-sync-7eec31b04b4b` 没有任何在用的引用。
6. 先写测试、打旧实现取红，再改实现取绿，提交后跑变异，最后用新旧两份模块在同一时刻比对实况（11:17 另一会话把 8792 从 `58d04e3780f4` 切到 `765ecbac9ad3`，所以两次回放的生产快照名不同）。

## 选择与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 单向规则：引用路径是树本身或在树里才挡，进程与启动器同一条 | 一条规则覆盖 `$HOME`、主检出根、`/private/tmp` 以及以后的任何容器目录；点名代码根 / 树里文件 / 经软链落到树上的引用都不受影响 | 采用 |
| 保留双向，再把主检出根、`/private/tmp` 加进豁免名单 | 名单要人维护，`/private/tmp` 还是平台路径；下一个容器（`/private/tmp/harness-opt` 本身就是一棵树、`~/.finance-runtime`、`~/.claude`）会再撞 | 不采用 |
| 祖先恰好是另一棵登记树的根时不算 | 管不到 `/private/tmp`（不是树）；还要把 worktree 清单塞进纯函数 | 不采用 |
| 只让 `WorkingDirectory` 键不向下继承 | 主检出根同样经 `FINANCE_WS` 等环境变量与 shell 启动器文本点名；按 plist 键分支，判据会随写法漂 | 不采用 |
| 保留 09-25 的 `$HOME` 采样端过滤作第二层 | 它只丢新规则本来就不算的引用：删它的变异没有测试能杀，注释「否则家目录下每棵树都被挡」变成假话；树恰好在 `$HOME` 时还会漏真引用 | 删除，并入规则；09-25 的测试一字不改继续绿，且在 M1 变异下变红，说明它现在直接钉住规则 |
| 顺手修 `_shell_paths` 的 `}` | 改的是「采到哪些引用」，可能让新树被挡，需要单独的先红后绿与实况回放 | 另开任务，不并入 |
| 把回放 / 比对脚本收进 `scripts/` | 见「工具沉淀盘点」 | 不收，留在证据目录 |

## 实现

`context_blockers` 的条件只剩 `Path(ref["path"]).is_relative_to(root)`，docstring 写明规则与两次事故（09-25 的 `$HOME`、10-05 的主检出根与 `/private/tmp`）。`sample_launchers.add_reference` 回到 09-25 之前的样子：`os.path.realpath(raw)` 原样记录。阻塞文案「进程 / 被 launchd/启动器引用」不变，`test_cleanup_gate_trees.py` 按文案匹配的断言不受影响。

## 验证

- **先红后绿**：新测试打 `origin/main`（`364120613`）的实现（测试已改、实现未改，故意的混合树读数），4 条 2 failed / 2 passed；改后 4 passed。红在对的原因上：`hungry-x`、`capture-quotes-0929` 被主检出根挡，`harness-opt`、`pr10-gates-1002` 被经 `tmp` 软链解析出的 `private/tmp` 挡；CLI dry-run 端到端里 `capture-quotes` ← `main-repo`、`pr10-gates` ← `scratch-root`。两条护栏（`test_reference_at_or_inside_a_tree_still_blocks_it` 与 09-25 原测试）新旧都绿，是预期：旧代码在这几支本来就对，所以靠变异钉。
- **四个 worktree 工具测试文件**：135 passed（改后、提交前；提交 `234a617d5` 未再改动，变异基线在干净的 `234a617d5` 上同为 135 passed）。
- **变异**（`scripts/mutation_check.py`，`234a617d5`）：M1 加回祖先方向 KILLED 3/3；M2 只认树本身 KILLED 2/2（另红 2）；M3 启动器一律不挡 KILLED 5/5（另红 3）；还原后与 HEAD 逐字节一致。
- **实况比对**（新旧模块各用自己的采样器、同一时刻）：新增阻塞 0；被删掉的每条阻塞都指向该树的严格祖先（脚本逐条断言）；其余 5 棵被挡的树条数不变（主检出 57、`finance-s7-sync` 2、`ffe1c60d84da` 2、`40fd5a847c65` 1、当前生产快照 29）。删 `$HOME` 过滤后采样多 2 条引用，都指向 `$HOME`，不挡任何树。
- **全量门禁**（ruff、全量 pytest、registry-check）在提交本交接之后的 PR 头上跑，读数贴 PR #49 评论。

证据目录 `~/.finance-runtime/reviews/worktree-safety-ancestor-refs-1005/`：`mutation-spec.json`、`mutation-summary.json`、`mutation-logs/`、`ancestor_ref_replay.py` 与 `replay-before-fix.txt`、`compare_old_new.py` 与 `compare-old-vs-new.txt`。

不成立的结论：回放是 10-05 11 时左右的本机快照，不证明以后的启动器都只用绝对路径；没跑任何 `--apply`，没对点名的三棵树重跑收口 dry-run（这是合入后的事）。

## 不在本 PR 的观察

1. `_shell_paths` 的无引号分支 `[^\s"'<>;)]+` 不在 `}` 停：`${FINANCE_RUNTIME:-$HOME/finance-workspace-runtime}` 采成 `…/finance-workspace-runtime}`，过不了软链。本机 63 条引用带 `}`。新旧规则都认不出这类引用；今天受影响的目标都另有精确引用挡着，或已不存在。已开独立任务。
2. `launchctl print` 看在役夜跑：sync / finalize 的 `FINANCE_SYNC_CODE_ROOT` 与 `FINANCE_CODE_ROOT` 都是 `finance-workspace-ffe1c60d84da`（被精确引用挡，且上锁）。`finance-sync-7eec31b04b4b` 没有任何在用引用，新旧规则都不靠引用闸保护它；10-05 收口记录把它列为「夜跑同步代码根」，与在役配置不符。仓内模板与 `tests/test_eval_launchd_wiring.py::SYNC_CODE_ROOT` 仍钉 `finance-sync-9c1e3154f613`，磁盘上已不存在。要不要给 `7eec31` 上锁或清掉，由用户定。
3. 8792 切走后的上一版快照同样没有引用；回滚锚靠部署账本与锁，不靠引用闸（收口工具自己的提示也这么说）。

## 工具沉淀盘点

| 问 | 本轮 |
|---|---|
| 同一手工排查做了两次以上？ | 实况回放跑了改前、改后两次，都走脚本 |
| 脚本只在临时目录跑过？ | `ancestor_ref_replay.py`、`compare_old_new.py` 留在证据目录，不收进 `scripts/`：比对脚本的核心断言（被删的阻塞都指向祖先）只对这一次规则修改成立；「每棵树现在被谁挡」的日常需求 `worktree_board.py` 已覆盖。下一次改引用规则时从证据目录拷来改断言即可 |
| 发现现有门禁的洞？ | `_shell_paths` 的 `}`：另开任务（理由见方案表），不只写进文档 |
| 可迁移模式？ | 「包含关系有方向，容器目录不能当伞」写进 `.claude/lessons_learned.md`（10-05 条） |

## 下一步

- CI 全绿且用户确认后合入。
- 合入后对 10-05 收口记录「等误报修好后回收」的两组树重跑 `worktree_closeout.py` dry-run：`.worktrees/capture-quotes-0929`、`/private/tmp` 下 `arena-harness-release-1002`、`pr10-gates-1002`，以及有未合内容的 `arena-8792-harness-takeover-0929`、`review-pr16-1002`、`harness-opt`（及其下 `harness-release-1002`）。`.claude/worktrees/*` 另有「Claude Code 会话树」规则，要到各自会话里归档。去留由用户按理由定。

## 不要做的

- 别为了「fail closed」把祖先方向加回来：它就是挡住 15 棵树的原因。启动器要保护嵌套树里的代码，就得点名树里的路径；要按约定保留，用 `git worktree lock` 写理由。
- 别再加 `$HOME` 之类的实例豁免：规则已经覆盖。
- 收口报 CLEAR 只说明「技术上无阻塞」，不是删除许可。
