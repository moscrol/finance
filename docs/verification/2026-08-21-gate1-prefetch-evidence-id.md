# Gate 1 分叉 + 子单 C：预取行拿不到引用把手（2026-08-21）

> 规格：`docs/superpowers/specs/2026-08-21-harness-success-path-design.md` §9 Gate 0/1、§6.3 子单 C
> 代码：`fix/prefetch-evidence-id` @ `dfc25221` 基线，改一处 `intelligence/services/asof_prefetch.py`
> sidecar：`:8796`，`code_root=fwp-wt-prefetch-evidence-id`
> 生产 `:8792` **未切**，仍 `dfc25221b07b`
> 入口：`POST /api/conversations/{id}/messages`（`live_probe ask` 落中立泳道，无 `continuous-episode.json`）
> **结论：分叉 = 禁错了 → 子单 C。已修，离线绿 + live 过。可合。不切 8792。**

## Gate 0

`gitea/main` == 树 HEAD == 8792 `/api/health` 三者一致 = `dfc25221b07b`。§1「不要重做」表照办。

## 新题（反过拟合，未进 spec 正文）

**「创新药这波是怎么发酵到 2026-08-07 这个位置的？把链路回溯一下，每一步给出当天的涨幅、成交额和成交额环比变化」**

选它的理由：库里有真实行（`创新药` 回溯到 2024-12-25）；`contains '药'` 会灌进 **11 个板块**（中成药/中药/仿制药/减肥药/化学制药/医药/医药医疗/医药商业/原料药/生物制药），污染面比锂矿那道更大。

### Cursor 侧（分析师确定性取数）

`is_double_red` 只引用 `theme_lifecycle_timeline.py` 一份，不另立字面量。两个口径：`886015.TI` **07-24 停更**，`990098.FP` 为活口径。

`07-10 双红试盘 +3.07%/1157.6亿/环比+30.3%` → `07-15 放量高点 +3.71%/1799.8亿/环比+48.0%` → `07-17 断崖 -6.88%` → 缩量出清至 `08-03 地量 677.4亿` → `07-29 / 08-04 / 08-05` 量先于价三连双红 → `08-07 主升 +4.86%/1396.3亿/环比+46.1%`

### 店侧（修前）`run_20260821_015459_794701`（生产 8792）

## 第一次分叉：不在进场桌，在呈现层

进场桌**是对的**。`outcome.evidence[0]` = `本地 DuckDB · 问句日预取`，窗口 **2026-06-29..2026-08-07** 全逐日行 + 双红戳 + 精确名，2671 字符——分析师那一刀桌上有，窗口甚至更长。模型那次多余的 `finance_query` 用了 `op=contains` + 5 天窗，但本题 `contains 创新药` 恰好只命中自身，**无害且非首分叉**。

> ⚠ **先记一次自纠**：初判写成「E 号从 E3 起跳，E1/E2 从没发号」。**错**。用产品代码 `evidence_ordinal_table` 复算这一跑的 13 条证据，预取两条 `content_hash` 齐全，稳拿 `E1`/`E2`。当时误读的来源是 `outcome.evidence[].evidence_id` 全为 `None`——那个字段本来就不落盘，号是终局现算的，**拿它当"没发号"的证据不成立**。真正的缺口在下一层。

`_seed_opening_prefetch`（`intelligence/runtime/agent_episode.py:540`）把预取**先**放进证据账本（故稳拿 E1..En），随后调 `format_opening_prefetch_message` 生成开场 user 消息——**这一步只拼 `title + detail`，把号丢了**：

```python
return "问句日预取（harness 进场事实，不是工具调用）：\n" + "\n\n".join(
    f"{item.title}\n{item.detail}" for item in items)
```

`attach_evidence_ordinals` 只用在 `agent_episode` / `episode_finalizer` 的公开证据投影上，进场那块从来没走过。

于是一条完整因果链：

1. 模型**诚实地**用了预取轴，显式标注「预取，无证据序号」，并写进 `gaps`
2. 判官按「数字必须有 evidence_id」逐句删：*「句5：6-29涨幅/成交额/环比数字无任何evidence_id，属**发明历史行情**」*
3. 被删的是**真话**——模型写的 7-15「约1800亿」对应分析师侧 1799.8亿
4. 用户拿到的稿只剩 `08-04..08-07` 四天 + 「证据缺口：…已删除」

## 三态：**禁错了** → 子单 C

对上 §3 定义原文「真话被删、预取了仍报缺能力」，也对上 §6.3 可红可绿形状「预取未计入」。

**为什么此刻开 A 是浪费**：A 要补的「起涨/补涨分层」确实缺（§6.1 第二触发条件成立），但那是往桌上加**更多没有引用把手的行**，会被同一把刀原样删掉。C 必须在 A 之前——这是 §9「反向执行的代价」的镜像形态。

## 修法

只改呈现层。号本来就有，把它写给模型看；**不动**判官「数字要有出处」那条规矩——那条是对的，正是它拦住模型瞎编。

`format_opening_prefetch_message` 用 `evidence_ordinal_table`（与终局注册表**同一张表**，不新编号）给每条预取行打 `[E1]` 前缀；认不出 `content_hash` 的条目不发号（fail closed），绝不自己编——编出来的号会解析到别人头上。判官侧 `resolve_evidence_refs` 本就认 `E1`，无需改动。

## 离线

`intelligence/tests/test_prefetch_evidence_ordinal.py` 5 条：

| 用例 | 锁什么 |
|---|---|
| `test_opening_message_labels_each_prefetch_item_with_ordinal` | 每条预取带号。**修前会红的那条** |
| `test_opening_ordinals_match_registry_after_tool_evidence_appends` | 开场号 == 终局注册表号；工具证据仍排 E3 之后，预取不被挤号 |
| `test_model_can_cite_prefetch_ordinal_and_judge_resolves_it` | 写 `E1` 能解析到预取那条 hash |
| `test_message_still_declares_prefetch_is_not_a_tool_call` | 带号后仍声明不是工具调用 |
| `test_items_without_hash_do_not_get_a_fabricated_ordinal` | 认不出就不发号 |

- TDD：修前 **3 failed / 2 passed**；修后 **5 passed**
- 定向宽集（prefetch + episode_protocol + agent_episode + episode_tools + semantic_verifier + answer_hygiene）：**381 passed**，收据 `~/.finance-runtime/test-receipts/20260820T181642Z-dfc25221.json`
- ruff 绿
- **变异**：`evidence_ordinal_table(tuple(reversed(hashed)))`（模拟第二套编号来源漂移，比"没号"更危险——会引到别人证据上）→ **3 failed**；还原 → 5 passed。变异前后各清一次 `__pycache__`，避免同长度改回假绿

## Live（修后）`run_20260821_021724_077535`

公开稿 **894 → 1027 字**，四段发酵弧全部保住，`E1` 引用 117 次（修前 0 次，且模型自陈「无证据序号」）。

| | 店（修后） | 分析师侧 |
|---|---|---|
| 6/29 | +6.08% / 1239亿 / +57.95% | 6.08 / 1239.13 / 57.95 ✓ |
| 7/15 | +3.71% / 1800亿 / +48.01% | 3.71 / 1799.8 / 48.0 ✓ |
| 8/3 | 677亿 / -14.39% | 677.4 / -14.4 ✓ |
| 8/7 | +4.86% / 1396亿 / +46.08% | 4.86 / 1396.3 / 46.1 ✓ |

§8.1.4 公开稿数字 ⊆ 桌上的行 ∪ 有收据的工具行：盘面数字全部落在 `E1`（预取）或 `E7`。

**副效果**：修后这跑 traces 里**没有 `finance_query`**——预取可引用之后模型不再重复去查同一段窗口，省掉一次工具调用。与 §4「已知长窗走预取」同向。

`[E1]` 标签不出现在 `continuous-episode.json` 里，因为开场 user 消息不落盘；直接调 `format_opening_prefetch_message` 打印确认（[实测]）。

## 遗留（本单不做，非本改动引入）

- `marker_loss: semantic repair removed required output: counterpoint` — 反证槽仍被删空，修前修后都有
- 第11句引用未注册的 `E11`/`E13` 资讯号；`kb_search` 报 `request_error` — 资讯侧，非盘面侧
- `resolve_theme_alias` 的 `None` **双关**：`candidates[0] != theme` 才返回值，故「解析不到」与「本来就是精确名」同一个返回值。§6.1 写「解析不到 → fail closed 不预取」，若预取侧照此判断，精确名会被误判成解析失败。**本次未触发**（预取正常锚定）
- 预取投的是两个口径不加区分（每天两行），模型写 6-29 时 pct 取一条、amount/环比 取另一条
- Q3 差 13 字没触发：修前 `public_answer` 253 字 vs 阈值 `20%×1200=240`。判得对（不是残句，是内容被掏空），但说明 Q3 的尺子量不了这形状，§6.2 已写明

## 账本

`R-20260821-03`，`pending`。单测绿 + 单跑 live ≠ `confirmed`；n=1 过不了方差门。
