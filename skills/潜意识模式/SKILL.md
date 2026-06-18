---
name: 潜意识模式
description: 可开关的会话级记忆巩固模式——开启后由 foresight 主动发问、你多轮追问，退出时把整段对话「回读」成结构化信号，先给 diff 等你确认，确认后双层落盘（机器层 interactions.jsonl 喂亲和度 + 人类层 Obsidian 沉淀 vault 日志，你读/改/看演化）。触发词：开启潜意识模式、潜意识模式、进入潜意识、退出潜意识、收工、回读对话、巩固记忆、沉淀这轮、记进沉淀、潜意识开关。
---

# 潜意识模式（会话级记忆巩固）

一个**用户开关**：你说「开启潜意识模式」它就进入，之后多轮对话；你说「退出/收工」它就**回读整段对话**，把信号双层落盘。它补上「快回路（每轮 inline 记）/ 慢回路（周期 refresh-profile）」之间缺的那一环——**一次完整对话结束时整体消化一遍**。

## 双层记忆（核心，别合并）

- **机器层 = `intelligence/users/<id>/interactions.jsonl`**：算法燃料，确定性，喂 `foresight` 亲和度排序（半衰期 14 天）。
- **人类层 = Obsidian「沉淀」vault** 的 `潜意识/<session>.md`：带 `[[题材]]` 反链的叙事日志，你读 / 改 / 看演化（**独立于**金融 Concept 知识库 vault）。路径走 env `SUBCONSCIOUS_VAULT` 或 `--vault`，不写死。

## 三条护栏（沿用仓库基因）

1. **绝不静默落盘**：退出时先 `review` 出「记忆提案」diff，你确认了才 `commit --apply`。
2. **真相源单向**：jsonl → Obsidian 自动写；反向（你在 Obsidian 里钉/改 → 升级「钉住画像」）走显式确认，不双向自动同步。
3. **user-id 固定**：必须定 `--user`（或 env `FORESIGHT_USER`），不固定会把记忆记串到 `default`。

## 跨机同步（两机一个大脑）

机器层（`interactions.jsonl` 等）默认落在仓库 `intelligence/users/<id>/`，`git pull` **不会**带过去（已 gitignore）。要让两台机器共享同一个大脑（profile / 派生画像 / 问题记忆 / interactions / 会话 buffer 全跟随），设环境变量 `FORESIGHT_USERS_DIR` 指向云同步盘里的隐藏目录（Obsidian 不显示 `.` 开头目录），两机都这样配：

```bash
export FORESIGHT_USER=<id>
export SUBCONSCIOUS_VAULT=~/路径/到/沉淀vault
export FORESIGHT_USERS_DIR="$SUBCONSCIOUS_VAULT/.foresight"   # 大脑目录随 vault 一处云同步
export KNOWLEDGE_WIKI=~/路径/到/知识库/wiki              # 可选：让 foresight 发问时主动调知识库题材
```

设了 `KNOWLEDGE_WIKI`（含 `relations/theme_signals.json`），`foresight` 发问时会把知识库里**认知最靠前/近期有新事件**的题材当发问素材（带 ★评级/进度/Tier/事件日期），让追问围绕你自己沉淀的认知发酵进度展开。没设/没该文件则优雅降级（只用盘面快照+画像），不报错。也可用 `foresight --kb-wiki <wiki> ...` 显式指定，或 `--no-kb` 关闭。

vault 用 Obsidian Sync / iCloud / 坚果云等同步，两机即自动共享。不设 `FORESIGHT_USERS_DIR` 则保持单机（仓库内）。`subconscious start` / `status` 会打印「大脑目录」并标注是否跨机同步。

## 流程（在仓库根目录运行）

### 1）开启
```bash
python3 -m intelligence.cli subconscious start --user <id> --vault "$SUBCONSCIOUS_VAULT"
# 开启后可先 `foresight --user <id>` 让它主动抛追问，再开始多轮对话
# 设了 KNOWLEDGE_WIKI 则 foresight 自动把知识库题材当发问素材；也可显式 `foresight --user <id> --kb-wiki <wiki>`
```

### 2）多轮对话里逐轮记信号（确认前**只进 buffer**，不进 interactions.jsonl）
你针对某题材/个股表态、或挑中/否掉 foresight 的某条问题时，**主动**记一条 buffer：
```bash
python3 -m intelligence.cli subconscious note --user <id> --kind click \
  --theme 液冷 --stock 中际旭创 --question "液冷渗透率拐点对中际旭创毛利率意味着什么" \
  --quote "这个方向我想深挖一下"
python3 -m intelligence.cli subconscious note --user <id> --kind dismiss --theme 钠电
```
`--kind` 沿用 foresight-feedback 映射：click +1.0 / follow +1.5 / pin +2.0 / ask +1.2 / view +0.3 / skip −0.5 / dismiss −1.0 / mute −1.5 / rate（配 `--rating 1~5`）。题材/个股提取规则同 foresight-feedback：只记具体题材/个股，领域（宏观/AI/半导体）不当题材记。

**沉淀日志要"有内容"——把发问和深挖结论也记进 buffer，不止记信号。** 信号（`--kind`）只是喂算法的燃料；人类层日志（你读/回看的那篇）要靠下面这两块才长出可读正文：

- **每条 foresight 抛出的追问 → 用 `--question` 记一次**（无需用户表态也记，留痕进「它问我的（foresight）」节）。一次 `note` 一个问题；多条追问就多 `note` 几次（可只带 `--kind ask --question "…"`，不带题材/个股也行）。
- **用户深挖某方向、你给出实质推演时 → 用 `--memo` 把结论压缩成结构化纪要记一次**（进「深挖纪要」节）。`--memo` 是自由 markdown 文本，建议固定三段：**核心判断**（1~2 句）、**可证伪点/关键指标**（带验证时点）、可选**跨域连接**。不要把整段长推演原文塞进去，提炼要点即可。

```bash
# 把刚抛的 3 条追问留痕（即使用户只挑了其中一条深挖）
python3 -m intelligence.cli subconscious note --user <id> --kind ask --theme 液冷 \
  --question "液冷供应链会否出现'一次侧泵过剩、二次侧阀件卡脖子'的结构性错配？"
python3 -m intelligence.cli subconscious note --user <id> --kind ask --theme 铜箔 \
  --question "HVLP铜箔供需缺口会否从'技术可行'转向'产能瓶颈'？"
# 用户说"液冷这个我想深挖" → 记信号 + 把你的深挖结论压成纪要
python3 -m intelligence.cli subconscious note --user <id> --kind click --theme 液冷 \
  --quote "液冷这个我想深挖" \
  --memo $'**核心判断**：一次侧泵(冰轮)已突破、二次侧阀件卡脖子，2026Q3 是估值切换关键窗口。\n**可证伪点**：冰轮二次侧 UL 认证(8月底)、GB200 机架功率密度(7月实测)。\n**跨域**：液冷×铜箔——液冷高纯铜管与 HVLP 铜箔争用铜资源。'
```
`--question` / `--memo` 都按原文去重（同义重复只保留一条），所以放心多记不会重。

### 2.5）你纠正它时 → 记一条纠偏（高信号，立刻生效、不进 buffer）
当你**不满意它的回答并纠正它**（口径错了、把软推演当硬事实、二元下结论、漏了证据分层、问得太泛……），
记一条纠偏。这条**不靠点击猜你喜欢哪个题材**（深挖≠偏好、市场动态），只靠你的**显式纠正**学方法论；
和 buffer 信号不同，它**直接落 `users/<id>/corrections.jsonl`、不走 review/commit**，下次 `foresight` 发问自动带上「别再犯」。
```bash
python3 -m intelligence.cli record-correction --user <id> \
  --correction "先判断板块走到哪一阶、强到哪一档再下结论，不要会/不会二元定论" \
  --original "氟化工要爆发了"  --principle "分级不二元"  --theme 氟化工
```
`--correction`（必填）= 你纠成什么；`--original`= 它原来的错法；`--principle`= 抽象出的可复用原则（最该被记住）；`--theme` 可多次。
发问前注入的还有**思考宪法** `intelligence/foresight_methodology.md`（入库、可编辑）——你的 7 条元思路+证据分层+发问落点；改这个文件就改它发问的脑子，无需动代码。`foresight` 渲染头部会显示「方法论：注入思考宪法 N 字 · 带 M 条纠偏」确认生效。

### 3）退出回读 → 出 diff（只读，不落盘）
```bash
python3 -m intelligence.cli subconscious review --user <id>
```
它把 buffer 按 (题材/个股, kind) **去重聚合**（重复同向只记一次、count 标 ×N），列出机器层将写哪些反馈 + 人类层日志路径预览。

### 4）确认后双层落盘
```bash
python3 -m intelligence.cli subconscious commit --user <id> --vault "$SUBCONSCIOUS_VAULT" --apply
# 不加 --apply 等同 review（只预览）
```
落盘后 buffer 归档（`<session>.buffer.done.jsonl`）、active 标记清除；下次 `foresight --user <id>` 即生效（命中题材/个股的问题排到前面，并标「反馈加成」可解释说明）。

### 看状态
```bash
python3 -m intelligence.cli subconscious status --user <id>
```

## 与现有件的关系（80% 复用）

- 信号权重 / 亲和度：复用 `intelligence/services/interactions.py`（同一套 KIND_WEIGHTS、record_interaction）。
- 用户命名空间：复用 `intelligence/userspace.py`（`--user` → `users/<id>/`）。
- 主动发问：复用 `foresight`（开启后开场抛追问、记忆回路去重；设 `KNOWLEDGE_WIKI`/`--kb-wiki` 后把知识库 `theme_signals` 题材当发问素材）。
- 本 skill 真正新增的只有：**模式开关 + 会话级回读巩固（consolidation）+ Obsidian 沉淀日志写入**，逻辑在 `intelligence/services/subconscious.py`。

## 护栏细则

- **一次表态只记一笔**：同一句话别重复 `note`；重复表达同一意图聚合后也只写一次。
- **模糊先问再记**：题材/个股指代不清、强度（click vs follow/pin）拿不准，先一句话确认再 `note`。
- **不臆造**：用户没表态就不记；只记真实信号。
- **vault 安全**：`SUBCONSCIOUS_VAULT` 没设时落到 `users/<id>/_vault`（已 gitignore，仅验证用）；真实落地必须显式指向你的沉淀 vault。
