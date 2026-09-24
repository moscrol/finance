# Finance #847 与 KB #157 耦合说明

## 组件边界

KB #157 负责晨汇正文、source / index 与 `wiki/raw/theme-radar/opinion-store/briefing-tier-events.jsonl` 投影。Finance #847 提供 IMA 缺输入失败语义和只读消费验收；验收脚本从 `--kb-wiki` 读取上述投影，从独立 labels DuckDB 读取 `history_teaching_labels`，再调用 market river。Finance 不向 KB 写正文、投影、标签或行情。

## 推荐顺序

先合 KB #157，再合 finance #847。这样 source 投影先具备，finance 的验收和后续标签构建才有明确输入。两张 PR 都合入前，不做 live PASS；合入 finance 前仍需确认它的 base/head 与最新 `gitea/main` 一致。

## 半合行为

| 状态 | 可观察行为 | 是否有副作用 |
|---|---|---|
| 只有 KB #157 | 内容和投影可被读到，但旧 finance 代码不会凭此自动写 teaching labels 或消费确认 | 无 finance 写入 |
| 只有 finance #847 | 验收仍只能读旧投影；缺 source 行会 FAIL，source 可用日超出 market calendar 会 BLOCKED；不会用其它日报冒充晨汇 | 只读，无造行情/标签 |
| 两者均合但 labels 未构建 | source 可见，验收在 label set/value/computed_at 或 teaching object 处 FAIL | labels DB 不由脚本写入 |
| 两者均合且 labels/行情就绪 | 才能进入 source -> label -> teaching object -> river 的 exit 0 判定；普通 river 仍为 `trade_date_only` | 验收只读 |

因此不存在必须原子合并的数据库写入耦合；存在输入版本耦合。半合不会污染生产，但会让验收明确失败或阻断，不能把 `BLOCKED` 当成通过。

## 当前状态

本 finance 候选 head 为 `6f14ed215184d5c97fae3c03513468c6c9ee9cd4`，KB #157 的候选树及主检出均未被本分支修改。KB 主检出有既有脏改动和冲突，本轮只读调查；不在该树上 reset、merge、清理或提交。两 PR 的工程合入与用户确认分开，#61 行情恢复完成后另行授权 live 验收。
