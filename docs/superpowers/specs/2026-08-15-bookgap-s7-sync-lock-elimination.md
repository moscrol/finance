# S7 · 行情同步写锁消除：staging 写 + 原子换库

- 索引：`2026-08-15-bookgap-index.md` · 靶：批 #2 塌方根因（2026-08-15 晨实测） · 仓：finance · 优先级 **P0**
- 并行安全：`market_feature_store/` 独立缝，立即可开工

## 1. 背景（证据，见母本「检阅方勘探」段）

- 2026-08-15 11:0x–11:16:29，日频同步管道持 `market_feature_store.duckdb`
  写锁全程（先拉远端数据后落库，锁窗 ≥14 分钟），期间生产 8792 的
  `finance_query` 只读短连接**秒败**（5–12ms `tool_exception`），
  批 #2 的 A1–A8 全灭。库 3.4G、23 表写入指纹齐。
- DuckDB 锁语义：一个进程 rw 打开期间，其他进程 read_only 连接直接拒。
  只要「长事务同步」与「生产读」共库，这个碰撞就会复发——探针（R-12）
  只能**检测**，本 spec 负责**消除**。
- 数据管道唯一写入口已收敛：`python3 -m market_feature_store.cli daily-full`
  （agent-memory 项目档案）；`db.py` 支持 env 覆盖 DB 路径——改造有抓手。

## 2. 目标 / 非目标

- 目标：同步全程不持有生产库写锁。方案 A（首选）：写 staging 副本 +
  `os.replace` 原子换名；方案 B（若 A 因 3.4G 拷贝成本被否）：远端拉取
  阶段不开库，所有网络 IO 完成后才开写事务，把锁窗从 ~14min 压到秒级。
  执行 agent 先测拷贝耗时再定 A/B，理由写进 PR。
- 目标：换库瞬间的读者安全：正在打开的旧句柄读旧文件（POSIX rename
  语义天然支持），新连接读新文件；换名后写一条 `ops_sync_run` 收据行
  （开始/结束/行数/耗时），R-12 探针与人都能查「最近一次同步何时结束」。
- 非目标：不改表结构与同步内容本身；不改生产读路径
  （`finance_query.py` 一行都不动——那是 runtime 邻缝）；不做增量同步。

## 3. 改动面

| 落点 | 内容 |
|---|---|
| `market_feature_store/db.py` | staging 路径推导 + 原子换名工具函数 |
| `market_feature_store/cli.py` | `daily-full` 流程改为「网络拉取（不开库）→ staging 写 → 校验 → 原子换名 → 收据」 |
| 同包新表 `ops_sync_run` | 同步收据（append-only） |
| 测试 | staging 换名原子性（换名前 crash 不留半成品在生产路径）、换名期间并发 read_only 连接不失败（起子进程实测）、收据行完整 |

## 4. 验收判据（预注册）

1. 并发实测：同步进行中，另一进程每秒发 read_only 连接+trivial 查询，
   **零失败**（对照：现状必失败——先跑现状臂留档）。
2. crash 安全：staging 阶段 kill -9，生产库文件字节不变、可正常打开。
3. 换名后 `ops_sync_run` 有收据行；`db/market_feature_store.duckdb`
   mtime 变化窗口 <5s（对照现状 ~14min 锁窗）。
4. `daily-full` 端到端跑一次真同步（挑非交易时段），产物表行数与
   现状口径一致（抽 3 表对 count）。

## 5. 风险

- 磁盘峰值 2×3.4G：确认卷余量（`df -h`）后再选方案 A；不够就 B。
- 换名瞬间若有进程恰好持旧句柄做长查询：旧句柄读旧 inode，安全；
  但旧文件空间在句柄释放前不归还——收据里记 pid 便于排查。
