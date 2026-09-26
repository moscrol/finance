# 2026-09-22 东财取数传输层修复 + 熔断合入与夜跑部署工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
**时限硬**：夜跑 sync 段 `com.financeworkspace.daily-full-review-sync` 每日 18:30 触发。2026-09-23 18:30 之前熔断必须进夜跑代码根，否则会再打一轮已知不侍候的端点并毒化同主机其他可用端点。
姊妹：#61（行情恢复：同花顺桥与缺口定性）。两单都影响 09-23 夜跑，可并行，各开各的分支；部署动作在两单之间要协调（同一个 sync 代码根）。

## 背景与动机

- 09-21、09-22 连续两晚 `sync-stock-daily-snapshot` 失败 → 兜底无源 → 后续 11 个本地计算步骤全红 → `same-day-gate rc=2` → staging 不晋升 → 主库个股日线停在 09-18。
- 09-22 实测两条根因（`~/.finance-runtime/reviews/market-source-probe-20260922T1840/`）：(1) `_get_json` 的捕获子句接不住 `http.client.RemoteDisconnected`，重试从未生效；(2) 本机代理把 push2/push2delay/push2his 解析到 `198.18.0.x` 伪地址段，建连即断（~90ms）。修复在 `b1d797593`（分支 `fix/eastmoney-snapshot-direct-ip-0922`，基座 `a2c8d1f90`，**未推、未合**）：瞬时错误族改 `(OSError, HTTPException, ValueError)`；系统解析落在 `198.18/15` 时直连公共 DNS 取到的真实 IP、SNI 与 Host 仍填域名；链路健康时行为一字不变；`sync_eastmoney_fund_flow` 删掉自己那份重复实现改为导入。19 例新测试；变异：换回旧捕获子句 7 红、关劫持判据 2 红。
- 该补丁已按用户授权于 09-22 19:20 **热部署**到夜跑 sync 代码根 `/Users/a77/.finance-runtime/finance-sync-adcda94b5e40`（两文件，`deployment.json` 记 before/after sha256，`original-files/` 可回滚），并重跑了当晚 sync 段：补丁生效（snapshot 步骤 41.7s → 90.9s，重试阶梯跑起来了），但仍失败。
- **根因修正（合并前必读）**：不是「按出口 IP 封禁」。同一主机、同一 IP、同一条 TLS 上：`/` 返 404（正常应答）、`/api/qt/ulist.np/get?secids=…` 返 200 有数据、`/api/qt/clist/get?…` 连接被掉。换 `fs`、去参数、加浏览器头、IPv4/IPv6 两个地址族，全部同形。且**打 clist 会毒化客户端**：6 连发后原本 200 的 `ulist.np` 也转空回应，冷却 45–75s 不恢复。这解释了「单发能成、整跑必败」。
- 熔断已实现：PR **#856**（`fix/eastmoney-circuit-breaker-0922` @ `3cd5f9b84`，基座 `b1d797593`，标题带 `WIP:`）。按错误形状分账：连上即空回应连续 3 发判 `UpstreamRefusing` 停本轮、该 host 后续页一发不打；挡板页 `ValueError` 只重试不改选路不计熔断；公共 DNS 查不到只缓存成功结果；新增 `reset_transport_state()`。11 例先红后绿，51 文件 899P/1S，变异 5/5 全杀。分支落后 main 9 个提交，#851 动过 sector 测试且与本分支有文件交集。
- **已定的形态决策**：修法是「传输层按错误形状分账 + 熔断」，不是「加长超时 / 加重试 / `except Exception` / 一律直连真实 IP / 改用同花顺当快照源」。五个被否方案的理由见 `fix/eastmoney-snapshot-direct-ip-0922` 的 inflight 交接。换源是 #61 的事。

## 目标

1. `b1d797593` 与 #856 合成一条可合入的线：把 `fix/eastmoney-snapshot-direct-ip-0922` 推上 gitea，#856 前向到最新 `gitea/main`（解与 #851 的测试文件交集），去掉 `WIP:` 前缀（`gitea_pr.py guard`），PR 描述写明根因修正与「传输层修好了但不充分」。
2. 四叶收据齐、revision == PR head；`tests/test_eastmoney_transport.py` 与熔断新增用例全在收集面内。
3. 用户确认后合入（`merge --yes --expect-head --record`）。
4. 09-23 18:30 前让熔断进夜跑代码根，二选一并留记录：
   - **A（正门）**：合入后按 #827 的钉根方式装新 sync 代码根——`scripts/install_eval_launchd.sh --nightly-only --dry-run` 预览 → 用户确认 → 去掉 `--dry-run` 执行；`com.financeworkspace.daily-full-review-sync.plist` 的 `FINANCE_SYNC_CODE_ROOT` 指向新 SHA 目录；原热补根保留不删。
   - **B（临时）**：若 17:00 前合不进，把 #856 的熔断文件按 `deployment.json` 同一格式热补进当前根 `finance-sync-adcda94b5e40`（记 source_commit / before / after sha256、`original-files/` 回滚件），并在 inflight 与 INDEX 明写「临时热补，待 A 替换」。B 也需用户一句授权。
5. 09-23 夜跑后回读：sync 段日志里对 `clist/get` 的请求数、熔断触发记录、`ulist.np` 是否仍可用；写进 `docs/verification/2026-09-23-eastmoney-nightly-readback.md`。

## 非目标（写死认领）

- ❌ 不实现 `ulist.np/get?secids=` 分批取全市场。这是比换源更小的潜在修复，但要在**长时间没发过 clist 的干净状态**下重测，今晚客户端已被毒化测不准。留线索进本单收据，另立单。
- ❌ 不用同花顺当快照源替代东财。那是 #61 的口径决定（`fact_stock_daily_hithink` → `fact_stock_daily` 的桥已存在）。
- ❌ 不补 09-21 / 09-22 缺口。个股日线两日已由 #61 的桥写入生产（21:47 换库）；其余表归 #61。
- ❌ 不改夜跑其他步骤、不改 finalize 守卫、不改 `same-day-gate` 判据。
- ❌ 不重启 8792、不动 `/Users/a77/finance-workspace-runtime` 软链。sync 代码根与 8792 运行时是两个不同目录（`deployment.json` 的 note 已写明，别混）。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/eastmoney-hotfix-20260922T1917/CLOSEOUT.json`、`deployment.json`、`FINDINGS.md`、`curl-direct-probe.json`、`ip-rotation-probe.json` | 热补目标与指纹、重跑实测、根因修正的原始探针（25 件） |
| `~/.finance-runtime/reviews/market-source-probe-20260922T1840/` | 两条原始根因的 6/6 探针样本 |
| `~/.finance-runtime/reviews/open-task-audit-20260922-1922/C1-eastmoney-independent-review.md`、`eastmoney-refusal-recheck-2111.md` | 第三方读码复核 R1–R4；21:11 复测（人工誊录，非自动收据） |
| 分支 `fix/eastmoney-snapshot-direct-ip-0922`：`docs/handoffs/inflight/fix-eastmoney-snapshot-direct-ip-0922.md` 文末「运行验证」节 | 接手前必读；五个被否方案 |
| 分支 `fix/eastmoney-circuit-breaker-0922`：`docs/handoffs/inflight/fix-eastmoney-circuit-breaker-0922.md` | 错误形状分账表、`UpstreamRefusing` 语义 |
| `market_feature_store/sync/sync_eastmoney_stock_snapshot.py`、`sync_eastmoney_fund_flow.py`、`tests/test_eastmoney_transport.py` | 被改的两模块与测试 |
| `intelligence/dream/com.financeworkspace.daily-full-review-sync.plist`、`scripts/install_eval_launchd.sh`、`tests/test_eval_launchd_installer.py` | 钉根方式与 dry-run 预览（#827 落地） |
| `~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist` | 生产实际装的 plist：`FINANCE_SYNC_CODE_ROOT` 与 `MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb` |
| `docs/handoffs/2026-09-21-nightly-deploy-closeout.md` | 上一次钉根部署的收据形状，照着写 |

## 步骤

1. 开工三连；确认 `~/fwp-wt-eastmoney-direct-ip-0922` 与 `~/fwp-wt-eastmoney-circuit-breaker-0922` 两棵树都 clean 且无人在动（`git status --short`、看 Pi 会话 mtime）。
2. `git push gitea fix/eastmoney-snapshot-direct-ip-0922`。在熔断树 `git fetch gitea && git merge-tree --write-tree gitea/main fix/eastmoney-circuit-breaker-0922` 探冲突；有冲突逐处解（sector 测试那几处以 #851 语义为准，别把「同日唯一 published」改回按 provider）。前向后推送。
3. 低负载（`uptime` load ≤ 8、`pgrep -fl pytest | wc -l` ≤ 2）时在独占干净检出跑四叶（命令见 #58 步骤 4–5）；registry 五条。
4. `python3 scripts/gitea_pr.py guard 856 --off`（或等价去 `WIP:`）；PR 描述补根因修正段与「合并前建议关注的三件事」。
5. 用户确认后 `gitea_pr.py merge 856 --yes --expect-head <SHA> --record … --authorized-by "<原话>" --authorization-source "<出处>"`。
6. 部署：优先 A。`install_eval_launchd.sh --nightly-only --dry-run` 输出贴进收据 → 用户确认 → 执行 → `plutil -p ~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist | grep FINANCE_SYNC_CODE_ROOT` 回读 → `launchctl print gui/$(id -u)/com.financeworkspace.daily-full-review-sync | grep -E 'state|program'`。若走 B，照 `deployment.json` 格式落一份 `deployment-circuit-breaker.json`。
7. 09-23 19:00 后回读 sync 日志与 `fact_stock_daily` 的 `max(trade_date)`、`source` 分布（只读 DuckDB）。
8. 交接 inflight ≤3K；INDEX #60 行改状态；两棵树合入后按 `delete-merged-branches` 惯例清分支。

## 验收

- [ ] #856 head 包含 `b1d797593` 的两文件改动与熔断改动，`git merge-base --is-ancestor gitea/main <head>` 为真。
- [ ] 四叶收据 revision == head；`tests/test_eastmoney_transport.py` 与熔断用例在 `collected` 内（#58 合入后用 `--require-full-scope` 复核）。
- [ ] 阳性对照：把连续拒绝阈值 3 改成 999 再跑熔断用例，恰好红「连续 3 发判拒绝」那组；还原后绿。
- [ ] 合并记录 JSON 含授权原话与出处。
- [ ] 09-23 18:30 前 `FINANCE_SYNC_CODE_ROOT` 指向含熔断的代码根（A），或热补记录落盘且 `original-files/` 齐（B）。
- [ ] 09-23 夜跑回读：`clist/get` 请求数 ≤ 3 × host 数；`UpstreamRefusing` 若触发，日志有一条且其后该 host 零请求。

## 红线

- 只用 pathspec 提交；合入 main 必须等用户确认；不强推；不删他人分支与工作树。
- 部署（A 或 B）**每一步都要用户一句授权**，dry-run 预览先贴出来。不重启 8792，不动 `finance-workspace-runtime` 软链。
- 不写生产库。回读只用 `duckdb.connect(..., read_only=True)`。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 探针别用 `curl -o` 落上游响应体当证据（对端不给响应体时文件根本不会写出来）；用 `curl -w '%{json}'` 落 curl 自身结果对象。
- 不写明文密钥；Gitea token 只从 Keychain 取。
