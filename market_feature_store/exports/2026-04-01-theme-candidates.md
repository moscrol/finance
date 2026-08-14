# 2026-04-01 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：横盘
- **成交额**：20122.0
- **上涨家数**：4495
- **涨停 / 跌停**：56 / 6
- **容量前三行业**：1.电子(15.9%, capacity)、2.电力设备(12.1%, normal)、3.医药生物(8.0%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 创新药 | 创新药 | 医药生物 | 193.82 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 化学制药 | 原料药 | 医药生物 | 186.71 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 3 | 合成生物 | 合成生物学 | 医药生物 | 183.11 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | PCB | PCB | 电子 | 169.55 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 5 | 半导体 | 半导体 | 电子 | 155.69 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 新型工业化 | 新型工业化 | 机械设备 | 150.4 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | AI PC | AI服务器 | 电子 | 148.41 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 8 | 3D打印 | 3D打印 | 机械设备 | 146.27 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 先进封装 | 先进封装 | 电子 | 122.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 2 | - |
| 10 | 英伟达 | 英伟达Rubin架构 | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 算力租赁 | 算力租赁 | 计算机 | 117.4 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 元件 | 电子元件 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 13 | 光伏设备 | 光伏设备 | 电力设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 医药 | 医药 | 医药生物 | 115.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 1 | - |
| 15 | AIGC | AIGC | 传媒 | 112.0 | double_red、new_high_cluster | 5 | 5 | 1 | - |
| 16 | 信创 | 信创 | 计算机 | 112.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 17 | 商业航天 | 商业航天 | 电力设备 | 99.33 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 18 | ChatGPT | ChatGPT | 传媒 | 90.0 | double_red | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 19 | 云计算 | 云计算 | 计算机 | 90.0 | double_red | 5 | 12 | 1 | - |
| 20 | 风电 | 风电 | 电力设备 | 83.48 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 21 | 数据中心 | 数据中心 | 计算机 | 80.79 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 22 | 共封装光学(CPO) | CPO | 电子 | 80.46 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 23 | CRO | CRO | 医药生物 | 79.52 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 24 | 医疗服务 | 医疗服务 | 医药生物 | 79.04 | new_high_direction、new_high_cluster、capacity_industry | 5 | 7 | 1 | - |
| 25 | 减肥药 | 减肥药 | 医药生物 | 78.81 | new_high_direction、new_high_cluster、capacity_industry | 0 | 1 | 0 | missing_concept、missing_evidence |
| 26 | 辅助生殖 | 辅助生殖 | 医药生物 | 78.01 | new_high_direction、new_high_cluster、capacity_industry | 2 | 8 | 1 | - |
| 27 | 生物制品 | 生物制品 | 医药生物 | 77.24 | new_high_direction、new_high_cluster、capacity_industry | 0 | 6 | 0 | missing_concept、missing_evidence |
| 28 | 液冷服务器 | 液冷服务器 | 电力设备 | 74.11 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 29 | 燃料电池 | SOFC燃料电池 | 电力设备 | 72.76 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 30 | 海峡两岸 | 海峡两岸 | 综合 | 70.85 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 人形机器人 | 人形机器人 | 机械设备 | 69.34 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 32 | 无人驾驶 | 无人驾驶 | 汽车 | 67.77 | new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 33 | 三胎 | 三胎 | 社会服务 | 67.01 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 34 | 特高压 | 特高压 | 电力设备 | 62.43 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 35 | 银行 | 区块链 | 银行 | 57.79 | new_high_direction、new_high_cluster | 3 | 1 | 0 | missing_evidence |
| 36 | 机器视觉 | 机器视觉 | 机械设备 | 56.22 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 37 | 存储芯片 | 存储芯片 | 电子 | 52.09 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 38 | 可控核聚变 | 可控核聚变 | 电力设备 | 51.45 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 39 | 通信设备 | 通信设备 | 通信 | 51.16 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 50.04 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 41 | 电力 | 新型电力系统 | 电力设备 | 48.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 42 | 量子科技 | 量子科技 | 计算机 | 45.21 | new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 43 | 6G | 6G | 通信 | 44.86 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 塑料制品 | 膜材料 | 基础化工 | 44.8 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 45 | 小米汽车 | 小米汽车 | 汽车 | 44.75 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 储能 | 储能 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 军工 | 军工 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 48 | AI应用 | AI应用 | - | 32.1 | limit_heat、new_high_cluster | 4 | 12 | 1 | - |
| 49 | 人工智能 | 人工智能 | - | 31.75 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 50 | AI智能体 | AI智能体 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：193.82
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.72%，边际量 49.29%，成交额 1196.42 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.72%，边际量49.29%，成交1196.42亿 |
| new_high_direction | 59.62 | 新高股100只，新高成交769.4100000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比21.43，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 10 |
| 创新药RWA | 5 |
| CDMO | 2 |
| RWA代币化 | 2 |
| 小分子 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | 创新药 | 院外零售渠道潜在相关 | peripheral | L1 | 10 |
| 上海医药 | 601607 | 创新药 | 医药流通渠道潜在相关 | peripheral | L1 | 10 |
| 东富龙 | 300171 | 创新药 | 创新药生产装备潜在供应商 | related | L1 | 10 |
| 九洲药业 | 603456 | 创新药 | 创新药定制研发生产/CDMO服务商 | core | L1 | 10 |
| 亚虹医药 | 688176 | 创新药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 10 |
| 信立泰 | 002294 | 创新药 | 心血管重磅创新药（S086等）研发商 | core | L2_candidate | 10 |
| 凯莱英 | 002821 | 创新药 | 小分子创新药CDMO服务商 | peripheral | graph_only | 10 |
| 和元生物 | 688238 | 创新药 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 2：化学制药

- **标准概念**：原料药
- **申万一级**：医药生物
- **评分**：186.71
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.62%，边际量 47.24%，成交额 657.65 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.62%，边际量47.24%，成交657.65亿 |
| new_high_direction | 54.61 | 新高股57只，新高成交369.08亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 6.1 | 涨停6只，市场占比10.71，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 原料药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 圣诺生物 | 688117 | 多肽药物 | 国内多肽合成领先、深度受益全球GLP-1减重/降糖（司美格鲁肽等）大爆发... | core | L1 | 1 |

## 候选 3：合成生物

- **标准概念**：合成生物学
- **申万一级**：医药生物
- **评分**：183.11
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.91%，边际量 14.85%，成交额 521.88 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.91%，边际量14.85%，成交521.88亿 |
| new_high_direction | 52.06 | 新高股25只，新高成交164.53000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 5.05 | 涨停3只，市场占比5.36，排名27 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 合成生物学 | 5 |
| 3D生物打印 | 2 |
| 保健品 | 2 |
| 功能性食品 | 2 |
| 化妆品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | - | 合成生物 | 受益标的 | related | - | 10 |
| 凯赛生物 | 688065 | 合成生物 | 受益标的 | related | - | 10 |
| 利民股份 | 002734 | 合成生物 | 受益标的 | related | - | 10 |
| 华恒生物 | 688639 | 合成生物 | 受益标的 | related | - | 10 |
| 奥翔药业 | 603229 | 合成生物 | 受益标的 | related | - | 10 |
| 富祥药业 | 300497 | 合成生物 | 受益标的 | related | - | 10 |
| 川宁生物 | 301301 | 合成生物 | 受益标的 | related | - | 10 |
| 巨子生物 | - | 合成生物 | 受益标的 | related | - | 10 |

## 候选 4：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：169.55
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.16%，边际量 10.96%，成交额 1204.6 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.16%，边际量10.96%，成交1204.6亿 |
| new_high_direction | 43.55 | 新高股10只，新高成交123.61999999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 10 |
| PCB印制电路板 | 5 |
| PCB概念 | 5 |
| PCB油墨 | 5 |
| PCB钻针 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 世运电路 | 603920 | PCB | 印制电路板生产商 | core | L1 | 10 |
| 东威科技 | 688700 | PCB | PCB电镀设备、复合集流体水电镀设备及先进封装电镀线供应商 | related | L1_L3_candidate | 10 |
| 东山精密 | 002384 | PCB | 光模块/光芯片与高多层AI PCB/HDI供应商，通过索尔思和Multe... | related | L1_L3_candidate | 10 |
| 东材科技 | 601208 | PCB | 覆铜板上游电子材料潜在供应商 | related | L2_candidate | 10 |
| 中国巨石 | 600176 | PCB | 上游材料 | related | L2_candidate | 10 |
| 中富电路 | 300814 | PCB | PCB研发生产销售企业 | core | L1 | 10 |
| 中金岭南 | 000060 | PCB | 参股PCB高端钻针生产商 | peripheral | L2_candidate | 10 |
| 中钨高新 | 000657 | PCB | PCB钻针/耗材链受益名单 | peripheral | graph_only | 10 |

## 候选 5：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：155.69
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.89%，边际量 10.26%，成交额 1537.7 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.89%，边际量10.26%，成交1537.7亿 |
| new_high_direction | 35.69 | 新高股4只，新高成交167.26999999999998亿，容量前三=True |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体 | 10 |
| 功率半导体 | 5 |
| 化合物半导体 | 5 |
| 半导体IP | 5 |
| 半导体产业链 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三安光电 | 600703 | 功率半导体 | 碳化硅功率半导体材料/器件相关厂商 | peripheral | L1 | 10 |
| 华润微 | 688396 | 功率半导体 | 国内功率半导体MOSFET、IGBT及宽禁带（SiC/GaN）IDM全产... | core | L1 | 10 |
| 华虹公司 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 士兰微 | 600460 | 功率半导体 | 国内极成熟、拥有多代特色晶圆制造代工线的一流功率分立器件IDM全产业链巨... | core | L1 | 10 |
| 天岳先进 | 688234 | 功率半导体 | 弱相关，待验证 | related | L2 | 10 |
| 斯达半导 | 603290 | 功率半导体 | 功率半导体相关产品/材料供应商 | related | L2 | 10 |
| 晶升股份 | 688478 | 功率半导体 | 核心设备及产品供应商 | related | L2_candidate | 10 |
| 晶盛机电 | 300316 | 功率半导体 | 首条12寸碳化硅衬底中试线，SiC设备龙头 | peripheral | L1 | 10 |

## 候选 6：新型工业化

- **标准概念**：新型工业化
- **申万一级**：机械设备
- **评分**：150.4
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.23%，边际量 10.98%，成交额 827.31 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.23%，边际量10.98%，成交827.31亿 |
| new_high_direction | 34.4 | 新高股11只，新高成交80.24999999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：AI PC

- **标准概念**：AI服务器
- **申万一级**：电子
- **评分**：148.41
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.19%，边际量 17.98%，成交额 584.19 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.19%，边际量17.98%，成交584.19亿 |
| new_high_direction | 32.41 | 新高股2只，新高成交128.98亿，容量前三=True |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI服务器 | 7 |
| AI硬件 | 7 |
| AI算力驱动下的交换机产业 | 7 |
| EPC模式 | 7 |
| PCB | 7 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 春秋电子 | - | AIPC液冷 | 电子结构件/液冷解决方案 | peripheral | L1_L3_candidate | 15 |
| 泽宇智能 | 301179 | AI | 电力信息系统、数智化解决方案与电网AI巡检服务商 | related | L1_L3_candidate | 10 |
| 东山精密 | 002384 | AI服务器 | 光模块/光芯片与高多层AI PCB/HDI供应商，通过索尔思和Multe... | related | L1_L3_candidate | 10 |
| 中富电路 | 300814 | AI服务器 | AI服务器PCB潜在供应商 | peripheral | L1 | 10 |
| 东材科技 | 601208 | AI服务器 | AI服务器高速材料潜在相关 | peripheral | L2_candidate | 10 |
| 中石科技 | 300684 | AI服务器 | AI服务器热管理材料潜在供应商 | related | L1 | 10 |
| 中航光电 | 002179 | AI服务器 | AI服务器液冷连接与组件相关受益名单公司 | peripheral | graph_only | 10 |
| 云图控股 | 002539 | AI服务器 | 公司级调研线索待核验 | peripheral | graph_only | 10 |

## 候选 8：3D打印

- **标准概念**：3D打印
- **申万一级**：机械设备
- **评分**：146.27
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.44%，边际量 13.86%，成交额 660.17 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.44%，边际量13.86%，成交660.17亿 |
| new_high_direction | 30.27 | 新高股7只，新高成交197.76亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 3D打印 | 10 |
| 3D打印钛合金 | 5 |
| 开源3D打印 | 5 |
| 微通道冷板（绿激光3D打印） | 5 |
| 消费级3D打印 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华曙高科 | 688433 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 南风股份 | 300004 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 大族激光 | 002008 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| XD艾为电 | 688798 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中兴通讯 | 000063 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中恒电气 | 002364 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中石科技 | 300684 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中科曙光 | 603019 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 9：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：122.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 2.9%，边际量 17.82%，成交额 1238.99 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.9%，边际量17.82%，成交1238.99亿 |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 先进封装 | 10 |
| AI芯片 | 2 |
| CANN（华为昇腾异构计算架构） | 2 |
| CPO（共封装光学） | 2 |
| GPU（图形处理器） | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 上峰水泥 | 000672 | 先进封装 | 投资潜在相关（非直接产业链） | peripheral | L2_candidate | 10 |
| 上海新阳 | 300236 | 先进封装 | 先进封装用电镀液及添加剂供应商 | related | L1 | 10 |
| 东威科技 | 688700 | 先进封装 | PCB电镀设备、复合集流体水电镀设备及先进封装电镀线供应商 | related | L1_L3_candidate | 10 |
| 中国巨石 | 600176 | 先进封装 | 先进封装上游高端电子布潜在相关 | peripheral | L2_candidate | 10 |
| 中微公司 | 688012 | 先进封装 | 先进封装刻蚀/薄膜沉积设备供应商 | peripheral | L2_candidate | 10 |
| 中材科技 | 002080 | 先进封装 | Low-CTE电子布供应商，AI先进封装关键材料 | peripheral | L1 | 10 |
| 中科飞测 | 688361 | 先进封装 | 先进封装硅通孔等量检测设备供应商 | related | L2_candidate | 10 |
| 京东方A | 000725 | 先进封装 | 市场信号弱关联 | peripheral | L2_candidate | 10 |

## 候选 10：英伟达

- **标准概念**：英伟达Rubin架构
- **申万一级**：电子
- **评分**：118.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 3.14%，边际量 18.76%，成交额 874.54 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.14%，边际量18.76%，成交874.54亿 |
| new_high_cluster | 18.0 | 题材内新高股3只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 英伟达Rubin架构 | 5 |
| 6G产业 | 2 |
| AI硬件 | 2 |
| AI算力驱动下的交换机产业 | 2 |
| HBM | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中际旭创 | 300308 | 英伟达 | 产业链供应商 | peripheral | L2_candidate | 10 |
| 华工科技 | 000988 | 英伟达 | 上游材料 | peripheral | L1 | 10 |
| 工业富联 | 601138 | 英伟达 | 芯片/核心器件 | core | L2_candidate | 10 |
| 新易盛 | 300502 | 英伟达 | 产业链供应商 | peripheral | L1 | 10 |
| 沪电股份 | 002463 | 英伟达 | 产业链供应商 | core | L2_candidate | 10 |
| 浪潮信息 | 000977 | 英伟达 | 下游应用 | peripheral | L1_L3_candidate | 10 |
| 生益科技 | 600183 | 英伟达 | 6.4 投资策略建议 | peripheral | L1 | 10 |
| 胜宏科技 | 300476 | 英伟达 | 产业链供应商 | core | L2_candidate | 10 |
