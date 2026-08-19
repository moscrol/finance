# feat/lane-composition-rules

## 这个分支做什么

W4：主车道 + overlay 声明式组合表。overnight 专用 if 已迁成表第一条；第二条是外部宏观事件 + 本地推演。

## 当前状态

已提交（本交接与实现同 commit）。未 push、未合 main。树应干净。

实现：`route_table.LANE_COMPOSITION_RULES`（谓词, extras, 名）。`resolve_evidence_plan` 通吃 `_apply_lane_composition`，无 `if _has_overnight_external_premise`。谓词仍导出给 `episode_tools`（同对象）。overlay 只追加 `news_search`/`web_search`，`mandatory=False`；不改 `question_type`、不加 required_outputs。

## 未验证 / 已知边界

- 从未 live；不与 #222 共存验证。
- overlay 只作用在已有 requirements 的 plan（forecast / 当日盘面）；空的 methodology/概念题不加。
- 第二条谓词收紧：美联储/FOMC/非农/CPI同比 ∧ A股/板块/推演。裸 CPI、纯新闻、纯「今晚复盘」不触发。

## 下一步

1. 用户确认后可 push / 开 PR。
2. 新混合形状往表加一行 + `_COMPOSITION_RULE_QUERIES` 登记，否则穷尽测试红。

## 踩过的坑

谓词若搬模块，必须保持 `evidence_capabilities._has_overnight_external_premise` 可调用——`episode_tools` 读这个私有名。现用「表第一条同对象别名」，别再写一份词表。

## 已验证

`test_evidence_capabilities` + `test_route_table` + overnight episode 回归全绿。表征：plan 源码无 overnight 专用 if。
