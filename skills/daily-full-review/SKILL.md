---
name: daily-full-review
description: "仅用于单日全量复盘。触发：全量复盘、今日全量复盘、跑全量复盘、daily full review。按已验证模块顺序同步当日 market_feature_store 并生成日报/题材/HTML。只补单表、只补历史缺口、只跑某个 sync 子命令不要用（历史缺口用 duckdb-backfill）。"
---

> 硬约束在前；细节见 `references/`。官方压缩截断保开头，所以闸门/红线必须留在文首。

# 单日全量复盘（Daily Full Review）

## 这个 skill 存在的理由（必须先读）

`python3 -m intelligence.cli daily` 内部第一步是 monolith `daily-update`
（`market_feature_store/sync/sync_daily_full.py:run_daily_update`），它把全部同步
模块串在一个进程里。**只要其中任意一个重模块（sector-stocks / limit-heat /
stock-daily）静默挂起，整个 daily 就卡死且无进度输出。**

历史教训（2026-06-16）：monolith 卡住后，没有切到已验证的"按模块逐个跑 + 兜底
脚本"路径，而是临时手搓 inline 批次，导致：
1. 没按已验证脚本回填（该用 `backfill_review_hot_data.py` / 逐模块 CLI / fallback）。
2. 没分模块批量回填，反复在同一种卡法上重试。
3. 没记录经验，下次还会踩同样的坑。

**本 skill = 限制提示词 + 模块化批量同步脚本 + runlog 经验记录。**

## 硬性限制提示词（每次开工前默念）

- **禁止手搓 inline 批次**：所有同步只能走 `python3 -m market_feature_store.cli <sync-*>`
  或本 skill 的 `scripts/run_review_sync.py`，不允许临时写 SQL/heredoc 凑数。
- **逐模块隔离 + 超时**：每个模块单独子进程跑，带超时；一个挂了不拖死整轮。
- **静默挂起即停**：模块无输出且 CPU≈0 约 2 分钟 → 终止，按下表走兜底路径，
  不要盲目重试同一条命令。
- **重模块先看进度**：`limit-heat` 必须能看到 `[limit-heat] detail chunk i/N` 进度；
  看不到就是被 PIPE 吞了，改成直跑（继承 stdout）。
- **每模块审计**：写完用 `check_daily_review_data.py` 或行数查询确认，再进下一模块。
  **行数不够**：再抽查 `price`/`pct_chg`/`amount` 非空（`COUNT(*)` 过门、值全 NULL 是 06-22 假绿）。
- **market_snapshot 产物是修复/补跑完成判据的一部分**：判 COMPLETE 前必须
  `market_snapshot/latest.json` 的 `served_trade_date == 当次修复的交易日`，否则不算收尾；
  缺就补 `PYTHONPATH=$FINANCE_WS .venv-workbench/bin/python scripts/sync_market_snapshot.py --date D`。
  教训（2026-08-26）：0825 修复补齐 DuckDB + 复盘产物即判 COMPLETE，但 snapshot 停在 08-24，
  `_runtime_market_reference_date = min(snapshot, db)` 把生产问答整日钳在 08-24 而 health/覆盖率全绿
  （台账 `R-20260826-01`；工单 `docs/superpowers/specs/2026-08-26-width-resonance-bag-workorder.md` §P0）。
- **夜跑失败禁止直写生产**：18:30 S7 写的是 `db/market_feature_store.duckdb.staging`，same-day 不过门就不换名。补洞设 `MARKET_FEATURE_STORE_DB=…staging`，门绿才 `atomic_swap_into_place`。详见 `references/ops-pitfalls.md`「S7 staging」。
- **两个 python 不是同一个**：`intelligence.cli` / DuckDB 用 `.venv-workbench/bin/python`；生成段 `CommandSpec` 写死 PATH 里的 `python3`，必须以 `/opt/homebrew/bin` 开头（venv 缺 `markdown`/`matplotlib`）。
- **每轮必记 runlog**：跑完把每个模块的 状态/耗时/走了哪条路径 追加到
  `state/runlog.md`，顺的路径记住，坑的路径下次规避。
- **末尾自动补偿重试**：编排器跑完一轮后会对 fail/timeout 的模块统一重跑
  `--retry-rounds` 轮（默认1），CDP 500 等瞬态故障到末尾往往已自愈；runlog 备注会带 `[retry rN]`。
- **必须用编排层 run_review_sync.py**：不要手动逐步跑 sync-* 命令，参数极易搞错
  （如 sync-stock-daily --refresh 默认 offset=180 ≈ 90min）。编排层自带正确参数 + 超时 + 兜底。
- **超时后检查残留进程再起新任务**：`ps aux | grep market_feature_store | grep -v grep`
  确认 DuckDB 锁已释放，否则新写操作会报 Conflicting lock。
- **Devin 远程场景必须 nohup 后台**：通过 Cloudflare 隧道跑 ≥ 100s 的命令一律
  `nohup python3 -u ... > /tmp/bf/<log>.log 2>&1 &`，然后轮询日志。
- **agent-daily 是独立步骤**：不在 evolve_daily.sh 中，evolve 跑完后必须单独执行
  `python3 -m intelligence.cli agent-daily --date D`，否则驾驶台缺研究队列。
  研究队列 `{D}-research-queue.json` 是 canonical；完整 `{D}-daily-agent.*` 仅在
  fidelity 1.2 通过时落盘，缺它不阻断后续矩阵。
  **夜跑 / `intelligence.cli daily` 默认 `--semantic-rag-top-n 0`**：分桶不读 wiki RAG，
  避免索引超时拖死 20:40 生成段。手动深挖仍可显式传 `--semantic-rag-top-n 3`。
  队列写出后会 `kb-queue-receive` 把 `{D}-kb-ingest-queue.json` 归档到知识库
  `wiki/raw/cross-repo-ingest-queue/`；**只归档、不 apply、不改 relations**。
  若 `content delta exceeds maximum size`（10MB）：gitignore 缩不了 delta；临时 park
  手法见 `references/ops-pitfalls.md`，不要扩 cap、不要把归档 commit 进别人的知识库分支。
  补跑队列后必须重渲染 workbench + cockpit。`daily-workflow-summary.json` 若
  `skip_agent=true`，不能当「研究队列已跑」的证据。

## Git 安全

开工先报告：

```bash
git status --short
git branch --show-current
```

不要 `git add .`。复盘产物（`market_feature_store/exports/*`、`复盘/daily/*`、
矩阵 HTML）和 DuckDB 本地状态与源码改动分开提交。

## 标准编排：单日全量复盘

### 一键入口（推荐）

```bash
python3 skills/daily-full-review/scripts/run_review_sync.py --date YYYY-MM-DD
```

脚本按下面的"已验证模块顺序"逐个跑，逐模块超时 + 自动兜底 + 写 runlog。
同步全绿后再跑生成段：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD --skip-sync --from-step daily-review \
  --summary-json market_feature_store/exports/YYYY-MM-DD-daily-workflow-summary.json
```

### 收尾：当日增量导出到 iCloud（自动）

`run_review_sync.py` 在质检后会自动跑一步 `export-increment`（`scripts/export_increment.py`），
把当日新增的行导成小 parquet 备份到 iCloud：

```bash
# 编排器已内置调用；也可手动补跑某日：
python3 skills/daily-full-review/scripts/export_increment.py --date YYYY-MM-DD
```

产物：`~/Library/Mobile Documents/com~apple~CloudDocs/duckdb-snapshots/increments/market_feature_store-inc-<日期>.tar.gz`
（每张含 `trade_date` 的 fact/feature 表 `WHERE trade_date=当日` → parquet+zstd + manifest.json，一天通常仅几 MB）。

**为什么不直接 iCloud 同步 `.duckdb`**：单个 ~3GB 文件 iCloud 无块级增量，每次改动整文件重传，
且开「优化储存」时可能被逐出成占位、DuckDB 打开要先下完整库。所以按 `trade_date` 导当日增量小文件更省更稳。
**还原**：增量不能独立重建库，需「一份全量基线 + 其后每日增量按序回放（`COPY`/`IMPORT`）」；
全量基线用 `EXPORT DATABASE` 另存，本步只管每日增量。导出失败仅告警、不影响复盘结果。


## 模块顺序与运维细节

按需读取，不要一次性加载进主上下文：

- `references/module-order.md` — 已验证的 8 模块顺序与依赖
- `references/ops-pitfalls.md` — 防坑、launchd、Devin 隧道、常见失败

## 后置环节（同步完成后必做）

夜跑 `intelligence.cli daily --skip-sync --from-step daily-review` **已经串**下面「canonical」步
（含日报 HTML、题材、队列、矩阵、workbench、cockpit）。手工补跑只补缺的那步，不要按旧脚本名另写一套。

| 序 | 步骤 | 命令 | 备注 |
|---|---|---|---|
| 1 | 渲染每日复盘 HTML | `python3 scripts/render_daily_review_briefing.py D` | canonical；旧的 `render_daily_review_html.py` 是另一套暗色模板，不要混用 |
| 2 | 渲染题材雷达 HTML | `python3 scripts/render_market_triggered_theme_brief_html.py D` | 若 quality-gate 拦截，手工从 md 渲染 |
| 3 | 渲染题材候选工作台 | `python3 scripts/render_theme_candidates_workbench_html.py D` | |
| 4 | 策略四矩阵 | 已内置到 `intelligence.cli daily`（strategy4-matrix 步） | 也可手动 `render_strategy4_dual_engine_matrix.py --end D` |
| 5 | 策略一/三矩阵 | 已内置到 `intelligence.cli daily`（strategy1-matrix-draft / strategy3-matrix 步） | 策略一自动行为「机械初稿」，人工复核仍走 `skills/strategy1-matrix`（人工行不会被机械行覆盖） |
| 6 | 研究队列 | `python3 -m intelligence.cli agent-daily --date D`（夜跑带 `--semantic-rag-top-n 0`） | canonical `{D}-research-queue.*`；完整日报 best-effort |
| 6b | 跨仓缺口归档 | `python3 -m intelligence.cli kb-queue-receive --date D --kb-wiki <KB_WIKI>` | 只 receive 到 wiki/raw；`auto_apply` 保持 false；不写 IMA/relations |
| 7 | 策略工作台 | `python3 scripts/render_review_workbench.py` | 队列补跑后必须再跑，否则 08-25 卡仍缺「研究队列」 |
| 8 | 驾驶台 cockpit | `python3 scripts/render_cockpit.py --knowledge-root <KB_ROOT>` | 参数是知识库**仓根**（`…/knowledge-base-private`），不是 `--kb-briefings-dir` |
| 9 | L3 补录（例行池+agent缺口） | `python3 skills/daily-full-review/scripts/l3_daily_backfill.py --date D --apply` | **在 agent-daily 之后**；先 dry-run。知识库在别人脏分支上只 dry-run、不 `--apply` |

有源才跑（**不是**夜跑完成判据；缺它们不要当成复盘没收尾）：

| 步骤 | 命令 | 备注 |
|---|---|---|
| 机构胜率 | `python3 skills/opinion-cross/scripts/render_winrate_html.py --vault <KB_WIKI> --date D` | 驾驶台能链到历史胜率页即可 |
| 晨会简报 | `python3 <KB>/skills/morning-briefing/scripts/render_briefing_html.py D --vault <KB_WIKI>` | 需 `wiki/briefings/D.md` |
| 进化流水线 | `bash scripts/evolve_daily.sh D` | 不加 `--force` 除非数据有缺口 |

> **KB 路径**：仓根 `/Users/a77/knowledge-base-private`，`KB_WIKI` = `…/wiki`。

## L3 补录（全量复盘后必做，两项）

时点：全量同步 + 生成段 + evolve + **agent-daily 之后**（依赖 <D>-research-queue.json，fallback daily-agent.json）。
统一入口（例行池 + agent-daily 缺口一次跑完）：

```bash
export FINANCE_L3_LOOKUP_ENABLED=1
export FINANCE_L3_PYTHON=/Users/a77/.venv-disclosure/bin/python
export FINANCE_L3_PYTHONPATH=/Users/a77/finhot/finhot
export FINANCE_L3_CWD=/Users/a77/finhot/finhot
# 先 dry-run 看写入计划，确认后加 --apply 真正进审核队列
python3 skills/daily-full-review/scripts/l3_daily_backfill.py --date D --apply
```

两项任务（脚本已合一）：

1. **每日巨潮/互动易例行扫描**：候选池 = `复盘/matrices/strategy1-priority-stock-matrix.html`
   **当日行** T1/T2/OBS 代码（不扫历史全表；旧 md 辅助稿已退役）。每只按交易所路由源：
   沪市 `cninfo,sse_einteract`、深市 `cninfo,irm_szse`、北交所仅 `cninfo`。默认近 3 天增量窗口。
2. **agent-daily L3 缺口自动补**：优先读 `market_feature_store/exports/<D>-research-queue.json`
   （没有则 fallback `<D>-daily-agent.json`）的
   `research_queue.today_find_official_evidence` / `today_do_ima`；完整 daily-agent
   若存在，再并入证据裁判「重点验证/能力栈候选」目标中的股票代码（纯题材名无代码的跳过）。

硬性闸门（不可越过）：

- apply **永远不带 `--reviewed`**：所有产出 `review_required=true`，只进审核队列。
- 只写 `wiki/sources/*` + `wiki/entities/*`，**不碰 relations/evidence_index、不提升图谱、不改实体事实**。
- 同一公司同日多源**必须一次调用逗号多源**（如 `--source cninfo,irm_szse`）生成单一 payload；
  分两次 apply 会因同日 source note 同名而互相覆盖（2026-07-16 教训）。
- `--source irm_szse` 需要 l3_evidence.py 源白名单包含 irm_szse（PR #241 修复；
  否则会被静默回退成 cninfo，把公告当互动易）。
- 长批量经隧道跑必须 spawn.py/nohup 守护化 + 轮询 summary.tsv（沪市 sse_einteract 单只可达分钟级）。
- 提交只包含本轮 `wiki/sources` / `wiki/entities` 改动，排除 access_log / .audit。
- dry-run 0 条可写候选 = 不要 `--apply`。知识库当前分支是别人的活时，只 dry-run。

## 生成段与矩阵段（同步全绿后）

1. 生成：`intelligence.cli daily --skip-sync --from-step daily-review`（见上）。
2. 策略记录：`python3 scripts/evolve.py generate --date D`。
3. 策略一/三/四矩阵：`intelligence.cli daily` 生成段已自动跑（strategy1-matrix-draft →
   strategy3-matrix --append-missing → strategy4-matrix）；策略一产出的是「机械初稿·待人工复核」行，
   人工终判仍走 `skills/strategy1-matrix`（事实层 → row JSON → update_matrix.py，先 `--dry-run`；
   人工行不会被后续机械初稿覆盖）。
4. 手动补跑单个矩阵：`generate_strategy1_mechanical_row.py --date D`、
   `backfill_strategy3_touch_matrix.py --append-missing`、`render_strategy4_dual_engine_matrix.py --end D`。

## 迭代规则

每次单日复盘后：

- 把本轮每模块 状态/耗时/路径 追加到 `state/runlog.md`（脚本自动写，人工可补注释）。
- 如果某模块用了新的兜底或踩了新坑，**立即更新 `references/ops-pitfalls.md` 的"顺/坑 速查"表**，
  再继续，让下次少踩坑。
