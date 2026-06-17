# Theme Radar 公司分层规则

> 本文件由 `skills/theme-radar/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

按 `entity_exposures.json` 和 `concept_graph.json` 的暴露强度排序：

- `core`：第一梯队，直接参与核心环节或主营高度相关。
- `related`：第二梯队，业务相关但弹性/纯度待验证。
- `peripheral`：第三梯队，间接受益或概念弱相关。

缺少 baseline 的公司不能硬判为第一梯队；标记为“待 baseline 补证”。

### 证据 Tier

公司最终输出要优先按证据 Tier 收敛，而不是只按概念命中次数：

- `Tier 1`：产业逻辑 + baseline 能力栈 + 公告/订单/客户验证 + 市场信号共振。
- `Tier 2`：产业逻辑 + baseline 能力栈 + 公告/订单/客户验证，但市场尚未充分认同。
- `Tier 3`：产业逻辑 + baseline 能力栈，缺少事实验证；适合观察，不适合写核心。
- `Watch`：只有代理变量或外部线索，等待 baseline / 公告补证。
- `Noise`：只有大概念标签、普通业务或盘面异动，默认剔除。

升级规则：

- 从 `Watch` 升 `Tier 3`：需要 baseline 证明公司确实有对应产品/工艺/客户/产能。
- 从 `Tier 3` 升 `Tier 2`：需要公告、互动、订单、送样、认证、量产、涨价中至少一项事实验证。
- 从 `Tier 2` 升 `Tier 1`：需要市场信号或多源验证共振。
- 没有 L2 baseline 的公司，即使公告或复盘提到，也要先标“待主营/能力栈核验”。
- `graph_only` 或 `exposure_only` 默认只能作为产业链暴露和观察线索；公司升级到 `Tier 2/1` 前，需要 `delta` 或公告/订单/客户/认证/量产等 L3 事实验证。

### 渲染层弱关联过滤（可逆，不改 ground-truth）

`entity_exposures.json` 里约 1/4 的 concept-exposure 是共现图谱/候选噪声（典型：把 CPO 封装公司天孚通信、罗博特科错挂到上游材料 ABF 载板 / 电子级环氧树脂 / 磷 / 硅）。radar **只在渲染层**默认隐藏这类弱关联，不修改 `entity_exposures.json`：

- 判定规则（`is_weak_exposure`）：`strength != core` **且** `confidence == low` 即视为弱关联隐藏。
- `core` 强度、以及中/高置信关联一律保留 → CPO 核心映射（1.6T CPO / CPO 封装 / 光引擎 / 光模块）不受影响。
- 实体名下若全是弱关联，则该实体整体不进公司表。
- `--show-weak-exposures` 关闭过滤、还原全量，便于人工复核或重新校准。
