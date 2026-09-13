# daily-swap-lock：QC 四轮 P1（公共换库路径竞态）+ 目标身份校验

## 状态（先读这节）

基于 `data-source/hithink-rewrite-0911` 尖端 601db6dd 叠一刀 `ed0dce4c`。
**生产库仍未动**；本刀修的是 QC 四轮点出的公共 staging 编排竞态，不是 hithink
数据本身。下一步：QC 五轮复审 → 用户授权 → 正式换库。
禁令沿用上游：勿凭隔离克隆成功绕过复审；勿扩大回填日期。

## 四轮 P1：换库锁只挂在备份分支上

复现（在 601db6dd 干净工作树实测，非转述 QC）：

```
AssertionError: 日更换库窗口丢写: 第三方已提交 17000，编排仍
rc=0 swapped=True，新库不含该行
assert not (True and True and 0 == 0)
```

根因：临界区只有 `pre_swap_backup=True` 才进 `hold_swap_lock`。日更默认
`pre_swap_backup=False`，走「最终守卫 → 无锁 `os.replace`」，守卫与使用之间是
裸窗口（TOCTOU）。与二轮 backup→swap 竞态同形，只是挪到了不带备份的公共路径。
`repair-stock-daily-hithink` CLI 因强制 `pre_swap_backup=True` 本就在锁内——
**修复类调用方走锁内 ≠ 公共换库链安全**，这是四轮判定分两层的原因。

## 落点（ed0dce4c）

1. `sync_daily_full`：`source_exists` 时「锁内最终复查 →[可选备份]→ 原子换名」
   统一进 `hold_swap_lock`，**与 `pre_swap_backup` 无关**。日更锁窗只有
   stat+rename 量级（毫秒），SH 排写不排读，不重新饿死只读读者（S7 判据 1）。
2. 目标身份（三轮报告要求、四轮重提的 inode/path identity）：
   - `db.file_identity` / `db.assert_same_target` / `SwapTargetReplacedError`；
   - `hold_swap_lock` 拿锁瞬间自查路径身份，并 yield 被锁 inode 的 `(dev, ino)`；
   - `atomic_swap_into_place` 新增 `expect_identity`，`os.replace` 前最后一刻复查；
   - 编排另记克隆窗口内的 `source_identity`，末端覆盖的必须是「我克隆的那个 inode」。
   三处（锁 fd / 检查路径 / 换名目标）确认同一身份，整文件替换（mv/cp 换 inode）
   不再靠「不在威胁模型」排除。**mtime/size 单独挡不住这一类**——cp -c 与
   shutil.copy2 会把 mtime 一并带过去，造版本读数完全一致的新 inode 是可行的。
3. `SwapTargetReplacedError` 继承 `DatabaseLockedError`：既有 `except` 把它变成
   明确 rc=2 拒绝，不让异常逃逸出编排（三轮 P2 已定口径）。

## 已验证

- 新增回归 4 条（`tests/test_market_feature_store_staging_swap.py`）：
  不带备份的写者竞态 / 目标被换 inode 拒绝换名 / db 层身份单测（对不上·目标消失·
  对得上）/ `hold_swap_lock` 身份 yield。
- **红过再绿**：两条编排级测试用 `**kwargs` 透传而非写死 `expect_identity`，
  故在 601db6dd 上因**行为**变红（丢写 / swapped=True 覆盖冒名者），不是因签名
  变红——实测两条均红，修复后 31 passed。
- 定向三文件（staging_swap + repair_hithink + write_path_guard）：601db6dd 50 →
  本刀 54（+4），无回归。
- 全量：9,498 passed / 2 failed / 77 skipped。两条红都不在 `market_feature_store`：
  - `test_installed_codex_sandbox_denies_network_and_unix_socket`——**在 601db6dd
    干净对照树上同样红**（本机已知抖动，见记忆卡），与本刀无关；
  - `test_real_conversation_round_trip_...`——全量跑时另有一棵树在并发跑全量
    （pid 43353），第三轮停在 pending；单跑本树绿，且该文件对
    `market_feature_store`/换库代码零引用。
- ruff：`market_feature_store` + 改动测试文件全过。

## 未验证 / 已知边界

- 未换库；五轮复审未做。
- **首次建库路径（target 不存在）未闭合**：没有 inode 可锁，只剩「同步期间被第三方
  创建」这一次性守卫，守卫通过后才被创建的窗口仍在。该路径下生产库本不存在、无既有
  数据可丢，同 target 并发轮次已被 run 互斥锁排开——已在码内标注，若要闭合可用
  `os.link`（存在即 `FileExistsError`）做「只在缺席时发布」，但那是另一条发布原语，
  需单独测试与复审。
- 身份校验挡整文件替换，**不挡裸字节直写**（cp/dd 写进同一个 inode）——那仍不在
  威胁模型，理由不变：本仓写者全走 duckdb。
- 锁窗内 `probe_no_active_writer` 未重跑：持 SH 即证明无 duckdb 写者（写者要 EX），
  重跑反而会被自己的锁拦下（见 `backup_before_swap(writer_lock_held=True)` 的同款理由）。

## 踩过的坑

- **「某个调用方在锁内」会被读成「这条链安全」。** 分层判定要写清分母：公共
  `run_daily_full_staged` 的全部调用方 vs 本次那一个 CLI。
- 回归测试的 mock 别写死新签名：写死了就在旧代码上因 `TypeError` 变红，看着是红的，
  其实**没复现缺陷**。用 `**kwargs` 透传才能让「红」证明行为而不是证明签名。
- 全量红要先做**干净对照**再归因：本轮 2 红，一条在对照树同样红（环境），一条是
  并发跑全量的负载抖动——都不是本刀。别把「另一棵树在跑」当背景噪声忽略。
