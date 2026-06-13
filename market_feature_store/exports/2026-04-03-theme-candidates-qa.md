# 2026-04-03 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-03-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-03-triggered-themes.json |
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
| 共同候选 | 共封装光学(CPO)、光纤、通信设备、铜缆高速连接、6G、光通信、医药、数据中心、风电、无人驾驶 |
| 仅新产物 | 创新药、液冷服务器、商业航天、特高压、光学光电子、化学制药、电网设备、人形机器人、海峡两岸、可控核聚变、光刻机、AI眼镜、新型工业化、医药商业、辅助生殖、机器视觉、半导体、PET铜箔、3D打印、HJT电池、港口航运、自动化设备、量子科技、小金属、TOPCON电池、太赫兹、小米汽车、减肥药、人工智能、储能、军工、AI智能体、低空经济、固态电池、AI应用、信创、数据要素、软件开发、钠离子电池、算力租赁 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 共封装光学(CPO) | 190.81 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 共封装光学(CPO) | 190.81 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 2 | 光纤 | 184.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 光纤 | 184.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 3 | 通信设备 | 180.03 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 3 | 通信设备 | 180.03 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 4 | 铜缆高速连接 | 159.49 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 4 | 铜缆高速连接 | 159.49 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 5 | 6G | 159.23 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 6G | 159.23 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 6 | 光通信 | 107.0 | limit_advance_cluster、capacity_industry | 6 | 光通信 | 107.0 | limit_advance_cluster、capacity_industry | matched |
| 7 | 医药 | 105.0 | limit_advance_cluster | 7 | 医药 | 105.0 | limit_advance_cluster | matched |
| 8 | 数据中心 | 80.5 | limit_heat、new_high_direction、new_high_cluster | 8 | 数据中心 | 80.5 | limit_heat、new_high_direction、new_high_cluster | matched |
| 9 | 风电 | 76.99 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 9 | 风电 | 76.99 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 10 | 无人驾驶 | 76.42 | limit_heat、new_high_direction、new_high_cluster | 10 | 无人驾驶 | 76.42 | limit_heat、new_high_direction、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 共封装光学(CPO) | CPO | 5 | 12 | 0 | missing_evidence | 涨幅2.12%，边际量16.59%，成交2572.5亿，容量前三 |
| 光纤 | AI算力驱动下的MPO光纤连接器产业 | 5 | 12 | 0 | missing_evidence | 涨幅1.79%，边际量18.58%，成交1473.49亿，容量前三 |
| 通信设备 | 通信设备 | 5 | 12 | 1 | - | 涨幅0.74%，边际量23.22%，成交1422.96亿，容量前三 |
| 铜缆高速连接 | 铜缆高速连接 | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence | 涨幅0.6%，边际量15.97%，成交538.36亿，容量前三 |
| 6G | 6G | 5 | 12 | 1 | - | 涨幅0.68%，边际量17.94%，成交1002.61亿，容量前三 |
| 光通信 | 光通信 | 5 | 12 | 2 | - | - |
| 医药 | 医药 | 5 | 12 | 1 | - | - |
| 数据中心 | 数据中心 | 5 | 12 | 1 | - | - |
| 风电 | 风电 | 5 | 12 | 1 | - | - |
| 无人驾驶 | 无人驾驶 | 4 | 10 | 1 | - | - |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 共封装光学(CPO) | 光莆股份、Coherent（COHR）、东山精密、东材科技、中芯国际 | 0 | missing_evidence |
| 光纤 | 三环集团、仕佳光子、光库科技、博创科技、太辰光 | 0 | missing_evidence |
| 通信设备 | 东山精密、中兴通讯、信科移动、意华股份、烽火通信 | 1 | - |
| 铜缆高速连接 | - | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 6G | 万丰奥威、三安光电、东方财富、中信海直、中兴通讯 | 1 | - |
| 光通信 | Lumentum、三安光电、东山精密、东材科技、中兴通讯 | 2 | - |
| 医药 | 丽珠集团、亚虹医药、仙琚制药、上海医药、达嘉维康 | 1 | - |
| 数据中心 | 东山精密、东阳光、中天科技、中恒电气、中电鑫龙 | 1 | - |
| 风电 | 东方电气、东方电缆、中信海直、中天科技、亨通光电 | 1 | - |
| 无人驾驶 | 万集科技、保隆科技、千里科技、四维图新、富临运业 | 1 | - |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 6 | 铜缆高速连接、海峡两岸、新型工业化、机器视觉、小米汽车、减肥药 |
| missing_entity_exposures | 4 | 铜缆高速连接、海峡两岸、新型工业化、小米汽车 |
| missing_evidence | 15 | 共封装光学(CPO)、光纤、铜缆高速连接、光学光电子、化学制药、海峡两岸、新型工业化、医药商业、机器视觉、TOPCON电池、太赫兹、小米汽车、减肥药、软件开发、钠离子电池 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=6、missing_entity_exposures=4、missing_evidence=15。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
