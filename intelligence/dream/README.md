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
