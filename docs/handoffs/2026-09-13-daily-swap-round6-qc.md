# daily-swap 五轮修补的第六轮独立审查

## 范围与裁定

审查输入：`fix/daily-swap-lock-all-callers@c90036fa`；代码提交 `7c89ca81`，两者只差在途交接。独立树 `/tmp/daily-swap-qc-7c89ca81`，审查分支 `docs/qc-daily-swap-7c89ca81`。主检出树有大量他人改动，未使用其代码跑审查。施工分支与生产库均未修改。

**裁定：五轮的两个具体修复成立；接受既有库 identity-check→replace 的收窄策略，但不放行整条公共链与正式换库。P2 同类异常仍有两处逃逸；首次建库的已声明边界可吞掉普通 DuckDB 写者的已提交数据，应独立修复，而非继续以「无既有数据可丢」淡化。** 这是针对所审 revision 的结论，不宣称六轮全面安全。

## 已通过的内容

- `hold_swap_lock` 的 `os.open` 遇到目标缺失转成 `SwapTargetReplacedError`；所补测试命中这个确切窗口。
- 克隆基线取 `lock.identity`，版本取 `lock.stat()` / fstat，克隆后检查目标身份；所补克隆后换 inode 回归通过。
- 已有 target 的发布不再由 `pre_swap_backup` 决定是否持锁；带备份/不带备份定向测试都通过。
- 承認 `assert_same_target` 与 `os.replace` 不原子是正确的。POSIX 通用 rename 接口无按预期 inode 条件覆盖；多加 stat 不会消灭最后一个检查窗口。本审查不要求把外部任意 mv/cp 全部纳入本轮保障。

## 发现（按严重性）

### P1：首次建库可覆盖使用 DuckDB 锁的正常写者

位置：`market_feature_store/sync/sync_daily_full.py:748-755`；相关过强前提在 `market_feature_store/db.py:179-181` 和施工交接「首次建库路径」。

独立探针时序：target 初始不存在 → staging 子进程成功并完成全部检查 → 在真实 `os.replace` 前暂停 → 普通 `duckdb.connect(target)` 新建库、建表、插入 17000、close → 再 read_only 打开读回 17000，确认已经提交 → 恢复原换名。

实际：`rc=0 / swapped=True`；target 仅有 `fact_market_daily` 与 `ops_sync_run`，第三方表消失。没有手工 mv/cp，也没有绕过 DuckDB 文件锁。这是已声明但未闭合的既有边界，不伪称五轮新回归；新增证据否定的是「开始不存在，因此无数据可丢」这个理由。run mutex 只排同协议的 staging 编排，不排普通 DuckDB 新建库。

建议独立提交：首次发布用同目录 `os.link(staging, target)`，目标在发布时已存在就 `FileExistsError` → rc=2、保留目标与 staging；不要 fallback 到 replace。`os.link` 是给已完整写好的文件增加一个名字，目标名存在时原子拒绝，解决的是 absent→present，不解决既有对象按 inode 条件替换。

必须另测：无竞争成功且收据在；检查之后第三方创建并提交，拒绝且其行/字节保留；目标为普通文件/有效或悬空软链一律不覆盖；WAL（预写日志）前置条件继续成立；非 EEXIST 错误不得退回覆盖；link 成功但 staging.unlink 失败的返回语义与重启清理。**link 成功已经发布，不能因为清理失败返回「rc=2、生产未动」。** 不能把未测断电持久性混入「原子发布」的保证。

### P2：目标删除的结构化拒绝尚未全链覆盖

独立探针两条均红在真实 FileNotFoundError，不是 mock 签名不兼容：

1. `market_feature_store/db.py:242`：克隆已完成后，返回 copy 元信息仍执行 `source.stat().st_size`；在此删除目标，异常先于 `assert_same_target` 逃逸。`sync_daily_full.py:539` 只捕 DatabaseLockedError。
2. `market_feature_store/sync/sync_daily_full.py:673-675`：锁外 `target.exists()` 返回 True 后删文件，随后的裸 `target.stat()` 直接逃逸。

所以「os.open 的缺失已归一」成立，「target 删除已统一 rc=2」不成立。建议在适当的文件操作/编排边界归一目标消失，移除不必要的来源路径 stat（copy bytes 可取副本或被锁 fd），并检查两次 `probe_no_active_writer` 内部 exists→DuckDB open 的同类窗口。不要靠大范围 except Exception 吞掉损坏、权限、存储 IO 等不同故障。

验收：各注入窗口分别断言 rc=2、swapped=False、目标不被重建、staging 留证、reason 可定位；至少覆盖 clone 前/中/后和锁外预检，不只重复 os.open 那一点。

### 口径与交接（不是新增运行时漏洞）

- `test_identity_check_and_replace_are_not_atomic` 是行为边界证据，不是措辞门禁。只把注释改回「已闭合」，它仍然绿。故施工交接第 106 行「口径漂了测试会先说话」仍然过强。建议改成「为后续审查留下可重复的反例，措辞是否越界仍由评审判断」，不必为此堆关键词扫描门禁。
- 「协同方」应拆开写：同 target 的 staging 发布方靠 **run mutex 的 EX** 相互排斥；既有库的 DuckDB rw 写者靠 **target inode 的 SH 对 EX** 排斥。SH 不排斥另一个只持 SH 的发布方，这三个锁不能用斜杠写成任选其一都充分；首次创建也不受不存在的 target inode 锁保护。
- 「本仓所有写者都是协同方」不是安全的仓库全集断言：`scripts/db_delta_pull.py:70-128` 保留不取上述锁的 baseline restore/rollback，CLI 默认库路径为 `db/market_feature_store.duckdb`。`skills/market-overview/SKILL.md` 把这一跨机脚本标为保留备用，因此这里只证明代码存在，不声称它正在生产运行。用「当前受支持的 daily-full 发布链，外部/备用恢复入口须停用或另行协调」更准确。
- 施工 inflight 实测 **7,665 字节**，超过 3K。决定与证据应移到日期快照，inflight 只留指针、阻塞、下一步，避免自动注入截掉限制条件。

## 独立收据

解释器均 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

- 干净固定树：`pytest -q tests/test_market_feature_store_staging_swap.py tests/test_repair_hithink_stock_day.py tests/test_write_path_guard.py` → **57 passed / 10.07s**。
  原件：`~/.finance-runtime/test-receipts/20260913T072926Z-c90036fa.json`，dirty=false。
- `ruff check market_feature_store/db.py market_feature_store/sync/sync_daily_full.py tests/test_market_feature_store_staging_swap.py` → passed。
- 独立探针先在 `/tmp` 跑 **3 failed / 0.73s**；归档为 `scripts/review_daily_swap_races.py` 后再跑 **3 failed / 0.52s**，同一行为。脚本自身 Ruff passed。
  复现：`python -m pytest -q scripts/review_daily_swap_races.py --tb=short`。脚本是显式调用的审查证据，不冒充已绿的常规测试；修改代码后需按新边界迁成 `tests/` 常规回归，勿只以注入未触发当绿。
  日志：`~/.finance-runtime/reviews/daily-swap-7c89ca81/{round6.log,portable-probes.log}`。
- 本轮**未跑全量、未独立重跑 sandbox 红项、未重做 hithink 数据端到端对账**。用户报告的 9,502P/1F 不转写成本轮独立结论。基线同红可排查归因，不等于允许带红合并。

## 下一步 / 被否方案

| 选择 | 理由 |
|---|---|
| 保留既有库最后窗口的明确限制，不追加 stat 冒充闭合 | 当前无按 inode 条件 rename 原语；无授权不扩为全仓发布协议重构 |
| 先单独补 P2 全链拒绝，再独立补首次建库 no-clobber 发布 | 各有可复现行为与明确验收，避免数据保护问题藏进声明修订 |
| 否决「首次建库初始无数据所以可延期忽略」 | 普通写者在窗口中提交的数据同样需要保护 |
| 暂不合入、不授权生产换库 | 公共链阻断未清；既有全量红也未满足全绿合入门槛 |

收尾顺序：两个运行时修复及回归 → 口径/短交接修订 → 独立复审 → 干净候选 revision 的适用门禁全绿 → 用户另行确认合并/生产操作。禁止借当前审查结果扩大修复日期或直接执行生产命令。
