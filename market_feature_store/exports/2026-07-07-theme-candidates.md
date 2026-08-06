# 2026-07-07 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：25810.0
- **上涨家数**：693
- **涨停 / 跌停**：33 / 31
- **容量前三行业**：1.电子(32.1%, super_capacity)、2.机械设备(9.1%, normal)、3.电力设备(7.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 通用设备 | 金属制品 | 机械设备 | 67.45 | new_high_direction、new_high_cluster、capacity_industry | 1 | 8 | 0 | missing_evidence |
| 2 | 液冷服务器 | 液冷服务器 | 电力设备 | 67.11 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 3 | 半导体 | 半导体 | 电子 | 64.24 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 4 | 数据中心 | 数据中心 | 计算机 | 62.88 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 人形机器人 | 人形机器人 | 机械设备 | 62.12 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 6 | 燃料电池 | 燃料电池 | 电力设备 | 58.06 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 7 | 先进封装 | 先进封装 | 电子 | 53.2 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 8 | 共封装光学(CPO) | CPO | 电子 | 52.51 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 9 | 机器人 | 机器人 | 计算机 | 50.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 2 | - |
| 10 | 长安汽车 | 长安汽车 | 汽车 | 48.46 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 机器视觉 | 机器视觉 | 机械设备 | 48.25 | new_high_direction、new_high_cluster、capacity_industry | 2 | 10 | 0 | missing_evidence |
| 12 | 工业母机 | 工业母机 | 机械设备 | 48.15 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 13 | 新型工业化 | 新型工业化 | 机械设备 | 48.15 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 14 | 信创 | 信创 | 计算机 | 45.99 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 股权 | IC载板 | 建筑装饰 | 36.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 16 | TAC膜上游 | TAC膜上游 | 轻工制造 | 33.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 人工智能 | 人工智能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 储能 | 储能 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 19 | AI电源 | AI电源 | 电力设备 | 30.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 5 | - |
| 20 | 算力芯片 | AI硬件 | 电子 | 30.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 21 | 军工 | 军工 | - | 27.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 22 | 商业航天 | 商业航天 | - | 25.4 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 23 | 风电 | 风电 | - | 25.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 低空经济 | 低空经济 | - | 23.75 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 25 | 化学制品 | 化工周期 | - | 23.4 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 26 | 无人驾驶 | 无人驾驶 | - | 23.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 27 | AI眼镜 | AI眼镜 | - | 21.05 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 28 | 汽车零部件 | 汽车零部件 | - | 21.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 29 | AI应用 | AI应用 | - | 20.7 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 30 | 固态电池 | 固态电池 | - | 20.7 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 机器人概念 | 机器人概念 | - | 7.5 | limit_heat | 0 | 10 | 0 | missing_concept、missing_evidence |
| 32 | 芯片概念 | 芯片概念 | - | 7.5 | limit_heat | 0 | 2 | 0 | missing_concept、missing_evidence |
| 33 | 光伏概念 | 光伏概念 | - | 6.45 | limit_heat | 0 | 2 | 0 | missing_concept、missing_evidence |
| 34 | 存储芯片 | 存储芯片 | - | 5.4 | limit_heat | 5 | 12 | 5 | - |
| 35 | 智能座舱 | 智能座舱 | - | 5.4 | limit_heat | 5 | 12 | 1 | - |
| 36 | 计算机设备 | 计算机设备 | - | 5.05 | limit_heat | 1 | 9 | 1 | - |
| 37 | AIGC概念 | AIGC概念 | - | 4.7 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | DeepSeek概念 | DeepSeek概念 | - | 4.7 | limit_heat | 0 | 2 | 0 | missing_concept、missing_evidence |
| 39 | PCB概念 | PCB概念 | - | 4.7 | limit_heat | 4 | 1 | 1 | - |
| 40 | 光纤概念 | 空芯光纤产业 | - | 4.7 | limit_heat | 1 | 2 | 0 | missing_evidence |
| 41 | 军工信息化 | 军工信息化 | - | 4.7 | limit_heat | 5 | 12 | 1 | - |
| 42 | 毫米波雷达 | 毫米波雷达 | - | 4.7 | limit_heat | 5 | 12 | 1 | - |
| 43 | 长安汽车概念 | 长安汽车概念 | - | 4.7 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 五、核心候选明细

## 候选 1：通用设备

- **标准概念**：金属制品
- **申万一级**：机械设备
- **评分**：67.45
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（8），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.45 | 新高股8只，新高成交180.26000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 金属制品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光格科技 | 688450 | AIoT | 分布式光纤传感、AIoT资产运维、四足巡检机器人 | core | L2 | 1 |
| 东方中科 | 002819 | AI安全 | 测试技术与服务（占比~81%）、数字安全与数智应用（占比~19%） | related | L2 | 1 |
| 必创科技 | 300667 | CPO | 精密光机（六轴并联平台/耦合台）、光电仪器（光谱仪/光源/检测系统）、智... | related | L1_L3_candidate | 1 |
| 瑜欣电子 | 301107 | 工业电机 | 1) 通用机械行业景气度、2) 新能源产品增长、3) 机器人关节电机合作... | related | L1_L3_candidate | 1 |
| 中核科技 | 000777 | 工业阀门 | 核工程阀门、核聚变阀门、石油石化阀门 | related | L1_L3_candidate | 1 |
| 五洋自控 | 300420 | 智能物流 | 智慧矿山核心装置、自动化装备与智能物流仓储系统、立体停车设备、停车场投资... | core | L2 | 1 |
| 绿的谐波 | 688017 | 机器人零部件 | 谐波减速器、机电一体化执行器、行星滚柱丝杠 | related | L1_L3_candidate | 1 |
| 东睦股份 | 600114 | 金属制品 | 金属制品制造企业 | peripheral | graph_only | 1 |

## 候选 2：液冷服务器

- **标准概念**：液冷服务器
- **申万一级**：电力设备
- **评分**：67.11
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.11 | 新高股8只，新高成交152.59亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 液冷服务器 | 10 |
| AI服务器 | 2 |
| AI服务器电源 | 2 |
| AI算力 | 2 |
| AI超节点 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三花智控 | 002050 | 液冷服务器 | 产业链供应商 | peripheral | L1 | 10 |
| 东阳光 | 600673 | 液冷服务器 | AI算力液冷组件、SST智能直流供电核心电容及AIDC运营闭环平台 | related | L1_L3_candidate | 10 |
| 中兴通讯 | 000063 | 液冷服务器 | - | - | - | 10 |
| 中石科技 | 300684 | 液冷服务器 | 导热/屏蔽材料配套供应商 | peripheral | L2 | 10 |
| 中科曙光 | 603019 | 液冷服务器 | 浸没式液冷服务器/算力中心液冷基础设施供应商 | related | L1_L3_candidate | 10 |
| 中航光电 | 002179 | 液冷服务器 | - | - | - | 10 |
| 冰轮环境 | 000811 | 液冷服务器 | AIDC液冷一次侧冷水机组/压缩机国产替代受益名单 | peripheral | graph_only | 10 |
| 利和兴 | 301013 | 液冷服务器 | MLCC（片式多层陶瓷电容器）制造、智能制造设备 | related | L1_L3_candidate | 10 |

## 候选 3：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：64.24
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 36.84 | 新高股5只，新高成交147.48000000000002亿，容量前三=True |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| limit_heat | 5.4 | 涨停4只，市场占比12.12，排名7 |

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
| 上海合晶 | 688584 | 功率半导体 | 为功率器件/模拟芯片提供外延片衬底 | related | L2 | 10 |
| 东微半导 | 688261 | 功率半导体 | 受益标的 | core | pricing | 10 |
| 华天科技 | 002185 | 功率半导体 | - | - | - | 10 |
| 华润微 | 688396 | 功率半导体 | 功率IDM | core | pricing | 10 |
| 华虹宏力 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 士兰微 | 600460 | 功率半导体 | 分立器件产品营收63.79亿元/毛利率12.22%/同比+17.32% | core | L2 | 10 |
| 天岳先进 | 688234 | 功率半导体 | SiC衬底 | core | L2 | 10 |

## 候选 4：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：62.88
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.83 | 新高股8只，新高成交210.48亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| limit_heat | 5.05 | 涨停3只，市场占比9.09，排名19 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 10 |
| AI数据中心 | 5 |
| AI数据中心储能 | 5 |
| IDC数据中心 | 5 |
| 云计算数据中心 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中仑新材 | 301565 | AI数据中心 | BOPP新能源膜材（薄膜电容器基膜）、功能性BOPA膜材、生物降解BOP... | related | L1_L3_candidate | 10 |
| 中国西电 | 601179 | AI数据中心 | 特高压设备、主网一次设备、海外电力设备 | related | L1_L3_candidate | 10 |
| 亨通光电 | 600487 | AI数据中心 | 特别是AI数据中心需求驱动的光纤业务 | core | L1_L3_candidate | 10 |
| 京泉华 | 002885 | AI数据中心 | MFT高频变压器（AI数据中心） | related | L1_L3_candidate | 10 |
| 佛燃能源 | 002911 | AI数据中心 | 城市燃气（天然气销售与输配）、能源化工服务及延伸（油品/化工品贸易）、绿... | related | L1_L3_candidate | 10 |
| 天齐锂业 | 002466 | AI数据中心 | 锂矿采选、锂化工产品（碳酸锂、氢氧化锂 | related | L1_L3_candidate | 10 |
| 宏微科技 | 688711 | AI数据中心 | AI数据中心电源 | related | L1_L3_candidate | 10 |
| 宗申动力 | 001696 | AI数据中心 | 通用机械、摩托车发动机、航空动力 | related | L1_L3_candidate | 10 |

## 候选 5：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：62.12
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 38.12 | 新高股6只，新高成交137.49亿，容量前三=True |
| new_high_cluster | 24.0 | 题材内新高股6只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人形机器人 | 10 |
| AI终端 | 2 |
| MIM金属注射成型 | 2 |
| PEEK材料 | 2 |
| 传感器 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万凯新材 | 301216 | 人形机器人 | 聚酯瓶片(PET)、天然气制乙二醇(MEG)、rPET生物酶法再生 | related | L1_L3_candidate | 10 |
| 万向钱潮 | 000559 | 人形机器人 | 研发布局人形机器人精密零部件（依托精密轴承技术平台） | peripheral | L2 | 10 |
| 万通液压 | 920839 | 人形机器人 | 研发人形机器人关节用高精度行星滚柱丝杠副、超大负载工业机器人油气分离平衡... | peripheral | L2 | 10 |
| 三花智控 | 002050 | 人形机器人 | 全产业链（执行器、减速器、丝杠、灵巧手） | core | L1 | 10 |
| 东睦股份 | 600114 | 人形机器人 | MIM金属注射成形（折叠屏铰链、AI连接器、机器人灵巧手零件）、P&S粉... | related | L1_L3_candidate | 10 |
| 东阳光 | 600673 | 人形机器人 | 具身智能（人形机器人） | core | L1_L3_candidate | 10 |
| 中大力德 | 002896 | 人形机器人 | 机器人核心零部件供应商 | related | L2 | 10 |
| 中控技术 | 688777 | 人形机器人 | TPT工业大模型、DCS、SIS控制系统、UCS通用控制系统 | core | L1_L3_candidate | 10 |

## 候选 6：燃料电池

- **标准概念**：燃料电池
- **申万一级**：电力设备
- **评分**：58.06
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 36.06 | 新高股5只，新高成交84.97亿，容量前三=True |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 燃料电池 | 10 |
| SOFC燃料电池 | 5 |
| SOFC（固体氧化物燃料电池） | 5 |
| 固体氧化物燃料电池(SOFC) | 5 |
| 储能电池 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 壹石通 | 688733 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 三环集团 | 300408 | SOFC（固体氧化物燃料电池） | 陶瓷材料与零部件潜在相关 | peripheral | L1 | 20 |
| 三花智控 | 002050 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国巨石 | 600176 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国船舶 | 600150 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中材科技 | 002080 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中航光电 | 002179 | SOFC（固体氧化物燃料电池） | - | - | - | 20 |
| 京东方A | 000725 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 7：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：53.2
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.8 | 新高股2只，新高成交80.19亿，容量前三=True |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| limit_heat | 5.4 | 涨停4只，市场占比12.12，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 先进封装 | 10 |
| 1.6T CPO | 2 |
| 2.5D封装 | 2 |
| 3D封装 | 2 |
| ABF膜涨价 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三孚新科 | 688359 | 先进封装 | TGV玻璃基板设备+药水 | related | L1_L3_candidate | 10 |
| 三安光电 | 600703 | 先进封装 | 光芯片（AI算力光互联）、碳化硅（SiC功率器件）、Mini | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 先进封装 | 投资潜在相关（非直接产业链） | peripheral | L2_candidate | 10 |
| 上海新阳 | 300236 | 先进封装 | 集成电路制造及先进封装用关键工艺材料（电镀液 | related | L1_L3_candidate | 10 |
| 东威科技 | 688700 | 先进封装 | 半导体封装电镀设备 | related | L1_L3_candidate | 10 |
| 中京电子 | 002579 | 先进封装 | - | - | - | 10 |
| 中国巨石 | 600176 | 先进封装 | 先进封装上游高端电子布潜在相关 | peripheral | L2_candidate | 10 |
| 中微公司 | 688012 | 先进封装 | 封装设备 | related | L2_candidate | 10 |

## 候选 8：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：52.51
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.81 | 新高股2只，新高成交80.91亿，容量前三=True |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| limit_heat | 4.7 | 涨停2只，市场占比6.06，排名21 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |
| CPO（共封装光学） | 10 |
| 1.6T CPO | 5 |
| CPO一级封装 | 5 |
| CPO二级封装 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中瓷电子 | 003031 | 1.6T CPO | 陶瓷封装、高导热材料 | related | L1_image_extraction | 20 |
| 中际旭创 | 300308 | 1.6T CPO | 高速光模块龙头、完整方案交付 | core | L1_image_extraction | 20 |
| 光迅科技 | 002281 | 1.6T CPO | 光芯片/器件/模块 | related | L1_image_extraction | 20 |
| 华工科技 | 000988 | 1.6T CPO | 800G规模交付、1.6T LPO/LRO、3.2T CPO布局 | related | L1_image_extraction | 20 |
| 博众精工 | 688097 | 1.6T CPO | 贴片、耦合、检测自动化 | peripheral | L1_image_extraction | 20 |
| 天孚通信 | 300394 | 1.6T CPO | 高速光引擎、FAU、微光学器件 | core | L1_image_extraction | 20 |
| 新易盛 | 300502 | 1.6T CPO | 400G/800G/1.6T产品线 | related | L1_image_extraction | 20 |
| 水晶光电 | 002273 | 1.6T CPO | 微光学元件 | peripheral | L1_image_extraction | 20 |

## 候选 9：机器人

- **标准概念**：机器人
- **申万一级**：计算机
- **评分**：50.0
- **触发类型**：limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 机器人 | 10 |
| AI机器人 | 5 |
| 人形机器人 | 5 |
| 医疗机器人 | 5 |
| 外骨骼机器人 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 宜通世纪 | 300310 | AI机器人 | 通信网络工程服务、通信网络维护服务、通信网络优化服务 | related | L2 | 10 |
| 富奥股份 | 000030 | AI机器人 | - | related | L1 | 10 |
| 德赛西威 | 002920 | AI机器人 | 智能座舱、智能驾驶、网联服务 | core | L1_L3_candidate | 10 |
| 泽宇智能 | 301179 | AI机器人 | AI机器人 | core | L1_L3_candidate | 10 |
| 移远通信 | 603236 | AI机器人 | 蜂窝模组、车载模组、AI模组 | related | L1_L3_candidate | 10 |
| 万凯新材 | 301216 | 人形机器人 | 聚酯瓶片(PET)、天然气制乙二醇(MEG)、rPET生物酶法再生 | related | L1_L3_candidate | 10 |
| 万向钱潮 | 000559 | 人形机器人 | 研发布局人形机器人精密零部件（依托精密轴承技术平台） | peripheral | L2 | 10 |
| 万通液压 | 920839 | 人形机器人 | 研发人形机器人关节用高精度行星滚柱丝杠副、超大负载工业机器人油气分离平衡... | peripheral | L2 | 10 |

## 候选 10：长安汽车

- **标准概念**：长安汽车
- **申万一级**：汽车
- **评分**：48.46
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 26.46 | 新高股5只，新高成交116.74亿，容量前三=False |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
