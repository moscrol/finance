# 2026-04-02 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-02-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-02-triggered-themes.json |
| 新候选数量 | 50 | candidates |
| Deep 候选数量 | 10 | deep_candidates |
| Watch 候选数量 | 20 | watch_candidates |
| Long Tail 候选数量 | 20 | long_tail_candidates |
| 旧候选数量 | 10 | deep_themes + watch_themes |
| 共同候选 | 10 | 按 market_theme/canonical_concept 归一匹配 |
| 仅新产物 | 40 | - |
| 仅旧产物 | 0 | - |

## 二、新旧候选重合情况

| 类型 | 题材 |
| --- | --- |
| 共同候选 | 医药、商业航天、创新药、化学制药、减肥药、辅助生殖、合成生物、CRO、医疗服务、共封装光学(CPO) |
| 仅新产物 | 数据中心、生物制品、风电、阿尔茨海默、医疗器械、特高压、通信设备、光纤、海峡两岸、人形机器人、无人驾驶、液冷服务器、维生素、燃料电池、可控核聚变、铜缆高速连接、AIGC、港口航运、银行、3D打印、量子科技、算力租赁、塑料制品、盐湖提锂、6G、小米汽车、长安汽车、太赫兹、电力、储能、军工、氢能源、医药商业、股权变更、虚拟电厂、电网设备、石油加工贸易、光伏概念、光纤概念、油气开采及服务 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 医药 | 127.0 | limit_advance_cluster、capacity_industry | 1 | 医药 | 127.0 | limit_advance_cluster、capacity_industry | matched |
| 2 | 商业航天 | 96.29 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 2 | 商业航天 | 96.29 | limit_advance_cluster、capacity_industry、new_high_direction、new_high_cluster | matched |
| 3 | 创新药 | 93.07 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 创新药 | 93.07 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 4 | 化学制药 | 86.97 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 4 | 化学制药 | 86.97 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 5 | 减肥药 | 84.09 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 减肥药 | 84.09 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 6 | 辅助生殖 | 83.16 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 6 | 辅助生殖 | 83.16 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 7 | 合成生物 | 79.47 | new_high_direction、new_high_cluster、capacity_industry | 7 | 合成生物 | 79.47 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 8 | CRO | 79.29 | new_high_direction、new_high_cluster、capacity_industry | 8 | CRO | 79.29 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 9 | 医疗服务 | 78.56 | new_high_direction、new_high_cluster、capacity_industry | 9 | 医疗服务 | 78.56 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 10 | 共封装光学(CPO) | 78.24 | new_high_direction、new_high_cluster、capacity_industry | 10 | 共封装光学(CPO) | 78.24 | new_high_direction、capacity_industry、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 医药 | 医药 | 5 | 12 | 1 | - | - |
| 商业航天 | 商业航天 | 5 | 12 | 2 | - | - |
| 创新药 | 创新药 | 5 | 12 | 1 | - | - |
| 化学制药 | 原料药 | 1 | 1 | 0 | missing_evidence | - |
| 减肥药 | 减肥药 | 0 | 1 | 0 | missing_concept、missing_evidence | - |
| 辅助生殖 | 辅助生殖 | 2 | 8 | 1 | - | - |
| 合成生物 | 合成生物学 | 5 | 12 | 1 | - | - |
| CRO | CRO | 5 | 12 | 1 | - | - |
| 医疗服务 | 医疗服务 | 5 | 7 | 1 | - | - |
| 共封装光学(CPO) | CPO | 5 | 12 | 0 | missing_evidence | - |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 医药 | 丽珠集团、亚虹医药、仙琚制药、上海医药、达嘉维康 | 1 | - |
| 商业航天 | SpaceX、上海港湾、东方日升、中国卫通、中国星网 | 2 | - |
| 创新药 | 一心堂、上海医药、东富龙、九洲药业、亚虹医药 | 1 | - |
| 化学制药 | 圣诺生物 | 0 | missing_evidence |
| 减肥药 | 圣诺生物 | 0 | missing_concept、missing_evidence |
| 辅助生殖 | 丽珠集团、仙琚制药、共同药业、华大基因、开立医疗 | 1 | - |
| 合成生物 | ALL、凯赛生物、利民股份、华恒生物、奥翔药业 | 1 | - |
| CRO | TCL科技、三友化工、三超新材、东旭光电、中兴通讯 | 1 | - |
| 医疗服务 | 三博脑科、新开源、麦迪科技、乐普医疗、创新医疗 | 1 | - |
| 共封装光学(CPO) | 光莆股份、Coherent（COHR）、东山精密、东材科技、中芯国际 | 0 | missing_evidence |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 12 | 减肥药、生物制品、阿尔茨海默、海峡两岸、维生素、铜缆高速连接、小米汽车、长安汽车、股权变更、石油加工贸易、光伏概念、油气开采及服务 |
| missing_entity_exposures | 9 | 阿尔茨海默、海峡两岸、铜缆高速连接、小米汽车、长安汽车、股权变更、石油加工贸易、光伏概念、油气开采及服务 |
| missing_evidence | 23 | 化学制药、减肥药、共封装光学(CPO)、生物制品、阿尔茨海默、光纤、海峡两岸、维生素、燃料电池、铜缆高速连接、银行、塑料制品、盐湖提锂、小米汽车、长安汽车、太赫兹、电力、医药商业、股权变更、石油加工贸易、光伏概念、光纤概念、油气开采及服务 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=12、missing_entity_exposures=9、missing_evidence=23。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
