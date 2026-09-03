# 2026-08-26 题材补库 Review Queue

本文件是 review_only 清单，不直接写知识库。

## 策略

- **mode**: review_only
- **min_priority**: high
- **knowledge_write_allowed**: False
- **placeholder_rule**: items containing 未映射 are blocked_review

## 摘要

- **review_count**: 11
- **status_counts**: `{"approved-done": 4, "rejected-stub无核心公司证据": 1, "rejected-过宽同义不空建": 1, "rejected-随概念驳回": 2, "rejected-占位壳无独立研报": 1, "rejected-政策篮子过宽": 1, "rejected-8/16过宽不空建": 1}`
- **action_counts**: `{"review_attach_or_archive_evidence": 5, "review_create_or_link_concept": 4, "review_map_entity_exposures": 2}`

## 待审核项

| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |
|---|---|---:|---|---|---|---|---|
| critical | approved-done | 1 | deep | 工业金属 | missing_concept | review_create_or_link_concept | 已建 L1 子集卡 [[工业金属]]（Cu/Al/Zn/Pb），挂铜 DeepDive；不 alias 成铜。 |
| critical | rejected-stub无核心公司证据 | 4 | deep | 中特估 | missing_entity_exposures | review_map_entity_exposures | [[中特估]] 是黄金 DeepDive 带出的 stub，无独立核心公司证据；不拿央企名单凑暴露。 |
| critical | rejected-过宽同义不空建 | 5 | deep | 互联金融 | missing_concept | review_create_or_link_concept | 互联金融是支付/金融IT篮子；库内已有数字货币、跨境支付、互联网金融信息服务。8/16 不空建同义页。 |
| critical | rejected-随概念驳回 | 5 | deep | 互联金融 | missing_entity_exposures | review_map_entity_exposures | 概念不建页，不映射泛金融IT公司。 |
| high | approved-done | 1 | deep | 工业金属 | missing_evidence | review_attach_or_archive_evidence | 已挂 evidence target=工业金属，来源 [[铜_DeepDive_数据抽取_20260602]]。 |
| high | approved-done | 3 | deep | 黄金概念 | missing_evidence | review_attach_or_archive_evidence | 已挂 evidence target=黄金概念，来源 [[黄金_DeepDive_数据抽取_20260602]]；canonical 仍是黄金。 |
| high | rejected-随概念驳回 | 5 | deep | 互联金融 | missing_evidence | review_attach_or_archive_evidence | 无独立归档来源可挂盘面名「互联金融」。 |
| high | rejected-占位壳无独立研报 | 7 | deep | 数字货币/跨境支付 | missing_evidence | review_attach_or_archive_evidence | 数字货币/跨境支付两侧都是待补证占位壳；evidence_index 仅有体检回填，不把占位当新证据挂盘面名。 |
| high | approved-done | 10 | deep | 疫苗 | missing_evidence | review_attach_or_archive_evidence | 已挂 evidence target=疫苗，来源 [[动物疫苗产业新变化与新格局深度研究报告]]；不新建疫苗伞页。 |
| high | rejected-政策篮子过宽 | 23 | watch | 乡村振兴 | missing_concept | review_create_or_link_concept | 乡村振兴是政策/指数篮子，8/16 过宽只观察不空建。 |
| high | rejected-8/16过宽不空建 | 30 | watch | 机械设备 | missing_concept | review_create_or_link_concept | 机械设备在 TOO_WIDE 名单（医疗/通信/机械设备/粮食概念/基因概念）。 |
