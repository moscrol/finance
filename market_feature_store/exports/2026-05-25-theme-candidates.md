# 2026-05-25 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：顶部横盘
- **成交额**：32054.48
- **上涨家数**：2181
- **涨停 / 跌停**：103 / 15
- **容量前三行业**：1.电子(32.7%, super_capacity)、2.电力设备(9.6%, normal)、3.机械设备(8.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 先进封装 | 先进封装 | 电子 | 336.95 | double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 2 | PCB | PCB | 电子 | 325.0 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 3 | MLCC | MLCC | 电子 | 298.36 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 4 | 存储芯片 | 存储芯片 | 电子 | 234.6 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 半导体 | 半导体 | 电子 | 214.35 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 共封装光学(CPO) | CPO | 电子 | 202.55 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 7 | 风电 | 风电 | 电力设备 | 191.47 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | MCU芯片 | MCU芯片 | 电子 | 186.75 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 2 | 1 | - |
| 9 | 半导体设备 | 半导体设备 | 电子 | 186.4 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 5 | 12 | 3 | - |
| 10 | 英伟达 | 英伟达Rubin架构 | 电子 | 185.97 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 高压快充 | 超充 | 电力设备 | 183.15 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 12 | 数据中心 | 数据中心 | 计算机 | 182.9 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 3D打印 | 3D打印 | 机械设备 | 182.4 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 消费电子 | 消费电子 | 电子 | 181.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 商业航天 | 商业航天 | 国防军工 | 181.5 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 16 | 光刻胶 | 光刻胶 | 电子 | 181.16 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | 华为手机 | 华为手机 | 电子 | 180.85 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 18 | 特高压 | 特高压 | 电力设备 | 180.27 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 无人驾驶 | 无人驾驶 | 汽车 | 179.11 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 20 | 超级电容 | 超级电容 | 电力设备 | 179.07 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | 毫米波雷达 | 毫米波雷达 | 汽车 | 176.65 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 11 | 1 | - |
| 22 | 电子化学品 | 电子化学品 | 基础化工 | 173.81 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 6G | 6G | 通信 | 164.7 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 大飞机 | 大飞机 | 国防军工 | 162.6 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 航空发动机 | 航空发动机 | 国防军工 | 160.07 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 元件 | 电子元件 | 电子 | 159.76 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 27 | 量子科技 | 量子科技 | 计算机 | 156.17 | double_red、new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 28 | 通信设备 | 通信设备 | 通信 | 153.13 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 29 | BC电池 | BC电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 1 | 1 | - |
| 30 | HJT电池 | HJT电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 3 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | MR(混合现实) | MRAM | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 11 | 0 | missing_evidence |
| 32 | 可控核聚变 | 可控核聚变 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 芯片 | AI推理芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 34 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 人工智能 | 人工智能 | 计算机 | 125.6 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 低空经济 | 低空经济 | 国防军工 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 37 | 军工 | 军工 | 国防军工 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 38 | AI智能体 | AI智能体 | 计算机 | 122.8 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 电力 | 新型电力系统 | 公用事业 | 122.8 | double_red、limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 40 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 41 | 云计算 | 云计算 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 信创 | 信创 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 军工装备 | 军工装备 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 8 | 1 | - |
| 44 | 软件开发 | AIGC | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 6 | 0 | missing_evidence |
| 45 | 雅下水电 | 雅下水电 | 电力设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 算力租赁 | 算力租赁 | 计算机 | 115.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 华为昇腾 | 华为昇腾 | 计算机 | 112.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 光通信 | 光通信 | 电力设备 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 | - |
| 49 | 人形机器人 | 人形机器人 | 机械设备 | 100.8 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 50 | 传感器 | 传感器 | 机械设备 | 100.45 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：336.95
- **触发类型**：double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.63%，边际量 19.37%，成交额 4202.9 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.63%，边际量19.37%，成交4202.9亿 |
| new_high_direction | 68.0 | 新高股76只，新高成交2492.830000000001亿，容量前三=True |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅4.63% |
| multi_period_rank | 27.4 | day10排名第3，区间涨幅12.56% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅8.59% |
| multi_period_rank | 26.6 | day3排名第4，区间涨幅4.28% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |

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

## 候选 2：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：325.0
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.36%，边际量 10.31%，成交额 3691.95 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 131.0 | 连板股5只，最高2板，容量前三=True |
| double_red | 90.0 | 涨幅2.36%，边际量10.31%，成交3691.95亿 |
| new_high_direction | 68.0 | 新高股85只，新高成交2254.259999999999亿，容量前三=True |
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

## 候选 3：MLCC

- **标准概念**：MLCC
- **申万一级**：电子
- **评分**：298.36
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.81%，边际量 85.05%，成交额 751.36 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股3只，最高2板，容量前三=True |
| double_red | 90.0 | 涨幅3.81%，边际量85.05%，成交751.36亿 |
| new_high_direction | 57.36 | 新高股28只，新高成交588.72亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MLCC | 10 |
| MLCC微型化 | 5 |
| MLCC材料 | 5 |
| MLCC镍粉 | 5 |
| 高阶MLCC | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 博杰股份 | 002975 | MLCC | 电子测试与自动化设备供应商，覆盖AI服务器测试、液冷方案、MLCC测试分... | related | L1_L3_candidate | 10 |
| 国瓷材料 | 300285 | MLCC | 上游材料/电子陶瓷与固态电解质 | related | L3_candidate | 10 |
| 洁美科技 | 002859 | MLCC | MLCC用离型膜供应商，拟拓展离子束抛光等超精密加工设备 | related | L1_L3_candidate | 10 |
| 风华高科 | 000636 | MLCC | MLCC、片式电阻器、电感器等被动元器件供应商，拓展AI服务器与车规电子... | related | L1_L3_candidate | 10 |
| 博迁新材 | 605376 | MLCC材料 | 全球MLCC（多层陶瓷电容器）内电极用纳米级超细镍粉绝对破局和保供垄断巨... | peripheral | graph_only | 10 |
| 三环集团 | 300408 | 高阶MLCC | MLCC/被动元件潜在相关 | related | L1 | 10 |
| 火炬电子 | 603678 | 高阶MLCC | 图谱弱关联 | peripheral | graph_only | 10 |
| 鸿远电子 | 603267 | 高阶MLCC | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 4：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：234.6
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.01%，边际量 21.11%，成交额 6008.52 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.01%，边际量21.11%，成交6008.52亿 |
| new_high_direction | 68.0 | 新高股64只，新高成交3209.7200000000016亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 16.6 | daily排名第4，区间涨幅4.01% |
| multi_period_rank | 15.8 | day10排名第5，区间涨幅11.1% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比11.65，排名10 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 存储芯片 | 10 |
| HBM（高带宽存储） | 2 |
| 先进封装 | 2 |
| 半导体 | 2 |
| 半导体材料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士（000660.KS） | 000660 | 存储芯片 | 图谱弱关联 | peripheral | graph_only | 10 |
| 上峰水泥 | 000672 | 存储芯片 | 股权投资潜在相关 | peripheral | L2_candidate | 10 |
| 上海合晶 | 688584 | 存储芯片 | 存储晶圆制造上游硅片材料潜在供应商 | peripheral | L2_candidate | 10 |
| 东芯股份 | 688110 | 存储芯片 | 中小容量通用型存储芯片设计商 | core | L2_candidate | 10 |
| 中微公司 | 688012 | 存储芯片 | 上游设备 | peripheral | L1 | 10 |
| 中科飞测 | 688361 | 存储芯片 | 存储晶圆制造量检测设备供应商 | related | L2_candidate | 10 |
| 中船特气 | 688146 | 存储芯片 | 存储芯片扩产关键特气材料供应商 | related | L2_candidate | 10 |
| 中芯国际 | 688981 | 存储芯片 | 芯片/核心器件 | peripheral | L1_L3_candidate | 10 |

## 候选 5：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：214.35
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.52%，边际量 23.46%，成交额 5344.67 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.52%，边际量23.46%，成交5344.67亿 |
| new_high_direction | 68.0 | 新高股55只，新高成交2431.9000000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 13.2 | daily排名第2，区间涨幅4.52% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.15 | 涨停9只，市场占比8.74，排名19 |

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

## 候选 6：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：202.55
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.7%，边际量 13.69%，成交额 6196.08 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.7%，边际量13.69%，成交6196.08亿 |
| new_high_direction | 68.0 | 新高股62只，新高成交2638.2400000000007亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.55 | 涨停13只，市场占比12.62，排名8 |

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

## 候选 7：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：191.47
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.44%，边际量 10.72%，成交额 3075.84 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.44%，边际量10.72%，成交3075.84亿 |
| new_high_direction | 56.57 | 新高股42只，新高成交525.9800000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 8.9 | 涨停14只，市场占比13.59，排名7 |

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

## 候选 8：MCU芯片

- **标准概念**：MCU芯片
- **申万一级**：电子
- **评分**：186.75
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.73%，边际量 25.28%，成交额 1450.33 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（2），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.73%，边际量25.28%，成交1450.33亿 |
| new_high_direction | 60.75 | 新高股32只，新高成交859.9000000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MCU芯片 | 10 |
| 智能控制器 | 2 |
| 车规芯片 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兆易创新 | 603986 | 半导体涨价潮 | 存储+MCU芯片厂商，券商研判其可能受益于半导体涨价潮 | peripheral | L1 | 1 |
| 乐鑫科技 | 688018 | 车规芯片 | 车规级Wi-Fi/蓝牙MCU芯片潜在供应商 | peripheral | graph_only | 1 |

## 候选 9：半导体设备

- **标准概念**：半导体设备
- **申万一级**：电子
- **评分**：186.4
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 3.74%，边际量 16.69%，成交额 837.9 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.74%，边际量16.69%，成交837.9亿 |
| multi_period_rank | 24.0 | day10排名第1，区间涨幅20.98% |
| multi_period_rank | 21.6 | day5排名第4，区间涨幅8.11% |
| multi_period_rank | 20.8 | daily排名第5，区间涨幅3.74% |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体设备 | 10 |
| CPO | 2 |
| GPU | 2 |
| GPU（图形处理器） | 2 |
| HBM | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中微公司 | 688012 | 半导体设备 | 半导体设备研发生产企业 | core | L2_candidate | 10 |
| 中科飞测 | 688361 | 半导体设备 | 半导体专用设备制造商 | core | L2_candidate | 10 |
| 亚翔集成 | 603929 | 半导体设备 | 洁净室工程服务商，受益半导体/AI基建洁净室工程量价齐升 | related | L1_L3_candidate | 10 |
| 光力科技 | 300480 | 半导体设备 | 半导体精密加工与检测设备供应商，推进激光划片、开槽和隐切设备验证 | related | L1_L3_candidate | 10 |
| 凤凰光学 | 600071 | 半导体设备 | 图谱弱关联 | peripheral | graph_only | 10 |
| 凯美特气 | 002549 | 半导体设备 | 图谱弱关联 | peripheral | graph_only | 10 |
| 北方华创 | 002371 | 半导体设备 | 国内前段核心制程（刻蚀、薄膜沉积、立式炉、清洗）谱系最全、份额最高的半导... | core | L2_candidate | 10 |
| 华峰测控 | 688200 | 半导体设备 | 国产半导体模拟及数模混合大功率测试机、数控核心测试信号采集装备絕對龙头 | core | L2_candidate | 10 |

## 候选 10：英伟达

- **标准概念**：英伟达Rubin架构
- **申万一级**：电子
- **评分**：185.97
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.77%，边际量 10.25%，成交额 1990.5 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.77%，边际量10.25%，成交1990.5亿 |
| new_high_direction | 59.97 | 新高股19只，新高成交797.77亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
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
