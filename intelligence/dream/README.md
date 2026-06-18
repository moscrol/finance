# dream-loop · transcript store（C-1A-S0 / S1）

> 决策 1「dream loop」的**采集半 + 落盘**。把多个对话源归一化、脱敏后写入 transcript store，
> 产出可提交的脱敏 digest。推理半（读摘要→开 suggest-only PR）是后续阶段
> （Devin 定时 session，路线图 C-1B-S2），不在本目录。
>
> - **C-1A-S0**：最小切入，飞书一个源 + 落盘三件套 + 脱敏硬门 + 幂等。
> - **C-1A-S1**：补 `claude-code` / `claude-mem` / `windsurf` / `devin` 四源归一化 adapter。

## 这步做什么 / 不做什么

- ✅ 统一 transcript schema（每行 JSONL）：`{ts, source, session_id, role, text, repo, tags, redacted}`。
- ✅ 脱敏硬门：密钥 / token / 持仓 / PII 命中即打码（`[REDACTED:<类别>]`），并置 `redacted=true`。
- ✅ 落盘三件套：
  - `<store>/<date>/<source>-<session>.jsonl` —— 正文（已脱敏），**gitignore**，本地留存；
  - `<store>/manifest.jsonl` —— 每个 (date, source, session) 一条元数据，可审计、可提交；
  - `<store>/digest-<date>.md` —— 当日脱敏摘要，**可提交**，供推理半读取。
- ✅ 幂等：重跑产生字节一致的结果（manifest 按主键 upsert、`collected_at` 取桶内最大 ts）。
- ✅ 源归一化 adapter（`_NORMALIZERS`）：`feishu` / `claude-code` / `claude-mem` / `windsurf` / `devin`，
  统一映射 role 到 `user|assistant|tool`，时间戳兼容 ISO8601 与 epoch 秒/毫秒。
- ❌ 不实现推理半、不开 Devin playbook/schedule、不自动合并 main。
- ❌ 不做采集半 launchd 定时化（C-1A 采集半，后续阶段）。
- ❌ 不碰 DuckDB、不抢写锁。

## 数据流

```
对话源原始 jsonl（每行一个事件/消息/会话/observation，视源而定）
  · feishu     —— feishu_bot.py --transcript-log 产出
  · claude-code—— Claude Code 会话历史 jsonl（逐行 message）
  · claude-mem —— get_observations 产出（逐行 observation）
  · windsurf   —— Cascade 会话（一行 = 一个含 messages 的会话）
  · devin      —— Devin API/MCP session 详情（一行 = 一个含 messages 的 session）
   └─ dream-collect --source <源> （collector.py）
        ├─ 归一化（_NORMALIZERS[源]）+ 脱敏
        ├─ <store>/<date>/<源>-<session>.jsonl  （正文，gitignore）
        ├─ <store>/manifest.jsonl               （元数据，可提交）
        └─ <store>/digest-<date>.md             （脱敏摘要，可提交）
```

各源原始 jsonl 的字段是容错解析的：缺字段走合理回退（session_id/ts/repo 都有兜底），
无可读文本的行（纯 summary / 空 content）自动跳过。

## 用法

1）让常驻飞书 bot 产出燃料（默认关闭，避免改变 B-S0 回声行为）：

```bash
# 用 flag 开启（或设 env FEISHU_TRANSCRIPT_LOG）
python3 -m intelligence.cli feishu-bot --transcript-log ~/feishu-bot-bs0/transcripts/feishu-events.jsonl
```

2）采集归一化 + 脱敏 + 摘要：

```bash
python3 -m intelligence.cli dream-collect \
  --events ~/feishu-bot-bs0/transcripts/feishu-events.jsonl \
  --store-dir <知识库>/raw/transcripts \
  --json
```

3）仅重建当日摘要（不读 events）：

```bash
python3 -m intelligence.cli dream-collect --store-dir <store> --digest-only
```

## 采集半（nightly / launchd）

`dream-nightly` 把「采集 + 提交脱敏 digest」串成每晚一跑的采集半（设计 §1/§4）：

```bash
python3 -m intelligence.cli dream-nightly \
  --repo-dir ~/dream-loop-repo \                       # 专用 clone，须独立于用户工作区
  --events ~/feishu-bot-bs0/transcripts/feishu-events.jsonl \
  --source feishu --push --json
```

流程：从最新 `origin/main` 切出 `dream-loop/transcripts-<date>` 分支 → 采集进
`<repo-dir>/raw/transcripts/` → **只显式提交** `manifest.jsonl` + `digest-*.md` →
（`--push` 时）push 该分支。**绝不合并 main、绝不在 base/用户工作分支上提交、绝不提交正文 jsonl、不碰 DuckDB。**
正文按 `.gitignore` 的 `raw/transcripts/*/*.jsonl` 忽略，代码里再加一道显式白名单（双保险）。

安全要点：
- `--repo-dir` 必须是**专用** clone，**不要**用 Mac 工作区 `/Users/lbq/Desktop/c c/金融`
  （那是 `evolve/strategy-engine-20260615` 分支，铁律不可碰）。
- `--push` 需要该 clone 的 `origin` 已配置可写凭证（PAT 走 credential helper / `~/.netrc`，
  **切勿把 PAT 写进入库文件**），且已 `git config` 提交身份。
- 合并 `dream-loop/transcripts-<date>` 分支由用户 / 推理半（C-1B-S2）PR 决定，采集半永不自动合并。

### launchd 安装（Mac，每晚 03:30）

模板 `com.financeworkspace.dream-collect.plist`，替换三处占位后安装：

```bash
PY=$(which python3); REPO=~/dream-loop-repo
EVENTS=~/feishu-bot-bs0/transcripts/feishu-events.jsonl
mkdir -p "$REPO/logs"
sed -e "s#__PYTHON__#$PY#g" -e "s#__DREAM_REPO__#$REPO#g" -e "s#__EVENTS__#$EVENTS#g" \
  intelligence/dream/com.financeworkspace.dream-collect.plist \
  > ~/Library/LaunchAgents/com.financeworkspace.dream-collect.plist
launchctl load ~/Library/LaunchAgents/com.financeworkspace.dream-collect.plist
```

> 部署前提：在 Mac 上为采集半建一个**专用** clone（独立于用户工作区），配好可写 `origin` 与提交身份；
> 该 clone 需含 `intelligence/`（才能 `python3 -m intelligence.cli dream-nightly`）。本仓代码不依赖 DuckDB。

## store 目录解析顺序

1. `--store-dir`
2. env `DREAM_TRANSCRIPT_STORE`
3. 知识库 `raw/transcripts`（由 env `KNOWLEDGE_WIKI` 推导，或 Mac 默认 `/Users/lbq/Desktop/c c/知识库`）
4. 回退到本仓 `intelligence/dream/_local_store/`（已 gitignore，仅本地验证用）

> 设计上 transcript store 归属 `knowledge-base-private`（`raw/transcripts/`）。collector 代码放在本仓、
> store 目录可配置，便于本地用临时目录验证；接入知识库仓时把 `--store-dir` 指向其 `raw/transcripts/` 即可，
> 并在知识库仓 `.gitignore` 中忽略 `raw/transcripts/*/*.jsonl` 正文（保留 manifest.jsonl 与 digest-*.md）。

## 脱敏说明

`collector.redact()` 覆盖：GitHub PAT、`sk-` 类 key、AWS AKID、`Bearer` token、`-----BEGIN ... PRIVATE KEY-----`、
`api_key=/secret:/token=/password=` 赋值式密钥（保留键名、掩码值）、邮箱、中国手机号、身份证号，以及
`持仓/仓位/建仓/清仓/成本价/买入价/盈亏...` 等持仓关键词后的内容。S0 保守地对**正文与 digest 都脱敏**，
保证任何可提交物（manifest / digest）都不含密钥或持仓明文。

---

# dream-loop · 推理半之 7A/7B（C-1C）

> 决策 1 的**推理半**编排：在采集半产出 digest 之后，把「策略调参建议」与「KB 事实回写候选」
> 都做成 **suggest-only + 分支 PR + 等用户确认才合** 的产物，绝不自动改 `params.json`、绝不写
> entity 正文、绝不起第二个 DuckDB 写进程。

## 7A · `evolve.py suggest` 夜间编排（`evolve_suggest.py` / CLI `dream-evolve-suggest`）

每晚（错峰，建议 03:45，晚于采集半 03:30）**只读**跑 `scripts/evolve.py suggest`：

- `evolve.py suggest` 用 `connect(read_only=True)` 读 `evolution/records/` + DuckDB，产出
  `evolution/suggestions/suggestion-<ts>.md`，**从不写 `params.json`**（设计原则「suggest 只建议」）。
- 编排做的事：跑前后快照 `evolution/suggestions/`，**只有出现新增** `suggestion-*.md` 才从 `main`
  切 `dream-loop/evolve-suggest-<date>` 分支，**白名单 `git add -f` 仅这些新增 `suggestion-*.md`**
  （该目录被 `.gitignore`，故用 `-f`），commit `[dream-loop] evolve suggest <date>`，可选 `--push`。
- **DB 锁现实**：Mac 上 DuckDB 回填写进程持排他锁时，`read_only` 打开会失败 → 编排**优雅跳过**
  （no-op，不崩），`skipped_reason` 标 `db-locked` / `duckdb-unavailable` / `db-missing` 等。
- **红线**：绝不 stage `evolution/params.json`（`stage_suggestions` 白名单 + 提交前复核双保险），
  绝不合并 main，绝不起第二个 DuckDB 写进程（只读）。

```bash
# 跑一次（本地 commit，不 push）
python3 -m intelligence.cli dream-evolve-suggest --repo-dir <专用clone> --json
# 夜间自动（提交并推分支，等用户 review 合 main）
python3 -m intelligence.cli dream-evolve-suggest --repo-dir <专用clone> --push
# 按用户 overlay（写 evolution/users/<id>/suggestions）
python3 -m intelligence.cli dream-evolve-suggest --repo-dir <专用clone> \
  --user <id> --suggest-subdir evolution/users/<id>/suggestions
```

安装 launchd（Mac）：把 `com.financeworkspace.dream-evolve-suggest.plist` 里的 `__PYTHON__`
（`which python3`）、`__DREAM_REPO__`（**独立**于用户工作区的专用 clone，勿用 evolve 分支工作区）
替换后拷到 `~/Library/LaunchAgents/` 再 `launchctl load`。`--repo-dir` 的 `origin` 须配好可推。

## 7B · KB 事实回写候选 payload 生成器（`kb_candidates.py` / CLI `dream-kb-candidates`）

把（**已脱敏的**）digest/lessons 候选条目转成**保守**的 KB 事实回写候选 payload，对齐
`<知识库>/wiki/raw/entity-delta-backfill/*.entity-delta.json` 的 `updates` 条目 schema，供人工 review。

**红线（写死，输入无法覆盖；`validate_payload` 硬门）**：

- `graph_only=true` / `exposure_only=true`（只进图谱与暴露索引，**绝不写 entity 正文**）
- `update_type=review_candidate`、`evidence_layer=L1_L3_candidate`、`tier=peripheral`（AGENTS 的
  `core/related/peripheral` strength，候选一律最弱）、`create_missing=false`（不自动新建 entity 页）
- 文本字段兜底再脱敏一次；`validate_payload` 拒绝任何翻转红线、含硬正文键
  （`entity_markdown`/`body`/`md`/…）或泄漏扫描命中的 payload。

```bash
python3 -m intelligence.cli dream-kb-candidates --input candidates.json --json
```

输入 `candidates.json`：

```json
{
  "source_name": "dream-2026-06-17",
  "source_date": "2026-06-17",
  "raw_sources": ["raw/transcripts/2026-06-17/digest-2026-06-17.md"],
  "candidates": [
    {"company": "某公司", "judgment": "边际订单改善（线索）", "concepts": ["液冷"],
     "chain_layer": "midstream", "role": "服务器液冷模组", "evidence": "digest 溯源"}
  ]
}
```

输出目录解析顺序：`--kb-dir` > env `KB_CANDIDATES_DIR` > 本仓 gitignore staging
`intelligence/dream/_kb_candidates/`（默认，安全回退）。文件后缀用 `.dream-candidate.json`
（**不**匹配人工回填 `*.entity-delta.json` glob，绝不会被 `--apply` 误吃）+ 追加
`dream-candidates-manifest.jsonl`。

> ⚠️ **schema 待 KB 访问后最终校验**：本仓与知识库 `scripts/ingest.py` 非同源；payload 字段按
> 知识库现有 `wiki/raw/entity-delta-backfill/*.entity-delta.json` 的 `updates` 条目实测建模
> （company/code/date/title/judgment/concepts/role/chain_layer/tier/confidence/evidence_layer/
> exposure_only/graph_only/bullets/evidence），并统一带 `schema_status="pending-kb-verify"`。
> 接入真实库前，请先用 1 个样例 payload 过一遍知识库侧的校验/lint。

---

# 可证伪点夜间回检（C 方案）· `checkpoint recheck`

> foresight 的 C 方案（可证伪点登记 → 到期回检打分 → 二阶推演校准）需要有人**到期把判断核对一遍**。
> 这一步挂进同一套夜间 cron：每晚跑 `checkpoint recheck --apply`，把到期点交给 resolver 拉数核对，
> 落 verdict 到 `users/<id>/verdicts.jsonl`，下次 foresight 自动按类别胜率注入校准。

与采集半 / 推理半**本质不同**——本任务**不碰 git、不切分支、不 commit、不 push**，只更新本地
gitignore 的 `verdicts.jsonl`。所以它跑在**你的工作区仓库本身**（含 `db/market_feature_store.duckdb`
与 `intelligence/` 包），而不是采集半那个专用 clone；无 git 操作，工作区安全。

- 盘面侧（`stock_return`）：本机有 DuckDB 才出真数；缺库 / 查询失败 → 自动降级 `unverifiable`
  （非终态、不计入胜率、绝不编造），下次重跑即判定。
- 知识库侧（`kb_evidence`）：读 `wiki/relations/`，云端也在仓里，随处可跑。
- 无机检规格（`manual`）：留给 `checkpoint score` 人工打分，回检会标 `unverifiable`、不强判。

先手动跑一次确认（不带 `--apply` 只预览；带 `--apply` 才落盘）：

```bash
python3 -m intelligence.cli checkpoint recheck --user <id>            # 预览到期点判定
python3 -m intelligence.cli checkpoint recheck --user <id> --apply    # 落 verdicts.jsonl
python3 -m intelligence.cli checkpoint calibrate --user <id>          # 看校准聚合
```

### launchd 安装（Mac，每晚 03:50，错峰）

模板 `com.financeworkspace.checkpoint-recheck.plist`，替换占位后安装：

```bash
PY=$(which python3)
WORKSPACE=~/finance-workspace-private          # 含 intelligence/ 与 db/market_feature_store.duckdb 的工作区
USER_ID=linxiaoqi5111                          # 你的 foresight 用户 id
KB_WIKI="$HOME/Desktop/c c/知识库/wiki"        # kb_evidence 回检用；按你的真实路径改
USERS_DIR="$HOME/Desktop/c c/知识库/.foresight"  # 只有跨机同步大脑才填，且须与交互 session 同一路径
mkdir -p "$WORKSPACE/logs"
sed -e "s#__PYTHON__#$PY#g" -e "s#__WORKSPACE__#$WORKSPACE#g" -e "s#__USER__#$USER_ID#g" \
    -e "s#__KNOWLEDGE_WIKI__#$KB_WIKI#g" -e "s#__FORESIGHT_USERS_DIR__#$USERS_DIR#g" \
  intelligence/dream/com.financeworkspace.checkpoint-recheck.plist \
  > ~/Library/LaunchAgents/com.financeworkspace.checkpoint-recheck.plist
launchctl load ~/Library/LaunchAgents/com.financeworkspace.checkpoint-recheck.plist
```

> - **不跨机同步大脑**：删掉 plist 里 `EnvironmentVariables` 的 `FORESIGHT_USERS_DIR` 那对
>   `<key>/<string>`（cron 自动用仓库内默认台账），上面 sed 的 `__FORESIGHT_USERS_DIR__` 那段也省掉。
> - **跨机同步**：`USERS_DIR` 必须与你交互跑 `foresight` 时用的 `FORESIGHT_USERS_DIR` 完全一致，
>   否则 cron 会回检另一份空台账。
> - 验证：`launchctl list | grep checkpoint-recheck`，日志看 `$WORKSPACE/logs/checkpoint-recheck.*.log`。
>   想立刻跑一次验证：`launchctl start com.financeworkspace.checkpoint-recheck`。

## 测试

```bash
python3 -m unittest discover -s intelligence/tests -p "test_*.py"
# 7A/7B 专项：DB / duckdb 缺席也能跑（优雅跳过、白名单 staging、红线拒绝、泄漏扫描）
python3 -m unittest intelligence.tests.test_evolve_suggest intelligence.tests.test_kb_candidates
# C 方案夜间回检 plist 模板自检（well-formed + 命令/调度正确）
python3 -m unittest intelligence.tests.test_checkpoint_cron
```
