# 在途交接 · fix/tool-schema-limit-fidelity

更新：2026-08-12 · Claude

## 这个分支做什么

按检索源（族 A 官方 Claude Code 文档 + 族 C ai-agent-book ch4）对**工具接口层**
逐条对表，把差距补上并逐项实测。**未合并 main，等用户确认。**

## 已完成（6 个提交，全部有实测读数）

| 提交 | 内容 |
|---|---|
| `29837cfc` | schema 广告的行数上限必须等于真正执行的上限（保真性） |
| `e1143571` | 建量具 `probe_tool_arguments.py` + 组件 1 基线 |
| `4c4f28b0` | T1：finance_query 参数描述与可执行示例 |
| `9215d09f` | 补跨字段约束说明 + 干净对照读数 |
| `0c1b1b46` | 把工具拒绝的具体原因回灌给模型（对全部 12 个工具生效） |
| `9f6ca142` | 探针加多轮回灌模式，让上一条可测 |

全量 **4485 passed / 0 failed** @ `.venv-workbench/bin/python`，8 道 pre-commit 全过。

## 核心读数（引用前先看成立条件）

`finance_query` 参数描述改前 / 改后，同题集、同模型 `gpt-5.6-terra`、同为 `--repeat 3`：

| | 改前 `e1143571` | 改后 |
|---|---|---|
| 合法率 | 55.9% (19/34) | 87.9% (29/33) |
| 靠 harness 代偿才合法 | 16 | 2 |
| `order_by` 写成单对象 | 14 | **0** |

读数落在 `~/.finance-runtime/tool-arg-probe/`（gitignored，会随清理消失）。

## ⚠ 三条读这些数时必须知道的边界

1. **噪声带 ≥±12pp（n≈30）**。两次**首轮条件完全相同**的 `--repeat 3` 跑出
   87.9% 与 100%。所以 32pp 的效果是真的，但精度远没有数字看上去那么高。
   引用时别写「提升 32 个百分点」这种精确说法。
2. **N=1 两头都会骗，且方向相反**。同一实验里改前 N=1 报 30.8%（真值 55.9%）、
   改后 N=1 报 100%（真值 87.9%）。探针的 `ablation_ready` 字段会在 `repeat<3`
   时自报 false，别绕过它。
3. **`0c1b1b46` 的效果是 null，不是 0**。描述修好后失败已稀少，最近一次
   `--repeat 3` 跑出 30/30 全合法，回灌路径压根没触发。**它没被证伪，是没机会被测**。

## 未验证 / 已知边界

- **拒绝理由回灌只改了 continuous-episode 这一条路径**。
  `headless_tool_gateway.py:715` 与 `openai_agents_runtime.py:655` 同样只留
  `exc.code`、丢消息，**未改**。要改先想清楚它们的下游怎么读 `rejected`。
- **解析期错误仍然没有重试提示**。`FinanceQueryValidationError` 继承 `ValueError`，
  在 `registry.prepare()` 被 `except (KeyError, TypeError, ValueError)` 捞走包成
  `InvalidResearchToolArguments`，**走不到 `validation_retry_hint`**；只有
  `_compile_query` 阶段的错误才有提示。本轮只补了通用回灌（把原因带上），
  没补解析期的「该怎么改」。
- **AST 扫出 `FinanceQueryValidationError` 共 35 处**，本轮按实测命中只文档化了
  其中约 8 条。**逐条写描述是打地鼠**——每补一批，长尾就换几条新的顶上来
  （实测：补掉 group_by/filter/dimension 三条后，冒出 contains/date_in_filters）。
- `_dataset_query_schema`（`finance_query.py:512`）是**死代码**，全树只有定义那一行。
  没删，但它带着一份重复的 `maximum: 1000`，下一个人可能改错地方。
- 探针的保真边界：合法调用生产会真的执行工具并回灌观测正文，量具不执行、
  只回一条标注 `[probe]` 的占位。所以 `--follow-up` **只能判「失败的会不会自愈」**。

## 下一步（按价值排序）

1. **T2/T3 别照抄 T1 的做法**。T1 有效是因为 `order_by` 有一个清晰的形状判据；
   9 个 query 类工具吃自由文本，没有等价的「合法性」判据，得先想清楚测什么。
2. **要测回灌就得造失败样本**——趁缺陷多的时候测，或在 pre-T1 的 worktree 上
   跑「旧描述 + 新回灌」。顺序错了永远补不回来。
3. 组件 2/3（上下文压缩 / agent RAG）的检索源仍是 `仅见标题`，
   **精读之前不得下结论**（INDEX 纪律）。要取的页已列在
   `~/harness-reference/INDEX.md` 第④节。

## 踩过的坑（都已写进 TOOLKIT / 蒸馏稿）

- **变异验证必须先确认变异真的落盘**：一次替换串带了引号前缀没匹配上，是 no-op，
  「测试没红」测的是空气。另一形状：变异后的字符串仍是断言子串，测试照样绿。
- **量具必须覆盖被改动的那一步**：改参数描述却想用 `probe_tool.py`（它 stub 掉模型），
  改回灌却用单轮探针。**动手前先问「我改的这一步，量具走不走得到」**。
- **按文件 mtime 分桶历史 run 是错的**：run 目录名带真实 episode 时间，
  mtime 可以差 6 天，据此得出的「8 月还在失败」结论是假的。
- 首次真跑：模型调用花完、读数算完，**最后一步落盘崩在 `mappingproxy` 不可序列化**，
  8 次配额白花。序列化是读数管道的一部分，dry-run 的 stub 参数太浅覆盖不到。
