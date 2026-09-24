# 输入与底座第一轮验收

关联规格：[`2026-09-24-architecture-input-foundation-audit-spec.md`](../../superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md)。这是阶段 A 的单次只读基线及审计器修复，不是整体稳定性认证。

## 身份与边界

- 采样：2026-09-24 20:44 起，+08:00；health/readiness 内含各自时刻，其余文件为同轮随后读取，非数据库级原子快照。
- 审计基线：`a54fed0d065f`，独立树 `/Users/a77/fwp-wt-architecture-audit-0924`。仅 daily ops 脚本和测试在本轮改动；其余检查执行基线代码。
- 生产：`3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，`source_dirty=false`，loaded/repo fingerprint 相等。生产代码根见 `health.json`，不等同于审计树。
- 金融数据：`/Users/a77/finance-workspace-private`；知识库：`/Users/a77/knowledge-base-private`，HEAD `8a413cde59cd0d6a7757c845243024a3016b50bc`，存在他人未提交内容及一个未解冲突，未处理。
- 生产用户根：`/Users/a77/.local/share/finance-workbench/users`。**启动器的默认账户为 `linxiaoqi5111`，不是字面值 `default`**。证据 `launcher-paths.txt`；显式 `?user=default` 的结果单独保留作身份对照。
- 未运行模型问答、生产补数、换库、部署、索引重建、定时采集恢复或用户记忆写入。未访问供应商网站。

## 原始结果

| 检查 | 原始结果 | 收据 | 能证明什么 |
|---|---|---|---|
| `GET /api/health` | HTTP 200、healthy | `health.json` | 进程存活、代码身份自洽 |
| `GET /api/readiness` | HTTP 503、not_ready | `readiness.json` | 行情日期一致性未通过 |
| `GET /api/perspectives` | HTTP 200 | `perspectives.json` | 当前默认账户可列出三份视角 |
| 显式 `?user=default` | HTTP 200，结果不同 | `perspectives-default.json` | 字面 default 是另一个用户空间，不是默认账户的别名 |
| daily ops 原版/修复版 | exit 0，均 WARN | `daily-ops-before/after.json`、`.md` | 仅文件盘点；exit 0 不能读成系统健康 |
| RAG readiness | exit 1 | `rag-readiness.txt`、`rag-index-meta.json` | 源/索引新鲜度规则不通过，不表示 worker 没启动 |
| daily review 数据检查 | exit 2、INCOMPLETE | `market-data.txt` | local 消费计划当日数据不完整，并发现历史字段空值 |
| 目录及画像元数据 | 见下表 | `input-file-inventory.json`、`perspective-active-profile-summary.json` | 文件与存储画像层证据，不是回答质量 |

## 输入线健康表

频率、告警和恢复未经过实跑的部分明确留为 UNKNOWN。代码/分支证据与本轮直接观察分列叙述。

| 线 | 触发、写入者与落点 | 本轮事实 | 消费/质量判定 | 下一步及归属 |
|---|---|---|---|---|
| 每日复盘 | 盘后 daily-full；标准 DuckDB 与快照 | 快照 09-24；market/stock 最大日 09-22，sector/sector_stock 等最大日 09-18；local 检查的 19 个对象均无 09-24 行 | 日期一致性 FAIL；9 月 22 日 market 行另有 13 个字段出现基线外 NULL。不能靠补一个日期解决 | #60/#61；先修身份/范围/字段，再走授权换库。告警已由 readiness 503 显示，通知送达 UNKNOWN |
| 晚间卖方 | 近月手贴，sellside-coverage-cross；`wiki/raw/sellside/` | 生产绑定目录的日期前缀 MD 最大材料日 08-17；候选 worktree 的 17 期订正不能代替生产原件 | 自动持续输入 UNKNOWN/未获证明；471 条 quarantine 的语义复核、river 订正投影消费仍未验 | 既有 sellside-consumption/miracle owner；核对候选发布与消费者，不恢复退役 plist；告警 UNKNOWN |
| 晨汇 | IMA bridge 原料 -> morning-briefing；`wiki/briefings/` | 标准目录最大材料日 09-14；ledger-map 记 09-15/18 已补，存在发布落点差异。当天没文件不能独自证明上游当天有货 | 代码 #87 已随 #902 合 main，生产仍旧版；生产正文可见性与长河消费 UNKNOWN | #87 + KB evidence-qc；先对齐已合版本/数据根/索引，再随 #61 就绪后真题验收；告警 UNKNOWN |
| Knevo | 用户原件 -> intake/absorption 候选 | 既有 owner 交接保留离线复算与原八问失败；本轮未运行新模型、未晋升规则 | 候选存在，不等于 runtime 采纳；实际消费/金融质量 BLOCKED | 沿既有 Knevo owner 的固定候选与失败样本推进，不在本单另写方法运行层 |
| SPT | 用户上传 -> perspective-distill；当前账户画像/文章 | API 报 50 篇、medium；存储画像包含待复核说明 | 列表可见 PASS；审批逐条状态、真问题中的正确应用 UNKNOWN | Perspective Lab：卡片/patch/画像版本对账，再验证选中视角的上下文。按输入事件验收，不强套日更 |
| 风远 | 同上，独立视角 | API 报 24 篇、medium；画像更新时间 09-16，含待复核说明 | 与 SPT 分开判；文章数不能证明方法已审或有效 | 同上；当前账户和 default 的风远数据不同，禁止跨用户混算 |
| 公告/财报/PDF/IMA | 既有 disclosure/ingest；原件、实体及报告上下文 | 标准库有实体改动；旧 IMA 三个库存文件夹均不存在。存量审计报告报缺 source 21、未覆盖 468，但这些报告的新鲜度未认证 | 原件到实体/索引/回答 UNKNOWN；文件夹不存在不能记零积压 PASS | 先确认现役 ingest 合同与实际目录，复用原 writer；不自动补卡或改正文 |
| 用户反馈/纠正 | userspace + ledger-map 中的唯一写者 | 已核对真实用户根与账户；未读取私人纠正正文、未写入 | 隔离代码定向测试有证据，生产回灌及撤回效果 UNKNOWN | 用真实账户的隔离副本验证纠正/撤回/跨用户负例，不污染个人库 |
| 按需查询 | 任务触发；工具注册表受执行合同门控 | 生产引擎 continuous_glm 就绪；本轮没有发起研究任务 | 声明可用不等于本次启用、正确调用或交付有效，UNKNOWN | 阶段 B 固定真入口轨迹；新模型运行仍受 #76 前置/预算约束 |

目录统计只覆盖路径名符合 `YYYY-MM-DD*.md` 的文件；不是知识库所有格式原件的完整枚举。日期是材料文件名日期，不是入库时刻或源可知时刻。

## 底座验收表

| 层 | 代码/装配证据 | 直接检查 | 实际消费与质量 |
|---|---|---|---|
| 事实存储 | 生产实际读取标准库 | FAIL：日期错位、字段空值；staging 有部分 09-24 行但未晋升 | 不把 staging 当已恢复；本轮无新回答验证 |
| 知识存储/版本 | 生产配置指向 KB 主检出树 | FAIL：索引 `source_dirty=true`，索引目录 35 个未提交文件，含未解冲突；索引构建 09-18 | 这是新鲜度门失败；没有把它扩写为所有检索方式均失效 |
| 检索/时间组织 | RAG worker ready；接口采用 legacy query 协议，缺 5 个可选过滤/收据参数 | worker 存活 PASS；证据可用性 FAIL；严格历史截止 UNKNOWN | 历史晨汇和卖方订正的长河绑定仍须验证 |
| 研究运行/Harness | 生产 A 引擎 continuous_glm、glm-5.3-flash；入口合同见门页 | 版本身份 PASS；readiness FAIL；另有 2 个 open episode，仅登记不推断损坏 | 未测重启恢复/预算/去重的生产闭环，不用工程单测替代 |
| 工具与 Skill | 注册表/权限合同及技能桥为既有实现 | 本轮未扩大注册或启用写能力 | 真调用和下游预算兑现 UNKNOWN，阶段 B/C 检查 |
| 质量与交付 | 现有质量门、自然验收工单 #76 | 本轮不跑模型、不重签其他 SHA 的绿 | 金融质量 UNKNOWN；既有失败保持失败 |
| 产品记忆/视角 | 生产 userspace 与 API 对应；中立/单视角等代码测试通过 | `linxiaoqi5111` 身份 PASS；待复核说明是审查风险，不能单凭文字判定未经授权生效 | 画像 `known_gaps` 不是审批日志，需逐 patch 追溯；本轮未签方法有效 |
| 开发共享记忆 | `.agent-memory` 项目笔记及能力图谱 | 用于开发约束/交接，非产品用户事实 | 不把本轮工程结论注入交易方法或用户偏好 |

## 已修复的审计缺陷

只修改 `scripts/build_daily_ops_ledger.py` 及测试，不改生产判据或业务数据。

1. 缺失/损坏/非对象 JSON、缺字段或非列表字段不再成为零欠账：计数 `None`、保留 error、状态 WARN。
2. IMA 库存目录不存在，不再因计数为零而 PASS；明确列出 missing_folders 并要求核对路径。
3. 目录不能充当期待的文件；关系文件缺失时给出对应行动，不再输出“surface is complete”。
4. JSON 与 Markdown 都显式标注 `file_inventory_only`，全绿也只证明清单齐备，不证明新鲜、正确或被消费。

决策：保留现有 PASS/WARN/FAIL 与 CLI exit 语义，避免破坏旧调用方；未知通过 WARN + None/error 表达。否掉新建综合健康评分器，现有确定性工具已能暴露主故障。没有把完整性门槛调低来消红。

验证：原版上新增用例 `6 failed, 4 passed`，修复后 `10 passed`，坏报告覆盖三类报告各七种输入；相关 RAG/视角/学习/用户空间定向回归 `103 passed`；ruff 和 diff-check exit 0。日志 `tests-red.txt` / `tests-green.txt` / `targeted-regression.txt`。这三份日志是本分支未提交变更上的定向读数。提交后又在干净 `6e6a2eac26b0b4d40034c6154b555bfafb3af2ba` 复跑同组 103P/0F，`dirty=false`、collected=103，收据为 `clean-targeted-receipt.json`。**两类读数都不是全量门禁、部署或真实金融验收；干净收据只绑定该提交，不移签后续文档提交。**

## 执行顺序

| 优先级 | 下一动作 | 开始/完成条件 |
|---|---|---|
| P0 | #61 行情恢复与日期/字段一致性 | 按既有 owner 的来源授权、固定候选、回滚点执行；生产写入和发布单独授权；完成后重跑同一检查，不只看 health |
| P0 | KB 源/索引发布一致性 | 由原改动 owner 处理未提交及冲突，固定已批准版本，再按其发布流程重建；本单不替他人提交或解冲突 |
| P1 | 晨汇/卖方从候选到生产落点核对 | 对齐原件、revision、标准数据根、索引和消费者；已合入不等于已部署 |
| P1 | 三类方法/视角逐条审批与上下文核对 | 真实用户空间；候选/批准/应用证据分别记录；待复核条目不以 article_count 自动背书 |
| P1 | 真入口消费与金融质量 | 前置收口、预算授权后按阶段 B 八例/#76 运行；不以 CLI 冒充 Workbench |
| P2 | 连续稳定与优化对照 | 完成阶段 C 的跨日观察及隔离故障对照后才开 D；今天不能提前签完 |

## 重跑方法

工作目录为本审计树，`PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。先阅读规格授权边界；每次输出用新目录，不覆盖本轮原件。HTTP 用有时限的 GET，保存状态码，503 是检查结果而非网络故障。

```bash
curl --max-time 20 -sS -w '\nHTTP %{http_code}\n' http://127.0.0.1:8792/api/health
curl --max-time 20 -sS -w '\nHTTP %{http_code}\n' http://127.0.0.1:8792/api/readiness
curl --max-time 20 -sS 'http://127.0.0.1:8792/api/perspectives?user=linxiaoqi5111'
KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python "$PY" scripts/check_rag_readiness.py --kb-root /Users/a77/knowledge-base-private --index-dir /Users/a77/knowledge-base-private/.rag_index
FINANCE_WS=/Users/a77/finance-workspace-private MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb "$PY" scripts/check_daily_review_data.py 2026-09-24 --phase data --plan local
"$PY" scripts/build_daily_ops_ledger.py --date 2026-09-24 --finance-root /Users/a77/finance-workspace-private --knowledge-wiki /Users/a77/knowledge-base-private/wiki --out-json "$OUT/daily-ops.json" --out-md "$OUT/daily-ops.md"
"$PY" -m pytest -q tests/test_daily_ops_ledger.py intelligence/tests/test_rag_readiness.py intelligence/tests/test_perspective_lab.py intelligence/tests/test_perspective_learning.py intelligence/tests/test_userspace.py
"$PY" -m ruff check scripts/build_daily_ops_ledger.py tests/test_daily_ops_ledger.py
```

运行前显式设置 `PY` 和新的 `OUT`。`daily-ops-before` 取自初始基线，`after` 是本轮修复后的同一数据根；旧文件只做 inventory，缺 10 个产物不用于定义全部现役报告合同。

## 外部证据入口

- 卖方候选：`/Users/a77/kb-wt-sellside-miracle-0818/docs/handoffs/inflight/ingest-sellside-miracle-0818-0918.md`。
- 晨汇：本基线 `docs/learning/ledger-map.md` 的 09-21 复核；代码合入由 `git log --ancestry-path 3b7e473575b0..a54fed0d065f --grep=902` 核对。
- Knevo：`/Users/a77/fwp-wt-knevo-closure-0923/docs/handoffs/inflight/feat-knevo-absorption-closure-0923.md` 与 intake 对应交接；这部分为 owner 历史证据，不是本轮重测。
- 生产视角装配：生产代码 `intelligence/services/perspective_lab.py::build_runtime_context` 读取画像字段；是否获批须回到 patch/人工审批记录，不能由画像风险文字倒推出完整权限结论。
