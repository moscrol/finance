# 2026-08-27 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 7
- **status_counts**: `{"rejected-申万一篮子": 1, "rejected-8/16过宽一级": 1, "rejected-无盘面target证据": 1, "approved-done": 1, "rejected-平台成分股篮子": 3}`
- **action_counts**: `{"review_attach_or_archive_evidence": 4, "review_create_or_link_concept": 3}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| high | rejected-申万一篮子 | 1 | deep | 电子 | missing_evidence | review_attach_or_archive_evidence | 盘面「电子」是申万一级，matcher 映射到 EDA；证据应留在 EDA/细分，不改挂「电子」。 |
| high | rejected-8/16过宽一级 | 5 | deep | 通信 | missing_evidence | review_attach_or_archive_evidence | 通信在 TOO_WIDE；光通信/通信设备等细分已有证据，不把细分证据改挂「通信」。 |
| high | rejected-无盘面target证据 | 6 | deep | 元器件 | missing_evidence | review_attach_or_archive_evidence | 电子元器件有图谱/年报暴露，但 evidence_index 无 target=元器件 的已归档条目；保持待补。 |
| high | approved-done | 9 | deep | CPO概念 | missing_evidence | review_attach_or_archive_evidence | 已挂 evidence target=CPO概念，来源 [[20260518 市场逻辑精选]]；canonical 仍是 CPO。 |
| high | rejected-平台成分股篮子 | 19 | watch | 抖音概念 | missing_concept | review_create_or_link_concept | 抖音概念是平台成分股篮子，8/16 不空建。 |
| high | rejected-平台成分股篮子 | 20 | watch | 阿里概念 | missing_concept | review_create_or_link_concept | 阿里概念是平台成分股篮子，8/16 不空建。 |
| high | rejected-平台成分股篮子 | 21 | watch | 腾讯概念 | missing_concept | review_create_or_link_concept | 腾讯概念是平台成分股篮子，8/16 不空建。 |
