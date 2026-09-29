# worktree 收口工具整合（2026-09-28）

分支 `claude/happy-lovelace-7eb522`。机制与用法以 `scripts/worktree_closeout.py` 的 docstring / `--help` 为准，本文只记背景、发现顺序、被否方案与验证。

## 背景

2026-09-23..09-28 七轮 worktree 清理，每轮各写一遍一次性脚本（`~/.finance-runtime/reviews/` 下 `disk-cleanup-20260923/round{4,5}-plan.sh`、`round5-worktrees.py`，`pi-session-inventory-20260924/cleanup/{classify,remove,salvage,salvage_and_remove,remove_evidence}_trees.py`，`unclosed-inventory-20260926/raw/{wt_classify,categorize}.py`，`legacy-worktree-closeout-20260928/{classify,plan,closeout}.py` + `ratio.sh`）。最全的是 09-28 那版（记录 `docs/handoffs/2026-09-28-legacy-worktree-closeout.md`，PR #950 分支）。仓内已有三件：`worktree_safety.py`（只读阻塞采样）、`cleanup_gate_trees.sh`（只拆已合入 / detached 的干净树）、`worktree_board.py`（git cherry 看板）。用户要求：把缺的能力收进仓内工具，默认 dry-run、`--apply` 才动、每轮 JSON 收据；**不加自动 / 定时清理**（09-23 明确否决）；开发期间不动任何现存 worktree，只在临时仓上测。

## 按发现顺序

1. 通读三件现有工具与七轮脚本。`worktree_safety.status_paths` 本来就不 strip（运行器只去尾部换行），但丢了 rename 源、分不出已跟踪 / 未跟踪，封存要用这两样。
2. **探针失误**：沙箱拒了 `mktemp -d`，`set -e` 没停住，`cd ""` 留在本树，`git init` 半途失败后 git 命令落到外层仓——本分支多 2 个垃圾提交、建又拆了一棵临时 worktree `wt`。已 `git reset bdd19f416`（非 --hard）退回、删垃圾目录；别的树没碰、没推送。教训进 `.claude/lessons_learned.md`。
3. 同一次探针顺带测实了三件事：`--ignored` 配 `-uall` 会把 `node_modules` 里每个文件逐条列出，`--ignored=matching` 只报 `dir/`；`rev-list <head> --not --stdin` **不否定** stdin 读进的 sha（同仓 6513 vs 1，09-28 `classify.py` 的未推计数因此是错的）；`git worktree remove` 拆 detached 树不警告，HEAD 只挂在该树上的提交当场成孤儿。
4. `cp -c` 跨卷静默退化成整份拷贝（man 页原文）；ctypes 调 `clonefile(2)` 失败会返回 -1 + errno。
5. 实现（见下节决策）。
6. 测试暴露：`git worktree list --porcelain` 在默认 `core.quotePath=true` 下把中文锁理由写成 `"\347\225\231..."`（本机未设 quotePath）。据此给 `cleanup_gate_trees.sh` 写了两条红测试，都先红后绿：中文「留待」锁在 `--release-merged-locks` 下被误解锁拆掉；detached 树的孤儿提交被拆掉。
7. 真实仓只读冒烟：`worktree_board.py --landed` 28 棵 12 秒，已算 15 条、≥90% 的 0 条。`worktree_closeout.py` dry-run 点名 4 棵本该保留的树（5a5e、7a40、FinArena、Knevo），全报无阻塞。诊断（沙箱外只读）：lsof 18899 条引用、本会话树命中 12 条，检测正常；是现状变了——`~/finance-workspace-runtime` 当天 12:29 已切到 `finance-workspace-8e45e299a13b`，5a5e 成了上一版。据此把 dry-run 输出改成 CLEAR「技术上无阻塞」并写明工具认不出回滚锚 / 保留约定。

## 决策与被否方案

| 决策 | 选了 | 否了 | 为什么 |
|---|---|---|---|
| 装在哪 | 新脚本 `worktree_closeout.py`；只读度量加进 board（`--landed`），只读原语回到 safety | 扩 `cleanup_gate_trees.sh`；扩 board | 扫描器的安全来自「只拆干净树」，加上保全能力等于给全仓自动扫配上拆脏树——被否决的自动清扫；board 契约是只打印、SessionStart 每会话跑。bash 写补丁回验 / tar 回读 / 收据就是第八轮重写 |
| 计划从哪来 | dry-run 收据即 apply 计划（带采样时 HEAD 与时刻）；`--apply` 只收它 | 手写计划直接 apply；apply 时现采现拆 | 「HEAD 未变 / 采样后无改动」需要一个采样基准；强制先看 dry-run |
| 数据库残留 | `clonefile(2)` 克隆 + sha256 回读，失败整棵停 | 进 tar；zstd 压缩（09-28 做法）；`cp -c` | 本仓 DuckDB 是 APFS 克隆，压缩是新写数据（09-28 实测净多占 ~4 GiB）；`cp -c` 跨卷静默整份拷 |
| 空间读数 | apply 收据只记 statvfs 前后差 | 按 du 估节省 | du 把共享块算进每份，高估可回收空间 |
| 封存回验 | 封存提交改动路径集 == `git diff --name-only HEAD`（树自己的索引只读）∩ 名单 + 未跟踪文件 | 刷新整棵临时索引后 diff-files；逐文件 hash-object | 前者要重新哈希整棵树（慢）；后者要自己处理过滤器与符号链接 |
| 盘点忽略项 | `--ignored=matching` + 自己展开目录 | traditional 逐文件列 | 后者把 node_modules / .venv 十万文件逐条列出 |
| Claude 会话树 | 硬阻塞，不给开关 | 允许点名拆 | app 归档时会清树；从外面拆会弄坏会话（09-28 同样保留了两棵） |
| 理由 | 没写理由算阻塞 | 可选 | 受托代拍的收据要能回答「为什么拆这棵」 |
| 锁 | 计划里逐棵 `release_lock`；锁在采样后变了就跳过 | 沿用 cleanup 的 retain 正则 | 09-28 就是解了「留待授权部署」的四棵——那是人的判断，正则判不了；新锁的理由没人审过 |
| 推送 | apply 一律推钉与封存分支，失败不拆 | 提供 `--no-push` | ls-remote 不通时本来就拆不了；本机独有提交保持 0 |
| 部署账本 | 不接，只在输出里提示「先查部署账本」 | 按账本把现役 / 上一版判阻塞 | 回滚锚常是人指定的（09-28 是 7a40 而非上一版），规则判不准；拆错可 `git worktree add` 重建且残留已归档 |
| cleanup 孤儿守卫 | 查具名 ref（分支 / 标签 / 远端跟踪 / refs/archive），离线 | 查 Gitea ls-remote | 扫描器原本离线可用，不引入网络依赖 |
| 缓存口径 | `.code-review-graph` 并入 `CACHE_IGNORED`（board / cleanup 同受影响） | 只在收口里当缓存 | 可由 `code_map.py build` 重建；两份被跟踪的 steering 文件仍按普通改动算 |

## 验证与收据

- 相关四个测试文件 121 条全绿（沙箱外；沙箱里 cleanup 测试的 `mktemp` 会被拒，是环境不是代码）：closeout 37、safety 27、board 43、cleanup 14。全部在 `tmp_path` 的一次性仓 + 裸仓当 gitea + 假 lsof 上跑。
- 真实仓只读冒烟两次（上节第 7 条），收据写在临时目录，未留存；没有对任何真实树 `--apply`。
- 全量四叶在本分支 head 上跑，读数贴 PR 评论（不回写本文件）。

## 后续

- 合入后第一次真用：先对一棵确定可拆的树走完整 dry-run → apply，核对收据里的 statvfs 差与归档目录，再批量。
- `worktree_board.py --landed` 目前只对 cherry+ 的树算；需要时可按文件给出未落地的行，帮人判断「余下 10% 是不是没合进去的修复」。
- 若以后要自动识别回滚锚，从部署账本读「人标注的锚」而不是推断上一版。

## 不要做的

- 不要把 dry-run 的 CLEAR 读成「该拆」：它只说明拆了不丢东西、没人在用。
- 不要为了「省空间」把 `*.duckdb` 打包或压缩，也不要按 `du` 估节省（理由见上表与脚本 docstring）。
- 不要给本工具加定时 / 自动触发：用户 09-23 否决过自动清扫，收口必须由人点名。
