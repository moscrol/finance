# 2026-05-25 theme-candidates 对照验证报告

> 说明：本报告只读取本地 JSON 产物；不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型，不包含买卖指令。

## 一、输入文件状态

| 项目 | 状态 | 路径/数值 |
| --- | --- | --- |
| 新 theme-candidates JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-05-25-theme-candidates.json |
| 旧 triggered-themes JSON | 存在 | /Users/lbq/Desktop/c c/金融/market_feature_store/exports/2026-05-25-triggered-themes.json |
| 新候选数量 | 50 | candidates |
| 旧候选数量 | 10 | deep_themes + watch_themes |
| 共同候选 | 10 | 按 market_theme/canonical_concept 归一匹配 |
| 仅新产物 | 40 | - |
| 仅旧产物 | 0 | - |

## 二、新旧候选重合情况

| 类型 | 题材 |
| --- | --- |
| 共同候选 | 先进封装、PCB、MLCC、存储芯片、半导体、共封装光学(CPO)、风电、MCU芯片、半导体设备、英伟达 |
| 仅新产物 | 高压快充、数据中心、3D打印、消费电子、商业航天、光刻胶、华为手机、特高压、无人驾驶、超级电容、毫米波雷达、电子化学品、6G、大飞机、航空发动机、元件、量子科技、通信设备、BC电池、HJT电池、MR(混合现实)、可控核聚变、芯片、铜缆高速连接、人工智能、低空经济、军工、AI智能体、电力、DeepSeek、云计算、信创、军工装备、软件开发、雅下水电、算力租赁、华为昇腾、光通信、人形机器人、传感器 |
| 仅旧产物 | - |

## 三、Top N 排序对照

| 新排名 | 新题材 | 新评分 | 新触发 | 旧排名 | 旧题材 | 旧评分 | 旧触发 | 匹配状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 先进封装 | 336.95 | double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 1 | 先进封装 | 336.95 | double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | matched |
| 2 | PCB | 325.0 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | PCB | 325.0 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | matched |
| 3 | MLCC | 298.36 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 3 | MLCC | 298.36 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | matched |
| 4 | 存储芯片 | 234.6 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 4 | 存储芯片 | 234.6 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | matched |
| 5 | 半导体 | 214.35 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 半导体 | 214.35 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | matched |
| 6 | 共封装光学(CPO) | 202.55 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 6 | 共封装光学(CPO) | 202.55 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 7 | 风电 | 191.47 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 7 | 风电 | 191.47 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | matched |
| 8 | MCU芯片 | 186.75 | double_red、capacity_industry、new_high_direction、new_high_cluster | 8 | MCU芯片 | 186.75 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |
| 9 | 半导体设备 | 186.4 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 9 | 半导体设备 | 186.4 | double_red、capacity_industry、multi_period_rank、new_high_cluster | matched |
| 10 | 英伟达 | 185.97 | double_red、capacity_industry、new_high_direction、new_high_cluster | 10 | 英伟达 | 185.97 | double_red、capacity_industry、new_high_direction、new_high_cluster | matched |

## 四、知识库命中与缺口

| 题材 | 标准概念 | 概念数 | 公司暴露数 | 证据数 | 缺口 | 盘面信号 |
| --- | --- | --- | --- | --- | --- | --- |
| 先进封装 | 先进封装 | 5 | 12 | 2 | - | 涨幅4.63%，边际量19.37%，成交4202.9亿，容量前三 |
| PCB | PCB | 5 | 12 | 2 | - | 涨幅2.36%，边际量10.31%，成交3691.95亿，容量前三 |
| MLCC | MLCC | 5 | 9 | 1 | - | 涨幅3.81%，边际量85.05%，成交751.36亿，容量前三 |
| 存储芯片 | 存储芯片 | 5 | 12 | 1 | - | 涨幅4.01%，边际量21.11%，成交6008.52亿，容量前三 |
| 半导体 | 半导体 | 5 | 12 | 1 | - | 涨幅4.52%，边际量23.46%，成交5344.67亿，容量前三 |
| 共封装光学(CPO) | CPO | 5 | 12 | 0 | missing_evidence | 涨幅2.7%，边际量13.69%，成交6196.08亿，容量前三 |
| 风电 | 风电 | 5 | 12 | 1 | - | 涨幅0.44%，边际量10.72%，成交3075.84亿，容量前三 |
| MCU芯片 | MCU芯片 | 3 | 2 | 1 | - | 涨幅3.73%，边际量25.28%，成交1450.33亿，容量前三 |
| 半导体设备 | 半导体设备 | 5 | 12 | 3 | - | 涨幅3.74%，边际量16.69%，成交837.9亿，容量前三 |
| 英伟达 | 英伟达Rubin架构 | 5 | 12 | 0 | missing_evidence | 涨幅1.77%，边际量10.25%，成交1990.5亿，容量前三 |

## 五、候选公司覆盖抽查

| 题材 | 候选公司 Top5 | 证据数 | 缺口 |
| --- | --- | --- | --- |
| 先进封装 | 上峰水泥、上海新阳、东威科技、中国巨石、中微公司 | 2 | - |
| PCB | 世运电路、东威科技、东山精密、东材科技、中国巨石 | 2 | - |
| MLCC | 博杰股份、国瓷材料、洁美科技、风华高科、博迁新材 | 1 | - |
| 存储芯片 | SK海力士（000660.KS）、上峰水泥、上海合晶、东芯股份、中微公司 | 1 | - |
| 半导体 | 三安光电、华润微、华虹公司、士兰微、天岳先进 | 1 | - |
| 共封装光学(CPO) | 光莆股份、Coherent（COHR）、东山精密、东材科技、中芯国际 | 0 | missing_evidence |
| 风电 | 东方电气、东方电缆、中信海直、中天科技、亨通光电 | 1 | - |
| MCU芯片 | 兆易创新、乐鑫科技 | 1 | - |
| 半导体设备 | 中微公司、中科飞测、亚翔集成、光力科技、凤凰光学 | 3 | - |
| 英伟达 | 中际旭创、华工科技、工业富联、新易盛、沪电股份 | 0 | missing_evidence |

## 六、待补库清单

| 缺口 | 次数 | 涉及题材 |
| --- | --- | --- |
| missing_concept | 4 | 华为手机、铜缆高速连接、DeepSeek、雅下水电 |
| missing_entity_exposures | 3 | 华为手机、铜缆高速连接、雅下水电 |
| missing_evidence | 12 | 共封装光学(CPO)、英伟达、高压快充、华为手机、元件、MR(混合现实)、芯片、铜缆高速连接、电力、DeepSeek、软件开发、雅下水电 |

## 七、工程结论

- **候选重合度**：10 / 50（以新候选数为主口径）。
- **新产物覆盖**：共 50 个候选，旧产物共 10 个 deep/watch 候选。
- **补库缺口**：missing_concept=4、missing_entity_exposures=3、missing_evidence=12。
- **工作台建议**：先保留为 QA 辅助产物，不替换旧题材简报；待多日期抽样稳定后再决定展示字段。
