# 2026-06-17 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 1
- **status_counts**: `{"pending_review": 1}`
- **action_counts**: `{"review_create_or_link_concept": 1}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| high | pending_review | 20 | watch | 大消费 | missing_concept | review_create_or_link_concept | 先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。 |
