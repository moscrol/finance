# 行情快照 Provider Chain 运行手册

## 目标与边界

canonical 同步顺序为“目标日 DuckDB → 目标日 AkShare → 最近完整 DuckDB”。AkShare
只负责在内部事实尚未落地时补最新日，不替代上游 `daily-full` 等更完整数据源。
同步器遵守三条数据质量规则：

- 已有 `daily-full` 等本链之外的 `quality=complete` 日快照时，不再发请求，也不覆盖文件。
- AkShare 所有输出先落临时目录；全市场 spot 缺失时产生的 partial 只进入 attempt
  telemetry，不写 canonical daily/latest/meta。
- 目标日外部数据不可用时，允许发布最近完整 DuckDB 日并标记
  `freshness=historical`；三层都失败才返回 `1`。只有 complete 返回 `0`。

运行时采用独立 venv，而不是把 AkShare 装进 Workbench API venv。这样可以隔离
AkShare 较快的依赖更新节奏，避免 pandas、requests 等传递依赖影响 API 服务。
替代方案是共用 `.venv-workbench`，部署更少一步，但依赖冲突和回滚半径更大，
因此不采用。

## 首次安装（main 合并并同步 runtime 后）

以下步骤只在 `/Users/a77/finance-workspace-runtime` 已切到目标 main 后执行：

```bash
cd /Users/a77/finance-workspace-runtime
./scripts/bootstrap_akshare_snapshot_runtime.sh
mkdir -p /Users/a77/.local/share/finance-workbench
cp intelligence/data/com.a77.finance-akshare-snapshot.plist \
  /Users/a77/Library/LaunchAgents/com.a77.finance-akshare-snapshot.plist
launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.a77.finance-akshare-snapshot.plist
```

LaunchAgent 在周一至周五 16:15 执行 `run_market_snapshot.sh`。DuckDB provider 使用
`.venv-workbench`，AkShare provider 使用独立 venv；交易日与数据质量由 provider
chain 兜底，休市日或端点无数据不会伪装成 complete。

## 代理策略

AkShare 的东方财富公开端点对透明代理较敏感，runner 默认
`AKSHARE_PROXY_MODE=direct`，清除常见 proxy 环境变量并设置 `NO_PROXY=*`。后者
很重要：Python `requests` 在 macOS 上还会读取 `scutil` 系统代理，单纯 unset 环境
变量并不等于直连。该策略使 launchd 与手工运行一致。如果所在网络必须走代理，
诊断 AkShare-only 时可临时显式使用：

```bash
AKSHARE_PROXY_MODE=inherit ./scripts/run_akshare_snapshot.sh --date YYYY-MM-DD
```

不要把含账号或 token 的代理地址写进 plist、仓库或日志。

AkShare provider 内部顺序为 Eastmoney spot 快路径、Sina spot 慢路径、partial。
Sina 需要约 70 页串行请求，实测约 2–3 分钟，因此只在独立定时进程中兜底，
不会进入 Workbench API 请求链。

## 验证

先手工跑一次，再检查结构与调度状态：

```bash
./scripts/run_market_snapshot.sh --date YYYY-MM-DD
python3 -m scripts.check_market_snapshot_contract \
  --root /Users/a77/finance-workspace-private/market_snapshot \
  --pretty
launchctl print gui/$(id -u)/com.a77.finance-akshare-snapshot
```

同时查看：

- `market_snapshot/market_snapshot_sync_status.json`：provider attempts、请求/服务日期、
  是否发布和错误。
- `/Users/a77/.local/share/finance-workbench/akshare-snapshot.log`：标准输出。
- `/Users/a77/.local/share/finance-workbench/akshare-snapshot.err.log`：错误输出。

## 回滚

```bash
launchctl bootout gui/$(id -u)/com.a77.finance-akshare-snapshot
rm /Users/a77/Library/LaunchAgents/com.a77.finance-akshare-snapshot.plist
```

独立 venv 可随后删除；已有 complete 快照不需要回滚。不要删除由其他上游生成的
`market_snapshot` 文件。
