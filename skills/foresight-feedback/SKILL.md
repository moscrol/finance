---
name: foresight-feedback
metadata:
  pattern: tool-wrapper
description: 对话自动记反馈——把对话里的兴趣/否定/评分信号自动写回 foresight 反馈回路（users/<id>/interactions.jsonl），让系统越用越懂你。触发词：记反馈、记一下、我关注、我对这个感兴趣、想深挖、这个不看了、跳过、不感兴趣、打个分、很重要、猜你想问、越用越懂、自动记反馈。
---

# 对话自动记反馈（foresight 反馈回路）

## 触发条件

当用户在对话中对某个**题材/个股**表达兴趣、否定或评分，或从 foresight「猜你想问」里挑中/否掉某条问题时——**主动**调用 `record-interaction` 落盘，**不需要**用户显式说"记反馈"。这层让 `foresight` 的排序越用越贴近用户最近真在看的票（亲和度按时间衰减，半衰期默认 14 天）。

reads/writes 的就是 `intelligence/users/<id>/interactions.jsonl`，与 GUI 点击共享同一个文件。

## 信号 → kind 映射

| 用户在对话里的表达 | kind | 说明 |
|---|---|---|
| 想深挖 / 帮我查 X / 点开看 | `click` | 一般兴趣（权重 +1.0） |
| 持续关注 / 盯着 / 加自选 | `follow` | 持续关注（+1.5） |
| 这个很重要 / 置顶 / 重点跟 | `pin` | 强信号（+2.0） |
| 追问 / 提问某题材或个股 | `ask` | 主动发问（+1.2） |
| 给 X 打个分（1~5 星） | `rate` + `--rating` | 映射到 [-1,1]×1.5 |
| 只是扫一眼 / 顺带提一句 | `view` | 弱正向（+0.3） |
| 跳过 / 先不看 | `skip` | 轻度负向（−0.5） |
| 不看了 / 没意思 / 排除掉 | `dismiss` | 负向（−1.0） |
| 别再推 / 反感这个方向 | `mute` / `dislike` | 强负向（−1.5） |

## 命令模板（在仓库根目录运行）

```bash
# 一般兴趣：题材 + 关联个股可多次 --theme/--stock
python3 -m intelligence.cli record-interaction --user <id> --kind click --theme 液冷 --stock 中际旭创

# 否定
python3 -m intelligence.cli record-interaction --user <id> --kind dismiss --theme 钠电

# 打分（kind=rate 时配 --rating 1~5）
python3 -m intelligence.cli record-interaction --user <id> --kind rate --rating 5 --theme 算力

# 针对 foresight 抛出的某条问题：把该问题涉及的题材/个股记 click，并用 --question 留痕
python3 -m intelligence.cli record-interaction --user <id> --kind click \
  --theme 液冷 --stock 中际旭创 --question "液冷渗透率拐点对中际旭创毛利率意味着什么"
```

加 `--json` 可拿到机器可读回执（确认 `kind`/`weight`/`themes` 落盘正确）。

## 题材 / 个股提取规则

1. 只记**具体**题材名（液冷、固态电池、算力）和个股名（中际旭创、寒武纪），可一笔多个 `--theme` / `--stock`。
2. `foresight` 问题里的 `domains`（如"宏观""AI""半导体"）是**领域**不是题材，**不要**当题材记。
3. 名称尽量对齐知识库/自选股里的标准简称；拿不准就用用户原话里的词。

## 护栏

- **一次互动只记一笔**：同一句话不要重复 record；用户重复表达同一意图也只记一次。
- **模糊先问再记**：题材/个股指代不清、或在 `click` 与 `follow`/`pin` 之间拿不准强度时，先用一句话跟用户确认，再落盘。
- **用对 user id**：默认取当前用户 id（从上下文或环境变量 `FORESIGHT_USER`）；不确定就问一次，**不要**乱记到 `default`。
- **只记真实信号**：不要替用户臆造兴趣或否定；用户没表态就不记。
- **可批量补记**：复盘/对话末尾可以把这一轮的若干信号一次性补记清楚。

## 闭环验证

记完后下一次 `python3 -m intelligence.cli foresight --user <id>` 会：
- 在摘要里展示「反馈亲和：算力(+1.5)、中际旭创(+1.0)、液冷(+1.0)」；
- 把命中这些题材/个股的问题排到前面，并在该问题下标注「反馈加成（近期你在看）：题材 液冷(+1.0) → +0.18」做可解释说明。
