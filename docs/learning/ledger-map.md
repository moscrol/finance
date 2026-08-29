# 台账地图（全部台账的一页总索引）

> 防再乱的总登记表：每条台账线只有一个 canonical 机器可读落点（JSON/JSONL），md/html 一律是渲染物；
> 按日期命名分区；每个台账文件只有一个写入者；需要 git 历史的进仓，缓存/超大生成物落仓外 `~/kb_work/`。
> 新增任何台账，必须先在这张表登记。

| 台账 | canonical 路径 | 格式 | 唯一写入者 | 提交? | 渲染物 |
|---|---|---|---|---|---|
| 复盘输入冻结 | `docs/learning/forecast-review-ledger/<date>.manifest.json` | JSON | `dual_blind_forecast.py manifest`（**夜跑已退役**，仅手动） | 是 | — |
| 复盘答卷 | `docs/learning/forecast-review-ledger/<date>.answer.<agent>.json` | JSON | `dual_blind_forecast.py validate`（校验；**夜跑已退役**） | 是 | `<date>.md` |
| 复盘验证 | `docs/learning/forecast-review-ledger/<date>.verdict.json` | JSON | `dual_blind_forecast.py verdict`（**夜跑已退役**，仅手动） | 是 | `index.md` 状态表（`index` 子命令） |
| 回答评分 | `intelligence/users/<id>/answer_scores.jsonl` | JSONL | auto_eval | 否（用户态） | — |
| 个人判断回检 | `intelligence/users/<id>/checkpoints.jsonl` + `verdicts.jsonl` | JSONL | foresight checkpoint | 否（用户态） | — |
| 记忆候选留档 | `intelligence/users/<id>/memory_candidates.jsonl` | JSONL | `run_memory_candidate_loop.py` | 否（用户态） | `trace` 子命令（归因反查）；生命周期见 `memory-candidate-lifecycle.md` |
| 双盲错因反思候选 | `docs/learning/forecast-lessons/reflections/<date>.reflection.<agent>.<source>.json` | JSON | `forecast_learning_loop sync-reflections` | 是 | Workbench / 人工审批 |
| 双盲已批准 lessons | `docs/learning/forecast-lessons/lessons.jsonl` | JSONL | `forecast_learning_loop approve-reflection` | 是 | 次日答卷 prompt |
| 双盲批注规则候选 | `docs/learning/forecast-lessons/rule_candidates.jsonl` | JSONL 事件流 | `forecast_learning_loop sync-annotations/approve-rule/reject-rule` | 是 | 次日答卷 prompt（仅 approved） |
| 分叉蒸馏批记录 | `docs/learning/distill/<date>-<对照名>.md` | md（例外：人过闸裁决文档，md 即 canonical） | divergence-distill skill 会话 | 是 | — |
| 晨汇 | 知识库仓 `wiki/briefings/<date>.md` | md | morning-briefing | 是 | `dashboard/briefings/<date>.html`（不提交） |
| 晨汇原料 | 知识库仓 `wiki/raw/briefings/<date>/` | 原文 | morning-briefing | 是 | — |
| 卖方原文 | 知识库仓 `wiki/raw/sellside/` | md/pdf 转写 | material-router（表定）/ 近月实写 sellside-coverage-cross | 是 | — |
| 卖方观点事件 | 知识库仓 `wiki/raw/theme-radar/opinion-store/opinion-events.jsonl` | JSONL | opinion-cross | 是 | `复盘/winrate/*.html`（不提交） |
| 机构胜率 | `~/kb_work/winrate_cache/` + `~/kb_work/winrate/` | md | refresh_winrate | 仓外 | 同上 |
| 每日运营总账 | `build_daily_ops_ledger.py` 输出 | JSON | 该脚本 | 生成物 | cockpit |
| 工作台 Run | `intelligence/users/<id>/runs/<run_id>/run.json` + `trace.jsonl` | JSON/JSONL | `run_store.py` | 否（用户态） | Workbench UI（协议见 `docs/superpowers/plans/2026-07-08-run-protocol.md`） |
| 工具饥饿 | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/tool_hunger.jsonl` | JSONL | episode/inline 运行时（fail-open） | 否（用户态） | `python -m intelligence.eval.tool_hunger` → `intelligence/eval/measurements/tool-hunger-YYYY-MM-DD.{json,md}` |
| 工作台会话 | `intelligence/users/<id>/conversations/<conversation_id>/conversation.json` + `messages.jsonl` | JSON/JSONL | `ConversationStore` | 否（用户态） | Chat-first Workbench UI |
| Fidelity 前向验收 | `/Users/a77/fidelity-runtime/forward-acceptance/records/<date>/*.json` | JSON | `fidelity_forward_acceptance.py record` | 仓外 | `latest/<date>.json` + `summary` 子命令 |
| 观测台薄账 | `docs/roadmap.md` | md（例外：md 即 canonical，不是渲染物） | 检阅方 | 是 | Phase 1 起 `var/observatory/index.html`（gitignored）；L2/曲线由生成器投影 |
| 视角考卷（已知题/边题） | `intelligence/users/<id>/perspectives/exam/<pid>.json` | JSON | `perspective exam add` | 否（用户态） | `perspective exam run` 报告 |
| 自用摩擦台账 | `docs/learning/self-use-ledger/<date>.jsonl` | JSONL | `scripts/self_use_ledger.py add`（只记真人使用，探针/评测不进账） | 是 | `summary` 子命令（Self-use Gate 读数，见目录 README） |
| 预测/假设台账（R-号，实验立案与预注册裁决） | `docs/prediction-ledger.md` | md（例外：md 即 canonical） | 号由 `scripts/claim_ledger_id.py claim` 原子预占（禁手工 max+1）；行由立案会话写入 | 是 | —（实验原始收据在 `~/.finance-runtime/<实验名>/`，本表行是唯一住址索引） |

## 保鲜状态（2026-08-28 P3 诊断）

工单 `docs/superpowers/specs/2026-08-28-ledger-refresh-workorder.md`。结论：**卖方是微信 API 频控 + 手贴停更；晨汇不是同一条线**——原料在 IMA 浑水调研，经 `ima-fetch.cjs`（desktop bridge）拉 PDF，再交 `morning-briefing` 入库。未补拉、未恢复任何退役链。双盲夜跑仍按表内「夜跑已退役、仅手动」，本诊断不碰。

| 台账 | 最近落点 | 缺档 | 触发方式 | 断因 | 证据 |
|---|---|---|---|---|---|
| 晨汇 / 晨汇原料 | `wiki/briefings/2026-08-20.md`（`#5400`，2026-08-22 入库）；原料同日 `wiki/raw/briefings/2026-08-20/` | 库内缺 08-21 起。IMA 侧已有 08-21/22 合刊、0823–0825、0826–0828 | **IMA bridge**：`ima-desktop-bridge/scripts/ima-fetch.cjs` 搜浑水调研 → 拉 PDF → `morning-briefing` 入库。无 crontab。默认检索词是「路演调研日报 / 全量复盘 / 全量总结」 | 上游 PDF 还在；本地最后一次拉到 `~/Downloads/ima-briefings` 是 08-22。新文件改名「全市场路演调研…」，默认词搜不到；今晚 bridge `connected=false`（IMA 未开/插件未心跳），OpenAPI 能搜不能下 | `#5400` 来源写「IMA 浑水调研《路演调研全日汇总 0820.pdf》」；`ima-fetch search --kb 浑水调研 全市场路演` 命中 0828/0827/0826 等 |
| 卖方原文 | `wiki/raw/sellside/2026-08-17-调研纪要miracle.md`（`#5366`，2026-08-18 手贴入库） | 08-18 起无 miracle/原文。东方财富 RSSHub 快照更早停在 07-21 | **近月实写是手贴**，不是 launchd。`material-router` 已 frozen（2026-07 审计：日志零使用）。双盲 sellside/briefing plist 在 `~/Library/LaunchAgents/disabled-by-devin/`，属退役夜跑，不恢复 | 三层自动源都出不了货，手贴也停了 | 见下表 |

卖方自动源（2026-08-28 实测）：

| 通道 | 状态 | 证据 |
|---|---|---|
| `fetch_eastmoney_rsshub_sellside.py` → `localhost:1200` | 采集器不在跑 | `:1200` 连不上；仓内最后一份 `2026-07-21-东方财富RSSHub.md` |
| `fetch_sellside.py` → FinHot `items-all.json` | 公共快照空 | HTTP 200，`{"items":[],"total":0,"filter":"watch","generatedAt":"2026-08-23T07:03:45.851Z"}`；`--dry-run --date 2026-08-17/18/28` 均「无匹配」 |
| wechat2rss `:8090` | 已死（08-14 已登记，08-28 复核仍死） | 端口无响应；`com.finhot.wechat2rss-sync` 未加载；`~/wechat2rss-data/res.db` mtime 08-05 |
| wechat-download-api `:5050` | 进程健康、库仍空 | `/api/health` healthy；`rss.db` `articles=0` / `subscriptions=39`（mtime 08-22）；`#5365/#5366` 写明频控，8/6 后抓不到，改手贴 |

状态标签：**晨汇 = 上游仍有货、抓取词表/会话断了，待打开 IMA 再拉；卖方 = 微信频控，待用户决策**。不要把两条线当成同一个故障。晨汇缺档不是「无原文」——IMA 里有 PDF，只是还没拉进仓；卖方缺档仍是「无原文，禁止编造」。

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
