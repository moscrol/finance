# P1-E4 live：下期关注消费端（2026-08-19）

> 派单：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 轨道 B  
> 判据：`docs/learning/spec-continuous-depth-gap-r1.md` R5 §三 P1-E「验收」  
> 代码：`feat/p1e4-next-watch-consume` @ `4dd56941`（parse `3388857c` + continuous 接线）  
> sidecar r3：`:8812`，`source_revision=4dd56941` dirty=false  
> 生产 `:8792` 未切，仍 `441c60f2`  
> 入口：`POST /api/conversations`（真 `theme_track`；`live_probe ask` 没有这一档）  
> **结论：过。可合。不切 8792（等你开 C / 部署窗）。**

## 三轮

| 轮 | 代码 | 结果 |
|---|---|---|
| r1 `:8808` | `44e6ef42` | 真跟踪题，正文有若/则；parse 只认 markdown 次行 `-` → **零入账** |
| r2 `:8810` | `3388857c` | 离线 parse 已绿；ingest 只挂 legacy ask-compose，会话口走 `_complete_continuous_turn` → **仍零入账** |
| r3 `:8812` | `4dd56941` | 收尾调用既有 helper → **入账** |

## 题目（同前两轮，非隔夜预测题）

1. 有 [M]/[V]（`p1e4-pv`）：「光伏最近一个月有什么新变化」`run_20260819_160851_737883`（107.7s）
2. 无基线（`p1e4-fresh`）：「动力电池产业链近况跟踪一下」`run_20260819_161039_495155`（241.9s）

## 判定（r3）

| 条 | 读数 | 结果 |
|---|---|---|
| 题型 | 两发 `task_frame.question_type=theme_track`，`execution_kind=continuous_episode` | 过 |
| 无基线 | Q2 正文「无上期基线，本期建立基线」 | 过 |
| 有基线 | Q1 对照 7-15 判断，判定「信息不足」 | 过 |
| TTL | 两发 `复核期限：2026-09-18` | 过 |
| 下期关注入账 | Q1 本 run `track_next_watch` **1** 条；Q2 **3** 条。`open_next_watch_records` / `render_next_watch_for_prompt` 非空 | **过** |
| E | Q1 episode 证据 33；Q2 21（地板 23，与 r1 一样略漂） | 不挡 E4 |
| 生产 | 8792 仍 `441c60f2` dirty=false；sidecar 已停 | 过 |

## 测试 / 合并探路

- 定向：`test_track_contract.py` + `test_foresight.py` + `test_complete_continuous_turn_registers_next_watch` → **53 passed**。独立复跑 `env -i` + umask 022，收据 `~/.finance-runtime/test-receipts/20260819T080415Z-4dd56941.json`（rev=`4dd56941`，dirty=false）。
- merge-tree：`git merge-tree --write-tree gitea/main HEAD` → `550c2d07`，exit 0。`gitea/main=adf045cb`。

## 残留 / 非本刀

- 两发 `business_status=partial`，degrade「证据或语义核验未完全通过」（复核超时）。R-06 形状。
- sidecar 起来后、本脚本发出前，同用户各多了一发（`160447` / `160724`）也成功入账；验收以本脚本两个 `run_id` 为准。
- 公开稿无 `[E]` 标签（复核前缀改写）；E 从 episode 计。

## 产物

- Q1/Q2 拷贝：`~/.finance-runtime/p1e4-next-watch-r3/q-baseline/`、`q-fresh/`
- 收据：同目录 `q-baseline.json`、`q-fresh.json`
