# 2026-04-01 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-01-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-04-01-triggered-themes.json |
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
| 共同候选 | 创新药、化学制药、合成生物、PCB、半导体、新型工业化、AI PC、3D打印、先进封装、英伟达 |
| 仅新产物 | 算力租赁、元件、光伏设备、医药、AIGC、信创、商业航天、ChatGPT、云计算、风电、数据中心、共封装光学(CPO)、CRO、医疗服务、减肥药、辅助生殖、生物制品、液冷服务器、燃料电池、海峡两岸、人形机器人、无人驾驶、三胎、特高压、银行、机器视觉、存储芯片、可控核聚变、通信设备、光纤、电力、量子科技、6G、塑料制品、小米汽车、储能、军工、AI应用、人工智能、AI智能体 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 创新药 | 193.82 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 创新药 | 193.82 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 2 | 化学制药 | 186.71 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 化学制药 | 186.71 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 3 | 合成生物 | 183.11 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 3 | 合成生物 | 183.11 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 4 | PCB | 169.55 | double_red、capacity_industry、new_high_direction、new_high_cluster | 4 | PCB | 169.55 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 5 | 半导体 | 155.69 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 半导体 | 155.69 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 6 | 新型工业化 | 150.4 | double_red、new_high_direction、new_high_cluster | 6 | 新型工业化 | 150.4 | double_red、new_high_direction、new_high_cluster | matched |
| 7 | AI PC | 148.41 | double_red、capacity_industry、new_high_direction、new_high_cluster | 7 | AI PC | 148.41 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 8 | 3D打印 | 146.27 | double_red、new_high_direction、new_high_cluster | 8 | 3D打印 | 146.27 | double_red、new_high_direction、new_high_cluster | matched |
| 9 | 先进封装 | 122.0 | double_red、capacity_industry、new_high_cluster | 9 | 先进封装 | 122.0 | double_red、capacity_industry、new_high_cluster | matched |
| 10 | 英伟达 | 118.0 | double_red、capacity_industry、new_high_cluster | 10 | 英伟达 | 118.0 | double_red、capacity_industry、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 创新药 | 创新药 | 5 | 12 | 1 | - | 涨幅4.72%，边际量49.29%，成交1196.42亿，容量前三 |
| 化学制药 | 原料药 | 1 | 1 | 0 | missing_evidence | 涨幅4.62%，边际量47.24%，成交657.65亿，容量前三 |
| 合成生物 | 合成生物学 | 5 | 12 | 1 | - | 涨幅2.91%，边际量14.85%，成交521.88亿，容量前三 |
| PCB | PCB | 5 | 12 | 2 | - | 涨幅3.16%，边际量10.96%，成交1204.6亿，容量前三 |
| 半导体 | 半导体 | 5 | 12 | 1 | - | 涨幅2.89%，边际量10.26%，成交1537.7亿，容量前三 |
| 新型工业化 | 新型工业化 | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence | 涨幅2.23%，边际量10.98%，成交827.31亿，非容量前三 |
| AI PC | AI服务器 | 5 | 12 | 0 | missing_evidence | 涨幅3.19%，边际量17.98%，成交584.19亿，容量前三 |
| 3D打印 | 3D打印 | 5 | 12 | 1 | - | 涨幅2.44%，边际量13.86%，成交660.17亿，非容量前三 |
| 先进封装 | 先进封装 | 5 | 12 | 2 | - | 涨幅2.9%，边际量17.82%，成交1238.99亿，容量前三 |
| 英伟达 | 英伟达Rubin架构 | 5 | 12 | 0 | missing_evidence | 涨幅3.14%，边际量18.76%，成交874.54亿，容量前三 |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 创新药 | 一心堂、上海医药、东富龙、九洲药业、亚虹医药 | 1 | - |
| 化学制药 | 圣诺生物 | 0 | missing_evidence |
| 合成生物 | ALL、凯赛生物、利民股份、华恒生物、奥翔药业 | 1 | - |
| PCB | 世运电路、东威科技、东山精密、东材科技、中国巨石 | 2 | - |
| 半导体 | 三安光电、华润微、华虹公司、士兰微、天岳先进 | 1 | - |
| 新型工业化 | - | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| AI PC | 春秋电子、泽宇智能、东山精密、中富电路、东材科技 | 0 | missing_evidence |
| 3D打印 | 华曙高科、南风股份、大族激光、XD艾为电、中兴通讯 | 1 | - |
| 先进封装 | 上峰水泥、上海新阳、东威科技、中国巨石、中微公司 | 2 | - |
| 英伟达 | 中际旭创、华工科技、工业富联、新易盛、沪电股份 | 0 | missing_evidence |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 8 | 新型工业化、ChatGPT、减肥药、生物制品、海峡两岸、三胎、机器视觉、小米汽车 |
| missing_entity_exposures | 5 | 新型工业化、ChatGPT、海峡两岸、三胎、小米汽车 |
| missing_evidence | 18 | 化学制药、新型工业化、AI PC、英伟达、元件、ChatGPT、共封装光学(CPO)、减肥药、生物制品、燃料电池、海峡两岸、三胎、银行、机器视觉、光纤、电力、塑料制品、小米汽车 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=8、missing_entity_exposures=5、missing_evidence=18。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
