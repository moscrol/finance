# 2026-08-21 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 6
- **status_counts**: `{"pending_review": 6}`
- **action_counts**: `{"review_attach_or_archive_evidence": 3, "review_create_or_link_concept": 3}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| high | pending_review | 6 | deep | 疫苗 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 8 | deep | 动力电池回收 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 10 | deep | 通信 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 20 | watch | 机械设备 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 23 | watch | 小米概念 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 27 | watch | 交通运输 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
