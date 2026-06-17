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
