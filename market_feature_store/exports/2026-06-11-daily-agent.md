# Daily Agent Report - 2026-06-11

## 今日判断

- Daily ops status: `WARN`
- Logic scanned: 8
- Old logic wakeup: 5
- New logic candidate: 0
- Data gap: 3
- Noise/unconfirmed: 0

## 旧逻辑唤醒

- 光刻胶｜priority=184.57｜confidence=0.95｜强势股=华特气体, 兴福电子, 雅克科技, 南大光电, 彤程新材｜缺口=-｜路径=front-map / deep-dive
- 小金属｜priority=163.23｜confidence=0.95｜强势股=云南锗业, 阿石创, 风华高科, 欧莱新材, 中钨高新｜缺口=-｜路径=front-map / deep-dive
- 电子化学品｜priority=154.08｜confidence=0.95｜强势股=中船特气, 中巨芯, 华特气体, 兴福电子, 南大光电｜缺口=-｜路径=front-map / deep-dive
- 氟化工｜priority=152.28｜confidence=0.95｜强势股=中船特气, 中巨芯, 华特气体, 云南锗业, 多氟多｜缺口=-｜路径=front-map / deep-dive
- 磷化工｜priority=145.98｜confidence=0.95｜强势股=兴福电子, 雅克科技, 南大光电, 昊华科技, 川金诺｜缺口=-｜路径=front-map / deep-dive

## 新逻辑候选

- 无

## 数据缺口 / 以后统一回补

- 连板未映射｜priority=183.0｜confidence=0.35｜强势股=-｜缺口=missing_concept, missing_entity_exposure, missing_evidence｜路径=进入统一回补队列，先判断是不是污染词或别名
- 金属铜｜priority=141.71｜confidence=0.55｜强势股=中钨高新, 章源钨业, 国城矿业, 翔鹭钨业, 鑫科材料｜缺口=missing_concept, missing_evidence｜路径=进入统一回补队列，先判断是不是污染词或别名
- 金属钴｜priority=132.49｜confidence=0.35｜强势股=中钨高新, 厦门钨业, 赣锋锂业, 洛阳钼业, 盛屯矿业｜缺口=missing_concept, missing_entity_exposure, missing_evidence｜路径=进入统一回补队列，先判断是不是污染词或别名

## 暂不处理

- 无

## Gap Queue

- 连板未映射｜data_gap｜priority=278.0｜gaps=missing_concept, missing_entity_exposure, missing_evidence
- 金属钴｜data_gap｜priority=227.49｜gaps=missing_concept, missing_entity_exposure, missing_evidence
- 金属铜｜data_gap｜priority=211.71｜gaps=missing_concept, missing_evidence

## Next Actions

- 优先打开 old_logic_wakeup：确认是否需要 front-map 或 deep-dive。
- 数据缺口只登记到回补队列；本轮不自动 source/concept/IMA 回补。
- 先补齐 daily workflow 产物，否则 agent 判断只作为预览。

## Notes

- agent-daily 是只读入口：读取 daily workflow、知识库和 logic-match 产物，不自动回补。
- 回补类事项只进入 data_gap / gap_queue，等待用户统一处理。
