# daily-swap 六轮：P2 全链归一 + P1 首次建库 no-clobber（日期快照）

分支 `fix/daily-swap-lock-all-callers`。本页是背景与理由的长文；在途交接
`docs/handoffs/inflight/fix-daily-swap-lock-all-callers.md` 只留指针、阻塞与下一步
（≤3K，SessionStart 会自动注入，超了限制条件会被截断——五轮那版 7,665 字节就是
被审查方点名的那个形状）。

## 这一轮的输入

第六轮独立审查（`docs/qc-daily-swap-7c89ca81` @ `e15379f5`，独立干净树
`/tmp/daily-swap-qc-7c89ca81`，报告 `docs/handoffs/2026-09-13-daily-swap-round6-qc.md`，
探针 `scripts/review_daily_swap_races.py`）裁定：

- 五轮的两个具体修复成立；既有库最后窗口按「收窄声明」处理可接受。
- **但整条公共换库链不放行**：P2 同类异常还有两处逃逸；首次建库的已声明边界能
  吞掉普通 DuckDB 写者**已提交**的数据。
- 另有三条口径/交接问题。

开工前先在施工树独立复现探针三条红（`shutil.py:260` / `pathlib.py:840` 的真
`FileNotFoundError`，以及 bootstrap 丢写），没有拿审查方的结论当自己的证据。

## P2（941373b8）：目标删除的结构化拒绝，从一点扩到整条链

五轮只归一了 `hold_swap_lock` 的 `os.open` 一处。逐窗口收口：

| 窗口 | 旧行为 | 处置 |
|---|---|---|
| 克隆**后** `clone_to_staging` 末尾 `source.stat()` | 裸 `FileNotFoundError` 逃逸 | **整个删掉**，`bytes` 改从副本量 |
| 克隆**中**（`cp` 失败→`shutil.copy2` 也失败、WAL 拷贝同理） | 裸 `FileNotFoundError` 逃逸 | 转 `SwapTargetReplacedError` |
| `probe_no_active_writer` 的 `exists()`→`connect()` | 非锁冲突 `IOException` 原样抛 | 复查路径确已消失才转换 |
| 锁外预检 `exists()` + 裸 `stat()` | 两段之间被删 → 逃逸 | 合成一次 `stat()`，窗口消失 |
| `backup_before_swap` 的裸 `stat()`（同族） | 已 fail closed，但 reason 只剩 Errno 2 | 补结构化理由 |

两个刻意的选择：

1. **收据字节数从副本量，不回头 stat 来源。** 克隆体与来源逐字节相同，取值等价；
   而那次 stat 纯粹为了填一个数字，却多开一道窗口。少一次 syscall 就少一个窗口，
   这比「给那次 stat 加 try」更彻底——**能删掉的窗口不要改成能处理的窗口**。
2. **转换面收窄到「复查确认路径确已消失」。** 损坏库 read_only 打开抛的是**同一个**
   `duckdb.IOException`（本机 1.5.4 实测）。用一层宽 `except` 判定的话，损坏、权限、
   存储故障都会被报成「目标被第三方替换」，把运维引向错误方向。测试
   `test_probe_no_active_writer_does_not_mask_other_io_errors` 钉的就是这个收窄面——
   它在修复前后都绿，**它不是缺陷回归，是防止将来把判据放宽**。

编排侧「基线窗口拿锁失败」放宽成「基线窗口失败」：这条出口不再只有拿锁一种来源。
连带发现既有 `test_swap_lock_contention` 的桩消息是 `"simulated contention"`（不含
「锁」字），那条 `assert "锁" in reason` 实际测的是编排前缀而不是锁竞争本身；桩已
补成真 `hold_swap_lock` 的措辞。

## P1（650c3d37）：首次建库不能再用 os.replace

旧理由是「生产库本就不存在、无既有数据可丢」。**这个理由不成立**：target 缺席时
一个普通 `duckdb.connect(target)` 写者可以建库、插入、提交、关闭（全程持 DuckDB
自己的 EX 锁，不是手工 mv/cp，也没绕过任何机制），`os.replace` 照样把它已提交的
数据静默覆盖，编排还报 rc=0 / swapped=True。run mutex 只排同协议的 staging 编排。

改用同目录 `os.link`：EEXIST 判定与建名字是**同一个 syscall**，没有 check-then-act
窗口。本机实测（Darwin 25.4 / APFS，2026-09-13）：

| 目标形态 | `os.link` 结果 |
|---|---|
| 普通文件 / 目录 | `FileExistsError` |
| 指向存在文件的软链 | `FileExistsError`（**不跟随**，不会顺着软链把库写到别处） |
| 悬空软链 | `FileExistsError` |
| 缺席 | 成功，两个名字同 inode |

悬空软链那一格值得单独说：它的 `exists()` 是 `False`，所以能一路穿过「同步期间被
第三方创建」那道守卫走到发布，旧码会把软链本身换成库文件。

三个刻意的选择：

- **失败不回退 `os.replace`。** 回退等于把刚拒绝掉的覆盖又做一遍。代价是不支持硬
  链接的文件系统会 fail closed（本仓 `db/` 在 APFS 上），这是选定的方向。
- **link 成功 = 已发布。** 此后删 staging 名字只是清理（两个名字同一个 inode），
  清理失败不改变「已发布」这个事实：`publish_new_into_place` 在 link 之后不再抛任何
  异常，编排也不得报成「未换库、生产未动」。残留名字由下一轮 `remove_stale_staging`
  收掉，删名不伤数据。
- **不声称换库整条链已原子。** 它只关掉 absent→present 这一类；既有目标按 inode
  条件替换仍无 POSIX 原语。未测的断电持久性也不混进「原子发布」的保证。

## 口径修订（本提交）

审查方三条，逐条独立核实后照改：

1. **三把锁拆开写，不用斜杠连成「任选其一都充分」。** run mutex 是 `<db>.run.lock`
   上的 EX，排同协议发布方；swap lock 是 target inode 上的 SH，排 DuckDB 写者（他们
   要 EX）但**不排另一个只持 SH 的发布方**；duckdb 文件锁是第 2 条能生效的原因。
   首次建库同时在 1 的排他面之外与 2 的保护之外，所以那条路径靠 link 不靠锁。
2. **删掉「本仓所有写者都是协同方」。** 这是证不出来的仓库全集断言。读码确认
   `scripts/db_delta_pull.py::restore_baseline` 保留着一条不取任何上述锁的
   `os.replace` 恢复路径；`skills/market-overview/SKILL.md` 把它标为「将来再起第二台
   机器可复用」，所以只证明**代码在**，不声称它正在生产运行。改用「当前受支持的
   daily-full 发布链；外部/备用恢复入口须停用或另行协调」。
3. **「口径漂了测试会先说话」说过头了。** `test_identity_check_and_replace_are_not_atomic`
   是行为边界证据，不是措辞门禁——把注释改回「已闭合」它照样绿。改成「为后续审查
   留下可重复的反例；措辞是否越界仍由评审判断」。也不为此堆关键词扫描门禁。

## 收据

解释器一律 `.venv-workbench/bin/python`。施工树
`.claude/worktrees/daily-swap-race-condition-d0f557`。

- 定向三文件（staging_swap + repair_hithink + write_path_guard）：
  57（五轮）→ **62**（P2）→ **71**（P1），无回归。ruff 全过。
- **反向证伪（每一轮都做）**：把源码退回上一提交、只留新测试——
  - P2 五条里 4 条真红（`shutil.py:260`、`pathlib.py:840` 的 `FileNotFoundError`、
    duckdb `IOException`），第 5 条两边绿（钉收窄面，非缺陷）。
  - P1 九红。其中 `test_bootstrap_refuses_target_created_after_final_check` 与
    `test_bootstrap_refuses_dangling_symlink_target` **不引用任何新符号**，红在行为
    本身（`rc=0` 而非 2）——即旧码确实发布了、吞掉第三方数据、换掉悬空软链。
    其余七条红在符号不存在，属结构性红，单独记账不混报。
- 审查方 `/tmp` 探针：`[_run_daily_full_staged_locked]` 转绿；另两条现以「注入未触达
  边界」失败——`source.stat()` 已删、bootstrap 不再走 `os.replace`，属**探针失效而非
  结论反转**（审查方预告过要迁边界）。等价覆盖已迁进 `tests/`，其中 bootstrap 那条
  同时挂在 `os.replace` 与 `os.link` 上，对新旧两种发布方式都触达。
- **全量 @ `a42cbc5c`（干净树，`-p no:randomly`）：9,517 passed / 0 failed /
  77 skipped / 1 xfailed，445.49s，exit 0。** `ruff check .` 全仓通过。
  对账：9,502P + 1F（@7c89ca81）+ 本轮新增 14 条 = 9,517，数目严丝合缝。
  新增 14 条的构成：P2 五条（含一条两参数化）+ P1 九条（含一条四参数化）。
- 四~五轮一直红的 `test_installed_codex_sandbox_denies_network_and_unix_socket`
  **本轮绿**（全量内与单独跑都绿）。这与本机已知抖动一致（同日红过又绿过），
  **不宣称它被修好了**；下一轮跑全量若它再红，按抖动处理前仍要先做干净对照。
- **未做数据端到端对账**——本刀不动数据，只动换库契约。

### 合并预检（a42cbc5c vs gitea/main）

- 落后 main **35** 个提交，领先 **17** 个。这 17 个是一条连续的线：hithink 09-11
  canonical 个股日线重建（`cd7f6fa9`）+ 六轮换库契约加固，不是两个话题拼在一起。
  上游 `data-source/hithink-rewrite-0911` 尚未合入任何远端分支，所以合这条分支等于
  同时合入整个 hithink 重建——审查面比本轮三个提交大得多，值得在授权时说清。
- **三个源文件（`db.py` / `sync_daily_full.py` / 换库测试）在 main 那侧零漂移**
  （`git log gitea/main ^a42cbc5c -- <三个路径>` 为空），所以这份门禁绿可以外推到
  合并之后，不是只对快照成立。
- `git merge-tree` 模拟：**唯一冲突是 `.claude/lessons_learned.md`**，双方都在文件末尾
  追加（main 侧是 `9e1d730b` 的「cwd 陷阱入 lessons」）。属热文件的 append-vs-append，
  保留两段即可，不是语义冲突。

## 被否方案

| 选择 | 理由 |
|---|---|
| 给 `clone_to_staging` 末尾那次 stat 加 try，而不是删掉它 | 能删掉的窗口不要改成能处理的窗口；那个数从副本取等价 |
| 用一层 `except Exception` 统一转「目标被替换」 | 会把损坏/权限/存储故障混进去，运维查错方向 |
| `os.link` 失败时回退 `os.replace` | 等于把刚拒绝掉的覆盖又做一遍 |
| 首次建库继续以「无既有数据可丢」延期 | 普通写者在窗口中提交的数据同样需要保护 |
| 为措辞加关键词扫描门禁 | 审查方明确不要求；测试只作反例，措辞由评审判断 |
| 借本轮扩大修复日期或直接执行生产换库 | 公共链未放行，用户未授权 |

## 本轮未处理（留给复审裁定，不夹带修）

`clone_to_staging` 里非「来源消失」类的 IO 故障（磁盘满、权限）仍以裸 `OSError`
逃出编排，CLI 会看到 traceback 而不是 `BLOCKED | 生产库未动`。这是**修改前就如此、
本轮未改变**的行为：`_copy_or_reject_vanished` 只在复查确认来源已消失时转换，其余
原样抛。它与 P2 同属「fail-closed 合同」的家族，但不在审查方本轮的要求内，且把它
一并收进来会让本轮的审查面变糊。要不要修、修成哪一类出口码，留给复审裁定。

## 下一步

P2（941373b8）、P1（650c3d37）、口径（a42cbc5c）三个独立提交已在分支上，门禁已全绿
→ **待独立复审** → 用户另行确认合并与生产换库。禁止凭本轮结果扩大修复日期或直接跑
生产命令。
