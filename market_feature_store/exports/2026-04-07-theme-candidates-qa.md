# 2026-04-07 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-07-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-07-triggered-themes.json |
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
| 共同候选 | 先进封装、存储芯片、光通信、半导体、PCB、共封装光学(CPO)、风电、光纤、通信设备、数据中心 |
| 仅新产物 | 液冷服务器、创新药、氢能源、6G、无人驾驶、特高压、电网设备、人形机器人、铜缆高速连接、商业航天、海峡两岸、机器视觉、光刻机、PET铜箔、新型工业化、TOPCON电池、可控核聚变、钙钛矿电池、传感器、虚拟电厂、量子科技、毫米波雷达、太赫兹、小米汽车、数据要素、医药、储能、固态电池、人工智能、低空经济、军工、化学制药、化学制品、地缘冲突、算力、化学原料、建筑装饰、家居用品、芯片概念、光伏概念 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 先进封装 | 166.5 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 先进封装 | 166.5 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 2 | 存储芯片 | 127.75 | double_red、capacity_industry、limit_heat、new_high_cluster | 2 | 存储芯片 | 127.75 | double_red、capacity_industry、limit_heat、new_high_cluster | matched |
| 3 | 光通信 | 119.0 | limit_advance_cluster、capacity_industry | 3 | 光通信 | 119.0 | limit_advance_cluster、capacity_industry | matched |
| 4 | 半导体 | 116.0 | double_red、capacity_industry、new_high_cluster | 4 | 半导体 | 116.0 | double_red、capacity_industry、new_high_cluster | matched |
| 5 | PCB | 101.14 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | PCB | 101.14 | limit_advance_cluster、capacity_industry、new_high_direction、new_high_cluster | matched |
| 6 | 共封装光学(CPO) | 85.26 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 6 | 共封装光学(CPO) | 85.26 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 7 | 风电 | 82.35 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 7 | 风电 | 82.35 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 8 | 光纤 | 82.14 | new_high_direction、new_high_cluster、capacity_industry | 8 | 光纤 | 82.14 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 9 | 通信设备 | 81.12 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 9 | 通信设备 | 81.12 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 10 | 数据中心 | 78.94 | limit_heat、new_high_direction、new_high_cluster | 10 | 数据中心 | 78.94 | limit_heat、new_high_direction、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 先进封装 | 先进封装 | 5 | 12 | 2 | - | 涨幅1.56%，边际量12.29%，成交1180.54亿，容量前三 |
| 存储芯片 | 存储芯片 | 5 | 12 | 1 | - | 涨幅1.79%，边际量12.76%，成交1214.06亿，容量前三 |
| 光通信 | 光通信 | 5 | 12 | 2 | - | - |
| 半导体 | 半导体 | 5 | 12 | 1 | - | 涨幅1.32%，边际量17.27%，成交1278.31亿，容量前三 |
| PCB | PCB | 5 | 12 | 2 | - | - |
| 共封装光学(CPO) | CPO | 5 | 12 | 0 | missing_evidence | - |
| 风电 | 风电 | 5 | 12 | 1 | - | - |
| 光纤 | AI算力驱动下的MPO光纤连接器产业 | 5 | 12 | 0 | missing_evidence | - |
| 通信设备 | 通信设备 | 5 | 12 | 1 | - | - |
| 数据中心 | 数据中心 | 5 | 12 | 1 | - | - |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 先进封装 | 上峰水泥、上海新阳、东威科技、中国巨石、中微公司 | 2 | - |
| 存储芯片 | SK海力士（000660.KS）、上峰水泥、上海合晶、东芯股份、中微公司 | 1 | - |
| 光通信 | Lumentum、三安光电、东山精密、东材科技、中兴通讯 | 2 | - |
| 半导体 | 三安光电、华润微、华虹公司、士兰微、天岳先进 | 1 | - |
| PCB | 世运电路、东威科技、东山精密、东材科技、中国巨石 | 2 | - |
| 共封装光学(CPO) | 光莆股份、Coherent（COHR）、东山精密、东材科技、中芯国际 | 0 | missing_evidence |
| 风电 | 东方电气、东方电缆、中信海直、中天科技、亨通光电 | 1 | - |
| 光纤 | 三环集团、仕佳光子、光库科技、博创科技、太辰光 | 0 | missing_evidence |
| 通信设备 | 东山精密、中兴通讯、信科移动、意华股份、烽火通信 | 1 | - |
| 数据中心 | 东山精密、东阳光、中天科技、中恒电气、中电鑫龙 | 1 | - |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 10 | 铜缆高速连接、海峡两岸、机器视觉、新型工业化、钙钛矿电池、小米汽车、地缘冲突、家居用品、芯片概念、光伏概念 |
| missing_entity_exposures | 7 | 铜缆高速连接、海峡两岸、新型工业化、小米汽车、家居用品、芯片概念、光伏概念 |
| missing_evidence | 18 | 共封装光学(CPO)、光纤、铜缆高速连接、海峡两岸、机器视觉、新型工业化、TOPCON电池、钙钛矿电池、太赫兹、小米汽车、化学制药、化学制品、地缘冲突、化学原料、建筑装饰、家居用品、芯片概念、光伏概念 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=10、missing_entity_exposures=7、missing_evidence=18。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
