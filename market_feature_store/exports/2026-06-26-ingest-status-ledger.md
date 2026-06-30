# 2026-06-26 Ingest Status Ledger

## 摘要

- **item_count**: 66
- **status_counts**: `{"candidate_detected": 50, "backfill_queued": 12, "pending_review": 4}`
- **action_counts**: `{"detect_candidate": 50, "queue_backfill_gap": 12, "review_attach_or_archive_evidence": 2, "review_create_or_link_concept": 2}`

## 明细

| 状态 | 优先级 | Rank | Tier | 题材 | 缺口 | 下一步 |
|---|---|---:|---|---|---|---|
| candidate_detected | - | 1 | deep | 光学光电子 | - | detect_candidate |
| candidate_detected | - | 2 | deep | 光刻机 | - | detect_candidate |
| candidate_detected | - | 3 | deep | 电子化学品 | - | detect_candidate |
| candidate_detected | - | 4 | deep | 连板未映射 | - | detect_candidate |
| candidate_detected | - | 5 | deep | 存储芯片 | - | detect_candidate |
| candidate_detected | - | 6 | deep | 先进封装 | - | detect_candidate |
| candidate_detected | - | 7 | deep | AI眼镜 | - | detect_candidate |
| candidate_detected | - | 8 | deep | 共封装光学(CPO) | - | detect_candidate |
| candidate_detected | - | 9 | deep | 半导体 | - | detect_candidate |
| candidate_detected | - | 10 | deep | 商业航天 | - | detect_candidate |
| candidate_detected | - | 11 | watch | PCB | - | detect_candidate |
| candidate_detected | - | 12 | watch | 氢能源 | - | detect_candidate |
| candidate_detected | - | 13 | watch | 液冷服务器 | - | detect_candidate |
| candidate_detected | - | 14 | watch | 光纤 | - | detect_candidate |
| candidate_detected | - | 15 | watch | 风电 | - | detect_candidate |
| candidate_detected | - | 16 | watch | 数据中心 | - | detect_candidate |
| candidate_detected | - | 17 | watch | MCU芯片 | - | detect_candidate |
| candidate_detected | - | 18 | watch | 人形机器人 | - | detect_candidate |
| candidate_detected | - | 19 | watch | 海峡两岸 | - | detect_candidate |
| candidate_detected | - | 20 | watch | 光刻胶 | - | detect_candidate |
| candidate_detected | - | 21 | watch | 半导体设备 | - | detect_candidate |
| candidate_detected | - | 22 | watch | 传感器 | - | detect_candidate |
| candidate_detected | - | 23 | watch | AI PC | - | detect_candidate |
| candidate_detected | - | 24 | watch | 钙钛矿电池 | - | detect_candidate |
| candidate_detected | - | 25 | watch | MLCC | - | detect_candidate |
| candidate_detected | - | 26 | watch | 元件 | - | detect_candidate |
| candidate_detected | - | 27 | watch | 无人驾驶 | - | detect_candidate |
| candidate_detected | - | 28 | watch | 智能座舱 | - | detect_candidate |
| candidate_detected | - | 29 | watch | 机器视觉 | - | detect_candidate |
| candidate_detected | - | 30 | watch | 新型工业化 | - | detect_candidate |
| candidate_detected | - | 31 | long_tail | 毫米波雷达 | - | detect_candidate |
| candidate_detected | - | 32 | long_tail | 超级电容 | - | detect_candidate |
| candidate_detected | - | 33 | long_tail | 消费电子 | - | detect_candidate |
| candidate_detected | - | 34 | long_tail | TOPCON电池 | - | detect_candidate |
| candidate_detected | - | 35 | long_tail | 6G | - | detect_candidate |
| candidate_detected | - | 36 | long_tail | 信创 | - | detect_candidate |
| candidate_detected | - | 37 | long_tail | MR(混合现实) | - | detect_candidate |
| candidate_detected | - | 38 | long_tail | HJT电池 | - | detect_candidate |
| candidate_detected | - | 39 | long_tail | 3D打印 | - | detect_candidate |
| candidate_detected | - | 40 | long_tail | 小金属 | - | detect_candidate |
| candidate_detected | - | 41 | long_tail | AI手机 | - | detect_candidate |
| candidate_detected | - | 42 | long_tail | 算力租赁 | - | detect_candidate |
| candidate_detected | - | 43 | long_tail | 氟化工 | - | detect_candidate |
| candidate_detected | - | 44 | long_tail | 长安汽车 | - | detect_candidate |
| candidate_detected | - | 45 | long_tail | 虚拟电厂 | - | detect_candidate |
| candidate_detected | - | 46 | long_tail | 工业母机 | - | detect_candidate |
| candidate_detected | - | 47 | long_tail | 建筑材料 | - | detect_candidate |
| candidate_detected | - | 48 | long_tail | 磷化工 | - | detect_candidate |
| candidate_detected | - | 49 | long_tail | 玻璃玻纤 | - | detect_candidate |
| candidate_detected | - | 50 | long_tail | 量子科技 | - | detect_candidate |
| backfill_queued | low | 4 | deep | 连板未映射 | placeholder_market_theme | queue_backfill_gap |
| backfill_queued | medium | 14 | watch | 光纤 | missing_evidence | queue_backfill_gap |
| backfill_queued | medium | 19 | watch | 海峡两岸 | missing_evidence | queue_backfill_gap |
| backfill_queued | medium | 24 | watch | 钙钛矿电池 | missing_evidence | queue_backfill_gap |
| backfill_queued | medium | 26 | watch | 元件 | missing_evidence | queue_backfill_gap |
| backfill_queued | medium | 29 | watch | 机器视觉 | missing_evidence | queue_backfill_gap |
| backfill_queued | low | 34 | long_tail | TOPCON电池 | missing_evidence | queue_backfill_gap |
| backfill_queued | low | 37 | long_tail | MR(混合现实) | missing_evidence | queue_backfill_gap |
| backfill_queued | low | 44 | long_tail | 长安汽车 | missing_concept | queue_backfill_gap |
| backfill_queued | low | 44 | long_tail | 长安汽车 | missing_entity_exposures | queue_backfill_gap |
| backfill_queued | low | 44 | long_tail | 长安汽车 | missing_evidence | queue_backfill_gap |
| backfill_queued | low | 49 | long_tail | 玻璃玻纤 | missing_evidence | queue_backfill_gap |
| pending_review | high | 1 | deep | 光学光电子 | missing_evidence | review_attach_or_archive_evidence |
| pending_review | high | 8 | deep | 共封装光学(CPO) | missing_evidence | review_attach_or_archive_evidence |
| pending_review | high | 19 | watch | 海峡两岸 | missing_concept | review_create_or_link_concept |
| pending_review | high | 24 | watch | 钙钛矿电池 | missing_concept | review_create_or_link_concept |
