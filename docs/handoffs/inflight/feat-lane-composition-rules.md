# feat/lane-composition-rules

## 这个分支做什么

W4：主车道 + overlay 声明式组合表。overnight 专用 if 已迁成表第一条；第二条是外部宏观事件 + 本地推演。

## 当前状态

两笔。未 push、未合 main。

`LANE_COMPOSITION_RULES` 声明式 overlay。overnight 是第一条；第二条外事+A股推演。general 回落也吃表（theme_analysis 真实路由），methodology/纯概念仍空。

## 未验证 / 已知边界

- 从未 live。
- 谓词：美联储/FOMC/非农/CPI同比 ∧ A股/板块/推演。裸 CPI、纯新闻、今晚复盘不触发。

## 下一步

用户确认后 push / 开 PR。新形状：表加一行 + `_COMPOSITION_RULE_QUERIES`。

## 踩过的坑

只在测试里写死 `market_forecast` 会让第二条规则空转——真实题常是 `theme_analysis`。`episode_tools` 仍读 `_has_overnight_external_premise` 私有名（表第一条同对象）。

## 已验证

`test_evidence_capabilities` + `test_route_table` 绿；theme_analysis 正例 + methodology 反例。
