# 2026-06-05 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：顶部横盘阶段
- **成交额**：30688.1
- **上涨家数**：3277
- **涨停 / 跌停**：73 / 11
- **容量前三行业**：1.电子(30.1%, super_capacity)、2.通信(10.9%, normal)、3.机械设备(8.6%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 人形机器人 | 人形机器人 | 机械设备 | 200.68 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 2 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 通信设备 | 通信设备 | 通信 | 191.6 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 新型工业化 | 新型工业化 | 机械设备 | 189.08 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 5 | 传感器 | 传感器 | 机械设备 | 187.17 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 通用设备 | 金属制品 | 机械设备 | 185.51 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 7 | 光学光电子 | LED芯片 | 电子 | 184.98 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 2 | 0 | missing_evidence |
| 8 | 6G | 6G | 通信 | 182.64 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 商业航天 | 商业航天 | 国防军工 | 182.55 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 10 | 机器视觉 | 机器视觉 | 机械设备 | 176.69 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 3D打印 | 3D打印 | 机械设备 | 175.6 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 减速器 | 减速器 | 机械设备 | 174.81 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 无人驾驶 | 无人驾驶 | 汽车 | 164.79 | double_red、new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 14 | 氢能源 | 氢能源 | 电力设备 | 163.04 | double_red、new_high_direction、new_high_cluster | 5 | 4 | 1 | - |
| 15 | 海峡两岸 | 海峡两岸 | 综合 | 161.74 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 16 | 燃料电池 | SOFC燃料电池 | 电力设备 | 160.48 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 17 | 机器人 | 机器人 | 机械设备 | 159.0 | double_red、capacity_industry、limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 长安汽车 | 长安汽车 | 汽车 | 154.27 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 19 | 量子科技 | 量子科技 | 计算机 | 153.92 | double_red、new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 20 | 毫米波雷达 | 毫米波雷达 | 汽车 | 152.16 | double_red、new_high_direction、new_high_cluster | 5 | 11 | 1 | - |
| 21 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 148.19 | double_red、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 22 | 数据要素 | 数据要素 | 计算机 | 147.41 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 太赫兹 | 6G产业 | 国防军工 | 143.99 | double_red、new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 24 | 多模态AI | 多模态AI | 计算机 | 136.37 | double_red、new_high_direction、new_high_cluster | 1 | 1 | 1 | - |
| 25 | 超导 | 超导 | 国防军工 | 134.73 | double_red、new_high_direction、new_high_cluster | 5 | 8 | 1 | - |
| 26 | 工业母机 | 工业母机 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 4 | 11 | 1 | - |
| 27 | 消费电子 | 消费电子 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 自动化设备 | 自动化设备 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 6 | 1 | - |
| 29 | 军工 | 军工 | 国防军工 | 124.55 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 30 | 人工智能 | 人工智能 | 计算机 | 123.85 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 低空经济 | 低空经济 | 国防军工 | 122.45 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 32 | AI智能体 | AI智能体 | 计算机 | 122.1 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 33 | AI应用 | AI应用 | 计算机 | 121.75 | double_red、limit_heat、new_high_cluster | 4 | 12 | 1 | - |
| 34 | 星闪 | 星闪技术 | 通信 | 120.0 | double_red、capacity_industry、new_high_cluster | 2 | 0 | 0 | missing_entity_exposures、missing_evidence |
| 35 | MR(混合现实) | MRAM | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 5 | 11 | 0 | missing_evidence |
| 36 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 37 | 光伏 | 光伏 | 电力设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 大飞机 | 大飞机 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 汽车零部件 | 汽车零部件 | 汽车 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 40 | PCB | PCB | 机械设备 | 115.42 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 41 | 飞行汽车(eVTOL) | 飞行汽车 | 汽车 | 114.0 | double_red、new_high_cluster | 5 | 4 | 0 | missing_evidence |
| 42 | AIGC | AIGC | 传媒 | 112.0 | double_red、new_high_cluster | 5 | 5 | 1 | - |
| 43 | 氟化工 | 氟化工 | 基础化工 | 112.0 | double_red、new_high_cluster | 5 | 9 | 1 | - |
| 44 | 军工信息化 | 军工信息化 | 国防军工 | 110.0 | double_red、new_high_cluster | 0 | 12 | 1 | missing_concept |
| 45 | ChatGPT | ChatGPT | 传媒 | 108.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 创新药 | 创新药 | 医药生物 | 108.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 航空发动机 | 航空发动机 | 国防军工 | 108.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 低价股 | 低价股 | 交通运输 | 101.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 共封装光学(CPO) | CPO | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 50 | 数据中心 | 数据中心 | 计算机 | 91.15 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：200.68
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.48%，边际量 18.16%，成交额 5168.65 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.48%，边际量18.16%，成交5168.65亿 |
| new_high_direction | 66.83 | 新高股37只，新高成交1346.4499999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |
| limit_heat | 7.85 | 涨停11只，市场占比15.07，排名6 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人形机器人 | 10 |
| MIM金属注射成型 | 2 |
| PEEK材料 | 2 |
| 传感器 | 2 |
| 固态电池 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三花智控 | 002050 | 人形机器人 | 热管理及执行器供应商，特斯拉V3产业链标的 | peripheral | L1 | 10 |
| 中大力德 | 002896 | 人形机器人 | 机器人核心零部件供应商 | related | L2 | 10 |
| 中研股份 | 688716 | 人形机器人 | 机器人关节轻量化PEEK材料潜在供应商 | related | L1 | 10 |
| 丰立智能 | 301368 | 人形机器人 | 减速器 | core | - | 10 |
| 亿嘉和 | 603666 | 人形机器人 | 基础业务暴露 | related | L2 | 10 |
| 信质集团 | 002704 | 人形机器人 | 全T链 | core | - | 10 |
| 光威复材 | 300699 | 人形机器人 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 北特科技 | 603009 | 人形机器人 | 丝杠 | core | - | 10 |

## 候选 2：光纤

- **标准概念**：AI算力驱动下的MPO光纤连接器产业
- **申万一级**：通信
- **评分**：194.0
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.04%，边际量 24.88%，成交额 3669.16 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.04%，边际量24.88%，成交3669.16亿 |
| new_high_direction | 68.0 | 新高股18只，新高成交1734.3100000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI算力驱动下的MPO光纤连接器产业 | 5 |
| G.654.E光纤 | 5 |
| MPO光纤连接器 | 5 |
| 光纤光缆 | 5 |
| 光纤通信 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | AI算力驱动下的MPO光纤连接器产业 | 4.4 国产替代进程分析 | peripheral | graph_only | 10 |
| 仕佳光子 | 688313 | AI算力驱动下的MPO光纤连接器产业 | 2025 年净利润预计 4.77-5.1 亿元，对应 PE 约 33 倍 | peripheral | graph_only | 10 |
| 光库科技 | 300620 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 博创科技 | 300548 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 太辰光 | 300570 | AI算力驱动下的MPO光纤连接器产业 | 3.2.1 太辰光（300570） | peripheral | graph_only | 10 |
| 亨通光电 | 600487 | 光纤 | 光纤光缆及数据中心互联光纤供应商 | related | L1_L3_candidate | 10 |
| 长飞光纤 | 601869 | 光纤 | 光纤光缆及新型光纤产品供应商 | related | L1_L3_candidate | 10 |
| 中天科技 | 600522 | 光纤光缆 | 数据中心光纤光缆和空芯光纤受益名单公司 | peripheral | graph_only | 10 |

## 候选 3：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：191.6
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.12%，边际量 42.94%，成交额 3204.66 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.12%，边际量42.94%，成交3204.66亿 |
| new_high_direction | 65.6 | 新高股14只，新高成交1472.88亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 通信设备 | 10 |
| 5G通信 | 2 |
| AI-RAN | 2 |
| 低空经济 | 2 |
| 光纤光缆 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | 通信设备 | 通信设备组件和光模块供应商 | related | L1 | 10 |
| 中兴通讯 | 000063 | 通信设备 | 通信网络设备及器件供应商 | core | L2_candidate | 10 |
| 信科移动 | 688387 | 通信设备 | 无线网络5G-A宏基站及核心网网络整机制造商 | core | L1 | 10 |
| 意华股份 | 002897 | 通信设备 | 通讯连接器产品相关产品供应商 | related | L2 | 10 |
| 烽火通信 | 600498 | 通信设备 | 通信系统设备相关产品供应商 | related | L2 | 10 |
| 锐捷网络 | 301165 | 通信设备 | 市场信号弱关联 | related | L2_candidate | 10 |
| 大为股份 | 002213 | ABF载板 | 半导体存储器、通信设备、计算机及其他电子设备、新能源材料、汽车缓速器、房... | related | L2 | 1 |
| 德科立 | 688205 | 光器件 | 光通信设备与模块企业，布局DCI、光引擎、光收发模块和硅基OCS | related | L1_L3_candidate | 1 |

## 候选 4：新型工业化

- **标准概念**：新型工业化
- **申万一级**：机械设备
- **评分**：189.08
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.21%，边际量 28.65%，成交额 1948.42 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.21%，边际量28.65%，成交1948.42亿 |
| new_high_direction | 55.58 | 新高股18只，新高成交446.3400000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |
| limit_heat | 7.5 | 涨停10只，市场占比13.7，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：传感器

- **标准概念**：传感器
- **申万一级**：机械设备
- **评分**：187.17
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.86%，边际量 18.95%，成交额 2957.25 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.86%，边际量18.95%，成交2957.25亿 |
| new_high_direction | 61.17 | 新高股23只，新高成交893.37亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 传感器 | 10 |
| AI传感器 | 5 |
| MEMS传感器 | 5 |
| ToF传感器 | 5 |
| 压力传感器 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华域汽车 | 600741 | 传感器 | 图谱弱关联 | peripheral | graph_only | 10 |
| 华润微 | 688396 | 传感器 | 图谱弱关联 | peripheral | graph_only | 10 |
| 士兰微 | 600460 | 传感器 | 4.2 相关业务布局公司分析 | peripheral | graph_only | 10 |
| 奥比中光 | 688322 | 传感器 | 物理agent传感器受益名单 | peripheral | graph_only | 10 |
| 安培龙 | 301413 | 传感器 | 传感器相关产品/材料供应商 | related | L2 | 10 |
| 敏芯股份 | 688286 | 传感器 | 传感器相关产品/材料供应商 | related | L2 | 10 |
| 晶华新材 | 603683 | 传感器 | 物理agent传感器受益名单 | peripheral | graph_only | 10 |
| 晶方科技 | 603005 | 传感器 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 6：通用设备

- **标准概念**：金属制品
- **申万一级**：机械设备
- **评分**：185.51
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.17%，边际量 21.57%，成交额 951.86 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.17%，边际量21.57%，成交951.86亿 |
| new_high_direction | 52.71 | 新高股22只，新高成交216.81000000000006亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比10.96，排名11 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 金属制品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东睦股份 | 600114 | 金属制品 | 金属制品制造企业 | peripheral | graph_only | 1 |

## 候选 7：光学光电子

- **标准概念**：LED芯片
- **申万一级**：电子
- **评分**：184.98
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.2%，边际量 31.5%，成交额 1300.78 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.2%，边际量31.5%，成交1300.78亿 |
| new_high_direction | 58.98 | 新高股18只，新高成交718.6800000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| LED芯片 | 2 |
| 显示材料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三安光电 | 600703 | LED芯片 | LED外延片和芯片供应商 | peripheral | graph_only | 1 |
| 三利谱 | 002876 | 显示材料 | 面板上游光学显示材料供应商 | peripheral | graph_only | 1 |

## 候选 8：6G

- **标准概念**：6G
- **申万一级**：通信
- **评分**：182.64
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.66%，边际量 31.57%，成交额 2394.21 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.66%，边际量31.57%，成交2394.21亿 |
| new_high_direction | 56.64 | 新高股13只，新高成交834.89亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 6G | 10 |
| 5G_6G | 5 |
| 5G_6G融合 | 5 |
| 5G_6G通信 | 5 |
| 6G产业 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万丰奥威 | 002085 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |
| 三安光电 | 600703 | 6G | 6G前置射频器件潜在相关 | peripheral | L1 | 10 |
| 东方财富 | 300059 | 6G | 证券业务、金融电子商务服务业务、金融数据服务业务研发/生产商 | related | L2 | 10 |
| 中信海直 | 000099 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |
| 中兴通讯 | 000063 | 6G | 6G前置技术和主设备映射 | related | L2_candidate | 10 |
| 中国卫通 | 601698 | 6G | 空天地一体化前置卫星通信环节 | related | L1 | 10 |
| 中国移动 | 600941 | 6G | 6G网络架构和场景牵引方 | related | L2_candidate | 10 |
| 中瓷电子 | 003031 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 9：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：182.55
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.09%，边际量 23.87%，成交额 5633.83 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.09%，边际量23.87%，成交5633.83亿 |
| new_high_direction | 58.0 | 新高股38只，新高成交1472.5999999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比17.81，排名3 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| 低轨卫星星座 | 2 |
| 卫星产业 | 2 |
| 电磁弹射 | 2 |
| 航天装备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 10 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 10 |
| 中国卫通 | 601698 | 商业航天 | 卫星通信运营商 | peripheral | L2 | 10 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 商业航天 | 商业航天高性能碳纤维本土供应商，推进卫星端验证 | related | L1_L3_candidate | 10 |
| 中科星图 | 688568 | 商业航天 | 卫星互联网/太空算力 | core | - | 10 |
| 中集集团 | 000039 | 商业航天 | 模块化/预制化数据中心与海工、航天储罐高端装备制造交付商 | related | L1_L3_candidate | 10 |

## 候选 10：机器视觉

- **标准概念**：机器视觉
- **申万一级**：机械设备
- **评分**：176.69
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.19%，边际量 15.25%，成交额 1676.71 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.19%，边际量15.25%，成交1676.71亿 |
| new_high_direction | 50.69 | 新高股14只，新高成交246.82000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 宇瞳光学 | 300790 | 机器视觉 | 机器视觉相关产品/材料供应商 | related | L2 | 10 |
| 联创电子 | 002036 | 集成电路 | 集成电路相关产品/材料供应商 | related | L2 | 1 |
