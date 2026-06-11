# 2026-06-05 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-06-05-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-06-05-triggered-themes.json |
| 新候选数量 | 50 | candidates |
| 旧候选数量 | 10 | deep_themes + watch_themes |
| 共同候选 | 10 | 按 market_theme/canonical_concept 归一匹配 |
| 仅新产物 | 40 | - |
| 仅旧产物 | 0 | - |

## 二、新旧候选重合情况

| 类型 | 题材 |
| --- | --- |
| 共同候选 | 人形机器人、光纤、通信设备、新型工业化、传感器、通用设备、光学光电子、6G、商业航天、机器视觉 |
| 仅新产物 | 3D打印、减速器、无人驾驶、氢能源、海峡两岸、燃料电池、机器人、长安汽车、量子科技、毫米波雷达、钙钛矿电池、数据要素、太赫兹、多模态AI、超导、工业母机、消费电子、自动化设备、军工、人工智能、低空经济、AI智能体、AI应用、星闪、MR(混合现实)、DeepSeek、光伏、大飞机、汽车零部件、PCB、飞行汽车(eVTOL)、AIGC、氟化工、军工信息化、ChatGPT、创新药、航空发动机、低价股、共封装光学(CPO)、数据中心 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 人形机器人 | 200.68 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 人形机器人 | 200.68 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 2 | 光纤 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 光纤 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 3 | 通信设备 | 191.6 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 通信设备 | 191.6 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 4 | 新型工业化 | 189.08 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 4 | 新型工业化 | 189.08 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 5 | 传感器 | 187.17 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 传感器 | 187.17 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 6 | 通用设备 | 185.51 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 6 | 通用设备 | 185.51 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 7 | 光学光电子 | 184.98 | double_red、capacity_industry、new_high_direction、new_high_cluster | 7 | 光学光电子 | 184.98 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 8 | 6G | 182.64 | double_red、capacity_industry、new_high_direction、new_high_cluster | 8 | 6G | 182.64 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 9 | 商业航天 | 182.55 | double_red、limit_heat、new_high_direction、new_high_cluster | 9 | 商业航天 | 182.55 | double_red、limit_heat、new_high_direction、new_high_cluster | matched |
| 10 | 机器视觉 | 176.69 | double_red、capacity_industry、new_high_direction、new_high_cluster | 10 | 机器视觉 | 176.69 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 人形机器人 | 人形机器人 | 5 | 12 | 2 | - | 涨幅1.48%，边际量18.16%，成交5168.65亿，容量前三 |
| 光纤 | AI算力驱动下的MPO光纤连接器产业 | 5 | 12 | 0 | missing_evidence | 涨幅0.04%，边际量24.88%，成交3669.16亿，容量前三 |
| 通信设备 | 通信设备 | 5 | 12 | 1 | - | 涨幅1.12%，边际量42.94%，成交3204.66亿，容量前三 |
| 新型工业化 | 新型工业化 | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence | 涨幅2.21%，边际量28.65%，成交1948.42亿，容量前三 |
| 传感器 | 传感器 | 5 | 12 | 1 | - | 涨幅0.86%，边际量18.95%，成交2957.25亿，容量前三 |
| 通用设备 | 金属制品 | 1 | 1 | 0 | missing_evidence | 涨幅2.17%，边际量21.57%，成交951.86亿，容量前三 |
| 光学光电子 | LED芯片 | 2 | 2 | 0 | missing_evidence | 涨幅1.2%，边际量31.5%，成交1300.78亿，容量前三 |
| 6G | 6G | 5 | 12 | 1 | - | 涨幅1.66%，边际量31.57%，成交2394.21亿，容量前三 |
| 商业航天 | 商业航天 | 5 | 12 | 2 | - | 涨幅1.09%，边际量23.87%，成交5633.83亿，非容量前三 |
| 机器视觉 | 机器视觉 | 0 | 2 | 0 | missing_concept、missing_evidence | 涨幅1.19%，边际量15.25%，成交1676.71亿，容量前三 |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 人形机器人 | 三花智控、中大力德、中研股份、丰立智能、亿嘉和 | 2 | - |
| 光纤 | 三环集团、仕佳光子、光库科技、博创科技、太辰光 | 0 | missing_evidence |
| 通信设备 | 东山精密、中兴通讯、信科移动、意华股份、烽火通信 | 1 | - |
| 新型工业化 | - | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 传感器 | 华域汽车、华润微、士兰微、奥比中光、安培龙 | 1 | - |
| 通用设备 | 东睦股份 | 0 | missing_evidence |
| 光学光电子 | 三安光电、三利谱 | 0 | missing_evidence |
| 6G | 万丰奥威、三安光电、东方财富、中信海直、中兴通讯 | 1 | - |
| 商业航天 | SpaceX、上海港湾、东方日升、中国卫通、中国星网 | 2 | - |
| 机器视觉 | 宇瞳光学、联创电子 | 0 | missing_concept、missing_evidence |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 9 | 新型工业化、机器视觉、海峡两岸、长安汽车、钙钛矿电池、DeepSeek、军工信息化、ChatGPT、低价股 |
| missing_entity_exposures | 6 | 新型工业化、海峡两岸、长安汽车、星闪、ChatGPT、低价股 |
| missing_evidence | 17 | 光纤、新型工业化、通用设备、光学光电子、机器视觉、海峡两岸、燃料电池、长安汽车、钙钛矿电池、太赫兹、星闪、MR(混合现实)、DeepSeek、飞行汽车(eVTOL)、ChatGPT、低价股、共封装光学(CPO) |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=9、missing_entity_exposures=6、missing_evidence=17。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
