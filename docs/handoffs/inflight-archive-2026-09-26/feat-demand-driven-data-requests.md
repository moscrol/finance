# feat/demand-driven-data-requests · 能力包 08「问题驱动补数」· 2026-09-09 晚（真实验收已完成）

树 `~/fwp-wt-demand-driven-data`，底 `gitea/main@5eb24515`，6 个提交至 `e62e09c3`，已推 gitea。**未合 main、未切流、生产库未动。**
收据（含完整差量表与时间线）`docs/verification/2026-09-09-data-requests-08.md`；进度 `docs/superpowers/plans/2026-09-09-capability-upgrade/progress/08.md`；
范围外 `…/blocked/08.md`（B1–B5）。

## 一句话

`finance_query` 窗口无数据现在留 `window_uncovered` 事件 → `data-requests` 聚合成请求（合并/消费者/路线/优先级）→ 覆盖检查
（交易日历 × 关键值非空 × 历史日不许被实时源覆写）→ 隔离库调现有 writer 补齐 → 沿 Workbench 原会话重问，回执保证同
`data_version` 只恢复一次、失败可重试。

## 四项状态

| 项 | 状态 |
|---|---|
| 已实现 | ✅ 全链 + CLI + 日产物兄弟件 + daily-agent 块；21+2 条单测 |
| 默认入口 | ✅ 接缝在生产装配 finance_query runner；resume 走 Workbench 消息接口 |
| 真实验收 | ✅ 隔离链全程（真实对话入口 × 真实模型 × 真实 akshare writer）：**QA 数字级差量**（补前「证据不足」→ 补后「-3.87%、最低 6/27 收 2945.852」，与库一致）；请求被 5 消费者复用；重放收敛 pending=0；恢复失败重试实证（014998 三次 attempt 后 completed）。未达成如实记：QB/QC 正文数字（网关多 turn 抖动 3 次停止）、QD/sw_l1 未被模型自然触发（排练库全链已验） |
| 生产生效 | ❌ 按单不做；生产回补归 #33 / daily-full 维护者 |

## 真实验收抓出的缺陷（全部当场修复 + 单测；这是本单最值钱的部分）

1. **恢复失败被永久跳过**：`execute_resume` 原对 failed 也落 `resumed` → 幂等键挡住重试。改落 `resume_attempt`（不消耗资格）。
2. **事件误报 × 2 → 恢复 run 无限自注册环**：请求窗写到日历日（06-30 周日）覆盖到最后交易日（06-28）判 back；`limit=1` 点查判 front。
   修：`uncovered_side` 4 天日历宽容带（rows>0 才享受）+ `record_window_uncovered(applied_limit=…)` 打满 limit 不记。
3. **CLI 回执域跟 env 不跟 `--runs-dir`**：手跑把回执写进生产 users 树、重放键对不上整批重恢复。修：`--users-dir` 缺省跟随 `--runs-dir`；误写 6 条已迁回隔离目录，生产 users 零残留。
4. **（范围外，blocked B4）引擎 A 库路径只认 `FINANCE_WS`**：`continuous_turn_adapter:533` 不传 finance_root → `_roots(None,None)` →
   `default_paths().finance_root`。`MARKET_FEATURE_STORE_DB`、orchestrator `_market_db_path`、本树 db/ 软链三条路都到不了 episode。
   隔离侧解法＝假数据根（`~/.finance-runtime/data-requests-08/finance-root/`，db→staging、其余软链回生产根）+ `FINANCE_WS` 注入
   （launch_api.py 第 6 参）。**runtime 修法留给 runtime-base 维护者**（建议 `_roots` 先认 env，或 adapter 传 orchestrator 的解析结果）。
5. **（范围外，blocked B2）`sync_akshare_sw_l1_daily` 历史窗把当日实时快照写到窗口末日**：排练库上被覆盖检查判 invalid 抓出（31 行
   `index_realtime_sw` 落在 2024-06-28）。归 daily-full 维护者。

## 接手须知

- 隔离环境：`~/.finance-runtime/data-requests-08/`（staging.duckdb / finance-root 假根 / users / acceptance 产物 / runbook + resume_one.py + launch_api.py）。
  :8808 实例可 kill；重起：`launch_api.py <prod8792_pid> 8808 <本树> <staging> <users> <finance-root>`。
- **不要在本树 `db/` 放任何库文件/软链**：它会被 `_market_db_path` 的 repo-local fixture 优先级吃掉，让
  `test_conversation_orchestrator` 一条 fixture 测试读到真库而红（2026-09-09 实测：软链在时 1 红，删掉即绿）。
  换库的正门只有 FINANCE_WS 假根（B4）。
- Mirasim 网关（127.0.0.1:8080）单发探针常 200、run 内多 turn 常 502——所有驱动脚本已内置「连续 2 发 200 才发问」。
- 后台长驻 shell 会被本机 OOM killer 杀（发生 3 次）：跑长任务用前台短命令或会话定时，别挂 sleep 循环。
- 合 main 前建议：把 blocked B4 转给 runtime 负责人（一行修复 + 一条回归测试）；QD/sw_l1 线如需自然触发，问法要点名「申万一级行业指数」。

## 决策与被否方案（沿上一版，新增）

- 误报处置选「宽容带启发式」而非「接缝层查交易日历」：tool_hunger 是 fail-open 观测层，不该连库；宁漏报不误报（吵闹门禁会被训练成忽略）。
- 引擎 A 库路径没有就地改 runtime：超白名单 + 有原负责人；假根法零代码改动、语义就是「给这棵树一个数据根」。
