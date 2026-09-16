# 2026-09-02 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 13
- **status_counts**: `{"pending_review": 13}`
- **action_counts**: `{"review_attach_or_archive_evidence": 7, "review_create_or_link_concept": 4, "review_map_entity_exposures": 2}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| critical | pending_review | 6 | deep | AI长剧 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| critical | pending_review | 6 | deep | AI长剧 | missing_entity_exposures | review_map_entity_exposures | 先确认题材核心公司，再补 entity_exposures 映射；不要用泛行业公司凑数。 |
| critical | pending_review | 8 | deep | 大金融 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| critical | pending_review | 8 | deep | 大金融 | missing_entity_exposures | review_map_entity_exposures | 先确认题材核心公司，再补 entity_exposures 映射；不要用泛行业公司凑数。 |
| high | pending_review | 4 | deep | 军贸概念 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 5 | deep | 大消费 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 6 | deep | AI长剧 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 7 | deep | AIGC概念 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 8 | deep | 大金融 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 9 | deep | 短剧游戏 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 10 | deep | 高端装备 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 13 | watch | 机械设备 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 15 | watch | 通用设备 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
