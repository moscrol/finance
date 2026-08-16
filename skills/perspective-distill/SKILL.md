---
name: perspective-distill
metadata:
  pattern: workflow
description: 视角蒸馏——用户发来 KOL/博主原文，走固定闭环把方法论蒸馏进 Perspective Lab 画像（ingest → extract-cards → propose-patches → 逐条评审写回）。触发词：蒸馏视角、视角蒸馏、KOL蒸馏、学这个博主、喂文章、把这篇文章喂给视角、新建视角、perspective distill。注意：只切换/使用已有视角回答问题不用本 skill，直接在 Workbench 选视角即可。
---

# 视角蒸馏（perspective-distill）

用户发来博主原文（微信公众号/文章文本/链接）说「蒸馏视角」「学这个博主」时执行本流程。
目标是把**认知框架**（怎么判断、看什么变量、如何证伪）蒸馏进结构化画像，不是学口癖、
不是复述文章。

核心纪律（P0 起就定死的）：**事实层与认知层分离**——画像只是解释盘面的镜头（overlay），
不改写事实、不写知识库实体层；**LLM 只产候选，人工确认才写画像**（三道 fail-closed 闸：
引文逐字核验 ≥6 字、字段白名单、patch 人工门禁）。

- 服务代码：`intelligence/services/perspective_lab.py`（P0）+ `perspective_learning.py`（P1 学习闭环）
- 使用文档：`docs/learning/perspective-lab.md`（含 3.5 节学习闭环）
- 设计分期：`docs/superpowers/specs/2026-07-03-perspective-lab-design.md`

## 第 0 步：前置确认（别跳）

1. **用户空间是哪个**：生产 Workbench 读 `FORESIGHT_USERS_DIR`，而它的真值**只在
   启动器里**，别照抄本文档、也别信当前 shell 的环境变量——交互 shell 的
   `.zshenv`/`.zshrc` 导出的是另一个目录，裸跑 CLI 会写出一份生产读不到的副本
   （2026-08-13 sptfei 实测踩中：画像四篇齐全、patch 全过，Workbench 里那个视角
   压根不存在）。每次现查，不缓存结论：

   ```bash
   rg -n 'FORESIGHT_USERS_DIR' ~/.local/bin/start-finance-workbench   # 生产真值
   FORESIGHT_USERS_DIR="<上面查到的值>" python3 -m intelligence.cli perspective ...
   ```

   本机便捷入口（从 launcher 读根，默认 `--user default`）：
   `~/.local/bin/perspective-workbench <init|ingest|...>`

   不设环境变量时默认落 `intelligence/users/<user>/perspectives/`。**在 worktree 里
   跑同样会写出生产读不到的副本**——先确认写的是启动器那份。
2. **user 是哪个**：路径对了但 user 写错，视角照样不可见。用 Workbench
   实际登录的那个 user。本机 launcher **不设** `FORESIGHT_USER`，API/UI
   因此落 `default`（`userspace.resolve_user_id`）。不要用 shell 里的
   `linxiaoqi5111`（那是共享大脑身份），也不要信本段 08-14 的旧结论。
   每次先查：`curl -s http://127.0.0.1:8792/api/perspectives` 能列到的就是对的 user。
3. **角色 id**：已有角色（`perspective profile --perspective <id>` 能读到）就直接
   ingest；新角色先 init。id 用小写下划线（如 `sptfei`），display_name 存中文名。
4. **文章元信息**：每篇要有 date（发文日期）和 title；`--date` **缺省是今天**，
   旧文漏传会把证据日期全标成今天，后面评审无法判断是不是过期的单次观察。

```bash
python3 -m intelligence.cli perspective init --user <id> --id <角色id> --name "<博主名>" --type blogger
```

## 第 1 步：原文落盘（🚫 红线）

- 原文存成本地 md 再 ingest；**文章只本地私用，永不进 git**（`perspectives/` 已
  gitignore），报告里只允许短摘录——版权红线。
- 微信文章 WebFetch 常被拦「环境异常」；Mac/VM 上 `curl` 抽 `js_content` 可用。
  抽完人工瞄一眼开头结尾，确认不是半截页面。

```bash
python3 -m intelligence.cli perspective ingest \
  --user <id> --perspective <角色id> \
  --input /path/to/article.md --title "<标题>" --date YYYY-MM-DD --source "<博主名>"
```

内容哈希去重：同一篇改标题重传不会重复计数。<3 篇时画像置信度 low（只能作候选视角），
≥3 篇升 medium。

## 第 2-3 步：抽卡片 → 聚合 patch

```bash
# 逐篇抽结构化认知卡片（需 LLM key；失败明确报错、不写半成品，不会伪造卡片）
python3 -m intelligence.cli perspective extract-cards --user <id> --perspective <角色id>

# 聚合引文核验通过的候选 → pending patch（确定性、幂等、rejected 不复活）
python3 -m intelligence.cli perspective propose-patches --user <id> --perspective <角色id>
```

LLM 候选只能进四个字段：`opportunity_preferences` / `risk_triggers` / `anti_patterns` /
`falsification_style`。带结构或顺序语义的字段（`market_lenses` / `evidence_hierarchy` /
`reasoning_patterns`）**不走闭环**，见第 5 步。

## 第 4 步：逐条评审（本 skill 的核心判断工作）

```bash
python3 -m intelligence.cli perspective patches --user <id> --perspective <角色id> --status pending
python3 -m intelligence.cli perspective review-patch --user <id> --perspective <角色id> \
  --patch-id pp-xxxx --approve   # 或 --reject --note "理由"
```

评审判据（sptfei 实战沉淀，2026-08-13；positive 三门借鉴 colleague-skill 的
triple-gate，2026-08-16）：

| 判 | 形状 | 例 |
|---|---|---|
| ✅ approve | 脱离具体行情也成立的**可执行规则** | 「大幅缩量+支撑位+30分钟底背离才算回流确认」 |
| ❌ reject | **episodic**：夹带具体日期/个股的单次观察 | 「7月20日AI硬件高位分歧应减仓」 |
| ❌ reject | **宏观世界观**：立场表态，不可执行、不可证伪 | 「长期看好中国资产」 |
| ❌ reject | 与画像已有条目**同义**（幂等闸挡不住换措辞的重复） | — |

approve 前再过 **triple-gate 三门**（排除坏候选≠选对好候选，三门用来区分
「可执行但平庸」和「真正值得进画像」；三门不满足的拒绝理由写进 --note）：

| 门 | 问什么 | 拦住的失败形状 |
|---|---|---|
| 跨语境复现 | 该规则只在本文一个场景出现过吗？ | 单篇孤证被当成方法论 |
| 生成力 | 能推出博主没写过的**新**判断吗？ | 复述性条目——对了对，没有增量 |
| 独占性 | 换个普通分析师也会这么说吗？ | 通用教科书废话，谁都能说 |

agent 可以代评并逐条给理由，但要在回复里报告 approve/reject 清单；**最终认定权在用户**，
画像的 `known_gaps` 里标注「agent 起草待用户复核」，用户过目前不当作已确认的方法论。

## 第 5 步：结构化字段人工编辑

镜头（market_lenses）、证据层级（evidence_hierarchy）、推理模板（reasoning_patterns）
带顺序/结构语义，「追加」不成立，闭环不碰。做法：对照原文提炼，直接编辑 profile JSON，
并在 `known_gaps` 写明哪些是 agent 起草��改完 `perspective profile --json` 核对。

同属人工编辑字段的还有两个（2026-08-16 起 schema 原生支持，默认空列表）：

- **`contradictions`（已知矛盾）**：博主前后不一致的判断，格式建议
  `「<日期A>说 X；<日期B>说 Y（同周期同位置）」`。KOL 牛市喊多熊市喊空是常态，
  不记矛盾会蒸馏出一个「事后永远正确」的假人。运行时注入 prompt 并要求
  **使用时声明、不得抹平**。注意它天然是 episodic（带日期），所以永远不进
  patch 闭环——这正是闭环排除它的原因，不是缺口。
- **`honest_boundaries`（诚实边界）**：该视角不可靠/无依据的领域
  （如「样本只覆盖 AI 硬件主线，未覆盖可转债与港股」）。低置信度画像
  （<3 篇）应有对应的边界条目；运行时模型在这些领域**不得输出该视角观点**。

这两个字段���胜率统计联动：已进 `framework_version` 内容哈希，改动后框架版本
自动换号，旧版本胜率不会污染新版本统计。

**手工编辑前的快照**：程序写 profile 前会自动留底（`perspective snapshots` 可查、
`perspective restore --perspective <角色id> --snapshot-id ps-xxxx` 可回滚，保留最近
20 份）；手工编辑 JSON 不被拦截，但改坏了用快照回滚，不用从 git 外捞。

## 第 5.5 步：留出验收（held-out，蒸馏后跑）

留一篇（或几篇）同博主文章**不进蒸馏**，用画像信号条目检验它对该篇的解释力：

```bash
# 标记留出（article_id 见 manifest；被标记的文章 extract-cards/propose-patches 自动跳过）
python3 -m intelligence.cli perspective holdout add --user <id> --perspective <角色id> \
  --article-id pa-xxxx --note "为什么留这篇"

# 确定性回声检验：画像四个白名单字段的条目词元在留出文章正文的命中率 ≥50% 为 pass
python3 -m intelligence.cli perspective holdout verify --user <id> --perspective <角色id>
```

- **为什么双侧排除**：留出文章若被抽卡/聚合，verify 测的就是蒸馏的「记忆」而非
  「解释力」——泄漏会让验收形同虚设（held-out 的第一性原理，RAG 评测同理）。
- **判读**：pass = 画像信号在该篇有回声；fail 且全零回声 = 画像对该类文章无解释力，
  回第 4/5 步补信号或收窄 `honest_boundaries`。fail 不代表博主方法错，只代表画像没学到。
- **边界**：回声检验是必要条件不是充分条件（信号词命中 ≠ 逻辑复现）；要测逻辑复现
  需 LLM 盲测（画像预测「他会怎么看」再对原文）——目前未实现，需要时再立项。
- 结果台账：`perspectives/holdout/<pid>.verify.jsonl`（已登记 ledger-map）。

## 第 6 步：验收

1. `perspective profile --user <id> --perspective <角色id>` 通读一遍，确认没有 episodic 残留；
2. **生产可见性闸**（这一条不过，前面全部不算完成）：

   ```bash
   curl -s "http://127.0.0.1:8792/api/perspectives?user=<id>" | rg '<角色id>'
   ```

   查不到就是写到了生产读不到的地方、或 user 写错——回第 0 步，别接着往下走。
3. 有生产 Workbench 且 DuckDB 无写锁时，单视角选该角色问一句行情题 smoke：
   正文应出现该视角的证据层级语言，首选证据缺失时应显式声明而不是降格为
   通用研究结论。**没有环境就停在 profile 通读，不编造端到端通过。**
4. 回复用户：几篇入库、几条 patch（approve/reject 各多少 + 拒绝理由）、哪些字段待复核。

## 常见坑

- **不冒充本人**：输出只是「某博主视角」，不是本人观点。
- extract-cards 无 LLM key 时整批 fail（明确报错）——不要退化成手工编卡片伪装抽取结果。
- 同一 (field,value) 的 patch id 是确定性哈希：重复 propose 幂等，**rejected 不会复活**；
  想翻案要手工删 patch 文件再 propose。
- 画像/卡片/patch/原文全部在 gitignore 的用户命名空间内——commit 前 `git status` 里
  不该出现它们，出现了说明写错了地方。
- 生产 Workbench 读 `FORESIGHT_USERS_DIR`；Mac 主仓若脏，另开干净 worktree 再跑
  CLI，venv 可用主树的，加载哪份代码由 cwd 决定。
- **CLI 与生产是两套用户空间**：CLI 跟随 shell 环境变量，生产跟随启动器里的 export。
  两者不一致时闭环每一步都会"成功"，只有 Workbench 里选不到视角这一个症状——所以
  第 6 步那道 API 可见性闸是唯一能证明蒸馏落地的检查，不能省。
