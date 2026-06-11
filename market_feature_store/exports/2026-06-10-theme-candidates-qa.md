# 2026-06-10 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-06-10-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-06-10-triggered-themes.json |
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
| 共同候选 | 光刻胶、PPE树脂、半导体设备、存储芯片、MLCC、先进封装、PCB、共封装光学(CPO)、人形机器人、半导体 |
| 仅新产物 | 商业航天、数据中心、风电、机器视觉、光纤、海峡两岸、新型工业化、化学制品、液冷服务器、氢能源、PET铜箔、光刻机、银行、元件、光学光电子、燃料电池、自动化设备、3D打印、无人驾驶、钠离子电池、工业母机、6G、特高压、数据要素、IP经济(谷子经济)、小金属、塑料制品、AIGC、电子化学品、通信设备、稀土永磁、信创、氟化工、毫米波雷达、可控核聚变、航空发动机、电池、太赫兹、量子科技、房地产 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光刻胶 | 180.09 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 光刻胶 | 180.09 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 2 | PPE树脂 | 123.0 | limit_advance_cluster、capacity_industry | 2 | PPE树脂 | 123.0 | limit_advance_cluster、capacity_industry | matched |
| 3 | 半导体设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 3 | 半导体设备 | 116.0 | double_red、capacity_industry、new_high_cluster | matched |
| 4 | 存储芯片 | 93.56 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 4 | 存储芯片 | 93.56 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 5 | MLCC | 91.56 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | MLCC | 91.56 | limit_advance_cluster、new_high_direction、capacity_industry、new_high_cluster | matched |
| 6 | 先进封装 | 89.36 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 6 | 先进封装 | 89.36 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 7 | PCB | 87.37 | new_high_direction、new_high_cluster、capacity_industry | 7 | PCB | 87.37 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 8 | 共封装光学(CPO) | 86.7 | new_high_direction、new_high_cluster、capacity_industry | 8 | 共封装光学(CPO) | 86.7 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 9 | 人形机器人 | 86.16 | new_high_direction、new_high_cluster、capacity_industry | 9 | 人形机器人 | 86.16 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 10 | 半导体 | 85.63 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 10 | 半导体 | 85.63 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 光刻胶 | 光刻胶 | 5 | 12 | 1 | - | 涨幅1.51%，边际量11.2%，成交725.24亿，容量前三 |
| PPE树脂 | PPE树脂 | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence | - |
| 半导体设备 | 半导体设备 | 5 | 12 | 3 | - | 涨幅1.31%，边际量27.02%，成交537.36亿，容量前三 |
| 存储芯片 | 存储芯片 | 5 | 12 | 1 | - | - |
| MLCC | MLCC | 5 | 9 | 1 | - | - |
| 先进封装 | 先进封装 | 5 | 12 | 2 | - | - |
| PCB | PCB | 5 | 12 | 2 | - | - |
| 共封装光学(CPO) | CPO | 5 | 12 | 0 | missing_evidence | - |
| 人形机器人 | 人形机器人 | 5 | 12 | 2 | - | - |
| 半导体 | 半导体 | 5 | 12 | 1 | - | - |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 光刻胶 | 万润股份、上海新阳、中芯国际、八亿时空、华特气体 | 1 | - |
| PPE树脂 | - | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 半导体设备 | 中微公司、中科飞测、亚翔集成、光力科技、凤凰光学 | 3 | - |
| 存储芯片 | SK海力士（000660.KS）、上峰水泥、上海合晶、东芯股份、中微公司 | 1 | - |
| MLCC | 博杰股份、国瓷材料、洁美科技、风华高科、博迁新材 | 1 | - |
| 先进封装 | 上峰水泥、上海新阳、东威科技、中国巨石、中微公司 | 2 | - |
| PCB | 世运电路、东威科技、东山精密、东材科技、中国巨石 | 2 | - |
| 共封装光学(CPO) | 光莆股份、Coherent（COHR）、东山精密、东材科技、中芯国际 | 0 | missing_evidence |
| 人形机器人 | 三花智控、中大力德、中研股份、丰立智能、亿嘉和 | 2 | - |
| 半导体 | 三安光电、华润微、华虹公司、士兰微、天岳先进 | 1 | - |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 4 | PPE树脂、机器视觉、海峡两岸、新型工业化 |
| missing_entity_exposures | 3 | PPE树脂、海峡两岸、新型工业化 |
| missing_evidence | 16 | PPE树脂、共封装光学(CPO)、机器视觉、光纤、海峡两岸、新型工业化、化学制品、银行、元件、光学光电子、燃料电池、钠离子电池、IP经济(谷子经济)、塑料制品、电池、太赫兹 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=4、missing_entity_exposures=3、missing_evidence=16。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
