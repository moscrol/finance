# 2026-06-09 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-06-09-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-06-09-triggered-themes.json |
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
| 共同候选 | 光刻胶、MLCC、CCL、物理AI、共封装光学(CPO)、人形机器人、数据中心、存储芯片、PCB、商业航天 |
| 仅新产物 | 风电、液冷服务器、元件、新型工业化、机器视觉、先进封装、通用设备、氢能源、半导体、无人驾驶、光纤、信创、燃料电池、传感器、数据要素、工业母机、海峡两岸、英伟达、AIGC、6G、ChatGPT、多模态AI、光刻机、PET铜箔、长安汽车、通信设备、低空经济、钙钛矿电池、钠离子电池、大飞机、机器人、云计算、特高压、电子化学品、IT服务、超级电容、毫米波雷达、可控核聚变、氟化工、量子科技 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光刻胶 | 168.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 光刻胶 | 168.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 2 | MLCC | 152.11 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | MLCC | 152.11 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 3 | CCL | 107.0 | limit_advance_cluster、capacity_industry | 3 | CCL | 107.0 | limit_advance_cluster、capacity_industry | matched |
| 4 | 物理AI | 101.0 | limit_advance_cluster | 4 | 物理AI | 101.0 | limit_advance_cluster | matched |
| 5 | 共封装光学(CPO) | 96.95 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 共封装光学(CPO) | 96.95 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 6 | 人形机器人 | 94.4 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 6 | 人形机器人 | 94.39 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 7 | 数据中心 | 91.93 | limit_heat、new_high_direction、new_high_cluster | 7 | 数据中心 | 91.93 | limit_heat、new_high_direction、new_high_cluster | matched |
| 8 | 存储芯片 | 90.69 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 8 | 存储芯片 | 90.69 | limit_heat、new_high_direction、capacity_industry、new_high_cluster | matched |
| 9 | PCB | 86.37 | new_high_direction、new_high_cluster、capacity_industry | 9 | PCB | 86.37 | new_high_direction、capacity_industry、new_high_cluster | matched |
| 10 | 商业航天 | 85.23 | limit_heat、new_high_direction、new_high_cluster | 10 | 商业航天 | 85.23 | limit_heat、new_high_direction、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 光刻胶 | 光刻胶 | 5 | 12 | 1 | - | 涨幅5.14%，边际量10.2%，成交652.19亿，容量前三 |
| MLCC | MLCC | 5 | 9 | 1 | - | 涨幅5.76%，边际量29.66%，成交957.19亿，容量前三 |
| CCL | 高端CCL | 3 | 5 | 0 | missing_evidence | - |
| 物理AI | 物理AI | 5 | 12 | 1 | - | - |
| 共封装光学(CPO) | CPO | 5 | 12 | 0 | missing_evidence | - |
| 人形机器人 | 人形机器人 | 5 | 12 | 2 | - | - |
| 数据中心 | 数据中心 | 5 | 12 | 1 | - | - |
| 存储芯片 | 存储芯片 | 5 | 12 | 1 | - | - |
| PCB | PCB | 5 | 12 | 2 | - | - |
| 商业航天 | 商业航天 | 5 | 12 | 2 | - | - |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 光刻胶 | 万润股份、上海新阳、中芯国际、八亿时空、华特气体 | 1 | - |
| MLCC | 博杰股份、国瓷材料、洁美科技、风华高科、博迁新材 | 1 | - |
| CCL | 沪电股份、南亚新材、德福科技、华正新材、圣泉集团 | 0 | missing_evidence |
| 物理AI | 万丰奥威、三花智控、中信海直、中大力德、中航光电 | 1 | - |
| 共封装光学(CPO) | 光莆股份、Coherent（COHR）、东山精密、东材科技、中芯国际 | 0 | missing_evidence |
| 人形机器人 | 三花智控、中大力德、中研股份、丰立智能、亿嘉和 | 2 | - |
| 数据中心 | 东山精密、东阳光、中天科技、中恒电气、中电鑫龙 | 1 | - |
| 存储芯片 | SK海力士（000660.KS）、上峰水泥、上海合晶、东芯股份、中微公司 | 1 | - |
| PCB | 世运电路、东威科技、东山精密、东材科技、中国巨石 | 2 | - |
| 商业航天 | SpaceX、上海港湾、东方日升、中国卫通、中国星网 | 2 | - |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 6 | 新型工业化、机器视觉、海峡两岸、ChatGPT、长安汽车、钙钛矿电池 |
| missing_entity_exposures | 4 | 新型工业化、海峡两岸、ChatGPT、长安汽车 |
| missing_evidence | 14 | CCL、共封装光学(CPO)、元件、新型工业化、机器视觉、通用设备、光纤、燃料电池、海峡两岸、英伟达、ChatGPT、长安汽车、钙钛矿电池、钠离子电池 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=6、missing_entity_exposures=4、missing_evidence=14。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
