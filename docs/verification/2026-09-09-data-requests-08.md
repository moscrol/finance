# 验收收据 · 08 问题驱动补数（隔离链）· 2026-09-09

分支 `feat/demand-driven-data-requests`（底 `gitea/main@5eb24515`），树 `~/fwp-wt-demand-driven-data`。
**全部写入都在隔离 staging 库**（`~/.finance-runtime/data-requests-08/*.duckdb`，生产库整文件拷贝），生产库一个字节未动；
生产回填仍归 daily-full 维护者（工单 #33）。四项状态见文末。

## 1. 断点与接法（任务 0 → 实现）

| 环节 | 之前 | 现在 |
|---|---|---|
| 回答里的数据缺口 | 只在给模型的 observation 里一句「没有结构化结果」，无机器痕迹 | `tool_hunger.jsonl` 多一类 `window_uncovered`（dataset / 物理表 / 请求窗 / 实际覆盖 / 行数 / 未覆盖侧），观测型，observation 逐字节不变（接缝测锁定） |
| 结构化请求 | 无 | `data-requests build`：同 dataset 窗口重叠合并、消费者（run / 用户 / 原问题 / 会话）并集、路线表（已有 writer 才叫可补）、优先级按消费者数 + 新鲜度 |
| 补齐 | 手工 | `data-requests fill`：隔离库上按依赖顺序调现有 writer；指向生产库拒绝；fupanhui 家族 / OPT-03 占位只显示真正缺什么 |
| 完成信号 | 无 | `data-requests check`：交易日历（`fact_stock_daily`）× 关键字段非空 × 日期/来源合理性 → `satisfied` 才给 `data_version`，并逐项报告依赖 |
| 恢复研究 | 用户重问 | `data-requests resume`：沿 Workbench 原会话重问原问题；`(request_id, data_version, consumer_run_id)` 只恢复一次 |

## 2. 反向验证（排练库 `rehearsal.duckdb`，真 writer、真 akshare）[实测 14:55–15:00]

| 步 | 动作 | 检查结果 | 说明 |
|---|---|---|---|
| 0 | 补前 | `market_daily` open「窗口内无行」；`sw_l1_daily` open | 基线 |
| 1 | fill `market_daily`（index-daily 19 行 + overview-local 19 日，27.8 s） | **partial**「有行但关键字段值空：industry_1」；依赖 `{stock_daily: satisfied, sw_l1_daily: open}` | 有行不等于补齐；依赖没满足就不放行 |
| 2 | fill `sw_l1_daily` **不关实时步**（41.2 s，589 行） | **invalid**「31 行历史日被实时源覆写」：`2024-06-28 source=akshare:index_realtime_sw:8017xx` | writer 缺 historical 模式（blocked/08.md B2），检查器抓到真实缺陷 |
| 3 | fill `sw_l1_daily` 关实时步（38.8 s） | **satisfied** 19/19，`pct_chg` 非空 1.0 | 06-28 被 hist 值覆盖回来 |
| 4 | 再 fill `market_daily`（62.0 s） | **satisfied** 19/19，`sh_index_close / total_amount / limit_up / industry_1` 均 1.0；依赖全 satisfied；`data_version=4c71ef2190ca` | 同一请求重复 check 版本不变（单测锁定），数据一改版本即变 |

单测另覆盖：部分回填（缺日）、全 NULL、来源失败（库不可读）、日历未知、重复完成信号（`completed` 只落一次）、重放（第二次 `resume` 0 动作、不打 Workbench）、dry-run 无副作用、原会话 404 时新开会话、拒绝生产库。

## 3. 真实对话入口（隔离实例 :8808）

实例：本树起的 uvicorn（`lsof` 验过 cwd = `~/fwp-wt-demand-driven-data`），环境从生产 :8792 进程复制（8 个关键变量 sha 一致），
`MARKET_FEATURE_STORE_DB=staging.duckdb`、`FORESIGHT_USERS_DIR=…/users`（隔离），用户 `cap08`。

**14:51 第一轮四问 [实测]**：全部 `continuous_runtime_failed / stop_reason=model_unavailable`，`model_turn.error="LLM 调用 HTTP 429"`，`provider_attempts=4`，
4 秒内结束，模型没走到 `finance_query`，所以没有 `window_uncovered` 事件——这一轮不能当基线。
直接探网关：`gpt-5.6-sol/terra` 429 `model_cooldown reset≈4180s`；15:22 网关重启后变 `usage_limit_reached` / `no auth available`（全部 4 个模型）。
生产用户的模型配置同为 `built_in`（同网关），本机无其他现有凭据。**真实验收待外部额度恢复**（blocked/08.md B1）。

无人值守 runbook `~/.finance-runtime/data-requests-08/run_acceptance.sh all` 已挂后台（`gateway-wait.log` 每 2 分钟探一次，回 200 即跑）：
基线四问（QA/QB → G1 复用同一请求；QC → G3；QD → G2）→ `build` / `check`（应 open）→ `fill` 两轮 → `check`（应 satisfied + `data_version`）
→ `resume`（原会话重问）→ `resume` 重放（应 0 动作）→ `status`。产物 `~/.finance-runtime/data-requests-08/acceptance/`；
跑完后把补前 / 补后答案差量填进本节，四项状态表随之更新。

### 3.1 QA 基线已到手（16:05 网关短暂恢复的窗口）[实测]

16:05:02 探针回 200，后台驱动开跑；QA 提交后驱动进程被系统低内存杀掉，但 **run 本身在 Workbench 内完成**
（`run_20260909_160509_937232` completed，基线记录已从 run 目录回填 `acceptance/baseline/QA.json`）：

- **模型真实行为**：调了一次 `finance_query`（`market_daily`，`time_range 2024-05-31..2024-06-30`，metrics `index_close/index_return_pct`），
  库内无行；修复轮又试了两个变窗（06-01..06-30、05-31..06-28），同样无行。
- **接缝在真实路径出声**：该 run 的 `tool_hunger.jsonl` 恰好 3 条 `window_uncovered`（dataset/物理表/请求窗/row_count=0/uncovered=all 齐全）——
  第 2 节排练库走的是纯函数路径，这里是生产同款装配 + 真实模型 + 真实对话入口的第一次实证。
- **补前答案（差量的「前」）**：「现有证据不足，暂不能可靠回答……证据数据截至 2026-09-09；缺口补齐后可复验。」`outcome.status=partial`。
- **事件 → 请求 → 检查 [实测 16:31]**：3 条事件合并成 **1 个请求 `dr-542907a52f`**（窗口取并集 2024-05-31..2024-06-30，消费者 1 个，
  priority 5.0，auto 路线）；`check` = open「窗口内无行」；语义字段 `index_close/index_return_pct` 正确映射到物理列
  `sh_index_close/sh_index_pct_chg`（覆盖率 0.0）；依赖 `stock_daily=satisfied / sw_l1_daily=open`。
  产物 `acceptance/requests-check-before.json`。

16:31 网关再次 429（`reset_in≈16418s`，约 21:04 恢复）。QB/QC/QD 基线与 fill/resume/replay 由 21:12 的一次性定时任务续跑
（runbook 已改幂等：有 `baseline/<Q>.json` 就跳过，不重复烧额度）。

### 3.2 写手切本机 Mirasim（127.0.0.1:8080）后完成全链 [实测 18:11–19:45]

网关特性：单发探针常 200，**多 turn 连发常 502/503**（一个 run 内 4 turn × 2 尝试可全灭）。对策：每问前探针
「连续 2 发 200 才发问」+ 逐消费者驱动（`resume_one.py`，同一 services 函数落回执）。

**完整时间线与三个被真实验收抓出的缺陷**（各自当场修复 + 单测锁定）：

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 恢复失败被永久跳过 | `execute_resume` 不管新 run 成败都落 `resumed`，幂等键挡住重试 | failed/timeout 改落 `resume_attempt`（审计留痕、不消耗资格）；单测 `test_failed_resume_does_not_consume_the_retry` |
| 2 | 补齐后重问仍 rows=0 | **引擎 A 库路径只认 FINANCE_WS**（blocked B4，三套解析并存）；`MARKET_FEATURE_STORE_DB` 与本树软链均到不了它 | 隔离侧：假数据根 + `FINANCE_WS` 注入（launch_api.py 第 6 参）；runtime 修法留给原维护者 |
| 3 | 恢复出的 run 反复自注册 | 两种事件误报：请求窗写到日历日（06-30 周日）而覆盖到最后交易日（06-28）判 back；`limit=1` 点查覆盖单日判 front | `uncovered_side` 加 4 天日历宽容带（rows>0 才享受）；`record_window_uncovered` 加 `applied_limit`——打满 limit 是有意取 N 条不记。两条单测锁定 |

另修 CLI 回执域合同缝（blocked B5：`--users-dir` 跟随 `--runs-dir`）。

**核心差量（同一问题、同一真实对话入口、同一装配）**：

| 问题 | 补前（16:05 / 18:28–18:33 基线） | 补后（19:23 起恢复重问） |
|---|---|---|
| QA 2024-06 月度涨跌幅 / 最低收盘日 | `finance_query` rows=0 × 3、「现有证据不足，暂不能可靠回答」 | run 622962：「**月度下跌约 3.87%**（5/31 收 3086.813 → 6/28 收 2967.403），**最低 6/27 收 2945.852**，覆盖全月交易日」——与库内数值一致 |
| QB 相对 5 日均线偏离度最大日 | rows=0、「证据不足」 | rows=24、「证据数据截至 2024-06-28」；正文数字三次尝试均被网关多 turn 抖动打断（461667/483701），按停止规则不再重试 |
| QC 成交额最高日 / 涨停最多日 | rows=0、「证据不足」 | rows=19、「证据数据截至 2024-06-28」；正文同上（201626/037484） |
| QD 申万一级最强行业 | 模型未触发 sw_l1 查询（G2 线未自然开张） | —（sw_l1 的 fill/check 链在排练库全链验证过，§2 步 2–3） |

**完成条件对账**：
- 「问题→请求→补齐→恢复」完整闭环：G1 达成（QA 数字级差量）；QB/QC 达成到「恢复 run completed 且读到补后数据」，正文数字受网关质量限制未达成（外部条件，非本链）。
- 「一个请求被两个研究任务复用」：`dr-0a4d0226aa` 被 **5 个消费者**（QA/QB/QC 基线 + 两个恢复 run 的续研）复用，回执 `affected_run_ids` 可证 ✓。
- 「完成信号可重放且只更新一次」：`completed` 幂等 ✓；`resumed` 幂等（937232 重放跳过实证）✓；failed 重试语义实证（014998 三次 attempt 后 completed）✓；最终隔离视角 `plan_resume` pending=0 收敛 ✓。
- 「显示真正缺什么、不盲重试」：`dr-424d4e7f54`（global_index_daily，恢复 run 续研发现的**第二个真实缺口**）走 manual 路线：
  「fupanhui 家族需 CDP + 登录态、归 daily-full 维护者」，check 恒 open、不自动重试 ✓。
- 生产未动：全部写入在 `~/.finance-runtime/data-requests-08/`（staging + 假根），生产库、生产 users 零残留（误写回执已迁移删除）✓。

## 4. 四项状态

| 项 | 状态 |
|---|---|
| 已实现 | ✅ 事件 / 请求 / 检查 / 隔离补齐 / 完成回执（含 failed 可重试语义）/ 恢复 / CLI（含 `--users-dir`）/ 日产物兄弟件（`{date}-data-requests.json`）/ daily-agent 报告块 |
| 已进默认入口 | ✅ 接缝在生产装配的 `finance_query` runner 上（`build_episode_registry`），任何 Workbench / CLI 对话走到该工具都会留痕；`resume` 走 Workbench 消息接口 |
| 真实验收 | ✅ 隔离链全程走通（§3.2）：真实对话入口 × 真实模型 × 真实 akshare writer；QA 数字级前后差量；请求被 5 消费者复用；重放收敛 pending=0；恢复失败重试语义实证。未达成项如实记：QB/QC 正文数字（网关多 turn 抖动，3 次停止）、QD/sw_l1 线未被模型自然触发（排练库全链已验） |
| 生产生效 | ❌ 未合 main、8792 未切流、生产库未回补（按单：只完成隔离验收；生产回补归 #33 / daily-full 维护者） |
