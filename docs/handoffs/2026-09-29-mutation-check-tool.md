# 2026-09-29 · 变异自检运行器 `scripts/mutation_check.py`（PR #965，含独立审查补丁）

## 背景

- 变异验证在 harness-reference `TOOLKIT.md` 里只登记为「手法，非脚本」，每次用都现写一次性脚本。
  #961 用的是 `~/.finance-runtime/reviews/gitea-pr-timeouts-0929/mutate_gitea_pr.py`（约 50 行）：
  源文件干净才开跑、替换恰 1 次、删 `scripts/__pycache__/gitea_pr*.pyc` 并带 `PYTHONDONTWRITEBYTECODE=1`、
  `git checkout --` 还原后核字节与干净、判据「期望红 ⊆ 实红且 exit≠0」。#961 交接的「下一步 3」就是把它做成工具。
- 记忆里记了这件事的坑：同秒同长度的过期 `.pyc`（08-01）、`git checkout --` 吞未提交实现（09-15）、
  替换 0 次测的是空气（08-12 / 09-15）、红错原因（09-21）、部分红（09-14）、两层防御要两条断言（09-14）。
- 仓内已有四个变异件，没有一个是「作者侧、任意文件、按点名子集判定」的通用件：
  `scripts/review_probes/run_extraction_mutations.py` 是证据级（冻结 revision + 临时 detached worktree +
  定义入库 + JUnit，判据「选中的测试里有失败」）；`run_boundary_repair_mutations.py`、
  `run_financial_contract_mutations.py`、`history_diagnostic_mutations.py` 在子进程内存里 monkeypatch，不改源码。

## 按发现顺序

1. 读 ad-hoc 脚本、8 条变异相关记忆、TOOLKIT 三处（B 表行、「三条量具陷阱」3/4、H 表行），发现
   `run_extraction_mutations.py`，比对后决定新建而不是扩它（见决策表第一行）。
2. 实测复现字节码陷阱：对齐到整秒后写原版、import、再写同长度变异体，import 到的仍是原版
   （`add(2,3)` 应为 -1，实得 5）。另证：`UNCHECKED_HASH` 的 `.pyc` 在源文件已改、
   `PYTHONDONTWRITEBYTECODE=1` 时照样被采信——测试里用它确定性复现这个陷阱，不靠时钟碰运气。
3. 写工具与 21 条测试，全绿。
4. 规划自检时发现三处「两层互相接住」，拆一层另一层兜住、测试照绿：
   - 还原点三道核验（不在 HEAD / `git status` / 与 HEAD blob 比）：modified 与 staged 三道都拦得住。
     补 untracked（只有「不在 HEAD」报对原因）、staged-then-reverted（工作区 == HEAD 而索引不是，只有 status 看得见）、
     assume-unchanged（status 说干净，只有 blob 比对看得见），并断言各自的报错文案。
   - 红错原因两条分支（收集期报错 / 点名测试没以断言失败的方式变红）：默认配置下收集报错会让所有测试都不跑，
     两条互相接住。补 `--continue-on-collection-errors` + 懒 import 的测试（只有收集期那条拦得住），
     和夹具 setup 报错（只有「没以断言失败变红」那条拦得住）。
   - 杀进程组 vs 只杀 leader：挂住的测试就是 pytest 进程本身，只杀 leader 也能过。补：挂住的测试起一个孙进程，断言两者都没了。
   - 顺手删了一条不可达分支（点名测试全在 call 阶段 failed 时，pytest 的 exit 必为 1），它无法被变异验证，留着只是噪声。
   → 23 条测试。
5. pytest 默认把非 ASCII 的参数化 id 转义成 `\u...`，spec 里没法点名 → 改为显式 ASCII ids。
6. 实现提交后跑自检 spec（30 个 mutant，每个拆一道保护、点名只有它拦得住的那条）：30/30 KILLED @460ffe388。
   推分支、开 PR #965（f4eaad043）。
7. **独立收尾审查（另一会话，15:07–15:30）找到合前阻断**：`file_problem` 只查末级 `is_symlink`。
   两种目标三道核验全过、写入却落到仓外：父目录是符号链接（配 `assume-unchanged` 让 status 隐去原路径，
   仓外放同字节文件骗过 HEAD blob 比对）；仓外同字节硬链接（同 inode）。硬链接这条比看上去更糟：
   崩溃后的兜底 `git checkout --` 会先删再建仓内那份，仓外那个 inode 留在变异态。审查会话在临时仓复现、
   回归测试对原版先红，非强推补进 #965：702481725（拒 `path.resolve() != path`）、040a4a261（拒 `st_nlink != 1`），
   并在 PR 评论写明「30/30 不是新头重跑的」「本地分支停在旧头，续作先核远端」。
8. 续作时 `git fetch` 发现远端多了这两个提交 → ff（本地只有两份未跟踪交接，无冲突），逐行审了补丁：
   两道检查各自独立（符号链接用例里的文件 nlink 为 1，硬链接用例里路径无符号链接），与原三道不重叠。
   在 040a4a261 上用仓外 spec（原 30 个 + M31 拆符号链接检查 + M32 拆硬链接检查）重跑整套自检：32/32 KILLED。
   随后把 M31/M32 并进仓内 spec，并把测试文件里两处多出的空行收回两行。

## 决策表

| 决策 | 方案 | 评价 | 结果 |
|---|---|---|---|
| 新建还是扩现有件 | 扩 `run_extraction_mutations.py`（加子集判定、行输出） | 它的冻结 revision / 临时 worktree / 定义入库是工单 #53 套件语义的一部分，测试也钉在上面；改判据会改变已有套件读数的含义 | 否 |
| | 新建 `scripts/mutation_check.py`，docstring 写清分工 | 两条路线互补：证据级 vs 作者侧快速回路 | 选 |
| 在哪棵树上改 | 临时 detached worktree | 不碰调用方的树、并发安全；但本仓检出大、新树缺未跟踪的本地文件（基线可能新树红而原树绿），失败会留树（09-23 盘上 78 棵 detached 树的教训） | 否（证据级那条已经是这样） |
| | 原地改，前置「与 HEAD 一致」，原字节写回，写前与还原前各做一次 CAS（比较后再写） | 快；代价是同树的其他进程会短暂看到变异体 → docstring 写明「跑在你认领的 worktree 里」 | 选 |
| 怎么还原 | `git checkout --` | 还原到的是索引不是 HEAD，依赖索引状态；实现没提交就一起清掉 | 否 |
| | 内存原字节写回，再核字节 / HEAD blob / `git status` | 不依赖索引；因为前置保证与 HEAD 一致，崩溃时 `git checkout --` 仍能兜底 | 选 |
| 字节码 | `PYTHONPYCACHEPREFIX` 指向每轮新目录 | 隔离最彻底，但 stdlib 与三方包每轮全量重编译（重仓每轮多几秒到十几秒）；测试用精简 env 起的孙进程也不继承 | 否 |
| | 被变异模块的 `.pyc` 在基线前 / 写入后 / 还原后三处删（含各 tag 与 prefix 镜像），加 `PYTHONDONTWRITEBYTECODE=1` | 精确；三处各有只有它拦得住的用例 | 选 |
| 读 pytest 结果 | 解析 `FAILED x::y - msg` 终端行（ad-hoc 做法） | 参数化 id 可以带空格和 ` - `，正则会切错 | 否 |
| | `--junitxml` | classname / name 映射回 node id 有损 | 否 |
| | 注入临时 pytest 插件写 JSON（nodeid、结局、崩溃行、收集错、被变异文件是否被 import） | 精确、零依赖 | 选 |
| 什么算红 | 选中的测试里有失败（现有证据级判据） | 参数化只红一部分会被读成全红（09-14） | 否 |
| | 点名子集：每条点名测试都在 call 阶段 failed；setup error / skipped / 没跑 归 `wrong_reason` | 与 ad-hoc 一致，并把「红错原因」单列 | 选 |
| 基线 | 不跑（ad-hoc 做法） | 点名测试本来就红、或名字拼错，变异后的读数都不可归因 | 否 |
| | 跑：exit 0，点名测试唯一收集到且 passed | 多一轮 pytest | 选 |
| spec 有错 | 跳过那个 mutant 继续（ad-hoc 做法） | 一处拼错就混进一条「测空气」的读数 | 否 |
| | 任一前置不满足，整份一轮不跑，问题一次报全 | — | 选 |
| 测试收据 | 全程关 | 基线是真读数，关了就没有可复核证据（记忆：别为了不污染 latest 关收据） | 否 |
| | 只有变异轮 `FWP_TEST_RECEIPT=0` | 变异轮是故意改坏的树，收据只会把 latest.json 指到一张脏的红收据 | 选 |
| 目标文件身份（审查补） | 只查末级 `is_symlink` + status + HEAD blob（首版） | 父目录符号链接 / 仓外硬链接三道全过，写入落到仓外 | 否 |
| | 另拒 `path.resolve() != path` 与 `st_nlink != 1` | 本仓工作树文件不会合法地带硬链接或经符号链接目录，误拒面为零 | 选（702481725 / 040a4a261） |
| 审查补丁进来后怎么续 | 本地旧头直接提交再推 | 非 ff，要么被拒要么诱导强推，覆盖别人的修补 | 否 |
| | fetch → ff → 审补丁 → 新头重跑整套自检 | 多 ~12 min，但「32/32」绑定的是 PR 现在的头 | 选 |
| 全量 Python 谁跑 | 本分支头再跑一遍全量 | 审查会话的五 PR 联合预览已含 #965@040a4a261；之后的增量只有 yaml（没有测试读它）/ 测试 docstring / docs，第二份全量只是给满载的机器加 20 min | 否 |
| | 采信联合预览读数 + 证明增量不改行为 | 与 #961 合入时「漂移不相交就复核而非重跑」同一做法 | 选 |

## 验证与收据

- 定向：`tests/test_mutation_check.py` 首版 23 passed；040a4a261 上 25 passed（`.venv-workbench/bin/python`），ruff 通过。
- 自检首轮 @460ffe388：30/30 KILLED，汇总 `~/.finance-runtime/reviews/mutation-check-tool-0929/self-check-460ffe388.json`，
  日志 `logs-460ffe388/`。
- 自检复跑 @040a4a261（审查补丁之后）：仓外 spec `self-check-32.yaml`（= 仓内 30 个 + M31 + M32，M31/M32 与之后并进仓内
  spec 的逐字节相同）→ 32/32 KILLED，汇总 `self-check-040a4a261.json`，日志 `logs-040a4a261/`；运行期间工具与测试文件未动。
- 四叶：全仓 Python / 前端 / E2E / registry 由审查会话在五 PR 联合预览 83e88fb8433c 上跑（目录
  `~/.finance-runtime/reviews/closeout-five-pr-20260929/`）；本分支头上的 ruff、定向、registry 与增量证明见 PR #965 评论。
- **不成立的结论**：自检每轮 15–72 s 是 load 5–7 下的单次耗时，不是性能读数。

## 已知边界

- 写入 / 还原那几行的信号屏蔽没有确定性用例（窗口微秒级），属纵深防御；还原后核验失败分支同理（写回原字节后不会不等）。
- `imported=false` 只是提示：测试走子进程或 xdist worker 时，pytest 主进程看不到那次 import。
- 固定带 `-p no:cacheprovider`：用 `cache` fixture 的测试会报 fixture 不存在。
- `pytest_args` 给 `-x` / `--maxfail` 会让点名测试没跑到，读数是 `wrong_reason`（有提示）。

## 后续要做

1. PR #965 合入后，**经用户同意**：在 harness-reference 从 `gitea/main` 新开分支，改 `TOOLKIT.md` 三处
   （B 表「变异验证」行、「三条量具陷阱」3/4、H 表那行）并同步 vault 镜像 `50_agents/TOOLKIT.md`。
   顺序不能反：harness-reference 的 `check_refs.py` 按 finance `gitea/main` 核引用，未合入就加引用会报缺文件。
2. 以后的变异读数直接用本工具，spec 放 `~/.finance-runtime/reviews/<任务>/`。

## 不要做

- 不要把本工具改成默认跑临时 worktree：证据级路线已有 `run_extraction_mutations.py`，合成一条会把快速回路变慢、把证据级的冻结语义变弱。
- 不要为了省时间去掉基线轮：去掉后，拼错的点名和本来就红的测试都会被读成「不承重」或「承重」。
- 不要把 `PYTHONDONTWRITEBYTECODE` 当成字节码安全的保证：测试用精简 env 起的 python 照样写 `.pyc`，保证来自三处删除。
