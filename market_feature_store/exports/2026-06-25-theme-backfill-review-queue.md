# 2026-06-25 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 5
- **status_counts**: `{"pending_review": 5}`
- **action_counts**: `{"review_attach_or_archive_evidence": 3, "review_create_or_link_concept": 2}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| high | pending_review | 2 | deep | 光纤 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 4 | deep | 共封装光学(CPO) | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 9 | deep | 元件 | missing_evidence | review_attach_or_archive_evidence | 先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。 |
| high | pending_review | 12 | watch | 钙钛矿电池 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
| high | pending_review | 26 | watch | 海峡两岸 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
