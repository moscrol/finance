# Query-aware Entity Anchor Design

## Goal

让实体锚定优先使用用户问题明确点名的概念族，避免实体关系中靠前但与本轮问题无关的概念污染图谱、证据和闭环检索，同时保持无显式概念问题的旧行为。

## Ranking Contract

名称匹配和股票代码匹配都把原始 query 传给 `_build_anchor`。排序前统一把 query 和 concept 做 Unicode-aware normalize：casefold，并移除空白、标点和下划线。

先从实体完整概念列表中找 explicit seed：normalized concept 完整出现在 normalized query 中，且中文/混合 seed 至少 2 个字符、纯 ASCII seed 至少 3 个字符，避免 `AI` 等短泛词扩散。多个 seed 按其在 query 中首次出现位置排序，同位置保持原概念顺序。

一个概念只要与任一 explicit seed 存在 normalized 包含关系，就属于命中概念族。最终使用 stable partition：命中族在前、其余在后，两组内部保持原存储顺序，再取 `MAX_ANCHOR_CONCEPTS`。因此 query 中的 `液冷` 会把 `液冷`、`数据中心液冷`、`液冷散热` 等稳定提升；若没有 explicit seed，直接使用旧 `rec.concepts[:4]`，顺序和文本完全兼容。

## Scope and Safety

- 不调用 LLM，不做最长公共子串或任意中文 n-gram，不维护题材同义词表。
- 不修改 `entity_exposures` 或其他 relation 数据。
- 只改变实体命中后的 concept 顺序；实体解析优先级、ticker、warning 和无实体 fallback 不变。
- 由于 `anchor.graph_query` 是 graph exposure、evidence targets 和 closed-loop retrieval 的共同输入，排序只在锚定边界完成一次。

## Verification

单测覆盖名称 query、代码 query、多个液冷族概念和无显式概念兼容。Ask 集成 fixture 模拟英维克多概念及 ABF/AI 容器 peer，验证 anchor/graph query、company table 和 evidence targets 排除 SK 海力士、东方财富等无关 peer，并保留英维克及液冷同链公司。
