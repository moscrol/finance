# Handoff：评估/运维在线环修复——六个 launchd 日更任务全挂，逐个修通并裁决回补

日期：2026-08-18
派单人：主 agent（2026-08-18 评估盘点批次）
背景：ai-n 第 8 章「持续进化」靠在线证据环；实测这条腿断了。复盘会管线 08-13 停摆（数据资产审计发现）与其中两个任务的撞锁时间线吻合。

## 已核实事实（派单前逐 job 取证，2026-08-18 02:00）

`launchctl list` 里六个 `com.financeworkspace.*` 日更任务最后一次退出全部非零。逐个看过 plist 与 err/out 日志：

| job | 最后失败症状 | 初诊 |
|---|---|---|
| `fidelity-daily-agent` | `ImportError: TypeAlias`（用了 CLT 系统 Python 3.9）；out.log 从 08-13 起连续「skip: no fact_market_daily row」 | 三病叠加：系统解释器 + 写死旧快照 `~/.finance-runtime/finance-workspace-96446a933491` + 数据根族病（#164 同族） |
| `checkpoint-recheck` | `ModuleNotFoundError: intelligence`（CLT python3） | 系统解释器 + 无 PYTHONPATH/树指针 |
| `fidelity-forward-acceptance` | `git rev-parse HEAD` 于 `finance-workspace-88b28ab4-standalone` 退 128 | 写死的 standalone 快照目录已不存在/非 git 仓 |
| `pit-snapshot` | `ValueError: manifest generator_commit missing for 2026-08-12` | manifest 契约缺字段，08-12 起卡住；先取证字段为何缺再修 |
| `daily-full-review-sync` | DuckDB 撞锁：`Conflicting lock … python3.14 PID 62525` | 撞上别的分析进程；该 PID 已退场、现无人持锁（lsof 空）；**job 无重试，一撞就躺** |
| `daily-full-review-finalize` | 同上（共用 err log） | 同上 |

关联事实：

- 复盘会管线（exports 全家 + `ops_pipeline_run_daily` 记账）停在 08-13，与 sync/finalize 撞锁躺平吻合。行情主表更新到 08-17 是另一条同步在跑，不归这六个管。
- `market_feature_store/db.py` 已有 staging 换库工具（2026-08-15 bookgap S7，就是为了长事务不饿死读者）：sync 若还在直写生产库，应改走 `sync_daily_full.run_daily_full_staged`。
- 仓内有 plist 源（如 `intelligence/eval/com.financeworkspace.fidelity-daily-agent.plist`），装到 `~/Library/LaunchAgents/` 的是副本——修复应改仓内源 + 重装，不许只改装机副本。
- pre-commit「工作区事实」钩子的警告原话：宿主 python3 没有依赖，别用它。六个 job 里两个正犯这条。

## 目标

1. 六个 job 逐个修通：能跑、跑对树、跑对解释器、读对数据根。
2. 停摆窗口记账：每个 job「最后一次成功 → 修复日」的黑暗期写进台账。
3. 回补裁决：08-13 以来漏跑的产物（exports、ops 记账、pit 快照、fidelity 判分）每类给出「补 / 不补 + 理由」，用户可否决。

## 实施边界

只动：

- 仓内 plist 源与对应 job 脚本的**接线**（解释器路径、树指针、重试/锁等待）
- `docs/handoffs/inflight/main.md` + 台账登记
- 修复后 `launchctl bootout/bootstrap + kickstart` 重装重跑

不动：

- #164 数据根代码面（那张单的活；本单若 #164 未落地，用 `MARKET_FEATURE_STORE_DB` env 在 plist 层止血并注明是临时件）
- 8792 服务与 launcher
- 判分器/评估逻辑本体（修的是「跑起来」，不是「判得准」）
- 不许用「删掉 job」当修复

## 修复方向（执行方按取证微调）

1. **解释器统一**：全部指 `.venv-workbench/bin/python`，禁止 CLT/系统 python。
2. **树指针统一**：一律走 canonical 符号链接 `~/finance-workspace-runtime`（跟随 8792 切换），废除写死的 `finance-workspace-<hash>` / `-standalone` 目录。若某 job 语义上要「冻结在某 SHA」，在 plist 注释里写明为什么，并给出更新纪律。
3. **撞锁治理**：sync/finalize 改走 staged 换库路径或加锁等待+重试（上限与退避写明）；失败要留痕（非零退出 + err 一行摘要），不许静默。
4. **pit-snapshot manifest**：先查 `generator_commit` 字段生产方为何 08-12 起缺失（很可能也是快照/树指针病），修生产方，再决定 08-12 起的快照补不补。
5. **重试与告警底线**：每个 job 失败后下次调度自动再试（launchd 本身保证）之外，连续 ≥3 天失败要能被看见——最低成本方案：job 末尾把状态行 append 到一个 `~/.finance-runtime/ops-health.log`，检阅时人眼可扫。不引入新告警系统。

## 验收标准

1. 六个 job `launchctl kickstart -k` 后 `launchctl list` 退出码全 0，且各自产物新鲜（fidelity 判分文件、pit 快照、checkpoint 回验记录、复盘会 exports/ops 行有当日或最近交易日数据）
2. 复盘会管线恢复的直接证据：`ops_pipeline_run_daily` 出现新交易日行，exports 目录出现新日期文件
3. 停摆窗口台账 + 回补裁决表（每类产物：补/不补/理由）
4. plist 源与装机副本一致（diff 干净），重装步骤写进交接
5. 四件套绿（若动了仓内 py 文件；纯 plist/文档改动跑 ruff + 相关测试即可）

## 红线

- 不碰 #164 代码面；env 止血件要在台账标「临时，#164 落地后拆」
- 不切 8792、不改 launcher
- 回补数据必须走原管线代码重放，不许手搓行填表
- 台账诚实：黑暗期多长写多长，不许把「修好了」写成「一直好着」

## skill 与工具建议

skill：leila-runtime + diagnosing-bugs。工具：launchctl、plutil、lsof、git worktree、pytest、Gitea API。
