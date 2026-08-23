# D2：W1 / W2 自然样本结案（2026-08-24）

- 规格：`docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md` §6
- 零产品代码。禁止重开 `fix/mandatory-satisfiability` / `fix/marker-loss-degrade-keep`。
- 现场：`~/.finance-runtime/trace-diff-spt-index-tech-20260824/`
- 题：`用spt的视角，分析一下指数与科技板块的关系，以及科技各细分之间的关系`
- 8792：`run_20260824_014134_796997` @ `8688545b`（`finance-workbench`）
- 对照：Knevo A1 `run_20260823_233412_640765`；08-22 减肥药 `run_20260822_002310_733136`

---

## 一句话

W2 的静态级（库无产业链 → `chain_mapping` 降 optional + 预置缺口）在 8792 这发打上了，公开稿是【结构缺口】不是剥盘 → `R-20260821-08` **confirmed**。

W1 要的 `marker_loss>0` 这发没有。稿头【质检降级】来自结构 `partial` 水印，不是判官删格后的残块路径 → `R-20260821-07` **仍 pending**。

不要用 8796 这发谈 W1/W2：那是判官 `unavailable` 剥稿，D1 已关。

---

## W2（`R-20260821-08`）为何可以结

08-22 减肥药：缺口文案有了，但路由成 `general_finance_qa`，`chain_mapping` 根本不在合同里。强路径空着。

08-24 指数×科技 8792 补上了那半截：

| 字段 | 读数 |
|---|---|
| `question_type` | `theme_analysis` |
| `chain_mapping.required` | `False` |
| `preplaced_gap` | `知识库暂无该题材产业链证据` |
| 结构格 | `direct_assessment/counterpoint/relation_map=fulfilled`，`chain_mapping=gap` |
| `gap_output_ids` | `[]`（不是 marker_loss） |
| 道歉横幅 | 无 |
| 公开稿 | 853 字还在；尾注 `【结构缺口】产业链层级…知识库暂无该题材产业链证据` |

这就是 W2 静态级的目标行为：库没有公司级链条时，不逼模型编、不因这一格整桌撤掉。

8796 同题合同一样把 `chain_mapping` 降成 optional，内部 draft 也写了缺口；公开 98 字是判官挂了走 `_gap_answer`，与 W2 无关。

---

## W1（`R-20260821-07`）为何还不能结

W1 的自然样本定义是：**`marker_loss>0` 的 run，残块还在、无道歉横幅。**

| 候选 | `gap_output_ids` | `rejected_claim_indexes` | 【质检降级】从哪来 | 结论 |
|---|---|---|---|---|
| 08-22 W1 探针 | 空 | 空 | 判官都没跑到删格 | 路径没激发 |
| Knevo A1 8792 | 空 | 空 | 结构 `partial` 水印；三格全 `fulfilled` | 不是 marker_loss |
| 08-24 指数×科技 8792 | 空 | 空 | 结构 `partial` + 产业链 explicit gap | 不是 marker_loss |

两发都有「质检降级…残块保留」，看起来像 W1，账本字段对不上。结案会把结构水印误认成删格降级。

还欠：一发真 `marker_loss>0`（判官合法删句后 `gap_output_ids` 非空），公开稿仍有该块剩余正文、无「现有证据不足」横幅。

---

## 不做什么

- 不改 `_gap_answer` / 放稿白名单（审查 P0，D1 已否决）。
- 不重做 W1/W2 实现。
- 不用 8796 剥稿否证 W2，也不用它当 W1 样本。
