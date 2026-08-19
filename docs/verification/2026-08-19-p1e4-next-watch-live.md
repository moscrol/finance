# P1-E4 live：下期关注消费端（2026-08-19）

> 派单：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 轨道 B  
> 判据真本源：`docs/learning/spec-continuous-depth-gap-r1.md` R5 §三 P1-E「验收」  
> 代码：`feat/p1e4-next-watch-consume` @ `44e6ef42`（实现 `3e58aa1e` + 交接）  
> sidecar：`:8808`（`live_probe start-sidecar`，隔离用户 `p1e4-pv` / `p1e4-fresh`）  
> 生产 `:8792` 未切，仍 `441c60f2`  
> 入口：同一 sidecar 上 `POST /api/conversations` → `.../messages`（`continuous_episode`）  
> **结论：打回。不合、不切 8792。**

## 为什么不用 `live_probe ask`

派单写的工具是 `scripts/live_probe.py ask`。它走 `POST /api/runs` → `plan_answer_question`。那份分类器的 `QUESTION_TYPES` **没有** `theme_track`：

| 题目 | turn_controller（会话口） | ask 规划器 |
|---|---|---|
| 光伏最近一个月有什么新变化 | `theme_track` | `general_finance_qa` 0.45 |
| 动力电池产业链近况跟踪一下 | `theme_track` | `theme_analysis` 0.76 |

若按字面跑 `live_probe ask`，`run.json` / `report.json` 不会出现 `theme_track`，正好复现 R5 §四.3「拿 theme_analysis 充跟踪题」。验收方改用**同一 sidecar** 的会话口，才压到真 `theme_track`。`question_type` 不在 `run.json` 顶层，在 `report.json` 的 `task_frame` / `turn_intent`（以及 `trace.jsonl` 的 controller 步）。

## 题目

1. **有上期 [M]/[V]**（用户 `p1e4-pv`）：「光伏最近一个月有什么新变化」  
   预置 `judgments.jsonl`（组件价格见底，2026-07-15）+ `checkpoints.jsonl`/`verdicts.jsonl`（中报毛利率 <12% 则削弱，`unverifiable`）。
2. **无基线**（用户 `p1e4-fresh`）：「动力电池产业链近况跟踪一下」  
   空台账。

都不是第五轮隔夜预测题。

## 判定

**打回。** 两发都是真 `theme_track`，无基线声明 / 四态词汇 / TTL / 下期关注**正文都在**；但 `parse_next_watch_items` 对 live 形状零命中，`source=track_next_watch` 一行都没写下。次日 foresight 的「下期关注对照」因此是空的——E4 消费端没接通。

夹具形状（单测绿）≠ live 形状：测试只喂

```text
## 下期关注清单
- 若 2026-09-12 中报毛利率 <20% 则削弱扩产逻辑
```

live 模型写成「标题行内联 若/则」，或「`1）` 全角编号跟标题同一行」。`_watch_section_body` 丢掉第 0 行（标题行），`_BULLET_RE` 只认 `-` / ASCII `1.` / `1)` / `1、`。

## 验收

| 条 | 要求 | 读数 | 结果 |
|---|---|---|---|
| 题型 | 1 道真 `theme_track`（读产物，禁止 theme_analysis） | Q1/Q2 `report.task_frame.question_type=theme_track`；controller 理由「路由表命中 theme_track」 | 过 |
| 无基线 | 无 [M]/[V] 时声明「无上期基线，本期建立基线」 | Q2 正文第 1 句即此声明 | 过 |
| 有基线 | 对照 [M]/[V]，四态之一 | Q1 引用 7-15 判断「组件价格已见底…」，判定「信息不足」；预置 [V] 毛利率条未逐条点名 | 部分 |
| TTL | 复核期限 YYYY-MM-DD | 两发均有 `复核期限：2026-09-18` | 过 |
| 下期关注入账 | 可证伪子弹 → `checkpoints.jsonl` `source=track_next_watch` | Q1 仍仅有 seed；Q2 文件不存在。离线 `parse_next_watch_items` 均为 0 | **不过** |
| 次日对照 | foresight 系统提示词强制对照 | `open_next_watch_records` 两用户都是 0；渲染空串 | **不过** |
| E 覆盖 | 不回退（历史地板 23，原为复盘/预测题） | Q1 `outcome.evidence` 22；Q2 55 | Q2 过 / Q1 略低于地板 |
| 生产 | 不切 8792 | health `source_revision=441c60f2` dirty=false | 过 |

## 定向测试 / 合并探路（独立复算，不抄实现方收据）

- merge-tree：`git merge-tree --write-tree gitea/main feat/p1e4-next-watch-consume` → `35f9d9e25e20608ffd3134686bbf3d994d9dbe5f`，exit 0，无冲突。`gitea/main=bc8c690b`，merge-base `a7e2d74f`。
- 测试：`env -i` + `umask 022`，解释器 `.venv-workbench`，50 passed / 0 failed。收据 `~/.finance-runtime/test-receipts/20260819T072325Z-44e6ef42.json`（`dirty=false`，rev=`44e6ef42`）。实现方那张 `20260819T065109Z-3e58aa1e` 未采信。

## 残留 / 非本刀

- 两发 `semantic_status=unavailable`（复核超时），`business_status=partial`，degrade「证据或语义核验未完全通过」。R-06 判官暂态形状，不是 E4 回归。
- Q1 公开稿被拼进 `","复核期限…"+"` 碎片，像核验改写泄漏；Q2 干净。不挡「parse 零命中」这条主因。
- 轨道 A（#227）已说 B 可链切。本轨道 **打回后不得链切**，A 的放行只覆盖门禁 live，不覆盖 E4 消费端。

## 产物（写前进过 `ls`）

- sidecar 已停；`:8808` 空闲；8792 仍 `441c60f2`
- Q1：`~/.finance-runtime/p1e4-next-watch-live/q-baseline/`（`run_20260819_152712_553514`，134.9s）
- Q2：`~/.finance-runtime/p1e4-next-watch-live/q-fresh/`（`run_20260819_153113_721347`，274.6s）
- 收据：`~/.finance-runtime/p1e4-next-watch-live/q-baseline.json`、`q-fresh.json`
- 测试：`~/.finance-runtime/test-receipts/20260819T072325Z-44e6ef42.json`

## 打回后怎么修（形状，不是本单补丁）

消费端要认 live 已写出的「若/则」句子，不能只认 markdown 次行 bullet。至少覆盖：标题行内联多条、全角 `1）`、中文句号分隔。夹具要加这两发的原文，单测绿才能再 live。修完另开验收，不要带着这次 0 入账合进去。
