# 2026-04-03 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：横盘
- **成交额**：16563.0
- **上涨家数**：716
- **涨停 / 跌停**：36 / 26
- **容量前三行业**：1.电子(15.4%, capacity)、2.电力设备(11.7%, normal)、3.通信(9.6%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 共封装光学(CPO) | CPO | 电子 | 190.81 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 184.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 通信设备 | 通信设备 | 通信 | 180.03 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 159.49 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 5 | 6G | 6G | 通信 | 159.23 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 光通信 | 光通信 | 通信 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 | - |
| 7 | 医药 | 医药 | 医药生物 | 105.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 8 | 数据中心 | 数据中心 | 计算机 | 80.5 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 风电 | 风电 | 电力设备 | 76.99 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 10 | 无人驾驶 | 无人驾驶 | 汽车 | 76.42 | limit_heat、new_high_direction、new_high_cluster | 4 | 10 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 创新药 | 创新药 | 医药生物 | 74.9 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 液冷服务器 | 液冷服务器 | 电力设备 | 73.83 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 13 | 商业航天 | 商业航天 | 国防军工 | 71.03 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 14 | 特高压 | 特高压 | 电力设备 | 70.11 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 15 | 光学光电子 | LED芯片 | 电子 | 68.12 | new_high_direction、new_high_cluster、capacity_industry | 2 | 2 | 0 | missing_evidence |
| 16 | 化学制药 | 原料药 | 医药生物 | 67.95 | new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 17 | 电网设备 | 电网设备 | 电力设备 | 67.23 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 18 | 人形机器人 | 人形机器人 | 机械设备 | 65.86 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 19 | 海峡两岸 | 海峡两岸 | 综合 | 63.41 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 20 | 可控核聚变 | 可控核聚变 | 电力设备 | 62.18 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 21 | 光刻机 | 光刻机 | 电子 | 61.87 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 22 | AI眼镜 | AI眼镜 | 电子 | 61.59 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | 新型工业化 | 新型工业化 | 机械设备 | 60.86 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | 医药商业 | 医药流通 | 医药生物 | 60.72 | new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 25 | 辅助生殖 | 辅助生殖 | 医药生物 | 60.27 | limit_heat、new_high_direction、new_high_cluster | 2 | 8 | 1 | - |
| 26 | 机器视觉 | 机器视觉 | 机械设备 | 59.64 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 27 | 半导体 | 半导体 | 电子 | 58.43 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 28 | PET铜箔 | PET铜箔 | 电力设备 | 58.21 | new_high_direction、new_high_cluster、capacity_industry | 5 | 9 | 1 | - |
| 29 | 3D打印 | 3D打印 | 机械设备 | 55.76 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 30 | HJT电池 | HJT电池 | 电力设备 | 54.96 | new_high_direction、new_high_cluster、capacity_industry | 5 | 3 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 港口航运 | 港口航运 | 交通运输 | 51.57 | new_high_direction、new_high_cluster | 1 | 10 | 1 | - |
| 32 | 自动化设备 | 自动化设备 | 机械设备 | 51.52 | new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 33 | 量子科技 | 量子科技 | 计算机 | 50.82 | new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 34 | 小金属 | 小金属 | 有色金属 | 48.05 | new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 35 | TOPCON电池 | TOPCon电池 | 电力设备 | 47.97 | new_high_direction、new_high_cluster、capacity_industry | 5 | 7 | 0 | missing_evidence |
| 36 | 太赫兹 | 6G产业 | 国防军工 | 46.12 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 37 | 小米汽车 | 小米汽车 | 汽车 | 45.03 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 减肥药 | 减肥药 | 医药生物 | 44.62 | new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 39 | 人工智能 | 人工智能 | - | 33.15 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 储能 | 储能 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 军工 | 军工 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 42 | AI智能体 | AI智能体 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 低空经济 | 低空经济 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 44 | 固态电池 | 固态电池 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 45 | AI应用 | AI应用 | - | 29.05 | limit_heat、new_high_cluster | 4 | 12 | 1 | - |
| 46 | 信创 | 信创 | - | 25.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 数据要素 | 数据要素 | - | 25.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 软件开发 | AIGC | - | 23.4 | limit_heat、new_high_cluster | 5 | 6 | 0 | missing_evidence |
| 49 | 钠离子电池 | 储能 | - | 23.05 | limit_heat、new_high_cluster | 5 | 9 | 0 | missing_evidence |
| 50 | 算力租赁 | 算力租赁 | - | 21.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：190.81
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.12%，边际量 16.59%，成交额 2572.5 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.12%，边际量16.59%，成交2572.5亿 |
| new_high_direction | 58.01 | 新高股19只，新高成交640.88亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比22.22，排名3 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |
| CPO（共封装光学） | 10 |
| CPO微透镜与高功率CW光源 | 5 |
| 6G产业 | 2 |
| MPO光纤连接器 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光莆股份 | 300632 | CPO | 共封装光学（CPO）新型光引擎精密光电对准封测代工商 | related | L2_candidate | 11 |
| Coherent（COHR） | - | CPO | 菊东光客户，光器件供应商 | peripheral | L1 | 10 |
| 东山精密 | 002384 | CPO | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 东材科技 | 601208 | CPO | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 中芯国际 | 688981 | CPO | 光通信电芯片代工与制造受益名单 | peripheral | graph_only | 10 |
| 中际旭创 | 300308 | CPO | 光通信芯片与半导体激光芯片供应商 | related | L1_L3_candidate | 10 |
| 乾照光电 | 300102 | CPO | 光通信/CPO用光电感测及芯片潜在研发送样方 | peripheral | L1 | 10 |
| 亨通光电 | 600487 | CPO | 市场信号弱关联 | related | L2_candidate | 10 |

## 候选 2：光纤

- **标准概念**：AI算力驱动下的MPO光纤连接器产业
- **申万一级**：通信
- **评分**：184.24
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.79%，边际量 18.58%，成交额 1473.49 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.79%，边际量18.58%，成交1473.49亿 |
| new_high_direction | 58.24 | 新高股21只，新高成交659.2199999999999亿，容量前三=True |
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
- **评分**：180.03
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.74%，边际量 23.22%，成交额 1422.96 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.74%，边际量23.22%，成交1422.96亿 |
| new_high_direction | 48.28 | 新高股11只，新高成交390.5599999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比13.89，排名12 |

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

## 候选 4：铜缆高速连接

- **标准概念**：铜缆高速连接
- **申万一级**：电力设备
- **评分**：159.49
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.6%，边际量 15.97%，成交额 538.36 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.6%，边际量15.97%，成交538.36亿 |
| new_high_direction | 34.79 | 新高股4只，新高成交95.47亿，容量前三=True |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 4.7 | 涨停2只，市场占比5.56，排名30 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：6G

- **标准概念**：6G
- **申万一级**：通信
- **评分**：159.23
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.68%，边际量 17.94%，成交额 1002.61 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.68%，边际量17.94%，成交1002.61亿 |
| new_high_direction | 37.23 | 新高股5只，新高成交178.67亿，容量前三=True |
| new_high_cluster | 22.0 | 题材内新高股5只 |
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

## 候选 6：光通信

- **标准概念**：光通信
- **申万一级**：通信
- **评分**：107.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光通信 | 10 |
| 光通信测试仪器 | 5 |
| 5G通信 | 2 |
| 6G产业 | 2 |
| AI眼镜 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| Lumentum | - | 光通信 | EML激光器/OCS/CPO光芯片龙头 | peripheral | L1 | 10 |
| 三安光电 | 600703 | 光通信 | 光通讯芯片供应商 | related | L1 | 10 |
| 东山精密 | 002384 | 光通信 | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 东材科技 | 601208 | 光通信 | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 中兴通讯 | 000063 | 光通信 | 有线通信产品供应商 | related | L2_candidate | 10 |
| 中国卫通 | 601698 | 光通信 | 图谱弱关联 | peripheral | graph_only | 10 |
| 中国移动 | 600941 | 光通信 | 通信网络建设需求方 | peripheral | L2_candidate | 10 |
| 中天科技 | 600522 | 光通信 | 光通信及网络产品供应商 | core | L2_candidate | 10 |

## 候选 7：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：105.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股2只，最高6板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医药 | 10 |
| AI+生物医药 | 5 |
| 医药分销 | 5 |
| 医药流通 | 5 |
| 医药生物 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 丽珠集团 | 000513 | 医药 | 综合性制药及生物制药、原料药一体化企业 | peripheral | graph_only | 10 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 10 |
| 仙琚制药 | 002332 | 医药 | 综合西药原料及特色制剂开发企业 | peripheral | graph_only | 10 |
| 上海医药 | 601607 | 医药分销 | 药品分销渠道商 | peripheral | graph_only | 10 |
| 达嘉维康 | 301126 | 医药流通 | 小建中颗粒相关产品供应商 | related | L2 | 10 |
| 万泽股份 | 000534 | 医药生物 | 微生态活菌药品与健康产品企业 | peripheral | graph_only | 10 |
| 伟思医疗 | 688580 | 医药生物 | 经颅磁刺激仪相关产品供应商 | related | L2 | 10 |
| 信立泰 | 002294 | 医药生物 | 心脑血管相关产品供应商 | related | L2 | 10 |

## 候选 8：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：80.5
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 47.7 | 新高股22只，新高成交616.3899999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比22.22，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 10 |
| AI数据中心储能 | 5 |
| 数据中心交换机 | 5 |
| 数据中心供电 | 5 |
| 数据中心液冷 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | 数据中心 | 数据中心光模块产品供应商 | related | L1 | 10 |
| 东阳光 | 600673 | 数据中心 | OpenClaw算力链与国产算力/华为系/字节系受益名单 | peripheral | graph_only | 10 |
| 中天科技 | 600522 | 数据中心 | 数据中心光纤光缆和空芯光纤受益名单公司 | peripheral | graph_only | 10 |
| 中恒电气 | 002364 | 数据中心 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 中电鑫龙 | 002298 | 数据中心 | 智能配电和智慧用能潜在硬件配套供应商 | related | L1 | 10 |
| 中科曙光 | 603019 | 数据中心 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 中航光电 | 002179 | 数据中心 | AI服务器液冷连接与组件相关受益名单公司 | peripheral | graph_only | 10 |
| 中际旭创 | 300308 | 数据中心 | 4.4 光模块领域核心上市公司 | peripheral | L1 | 10 |

## 候选 9：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：76.99
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.94 | 新高股10只，新高成交315.42亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比8.33，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电 | 10 |
| 海上风电 | 5 |
| 深远海风电 | 5 |
| 漂浮式风电 | 5 |
| 陆上风电 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 海上风电 | 中游制造 | core | L1_L3_candidate | 10 |
| 东方电缆 | 603606 | 海上风电 | 5.2.3 海缆系统企业 | core | L1_L3_candidate | 10 |
| 中信海直 | 000099 | 海上风电 | 海上风电通航服务潜在相关 | related | L1 | 10 |
| 中天科技 | 600522 | 海上风电 | 5.2.3 海缆系统企业 | related | L1_L3_candidate | 10 |
| 亨通光电 | 600487 | 海上风电 | 3.4 海缆系统环节 | related | L1_L3_candidate | 10 |
| 中材科技 | 002080 | 风电 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 大金重工 | 002487 | 风电 | 海上风电塔筒/基础及出口海工装备供应商，具备欧洲项目交付和海工运输能力 | related | L3 | 10 |
| 天顺风能 | 002531 | 风电 | 产业链供应商 | related | L1_L3_candidate | 10 |

## 候选 10：无人驾驶

- **标准概念**：无人驾驶
- **申万一级**：汽车
- **评分**：76.42
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（10），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.37 | 新高股20只，新高成交429.2799999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比8.33，排名24 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 无人驾驶 | 10 |
| 毫米波雷达 | 2 |
| 车路协同产业 | 2 |
| 高精地图 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万集科技 | 300552 | 无人驾驶 | 激光雷达/MEMS固态雷达供应商，适配城市NOA与L4客车场景 | related | L1_L3_candidate | 10 |
| 保隆科技 | 603197 | 无人驾驶 | 毫米波雷达与汽车传感器供应商 | related | L2_candidate | 10 |
| 千里科技 | 601777 | 无人驾驶 | Robotaxi闭环平台服务商 | related | L1_L3_candidate | 10 |
| 四维图新 | 002405 | 无人驾驶 | 高精地图与智能驾驶数据服务商 | related | L1_L3_candidate | 10 |
| 富临运业 | 002357 | 无人驾驶 | 公路客运运营商，与新石器合营切入L4无人驾驶物流，布局四川文旅低空物流 | related | L1_L3_candidate | 10 |
| 德赛西威 | 002920 | 无人驾驶 | 智能驾驶域控制器供应商 | related | L1_L3_candidate | 10 |
| 拓普集团 | 601689 | 无人驾驶 | 智能底盘供应商 | peripheral | L1 | 10 |
| 比亚迪 | 002594 | 无人驾驶 | 新能源汽车整车厂商与智能驾驶车型应用方 | peripheral | L1 | 10 |
