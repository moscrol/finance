# 台账地图（全部台账的一页总索引）

> 防再乱的总登记表：每条台账线只有一个 canonical 机器可读落点（JSON/JSONL），md/html 一律是渲染物；
> 按日期命名分区；每个台账文件只有一个写入者；需要 git 历史的进仓，缓存/超大生成物落仓外 `~/kb_work/`。
> 新增任何台账，必须先在这张表登记。

| 台账 | canonical 路径 | 格式 | 唯一写入者 | 提交? | 渲染物 |
|---|---|---|---|---|---|
| 复盘输入冻结 | `docs/learning/forecast-review-ledger/<date>.manifest.json` | JSON | `dual_blind_forecast.py manifest` | 是 | — |
| 复盘答卷 | `docs/learning/forecast-review-ledger/<date>.answer.<agent>.json` | JSON | `dual_blind_forecast.py validate`（校验） | 是 | `<date>.md` |
| 复盘验证 | `docs/learning/forecast-review-ledger/<date>.verdict.json` | JSON | `dual_blind_forecast.py verdict` | 是 | `index.md` 状态表（`index` 子命令） |
| 回答评分 | `intelligence/users/<id>/answer_scores.jsonl` | JSONL | auto_eval | 否（用户态） | — |
| 个人判断回检 | `intelligence/users/<id>/checkpoints.jsonl` + `verdicts.jsonl` | JSONL | foresight checkpoint | 否（用户态） | — |
| 记忆候选留档 | `intelligence/users/<id>/memory_candidates.jsonl` | JSONL | `run_memory_candidate_loop.py` | 否（用户态） | `trace` 子命令（归因反查）；生命周期见 `memory-candidate-lifecycle.md` |
| 双盲错因反思候选 | `docs/learning/forecast-lessons/reflections/<date>.reflection.<agent>.<source>.json` | JSON | `forecast_learning_loop sync-reflections` | 是 | Workbench / 人工审批 |
| 双盲已批准 lessons | `docs/learning/forecast-lessons/lessons.jsonl` | JSONL | `forecast_learning_loop approve-reflection` | 是 | 次日答卷 prompt |
| 双盲批注规则候选 | `docs/learning/forecast-lessons/rule_candidates.jsonl` | JSONL 事件流 | `forecast_learning_loop sync-annotations/approve-rule/reject-rule` | 是 | 次日答卷 prompt（仅 approved） |
| 分叉蒸馏批记录 | `docs/learning/distill/<date>-<对照名>.md` | md（例外：人过闸裁决文档，md 即 canonical） | divergence-distill skill 会话 | 是 | — |
| 晨汇 | 知识库仓 `wiki/briefings/<date>.md` | md | morning-briefing | 是 | `dashboard/briefings/<date>.html`（不提交） |
| 晨汇原料 | 知识库仓 `wiki/raw/briefings/<date>/` | 原文 | morning-briefing | 是 | — |
| 卖方原文 | 知识库仓 `wiki/raw/sellside/` | md/pdf 转写 | material-router | 是 | — |
| 卖方观点事件 | 知识库仓 `wiki/raw/theme-radar/opinion-store/opinion-events.jsonl` | JSONL | opinion-cross | 是 | `复盘/winrate/*.html`（不提交） |
| 机构胜率 | `~/kb_work/winrate_cache/` + `~/kb_work/winrate/` | md | refresh_winrate | 仓外 | 同上 |
| 每日运营总账 | `build_daily_ops_ledger.py` 输出 | JSON | 该脚本 | 生成物 | cockpit |
| 工作台 Run | `intelligence/users/<id>/runs/<run_id>/run.json` + `trace.jsonl` | JSON/JSONL | `run_store.py` | 否（用户态） | Workbench UI（协议见 `docs/superpowers/plans/2026-07-08-run-protocol.md`） |
| 工作台会话 | `intelligence/users/<id>/conversations/<conversation_id>/conversation.json` + `messages.jsonl` | JSON/JSONL | `ConversationStore` | 否（用户态） | Chat-first Workbench UI |
| Fidelity 前向验收 | `/Users/a77/fidelity-runtime/forward-acceptance/records/<date>/*.json` | JSON | `fidelity_forward_acceptance.py record` | 仓外 | `latest/<date>.json` + `summary` 子命令 |
| 观测台薄账 | `docs/roadmap.md` | md（例外：md 即 canonical，不是渲染物） | 检阅方 | 是 | Phase 1 起 `var/observatory/index.html`（gitignored）；L2/曲线由生成器投影 |

## 边界约定（去重复）

- **复盘验证唯一落点 = `<date>.verdict.json`**：每日复盘假设的 hit/miss 回检统一走这里，
  不再手工重复登记进 foresight `checkpoints.jsonl`（后者只留日常问答里的个人判断校准）。
- **晨汇 T1/T2/T3 兑现回检并入 verdict**：晨汇命中项作为假设来源之一登记进当日 `verdict.json`，不另建表。
- **任何晚间卖方材料第一步永远落知识库仓 `wiki/raw/sellside/`**，之后 pdf-ingest / material-router /
  opinion-cross 各管线从那里取，产物去向不变。
- **观测台薄账是例外**：`docs/roadmap.md` 的 md 本身是 L0/L1 canonical（手写只许薄，
  硬顶 120 行），不是 JSON 的渲染物；任务层 L2 与运行曲线禁止手写，由生成器投影。

## 设计原理（教学）

- **单一录入口（single source of truth）**：同一事实只有一个写入位置，其余全是投影，
  否则多写入口必然漂移。这与数仓的「一个事实表 + 多张物化视图」是同一思想。
- **按日期分区 + JSONL**：天然幂等（重跑覆盖当日文件即可）、git diff 友好、可 `jq`/pandas 直读。
  替代方案是集中进 SQLite/DuckDB——查询更强，但与 git 审计流、Obsidian 可读性冲突，
  且写入者变多容易锁冲突；台账量级（每天几 KB）用文件分区足够。
- **写入者唯一**：等价于数据库的「单 writer 原则」，把竞态和格式漂移消灭在源头；
  人工修改走该脚本 CLI，保证 schema 校验始终生效。这在 CDC/特征平台设计里同样适用。
