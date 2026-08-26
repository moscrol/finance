# 设计：dream loop 重定向——Workbench 会话夜间挖掘（dream-mine P0）

- 日期：2026-08-26
- 状态：**v1.0 · P0 已实施**（分支 `feat/dream-mine-p0`，基 `gitea/main@6c47450e`。落地物：collector `workbench` 源 + `intelligence/dream/miner.py` + CLI `dream-mine` + `com.financeworkspace.dream-mine.plist` + `test_dream_mine.py` 11 例。真实数据冒烟：485 会话索引 / 3 天窗口 31 选中 / 64 条脱敏入库 / `--no-llm` 降级路径正确。P1 前置条件与杀死条件见 §5，未部署 launchd——装载即视为 P0 上线、杀死条件计时开始）
- 来源：2026-08-26 全仓闭环盘点对话（逐环验尸：捕获端摩擦决定环的死活）+ 本机现场核验（工作树 `feat/reading-rules-baseline-batch1@5f236d78`，生产台账 `~/.local/share/finance-workbench/users/linxiaoqi5111/`）。
- 代码树纪律：从 `gitea/main` 开干净树 `feat/dream-mine-p0`。**禁止**在主检出脏树改 `intelligence/`；本稿文档本身允许落主树（untracked）。不动 8792 / 8796 生产配置——miner 不经 server，直接读文件。

## 0. 一句话

dream loop 原设计（飞书对话夜间采集→摘要→建议 PR）的燃料源已退役、两个输出路径被别的活机制覆盖，但它瞄准的问题——**把「沉淀」从要用户自觉改成夜间自动**——正是全系统最弱的半环（潜意识 judgments 仅 1 条、foresight interactions 停在 07-07）。本单把 collector 的燃料换成 Workbench 会话存储（485 个会话躺着没挖过），挖掘产物**只进潜意识提案 buffer + vault 人读 md**，人工 `subconscious commit` 才落台账——把「潜意识」从"你得记得开 session"翻转成"每晚自动提案、你只管批"。

**判别变量**（验收只锁这一条）：夜跑后 `<vault>/潜意识提案/<日期>.md` 存在且含 ≥1 条带 `conv_id` 溯源、引句已脱敏的候选判断；无人工 `commit --apply` 时 `judgments.jsonl` / `interactions.jsonl` **字节不变**（suggest-only 成立）；同窗口重跑 miner 不新增 buffer 行（幂等）；无 LLM key 时提案数=0 且降级标记可见。不是「digest 更长」，不是「多了个夜跑」。

人话：以前是让你睡前自己写日记（没人坚持得下来）；现在是管家半夜把你白天说过的话里值得记的挑出来、写成便签放在桌上，你早上花一分钟决定哪几张贴进本子。管家绝不直接往本子里贴。

## 1. 范围

### 1.1 做（P0）

- `intelligence/dream/collector.py` 新增 `workbench` 源：`KNOWN_SOURCES` 加项 + `_NORMALIZERS["workbench"]` + 目录读法 `read_workbench_conversations(conversations_root, since_days)`（现有 `read_events` 是单文件模型，workbench 是目录扫描，二者并存）。`messages.jsonl` 每行 → `TranscriptRecord(ts=created_at, source="workbench", session_id=conversation_id, role, text=content, tags=["workbench"])`；跳过 `status!="completed"` 或空 content 的行；入 store 前过既有 `redact()` 硬门。store 布局 / manifest upsert / digest / sort_keys 幂等**一字不改复用**。
- 新增 `intelligence/dream/miner.py` + CLI 子命令 `dream-mine`：对窗口内新增/更新会话跑一遍 LLM 挖掘，产出候选信号，逐条 `subconscious.append_signal(us, session_id=f"dream-{date}", ...)` 入 buffer（**显式 session_id，不动 active 标记**），同时写 vault 人读 md `潜意识提案/<日期>.md`（每条候选带 conv_id 溯源 + 已脱敏引句）。
- 挖掘目标：**只挖 role=user 的表达**（判断、兴趣、否定、纠偏语气、反复追问的主题）以及用户对 assistant 结论的明确采纳/拒绝；字段对齐 `append_signal` 既有签名（kind/themes/stocks/question/quote/memo/weight）。
- 增量水位：`conversation.json` 的 `updated_at` 字段（不是 mtime），游标存 store 侧 `mining-manifest.jsonl`（按 `(conversation_id, updated_at)` 去重）；buffer 侧按 `(session_id, conv_id, memo哈希)` 判重，重跑不重复提案。
- 预算硬编码：默认窗口近 7 天、每晚 ≤40 个会话、每会话送 LLM 前声明式截断（限定语排在被限定内容之前，KIT 模式）；历史 485 会话的回填走显式 `dream-mine --backfill --from --to` 分批命令，不进夜跑。
- LLM：复用 `llm_refine` provider 配置；严格 JSON 输出 + 解析失败丢弃该会话（`forecast_learning.sync_reflections` 先例）；**无 key → 只落 store+digest，提案数 0，降级标记写进 md**，绝不启发式编造判断。
- launchd：`com.financeworkspace.dream-mine.plist`，每晚 **04:05**（错峰：03:50 checkpoint-recheck 已装）。跑在工作区本身，**不碰 git**（checkpoint-recheck 先例，不是 dream-nightly 那套专用 clone + 分支推送）。
- 人工收口零新造：`subconscious review --session dream-<date>` / `subconscious commit --session dream-<date> --apply` 一字不改复用。commit 落三处（interactions + judgments + vault）→ foresight 既有回灌线自动生效。

### 1.2 不做

- **不自动写 judgments / interactions / corrections / 画像**——提案只有人工 `commit --apply` 才进台账。这是本单的存在前提，违反即整单作废。
- 不做 web 审批面（P1，见 §5；有前置条件）。
- 不做 foresight 追问的 per-click 反馈捕获——那是另一单（Workbench 前端埋点），与本单正交；本单经 commit 顺带写 interactions 只是副产品，不替代它。
- 不改 `foresight_followups` 生成、不动 Engine A 记忆注入（推/拉之争另议，先量 `memory_lookup` 生产触发率）。
- 不挖 assistant 的结论当用户判断；不挖 role=assistant 单方面输出。
- 不部署 `dream-nightly`（git 编排）、`dream-evolve-suggest`（7A）、`dream-kb-candidates`（7B）——处置见 §7。
- 不删既有五源 normalizer 与其测试（无害、有覆盖）。
- 不碰 DuckDB、不碰 sqlite（`workbench.sqlite3` 不读——会话正文在纯文件里已够用）。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **挖掘（mine）** | LLM 从已脱敏 transcript 里抽用户判断/兴趣候选，产物是**提案** | 自动记忆写入；摘要（digest 是另一物，继续产） |
| **提案（proposal）** | 潜意识 buffer 里的未确认信号行 + vault md 人读版 | 台账记录（只有 commit 后才是） |
| **水位（watermark）** | `conversation.json.updated_at`，增量挖掘的游标 | 文件 mtime（迁移/同步会打乱） |
| **杀死条件** | 预先声明的证伪判据，触发即退役本环 | 失败惩罚；KPI |

## 3. 已核实事实（2026-08-26 现场核验，实施时不要再探一遍）

1. `intelligence/dream/collector.py::KNOWN_SOURCES` = `("claude-code","claude-mem","windsurf","feishu","devin")`，**无 workbench**；主燃料源飞书 bot 已退役（exit 2 shim）。normalizer 契约：一行原始 dict → `list[TranscriptRecord]`；`TranscriptRecord.to_json_line` 用 `sort_keys` 保证字节幂等；store 布局 `<store>/<date>/<source>-<session>.jsonl` + `manifest.jsonl`（按 (date,source,session) upsert）+ `digest-<date>.md`。
2. `collector.resolve_store_dir` 默认链含**陈旧硬编码** `/Users/lbq/Desktop/c c/知识库`（本机 `/Users/a77` 不存在该路径 → 静默回退 `intelligence/dream/_local_store`）。部署**必须**显式 `--store-dir` 或 env `DREAM_TRANSCRIPT_STORE`，不得依赖默认链。
3. Workbench 会话存储是纯文件：`~/.local/share/finance-workbench/users/<id>/conversations/conv_*/conversation.json`（含 `conversation_id/user_id/title/status/created_at/updated_at/summary/last_run_id`）+ `messages.jsonl`（每行含 `message_id/role/content/created_at/status/run_id/followups/citations/...`）。2026-08-26 实数 485 个会话。server 对 messages.jsonl 是 append 写，逐行容错读安全（collector 已有跳坏行先例）；`conversation.json` 读失败跳过该会话即可。
4. `intelligence/services/subconscious.py::append_signal` 接受显式 `session_id`，`_resolve_session` 命中显式值时**不读不写 active 标记**——夜间写 `dream-<date>` 会话不劫持用户手动模式。`review`/`commit` CLI 均有 `--session` 参数。
5. `subconscious.commit` 落三处：`interactions.jsonl`（逐 row `record_interaction`）+ `judgments.jsonl`（`record_judgment`，foresight 下轮发问的输入）+ vault md（`VAULT_SUBDIR/<session>.md`）；`archive_session` 收尾归档 buffer。**即：本单复用 commit 即顺带补 interactions 台账（现停 07-07）。**
6. 「LLM 严格 JSON 产候选 + 启发式回退 + 文件落盘 + 人工 approve」已有活先例：`intelligence/services/forecast_learning.py::sync_reflections` + `approve_reflection` + web 面 `/api/workbench/learning-feedback`（`intelligence/api/app.py:2802-2855`）。P1 扩审批面时照此模式，不另造。
7. 夜间任务「跑在工作区、不碰 git、写本地 gitignore 台账 + vault 人读 md」先例：checkpoint-recheck（launchd 已装、上次退出码 0、verdicts 104 条）。
8. 消费现状基线（本单的证伪对照组）：judgments 1 条（08-18）、interactions 8 条（停 07-07）、corrections 104 条（活跃）、7A 仅 2026-06-18 一份产出、7B 零实迹、dream 采集半 launchd 从未安装。
9. 7B 职能已被覆盖：daily-agent 每日产 `market_feature_store/exports/YYYY-MM-DD-kb-ingest-queue.json`（08-25 仍在产），知识库侧接收器 `scripts/kb_ingest_queue.py`（validate/preview/receive）。
10. Engine A 生产注入面现状（本单不动，仅记档）：`conversation_orchestrator.py:1862` 推送视角；记忆仅 `memory_lookup` 拉取 + `prior_recall` 可选槽（`episode_factory.py:404` 注释，其「judgments/corrections 全为空」前提已部分老化——corrections 现有 104 条）。

## 4. P0 数据流

```
conversations/conv_*/{conversation.json,messages.jsonl}   （只读，485 会话）
  → collector workbench 源（归一化 + redact 硬门 + store/manifest/digest，全复用）
  → miner（LLM 严格 JSON 挖 user 侧判断/兴趣；水位=updated_at；预算+声明式截断）
  → 提案落点（三处，全部 suggest-only）：
      a) subconscious buffer  session=dream-<date>   （append_signal，显式 session）
      b) <vault>/潜意识提案/<日期>.md                （人读，带 conv_id 溯源；事实投递>提醒）
      c) mining-manifest.jsonl                        （幂等游标）
  → 人工：subconscious review/commit --session dream-<date> --apply   （一字不改）
  → judgments.jsonl + interactions.jsonl + vault 沉淀 → foresight 既有回灌线
```

## 5. 阶段与前置条件

| 阶段 | 内容 | 前置条件 |
|---|---|---|
| **P0**（本单） | workbench 源 + miner + 夜跑 + CLI 收口 | 用户批本稿 |
| **P1** | learning-feedback web 面扩「记忆提案」审批（approve 调 `subconscious.commit` 语义） | **P0 上线后连续 2 周有 ≥1 次真实 `commit --apply`**；否则不建 |
| **P2** | 7B 退役标注（KB 类候选改走 kb-ingest-queue 既有格式与接收器）；7A 标注按需（strategy-evolve skill 覆盖）；`dream-nightly` 标注飞书时代产物不部署；能力图谱回写 | P0 合并 |

**杀死条件（预先声明，下一个 agent 可直接执行）**：P0 上线后连续 4 周（≥20 个夜跑）无一次 `commit --apply`（judgments_written 累计=0），判死：卸载 plist、能力图谱标退役、回「方案 A 封存」。不许把杀死条件改成「再观察一阵」。

## 6. 红线

- 只读 conversations 目录；不写、不锁、不读 `workbench.sqlite3`。
- 脱敏在**入 store 前**（既有 redact 硬门）；提案 memo/quote 里出现 `[REDACTED:*]` 时保留掩码原样，不得复原、不得绕过。
- suggest-only：任何台账（judgments/interactions/corrections/画像）只接受人工 `commit --apply` 写入。
- 不碰 DuckDB；不 git（无分支无 commit 无 push）；不动 8792/8796。
- miner 的 LLM 调用带超时与预算，失败=该会话跳过并记 warning，绝不阻塞夜跑整体。

## 7. 失败形状（本页要挡住的）

- **自动落台账**：把 miner 做成直接写 judgments「反正都是它挖的」——那是把提案和记录合并，重蹈「自动回写」老坑；本单存在的前提就是人批。
- **依赖默认 store 路径**：`resolve_store_dir` 会静默落到 `_local_store` 或指向不存在的 `/Users/lbq/...`；必须显式传。
- **mtime 当水位**：迁移/备份/rsync 会重写 mtime；用 `updated_at` 字段。
- **一夜全量挖 485 会话**：预算失控 + 提案洪水（用户批不动=环死）；窗口与上限硬编码，回填走显式命令。
- **把 assistant 结论挖成用户判断**：污染画像的最快方式；只挖 user 侧表达与明确采纳信号。
- **提案洪水**：每晚 md 超过 ~10 条会让「批一分钟」变成「批半小时」，环照样死；miner 输出按置信度截断到每晚 ≤10 条，宁缺勿滥。

## 8. 能力图谱回写点（P0 合并后）

- dream 节点行：采集半补 `workbench` 源；新增「对话挖掘 miner」行（`intelligence/dream/miner.py::mine@<分支>`，合默认树后去 `@branch`）。
- 7A/7B/dream-nightly 三行改「已退役/按需」并注明接替指针（本稿 §5 P2）。
- 变更记录一条：燃料源从飞书换 Workbench 的一句话理由 + 杀死条件位置。

## 变更记录

- 2026-08-26 · claude · 首版草案。来源：全仓闭环盘点（活环/死环分界=捕获端摩擦）+ dream loop 冗余判定三问（输入源死了吗 / 输出被覆盖了吗 / 问题消失了吗）。
