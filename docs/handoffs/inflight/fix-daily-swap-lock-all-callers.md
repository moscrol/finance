# daily-swap-lock：QC 四轮 P1（公共换库路径竞态）+ 五轮 P2/基线身份

## 状态（先读这节）

基于 `data-source/hithink-rewrite-0911` 尖端 601db6dd 叠三刀：`ed0dce4c`（四轮）、
`7c89ca81`（五轮）+ 两份交接回写。**生产库仍未动**；这几刀修的是公共 staging
编排的换库契约，不是 hithink 数据本身。下一步：QC 六轮复审 → 用户授权 → 正式换库。
禁令沿用上游：勿凭隔离克隆成功绕过复审；勿扩大回填日期。

## 换库威胁模型（结论的成立条件，先读这条再读下面任何「已修复」）

**单一口径在 `market_feature_store/db.py` 顶部**（staging 段的注释块），这里只给指针
与结论。要点：

- **协同方**（走 `hold_run_mutex` / `hold_swap_lock` / duckdb 文件锁的写者，本仓全部
  写者都是）：「最终复查→[备份]→原子换名」全程在 SH 锁内，排他是**保证**。
- **非协同方**（不拿锁、直接动生产路径的 mv/cp/dd）：只能**检测，不能保证**。
  POSIX 没有「比对 inode 再换名」的原子原语——`os.replace` 无条件；macOS
  `renamex_np(RENAME_SWAP)` 只保证交换本身原子、照样跟冒名者换；`RENAME_EXCL` 只
  判存在与否，判不了「是不是我锁的那个 inode」。所以 `assert_same_target` 与
  `os.replace` 之间必然留一道窗口。
- 因此措辞纪律（写进 db.py，别再漂）：可以说「把整文件替换从**静默覆盖**变成
  **可检测的拒绝**」，**不能**说「已覆盖 / 已闭合 / 不再靠假设排除」。四轮的交接
  和 docstring 说过头了，五轮 QC 点得对，已全部改掉。

## 四轮 P1：换库锁只挂在备份分支上（ed0dce4c）

复现（在 601db6dd 干净工作树实测，非转述）：

```
AssertionError: 日更换库窗口丢写: 第三方已提交 17000，编排仍
rc=0 swapped=True，新库不含该行
```

根因：临界区只有 `pre_swap_backup=True` 才进 `hold_swap_lock`。日更默认 `False`，
走「最终守卫 → 无锁 `os.replace`」，守卫与使用之间是裸窗口（TOCTOU）。
`repair-stock-daily-hithink` CLI 因强制 `pre_swap_backup=True` 本就在锁内——
**修复类调用方走锁内 ≠ 公共换库链安全**，这是判定要分两层的原因。

落点：`source_exists` 时「锁内最终复查 →[可选备份]→ 原子换名」统一进
`hold_swap_lock`，与 `pre_swap_backup` 无关。日更锁窗只有 stat+rename 量级（毫秒），
SH 排写不排读，S7 判据 1 保住。

## 五轮三项（7c89ca81）

1. **P2 target 删除 → 异常逃逸（真 bug，已独立复现）**。`hold_swap_lock` 的
   `os.open` 在目标被删时抛裸 `FileNotFoundError`，逃出 `run_daily_full_staged`，
   违反 fail-closed 合同。改为转成 `SwapTargetReplacedError`（`DatabaseLockedError`
   子类），四处调用点统一收敛成 rc=2。
2. **基线身份没用上锁 yield 的那个（真 hole，不是风格问题）**。原先
   `source_identity` 从「克隆之后的路径 `stat()`」派生。克隆窗口内整文件替换会让
   staging 是 A 的副本、基线记成 B，末端两边自洽 → **旧码实测 rc=0 换库成功，把冒名
   者覆盖了**。现在：`source_identity = lock.identity`，克隆后 `assert_same_target`
   一次，版本基线改用 `lock.stat()`（fstat 被锁 inode，不再走路径）。为此
   `hold_swap_lock` 改 yield `SwapLock(dev, ino, fd)`，带 `.identity` / `.stat()`。
3. **P1 identity check → os.replace 非原子**：按 QC 给的二选一取**收窄声明**。
   理由见上面威胁模型——再加一次 stat 消不掉窗口，真闭合只能把所有发布方收编进同
   一把协调锁，那是改发布语义，不该夹带在本刀。处置：立威胁模型单一口径 + 删掉四轮
   的过强表述 + **把边界钉成测试**
   `test_identity_check_and_replace_are_not_atomic`（断言冒名者仍被覆盖，并写明闭合
   时必须同步改哪几处措辞）。未声明的残留就此变成已声明、已测试的边界。

## 已验证

- 新增回归共 7 条（`tests/test_market_feature_store_staging_swap.py`）。
- **红过再绿，且红在行为上**：
  - 四轮两条在 601db6dd 上红（丢写 / swapped=True 覆盖冒名者）；
  - 五轮两条在 0444823a 上红（`FileNotFoundError` 逃逸 @ db.py:415 / `rc=0` 覆盖冒名者）；
  - 边界测试在新旧两版都绿——它记录的是两版共有的边界，**不是**回归，这是有意的。
  - 编排级 mock 一律 `**kwargs` 透传，不写死新签名：写死了就在旧码上因 `TypeError`
    变红，看着红其实**没复现缺陷**。
- 定向三文件（staging_swap + repair_hithink + write_path_guard）：
  601db6dd 50 → 四轮 54 → 五轮 **57**，无回归。ruff 全过。
- 全量（7c89ca81，串行）：见下节「收据」。

## 收据

- 全量 @ `7c89ca81`（串行）：**9,502 passed / 1 failed / 77 skipped / 1 xfailed**，584s。
  9,499 + 3 条新增，数目对得上。
- 全量 @ `ed0dce4c`（串行）：9,499 passed / 1 failed / 77 skipped / 1 xfailed，358s。
- 两次唯一的红都是 `test_installed_codex_sandbox_denies_network_and_unix_socket`，
  在 601db6dd **干净对照树上单独跑同样红**（本机已知抖动）。本分支三刀只动
  `market_feature_store/` 与 `tests/test_market_feature_store_staging_swap.py`，
  与该测试无交集，故对照结论沿用；要新证据就在 gitea/main 干净树再跑一次它。
- 并发跑全量会多红一条 `test_real_conversation_round_trip_...`（另一棵树同时在跑全量
  时第三轮停在 pending，串行即绿）。下一个人跑全量前先看有没有别的树在跑。

## 未验证 / 已知边界

- 未换库；六轮复审未做。
- **identity check 与 os.replace 之间的窗口**：已声明、已测试、不闭合，见威胁模型。
- **裸字节直写**（cp/dd 写进同一个 inode）：身份不变，身份校验看不见，仍不在威胁模型。
- **首次建库路径（target 不存在）**：没有 inode 可锁，只剩「同步期间被第三方创建」
  一次性守卫。该路径下生产库本不存在、无既有数据可丢，同 target 并发轮次已被 run
  互斥锁排开。要闭合可用 `os.link`（存在即 `FileExistsError`）做「只在缺席时发布」，
  但那是第二条发布原语，需单独测试与复审。
- 锁窗内 `probe_no_active_writer` 未重跑：持 SH 即证明无 duckdb 写者（写者要 EX），
  重跑反而会被自己的锁拦下（同 `backup_before_swap(writer_lock_held=True)` 的理由）。

## 踩过的坑（可迁移）

- **「某个调用方在锁内」会被读成「这条链安全」。** 分层判定要写清分母：公共
  `run_daily_full_staged` 的全部调用方 vs 本次那一个 CLI。
- **结论要携带成立条件。** 四轮我写了「整文件替换已被身份校验覆盖」——机制对，
  话说过头，五轮被逐字打回。防复发的做法不是下次小心点，是**把措辞纪律写进代码**
  （db.py 顶部）并**把边界钉成测试**：口径漂了测试会先说话。
- **加了个能力却没在关键点用上，比没加更糟**——仪表显示「有身份校验」，基线那一处
  其实还在从路径 stat 派生。五轮第三项就是这个形状。加完新原语要 grep 每一个本该
  消费它的点。
- 回归测试的 mock 别写死新签名（否则旧码上是签名红不是缺陷红）。
- 全量红要先做**干净对照**再归因；并发跑全量会多红一条。
