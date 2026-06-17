# dream-loop · transcript store（C-1A-S0）

> 决策 1「dream loop」的**采集半 + 落盘**起点。本阶段（S0）只做最小切入：把**飞书** chat 一个源
> 归一化、脱敏后写入 transcript store，产出可提交的脱敏 digest。推理半（读摘要→开 suggest-only PR）
> 是后续阶段（Devin 定时 session，路线图 C-1B-S2），不在本目录。

## 这步做什么 / 不做什么

- ✅ 统一 transcript schema（每行 JSONL）：`{ts, source, session_id, role, text, repo, tags, redacted}`。
- ✅ 脱敏硬门：密钥 / token / 持仓 / PII 命中即打码（`[REDACTED:<类别>]`），并置 `redacted=true`。
- ✅ 落盘三件套：
  - `<store>/<date>/<source>-<session>.jsonl` —— 正文（已脱敏），**gitignore**，本地留存；
  - `<store>/manifest.jsonl` —— 每个 (date, source, session) 一条元数据，可审计、可提交；
  - `<store>/digest-<date>.md` —— 当日脱敏摘要，**可提交**，供推理半读取。
- ✅ 幂等：重跑产生字节一致的结果（manifest 按主键 upsert、`collected_at` 取桶内最大 ts）。
- ❌ 不接 claude-code / claude-mem / windsurf / devin 等其它源（S0 仅 feishu）。
- ❌ 不实现推理半、不开 Devin playbook/schedule、不自动合并 main。
- ❌ 不碰 DuckDB、不抢写锁。

## 数据流

```
飞书 bot（feishu_bot.py, --transcript-log 开启）
   └─ append 原始事件 jsonl（正文，本地，gitignore）
        └─ dream-collect（collector.py）
             ├─ 归一化 + 脱敏
             ├─ <store>/<date>/feishu-<session>.jsonl  （正文，gitignore）
             ├─ <store>/manifest.jsonl                 （元数据，可提交）
             └─ <store>/digest-<date>.md               （脱敏摘要，可提交）
```

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

## 测试

```bash
python3 -m unittest discover -s intelligence/tests -p "test_*.py"
# 7A/7B 专项：DB / duckdb 缺席也能跑（优雅跳过、白名单 staging、红线拒绝、泄漏扫描）
python3 -m unittest intelligence.tests.test_evolve_suggest intelligence.tests.test_kb_candidates
```
