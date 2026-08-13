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

1. **用户空间是哪个**：生产 Workbench 读 `FORESIGHT_USERS_DIR` 指向的目录
   （Mac 上是 `~/agent-memory/.foresight/<user>/perspectives/`）；不设环境变量时
   默认落 `intelligence/users/<user>/perspectives/`。**在 worktree 里跑会写出一份
   生产读不到的副本**——先确认写的是 canonical 那份。
2. **角色 id**：已有角色（`perspective profile --perspective <id>` 能读到）就直接
   ingest；新角色先 init。id 用小写下划线（如 `sptfei`），display_name 存中文名。
3. **文章元信息**：每篇要有 date（发文日期）和 title；缺了后面评审时无法判断
   条目是不是过期的单次观察。

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

评审判据（sptfei 实战沉淀，2026-08-13）：

| 判 | 形状 | 例 |
|---|---|---|
| ✅ approve | 脱离具体行情也成立的**可执行规则** | 「大幅缩量+支撑位+30分钟底背离才算回流确认」 |
| ❌ reject | **episodic**：夹带具体日期/个股的单次观察 | 「7月20日AI硬件高位分歧应减仓」 |
| ❌ reject | **宏观世界观**：立场表态，不可执行、不可证伪 | 「长期看好中国资产」 |
| ❌ reject | 与画像已有条目**同义**（幂等闸挡不住换措辞的重复） | — |

agent 可以代评并逐条给理由，但要在回复里报告 approve/reject 清单；**最终认定权在用户**，
画像的 `known_gaps` 里标注「agent 起草待用户复核」，用户过目前不当作已确认的方法论。

## 第 5 步：结构化字段人工编辑

镜头（market_lenses）、证据层级（evidence_hierarchy）、推理模板（reasoning_patterns）
带顺序/结构语义，「追加」不成立，闭环不碰。做法：对照原文提炼，直接编辑 profile JSON，
并在 `known_gaps` 写明哪些是 agent 起草。改完 `perspective profile --json` 核对。

## 第 6 步：验收

1. `perspective profile --user <id> --perspective <角色id>` 通读一遍，确认没有 episodic 残留；
2. Workbench 单视角选该角色问一句行情题 smoke：正文应出现该视角的证据层级语言，
   首选证据缺失时应显式声明而不是降格为通用研究结论；
3. 回复用户：几篇入库、几条 patch（approve/reject 各多少 + 拒绝理由）、哪些字段待复核。

## 常见坑

- **不冒充本人**：输出只是「某博主视角」，不是本人观点。
- extract-cards 无 LLM key 时整批 fail（明确报错）——不要退化成手工编卡片伪装抽取结果。
- 同一 (field,value) 的 patch id 是确定性哈希：重复 propose 幂等，**rejected 不会复活**；
  想翻案要手工删 patch 文件再 propose。
- 画像/卡片/patch/原文全部在 gitignore 的用户命名空间内——commit 前 `git status` 里
  不该出现它们，出现了说明写错了地方。
