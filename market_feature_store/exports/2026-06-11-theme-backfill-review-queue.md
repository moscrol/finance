# 2026-06-11 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 10
- **status_counts**: `{"blocked_review": 3, "pending_review": 7}`
- **action_counts**: `{"review_attach_or_archive_evidence": 3, "review_create_or_link_concept": 4, "review_map_entity_exposures": 3}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| critical | blocked_review | 2 | deep | 连板未映射 | missing_concept | review_create_or_link_concept | 候选名称包含未映射占位符，需先回到市场映射层确认真实题材，不建议直接写知识库。 |
| critical | blocked_review | 2 | deep | 连板未映射 | missing_entity_exposures | review_map_entity_exposures | 候选名称包含未映射占位符，需先回到市场映射层确认真实题材，不建议直接写知识库。 |
| critical | pending_review | 7 | deep | 金属铜 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| critical | pending_review | 7 | deep | 金属铜 | missing_entity_exposures | review_map_entity_exposures | 先确认题材核心公司，再补 entity_exposures 映射；不要用泛行业公司凑数。 |
| critical | pending_review | 8 | deep | 金属钴 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| critical | pending_review | 8 | deep | 金属钴 | missing_entity_exposures | review_map_entity_exposures | 先确认题材核心公司，再补 entity_exposures 映射；不要用泛行业公司凑数。 |
| high | blocked_review | 2 | deep | 连板未映射 | missing_evidence | review_attach_or_archive_evidence | 候选名称包含未映射占位符，需先回到市场映射层确认真实题材，不建议直接写知识库。 |
| high | pending_review | 7 | deep | 金属铜 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 8 | deep | 金属钴 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 19 | watch | 海峡两岸 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
