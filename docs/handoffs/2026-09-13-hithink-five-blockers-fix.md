# 2026-09-13 同花顺 09-11 修复：QC 五项阻断修补决策留痕

固定范围 `97dbc210...8ac5a788`（施工分支 data-source/hithink-rewrite-0911）。
QC 阻断清单与证据：`~/.finance-runtime/reviews/hithink-cd7f6fa9-20260913/review.md`。
修后反向证据：`~/.finance-runtime/db-repair/hithink-20260911/verify-after-fixes/`。

## 背景

cd7f6fa9 的数据对账成立但 QC 裁定五项阻断（G1/S1/S2/S3/S4）未修不得换库。
本轮逐项修补，生产库全程只读，全部验证在隔离克隆与夹具上完成。

## 按发现顺序

1. **G1（闸门）**：旧实现用包所在目录推导 canonical 生产路径。从独立 worktree
   跑代码时主检出树的真生产库被误判为普通副本，`--child --db <真库>` 直达写入
   函数（QC 探针实证）。修法：候选集 = 包相对 ∪ git common-dir 主树 ∪ env 钉
   （`MARKET_FEATURE_STORE_PRODUCTION_DB`，调用期读 env——import 期捕获正是
   staging 编排 docstring 点名的反模式）。git 解析失败退化为包相对 ∪ env，
   不会把非生产路径误判成生产。
2. **S3（断言）**：QC 探针给 302132 塞每股 10 元现金事件，旧版仍 ok=true，
   昨收 64.35→54.35。根因：除息名单断言与逐字段 diff 都只覆盖共同行，新增票
   两侧都不在。修法：RepairSpec 钉三前提（当日无事件 / dump 有昨日 bar /
   open…volume 逐字段预期），任一破即拒跑。预期值取 dump 实值，QC 复核一致。
3. **S1（消费契约）**：修复把 5,547 行写成 `hithink:daily-k-10d`，拼接白名单
   只认五家 → 修后克隆可拼接板块 403→0。修法：白名单接 `hithink`（判据是
   「独立外部供应商」，同花顺官方 dump 满足；值经 QC 逐值核验）。
   回归：`_today_values` 接受 hithink 行、fallback 自派生源仍被拒；
   同条件对照修后克隆恢复 403/403、接受行 3→5,550。
4. **S2（派生清单）**：QC 实测 `_build_stock` 也从主表派生（600176 的 10 日
   avg_amount 93.1063→93.1062），只重算 technical 漏 window；且 302132 修后
   仅 11 行历史，technical 需 26 条窗口记录 → 0 行，「补一行」承诺兑不了现。

   **本轮最大的非显然决策：派生重算收进 staging 子进程，与主表修复同一次
   原子换库交付。**
   - 被否方案 A（QC 原计划的换库后补跑）：换库后直写生产补派生——又会撞上
     G1 同形的直写问题，且换库后到补跑之间库里是「主表已修、派生旧值」的
     中间态，读者会读到自相矛盾的库。
   - 被否方案 B（单独再跑一轮 staging 换库）：两次换名双倍风险窗口，无收益。
   - 选中的形态：staging 克隆是全量库，compute_features 的全部输入在场；
     日更管道本来就在 staging 里跑 compute-features，同一形态。
   - 302132 处置：QC 允许二选一（另立授权回填 / 保留缺口置缺），选置缺——
     本次授权是「只改 09-11」，历史回填需单独授权并验证连续性。window 会把
     缺口两侧拼成「连续」5/10 日特征（起点拉回六月），必须删除并声明；
     technical 天然 0 行。断言：两表当日 302132 零行，否则拒跑。
5. **S4（备份）**：os.replace 不留旧库；已修后的干跑克隆不能充当换库前备份。
   修法：`db.backup_before_swap`（写者探针→clonefile→sha256→只读开库验证→
   带恢复步骤的 receipt.json），接在第三方写者守卫之后、换名之前——备份拷的
   是守卫验过的待换库状态。修复 CLI 强制开启、不换名不备份；日更默认关
   （每晚 3.6G 级文件会打爆磁盘）。

## 验证与收据

- 定向 41 条（QC 基线 27 + 新增 14）全过；全量 9,485 passed/77 skipped/1 xfailed，
  干净树收据 `~/.finance-runtime/test-receipts/20260912T194535Z-8ac5a788.json`
  （check_test_receipt 可采信）；ruff 全仓过。
- 反向证据（verify-after-fixes/）：
  - G1 探针：worktree 代码 + `--child --db 真库` → rc=2，写入函数未到达；
    候选集含主树真库路径。
  - S3 探针：合成现金事件 → RepairRefused「新增票当日存在除权事件」。
  - S1 对照：修后克隆 stitched 403/403（修前 0），today_values 5,550。
  - S2+S4 端到端（隔离克隆跑完整父进程）：fact 5,553 行；technical 5,529 /
    window 22,115 重算（22,117 staged − 302132 的 2 行 = 22,115，自洽）；
    302132 两表当日 0 行；600176 10 日 avg_amount=93.1062；备份指纹 ==
    生产库当前 sha256（备份即换库前状态）；收据 kind=repair-stock-daily-hithink。
- 生产库 inode/mtime/size 全程不变（探针与端到端都在克隆上）。

## 后续要做 / 不要做

- 要做：QC 复审五项 → 用户授权 → 正式换库（命令见 repair-plan.md，现在一次
  交付主表+派生+备份）→ 换库后核对收据 derived 段 → 并跑表补齐（拍板项 3）。
- 不要做：凭隔离克隆成功绕过复审；扩大历史回填日期范围；把 302132 置缺
  当作「补一行」兑现；把日更也开 pre_swap_backup（磁盘）。

## 边界

- G1 的跨克隆形态（独立 clone 代码写主仓真库）靠 env 钉覆盖，单测验证了
  解析逻辑，真机跨克隆未实测——主仓场景（worktree 家族）已实测。
- n=1 的端到端克隆运行，不快慢结论；只断言结构性事实。

---

## 复审二轮（2026-09-13 晚，9d73f01a）：竞态与遗留状态

QC 在 8ac5a788 上复审：G1/S1/S2/S3 通过；S4 不通过 + 新增一项 P1。

6. **备份→换名竞态**（backup-race.json）：备份完成到 os.replace 之间第三方
   写者提交一行，换名静默覆盖之，备份只对应写入前状态。QC 明言「备份后再
   检查一次」仍非严格 TOCTOU 闭环——要闭合窗口必须排他协调锁。
   **关键先验实验**：duckdb 单写者锁在 macOS 上与 flock 同命名空间（双向
   实测：我方 LOCK_EX 下 duckdb rw/ro 打开均「Could not set lock」；duckdb
   rw 持锁时我方 LOCK_EX|NB 得 EWOULDBLOCK）。因此 `hold_swap_lock` 直接对
   target inode 持 LOCK_EX|NB 即与全部 duckdb 写者互斥，且不产生 WAL（优于
   自己开 rw 连接当锁——那会让 atomic_swap 的 target 无 WAL 断言自爆）。
   被否方案：备份后再 stat 复查（两次检查之间仍有窗）；自己持 duckdb rw
   连接当锁（WAL 副作用 + 读探针全灭）。选中的形态：锁内「stat 复查 →
   备份 → 换名」，拿不到锁 rc=2。日更不带备份、不进锁（每晚锁几秒会撞
   读者；且其窗口本来只有守卫→换名的微秒级，QC 未异议）。
7. **status 遗留污染**（stale-status-min.json）：父进程固定读
   `<staging>.status.json`，旧文件不清理、无本轮身份校验；子进程 rc=1 不写
   status 时父进程读旧成功 JSON 照样换库。修法双保险：开工即删 +
   run_id 绑定（父 env MARKET_FEATURE_STORE_RUN_ID → 子写 status → 父校验）。
   注意现状语义保留：rc=1 但 status 是本轮真产物（有 run_id）仍按
   「失败步不回滚」换库——QC 未异议，行为不变。
   测试教训：测试里所有手写 status 的注入子进程都要跟着契约升级
   （两处 inline JSON 漏写 run_id 导致回归红）；验证锁占用的夹具要用
   LOCK_SH（不挡我方只读探针与克隆，只让 EX 失败），LOCK_EX 会先把自己
   的开工闸挡死。

反向证据 `verify-after-fixes/verify-round2.json`；全量 9,490 passed
干净树收据对应 9d73f01a。

---

## 复审三轮（2026-09-13 深夜，350b076d）：继承自旧编排的两个竞态

QC 在 9d73f01a 上沿全链审查，又复现两项能误换库的 P1（根因继承自旧
staging 编排，非本轮回归，但修复实际经过这些路径）+ 一项 P2。

8. **克隆-基线竞态**：旧代码先克隆、再把来源最新 stat 认领为基线，两步
   之间的写入会被记成「副本基线」——末端守卫比对的是错基线，换入旧副本，
   静默撤销已提交写入（QC 复现：克隆 10000→提交 17000→换入 10000）。
   修法：基线 stat 与克隆收进同一把换库锁窗口；形态基线改从克隆体自身
   读取（基线=副本版本，比读活库更准）。
   **关键设计变更：换库锁从 LOCK_EX 降为 LOCK_SH。** 起因是基线窗口要罩住
   克隆，而克隆内部有 read_only 探针（EX 会把它打死）；三向实验证明 SH
   排写不排读（我方 SH 下 duckdb rw 失败/ro 照常；duckdb rw 在场我方 SH
   拿不到；读者不挡我方 SH），且末端窗口用 SH 同样排写、还保住了判据 1
   的读者零失败——EX 其实是过度排他。
9. **两轮共用 staging**：A 校验完未换名，B 开工把 A 的 staging 当旧残留
   清掉重建，B 失败后 A 发布的是 B 的半成品（连 A 写进 staging 的收据
   一起没）。修法按 QC 首选：`hold_run_mutex` 运行互斥锁——同一 target
   一份，任何清理之前取得、覆盖本轮全生命周期；锁在独立 `.run.lock`
   文件上（不碰 duckdb 锁命名空间，读写无感），进程死亡 OS 释放，锁文件
   常驻不删（删锁文件本身有竞态）。被否方案（每轮唯一 staging + 发布
   竞争保护）留在 QC 报告里；互斥锁形态更简单且顺带让「清理残留」变得
   安全可判。
10. **P2 损坏 status**：`'{'`/`'[1]'` 原样抛 JSONDecodeError/AttributeError
    逃逸；改为统一 rc=2 明确拒绝（解析失败 / 不是 JSON 对象）。

反向证据 `verify-after-fixes/verify-round3.json`；全量 9,496 passed
干净树收据对应 350b076d。可迁移点（QC 原话，已进 corrections 候选）：
状态属于本轮，不代表最终发布的文件仍属于本轮——校验与使用之间，
产物所有权也必须受保护。
