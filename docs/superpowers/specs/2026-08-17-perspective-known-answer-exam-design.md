# 视角考卷：已知题 + 边题（保真验收）

- 日期：2026-08-17
- 状态：按最优路径落地（用户已锁定：金标人手写、空卷失败、边题必须弃权）
- 对照：colleague-skill 的 known-answer / edge-case；**不是**已扔掉的 holdout 词元回声门
- 实现：`intelligence/services/perspective_exam.py` + `perspective exam add|list|run`

## 1. 要解决什么

蒸馏闭环现在能把文章变成画像，但第 6 步验收只是「通读 profile + 8792 能列到」。
这证明**写到了地方**，不证明**画像还站在博主已经发表过的立场上**，也不证明
`honest_boundaries` 真的会拦住不该开口的题。

colleague-skill 的 validation 是：出已知答案题（≥2）+ 边题（≥1），对照金标打分。
本仓借的是这个**形状**，不是它的 LLM 写 `validation.md`、也不是口吻/版权检查。

## 2. 三种做法与取舍

| 方案 | 做法 | 测到的东西 | 为什么不采用 / 采用 |
|---|---|---|---|
| A. 留出回声 | 藏一篇文章，BM25 词元命中 ≥50% | 词面像不像原文 | 已扔掉。任意二字即可过，测的不是立场 |
| B. LLM 当考官 | 模型读文章再判「像不像该博主」 | 考官自己的品味 | 不可复现，和本仓「P0 确定性门禁」冲突 |
| **C. 用户钉子 + 确定性核对（采用）** | 用户写金标；程序只拿 `evaluate_role` 的产物对钉子 | 画像+运行时是否复现已发表立场；边界外是否弃权 | 空卷失败；坏 JSON 失败；不调 LLM |

C 测的是**保真（fidelity）**，不是泛化。金标对应的原文**可以**进蒸馏——题问的是
「蒸馏之后还能否重建博主已经公开说过的判断」，不是「没见过的文章也能猜中」。

这和软件测试里的 golden test 是同一思想：夹具是人写的期望，程序只做相等性检查。
替代方案是 property test（只断言不变量）或 holdout（测泛化）；前者太弱（过了也不知道
立场对不对），后者需要真的留出样本且不能用词元回声当尺子。

## 3. 锁定的行为

### 3.1 金标谁写

用户写。程序不生成考题、不当考官。CLI 只 `add` / `list` / `run`。

每道已知题的钉子：

- `question` + `facts`：题面与硬事实（facts 里出现画像信号词，才会命中）
- `expected_direction`：`opportunity` / `risk` / `mixed` / `none`
- `expected_field` + `expected_terms`：方向为机会/风险/混合时必填；字段白名单与
  patch 闭环相同（`opportunity_preferences` / `risk_triggers` / `anti_patterns` /
  `falsification_style`）
- `forbidden`：产物里不能出现的说法（例如这道题不该喊「加仓」）

边题：`question`（+ 可选 `facts`），`must_abstain=true`。题面落到
`honest_boundaries` 的**不可靠侧**时，运行时必须弃权；给出方向性命中 = 失败。

### 3.2 空 ≠ 过

套件通过当且仅当：

1. 考卷文件存在且 JSON 合法；
2. 至少 2 道 `known_answer`、至少 1 道 `edge_case`；
3. 每一道都通过。

缺文件、空 `cases`、题量不够、坏 JSON：全部失败。禁止「没卷也绿」。

### 3.3 运行时与考卷共用同一函数

`evaluate_role(profile, question, facts)` 是唯一判定器：

1. 用诚实边界的**不可靠子句**抽主题针，与 `question+facts` 做子串重叠 → 弃权，
   并清空机会/风险命中（弃权后不得再给方向性判断）；
2. 否则用既有 `_hit_terms` 对硬事实做信号词命中，推出 `direction`。

`run_debate` 的角色段走同一条函数，所以合议里也会标弃权——考卷不是另一套逻辑。

边界匹配必须区分「只覆盖 X」和「未覆盖 Y」。
「样本只覆盖 AI 硬件主线，未覆盖可转债与港股」遇到「AI 硬件怎么看」**不得**弃权；
遇到「可转债怎么定价」必须弃权。只抽带「未覆盖 / 不适用 / …」的子句；没有这类标记
的短边界（整条就是「可转债」）整条当主题。

不采用任意 CJK 二字回声：那是上一轮 holdout 的失败形状。

### 3.4 明确不做（v1）

- 不复活 holdout / snapshot / 「第 5.5 步」
- 不口吻检查、不版权倾倒检查、不让 LLM 写 validation.md
- 不要求两人合议才能考试（考卷是单角色）
- 不把金标文章塞进 prompt 当答案

## 4. 数据与 CLI

- 落点：`intelligence/users/<id>/perspectives/exam/<pid>.json`（用户态，已在
  `perspectives/` gitignore 下）
- 写入者：`perspective exam add`
- 判定者：`perspective exam run`（exit 0 仅当套件通过）

```bash
perspective exam add --perspective <id> --kind known_answer \
  --question "..." --facts "..." --direction risk \
  --field risk_triggers --term 产能过剩 --forbidden 加仓

perspective exam add --perspective <id> --kind edge_case \
  --question "可转债怎么定价？"

perspective exam run --user <id> --perspective <id>
```

## 5. 蒸馏第 6 步

`skills/perspective-distill/SKILL.md` 第 6 步在「通读 + 8792 可见」之前加
`exam run`：没有绿考卷，蒸馏不算验收完成。
