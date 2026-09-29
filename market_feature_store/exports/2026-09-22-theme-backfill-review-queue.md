# 2026-09-22 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 13
- **status_counts**: `{"pending_review": 13}`
- **action_counts**: `{"review_attach_or_archive_evidence": 5, "review_create_or_link_concept": 7, "review_map_entity_exposures": 1}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| critical | pending_review | 8 | deep | 百度概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| critical | pending_review | 8 | deep | 百度概念 | missing_entity_exposures | review_map_entity_exposures | 先确认题材核心公司，再补 entity_exposures 映射；不要用泛行业公司凑数。 |
| high | pending_review | 2 | deep | 新零售 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 4 | deep | 集成电路设计 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 5 | deep | 医药医疗 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 6 | deep | 电子 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 8 | deep | 百度概念 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 15 | watch | 阿里概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 16 | watch | 腾讯概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 18 | watch | 小米概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 21 | watch | 苹果概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 23 | watch | 抖音概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 26 | watch | 无线耳机 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
