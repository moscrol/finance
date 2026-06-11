# 2026-05-25 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：顶部横盘
- **成交额**：32054.48
- **上涨家数**：2181
- **涨停 / 跌停**：103 / 15
- **容量前三行业**：1.电子(32.7%, super_capacity)、2.电力设备(9.6%, normal)、3.机械设备(8.5%, normal)

## 二、候选总览

| 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 先进封装 | 先进封装 | 电子 | 336.95 | double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 2 |
| PCB | PCB | 电子 | 325.0 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 2 |
| MLCC | MLCC | 电子 | 298.36 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 9 | 1 |
| 存储芯片 | 存储芯片 | 电子 | 234.6 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 半导体 | 半导体 | 电子 | 214.35 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 共封装光学(CPO) | CPO | 电子 | 202.55 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 |
| 风电 | 风电 | 电力设备 | 191.47 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| MCU芯片 | MCU芯片 | 电子 | 186.75 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 2 | 1 |
| 半导体设备 | 半导体设备 | 电子 | 186.4 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 5 | 12 | 3 |
| 英伟达 | 英伟达Rubin架构 | 电子 | 185.97 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 |
| 高压快充 | 超充 | 电力设备 | 183.15 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 1 | 0 |
| 数据中心 | 数据中心 | 计算机 | 182.9 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 3D打印 | 3D打印 | 机械设备 | 182.4 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 消费电子 | 消费电子 | 电子 | 181.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 商业航天 | 商业航天 | 国防军工 | 181.5 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 |
| 光刻胶 | 光刻胶 | 电子 | 181.16 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 华为手机 | 华为手机 | 电子 | 180.85 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 0 | 0 |
| 特高压 | 特高压 | 电力设备 | 180.27 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 无人驾驶 | 无人驾驶 | 汽车 | 179.11 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 10 | 1 |
| 超级电容 | 超级电容 | 电力设备 | 179.07 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 毫米波雷达 | 毫米波雷达 | 汽车 | 176.65 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 11 | 1 |
| 电子化学品 | 电子化学品 | 基础化工 | 173.81 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 6G | 6G | 通信 | 164.7 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 大飞机 | 大飞机 | 国防军工 | 162.6 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 航空发动机 | 航空发动机 | 国防军工 | 160.07 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 元件 | 电子元件 | 电子 | 159.76 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 |
| 量子科技 | 量子科技 | 计算机 | 156.17 | double_red、new_high_direction、new_high_cluster | 2 | 7 | 1 |
| 通信设备 | 通信设备 | 通信 | 153.13 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| BC电池 | BC电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 1 | 1 |
| HJT电池 | HJT电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 3 | 1 |
| MR(混合现实) | MRAM | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 11 | 0 |
| 可控核聚变 | 可控核聚变 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 |
| 芯片 | AI推理芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 |
| 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 |
| 人工智能 | 人工智能 | 计算机 | 125.6 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 |
| 低空经济 | 低空经济 | 国防军工 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 |
| 军工 | 军工 | 国防军工 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 |
| AI智能体 | AI智能体 | 计算机 | 122.8 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 |
| 电力 | 新型电力系统 | 公用事业 | 122.8 | double_red、limit_heat、new_high_cluster | 5 | 12 | 0 |
| DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 1 | 0 |
| 云计算 | 云计算 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 |
| 信创 | 信创 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 |
| 军工装备 | 军工装备 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 8 | 1 |
| 软件开发 | AIGC | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 6 | 0 |
| 雅下水电 | 雅下水电 | 电力设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 |
| 算力租赁 | 算力租赁 | 计算机 | 115.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 1 |
| 华为昇腾 | 华为昇腾 | 计算机 | 112.0 | double_red、new_high_cluster | 5 | 12 | 1 |
| 光通信 | 光通信 | 电力设备 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 |
| 人形机器人 | 人形机器人 | 机械设备 | 100.8 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 |
| 传感器 | 传感器 | 机械设备 | 100.45 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |

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

## 候选 11：高压快充

- **标准概念**：超充
- **申万一级**：电力设备
- **评分**：183.15
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.38%，边际量 18.12%，成交额 1244.71 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.38%，边际量18.12%，成交1244.71亿 |
| new_high_direction | 57.15 | 新高股27只，新高成交571.92亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 超充 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 盛弘股份 | 300693 | 超充 | 产业链供应商 | peripheral | L1 | 1 |

## 候选 12：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：182.9
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.49%，边际量 12.75%，成交额 8895.12 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.49%，边际量12.75%，成交8895.12亿 |
| new_high_direction | 58.0 | 新高股96只，新高成交2373.7999999999993亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.9 | 涨停14只，市场占比13.59，排名6 |

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

## 候选 13：3D打印

- **标准概念**：3D打印
- **申万一级**：机械设备
- **评分**：182.4
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.64%，边际量 10.67%，成交额 1336.97 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.64%，边际量10.67%，成交1336.97亿 |
| new_high_direction | 56.4 | 新高股23只，新高成交512.2700000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

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

## 候选 14：消费电子

- **标准概念**：消费电子
- **申万一级**：电子
- **评分**：181.95
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.42%，边际量 16.23%，成交额 1183.17 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.42%，边际量16.23%，成交1183.17亿 |
| new_high_direction | 55.95 | 新高股21只，新高成交476.34999999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费电子 | 10 |
| 消费电子设备 | 5 |
| 3D打印钛合金 | 2 |
| 8.6代OLED产线 | 2 |
| 8K超高清 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三利谱 | 002876 | 消费电子 | 显示面板材料间接相关 | peripheral | L1 | 10 |
| 东睦股份 | 600114 | 消费电子 | 消费电子MIM结构件供应商 | related | L1 | 10 |
| 中石科技 | 300684 | 消费电子 | 消费电子高导热材料供应商 | core | L1 | 10 |
| 中科蓝讯 | 688332 | 消费电子 | 蓝牙耳机及音箱音频SoC芯片供应商 | core | L1 | 10 |
| 乐凯胶片 | 600135 | 消费电子 | 偏光片/显示薄膜及锂电外包装铝塑膜供应商 | related | L1 | 10 |
| 乐鑫科技 | 688018 | 消费电子 | 消费级及智能家居IoT芯片供应商 | core | L1 | 10 |
| 乾照光电 | 300102 | 消费电子 | 图谱弱关联 | peripheral | graph_only | 10 |
| 京东方A | 000725 | 消费电子 | 市场信号弱关联 | related | L2_candidate | 10 |

## 候选 15：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：181.5
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.74%，边际量 10.47%，成交额 4795.44 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.74%，边际量10.47%，成交4795.44亿 |
| new_high_direction | 58.0 | 新高股88只，新高成交1779.2599999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比9.71，排名16 |

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

## 候选 16：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：181.16
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.9%，边际量 19.54%，成交额 815.9 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.9%，边际量19.54%，成交815.9亿 |
| new_high_direction | 55.16 | 新高股24只，新高成交412.70000000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光刻胶 | 10 |
| EUV光刻胶 | 5 |
| g线光刻胶 | 5 |
| i线光刻胶 | 5 |
| 光刻胶树脂 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万润股份 | 002643 | 光刻胶 | 光刻胶上游材料潜在相关 | related | L1 | 10 |
| 上海新阳 | 300236 | 光刻胶 | 产业链供应商 | related | L2_candidate | 10 |
| 中芯国际 | 688981 | 光刻胶 | 2025 年国内 12 英寸晶圆产能同比增长 25%，带动成熟制程光刻胶... | peripheral | L1_L3_candidate | 10 |
| 八亿时空 | 688181 | 光刻胶 | 百吨级KrF高端光刻胶配方树脂国产化自主突破及生产平台 | related | L1 | 10 |
| 华特气体 | 688268 | 光刻胶 | 上游材料 | peripheral | graph_only | 10 |
| 南大光电 | 300346 | 光刻胶 | 高端193nm ArF光刻胶及配套底漆、电子特气与高纯MO源核心攻坚大厂 | core | L1 | 10 |
| 容大感光 | 300576 | 光刻胶 | 光刻胶相关产品/材料供应商 | related | L2 | 10 |
| 广信材料 | 300537 | 光刻胶 | 光刻胶相关产品/材料供应商 | related | L2 | 10 |

## 候选 17：华为手机

- **标准概念**：华为手机
- **申万一级**：电子
- **评分**：180.85
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.49%，边际量 18.35%，成交额 803.55 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.49%，边际量18.35%，成交803.55亿 |
| new_high_direction | 54.85 | 新高股16只，新高成交387.93000000000006亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 18：特高压

- **标准概念**：特高压
- **申万一级**：电力设备
- **评分**：180.27
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.46%，边际量 14.14%，成交额 1292.4 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.46%，边际量14.14%，成交1292.4亿 |
| new_high_direction | 54.27 | 新高股16只，新高成交341.36亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 特高压 | 10 |
| 中国盾构机 | 2 |
| 换流变压器 | 2 |
| 换流阀 | 2 |
| 汽车板 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国西电 | 601179 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 伊戈尔 | 002922 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 佛塑科技 | 000973 | 特高压 | 国家电网特高压电容器专用高等级电工绝缘薄膜核心供应商 | peripheral | graph_only | 10 |
| 国电南瑞 | 600406 | 特高压 | 特高压/电网设备受益名单 | peripheral | graph_only | 10 |
| 宝钢股份 | 600019 | 特高压 | 3.2.1 变压器产业链分析 | related | L2_candidate | 10 |
| 平高电气 | 600312 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 思源电气 | 002028 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 特变电工 | 600089 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |

## 候选 19：无人驾驶

- **标准概念**：无人驾驶
- **申万一级**：汽车
- **评分**：179.11
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.87%，边际量 11.09%，成交额 4022.82 亿，容量前三=否
- **知识库状态**：concept=是（4），exposure=是（10），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.87%，边际量11.09%，成交4022.82亿 |
| new_high_direction | 55.61 | 新高股67只，新高成交1249.0399999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比9.71，排名15 |

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

## 候选 20：超级电容

- **标准概念**：超级电容
- **申万一级**：电力设备
- **评分**：179.07
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.1%，边际量 15.96%，成交额 626.21 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.1%，边际量15.96%，成交626.21亿 |
| new_high_direction | 53.07 | 新高股15只，新高成交325.59000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 超级电容 | 10 |
| 电容 | 2 |
| 电容薄膜 | 2 |
| 电解液 | 2 |
| 铝电解电容 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三花智控 | 002050 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 东山精密 | 002384 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 东方财富 | 300059 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 东阳光 | 600673 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中兴通讯 | 000063 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中材科技 | 002080 | 超级电容 | 超级电容活性炭相关供应商 | related | L1_L3_candidate | 10 |
| 中际旭创 | 300308 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 京东方A | 000725 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |

## 候选 21：毫米波雷达

- **标准概念**：毫米波雷达
- **申万一级**：汽车
- **评分**：176.65
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.44%，边际量 11.04%，成交额 1933.32 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（11），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.44%，边际量11.04%，成交1933.32亿 |
| new_high_direction | 54.55 | 新高股33只，新高成交1164.33亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比5.83，排名30 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 毫米波雷达 | 10 |
| 传感器 | 2 |
| 光波导 | 2 |
| 均热板 | 2 |
| 安防监控 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中石科技 | 300684 | 毫米波雷达 | 4.3.2 射频器件公司 | related | L1_L3_candidate | 10 |
| 保隆科技 | 603197 | 毫米波雷达 | 4.3.3 模组集成公司 | related | L2_candidate | 10 |
| 华域汽车 | 600741 | 毫米波雷达 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 卓胜微 | 300782 | 毫米波雷达 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 德赛西威 | 002920 | 毫米波雷达 | 产业链供应商 | related | L2_candidate | 10 |
| 欧菲光 | 002456 | 毫米波雷达 | 4.3.4 其他相关公司 | related | L2_candidate | 10 |
| 比亚迪 | 002594 | 毫米波雷达 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 硕贝德 | 300322 | 毫米波雷达 | 产业链供应商 | related | L2_candidate | 10 |

## 候选 22：电子化学品

- **标准概念**：电子化学品
- **申万一级**：基础化工
- **评分**：173.81
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.76%，边际量 23.81%，成交额 725.54 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.76%，边际量23.81%，成交725.54亿 |
| new_high_direction | 44.61 | 新高股17只，新高成交369.0400000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 13.2 | day10排名第2，区间涨幅15.0% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子化学品 | 10 |
| g线光刻胶 | 2 |
| i线光刻胶 | 2 |
| 封装基板药水 | 2 |
| 推理芯片 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三孚新科 | 688359 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 上海新阳 | 300236 | 电子化学品 | 电子化学品研发生产商 | peripheral | graph_only | 10 |
| 中巨芯 | 688549 | 电子化学品 | 电子化学品供应商 | peripheral | graph_only | 10 |
| 兴福电子 | 688545 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 华特气体 | 688268 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 南大光电 | 300346 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 国瓷材料 | 300285 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 天承科技 | 688603 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |

## 候选 23：6G

- **标准概念**：6G
- **申万一级**：通信
- **评分**：164.7
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.35%，边际量 12.81%，成交额 1899.07 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.35%，边际量12.81%，成交1899.07亿 |
| new_high_direction | 48.7 | 新高股18只，新高成交696.2799999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 24：大飞机

- **标准概念**：大飞机
- **申万一级**：国防军工
- **评分**：162.6
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.57%，边际量 18.43%，成交额 1186.87 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.57%，边际量18.43%，成交1186.87亿 |
| new_high_direction | 46.6 | 新高股19只，新高成交527.87亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 大飞机 | 10 |
| C919大飞机 | 5 |
| C919 | 2 |
| C929 | 2 |
| 中国低空经济 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万泽股份 | 000534 | 大飞机 | 高温合金/航空发动机材料相关企业 | peripheral | graph_only | 10 |
| 三角防务 | 300775 | 大飞机 | C919等大飞机机身及结构件大型模锻件核心供应商 | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 大飞机 | 上游材料 | related | L2_candidate | 10 |
| 中航光电 | 002179 | 大飞机 | 产业链供应商 | peripheral | L1 | 10 |
| 中航沈飞 | 600760 | 大飞机 | 民用商用大飞机机体（C919后机身、垂直尾翼）核心机体结构件供应商 | peripheral | graph_only | 10 |
| 中航西飞 | 000768 | 大飞机 | 产业链供应商 | related | L2_candidate | 10 |
| 光威复材 | 300699 | 大飞机 | 上游材料 | related | L1_L3_candidate | 10 |
| 北摩高科 | 002985 | 大飞机 | 航空刹车制动与起落架相关产品供应商，推进起落架批产交付和国产大飞机刹车盘... | related | L1_L3_candidate | 10 |

## 候选 25：航空发动机

- **标准概念**：航空发动机
- **申万一级**：国防军工
- **评分**：160.07
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.09%，边际量 14.95%，成交额 838.24 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.09%，边际量14.95%，成交838.24亿 |
| new_high_direction | 44.07 | 新高股15只，新高成交405.58000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 航空发动机 | 10 |
| 军用航空发动机 | 5 |
| 民用航空发动机 | 5 |
| C929 | 2 |
| EPC模式 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万泽股份 | 000534 | 航空发动机 | 高温合金/航空发动机材料相关企业 | peripheral | graph_only | 10 |
| 中航重机 | 600765 | 航空发动机 | 航空发动机核心锻件供应商 | core | L1 | 10 |
| 云路股份 | 688190 | 航空发动机 | 航空配套电机/传感器用精密软磁材料潜在供应商 | peripheral | L1 | 10 |
| 宝钛股份 | 600456 | 航空发动机 | 航空发动机用高端钛合金材料制造商 | core | L1 | 10 |
| 抚顺特钢 | 600399 | 航空发动机 | 航空特殊钢/高温合金材料供应商 | peripheral | graph_only | 10 |
| 派克新材 | 605123 | 航空发动机 | 航空发动机锻件/环锻件供应商 | peripheral | graph_only | 10 |
| 航亚科技 | 688510 | 航空发动机 | 图谱弱关联 | peripheral | graph_only | 10 |
| 航发动力 | 600893 | 航空发动机 | 航空发动机主机/配套企业 | peripheral | graph_only | 10 |

## 候选 26：元件

- **标准概念**：电子元件
- **申万一级**：电子
- **评分**：159.76
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 64.96 | 新高股31只，新高成交1197.0亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅10.83% |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅7.97% |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅11.48% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元件 | 5 |
| 磁性元件 | 5 |
| 被动元件 | 5 |
| AI硬件 | 2 |
| OCS光电路交换机产业链 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | 电子元件 | 电子元件和基础材料生产商 | core | L1 | 10 |
| 博迁新材 | 605376 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 国瓷材料 | 300285 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 洁美科技 | 002859 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 深圳华强 | 000062 | 电子元件 | 半导体授权分销/边缘AI计算系统 | peripheral | L1_L3_candidate | 10 |
| 火炬电子 | 603678 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 铜冠铜箔 | 301217 | 电子元件 | 市场信号弱关联 | related | L2_candidate | 10 |
| 风华高科 | 000636 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 27：量子科技

- **标准概念**：量子科技
- **申万一级**：计算机
- **评分**：156.17
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.06%，边际量 16.77%，成交额 1465.23 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.06%，边际量16.77%，成交1465.23亿 |
| new_high_direction | 40.17 | 新高股13只，新高成交317.86亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 量子科技 | 10 |
| 量子计算 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科曙光 | 603019 | 量子科技 | 产业链供应商 | peripheral | L1_L3_candidate | 10 |
| 光迅科技 | 002281 | 量子科技 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 华工科技 | 000988 | 量子科技 | 上游设备 | peripheral | L1 | 10 |
| 国盾量子 | 688027 | 量子科技 | 5.3 产能布局与扩产计划 | peripheral | L1 | 10 |
| 国芯科技 | 688262 | 量子科技 | 汽车电子芯片(域控MCU)国产替代厂商，RISC-V车规MCU与量子安全... | related | L1_L3_candidate | 10 |
| 神州信息 | 000555 | 量子科技 | 产业链供应商 | peripheral | L2_candidate | 10 |
| 腾景科技 | 688195 | 量子科技 | 产业链供应商 | core | L1_L3_candidate | 10 |

## 候选 28：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：153.13
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.76%，边际量 11.85%，成交额 2063.71 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.76%，边际量11.85%，成交2063.71亿 |
| new_high_direction | 37.13 | 新高股10只，新高成交410.65亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 29：BC电池

- **标准概念**：BC电池
- **申万一级**：电力设备
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.95%，边际量 18.65%，成交额 576.5 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（1），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.95%，边际量18.65%，成交576.5亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| BC电池 | 10 |
| 210尺寸 | 2 |
| 4C_5C快充 | 2 |
| 4C电池 | 2 |
| 800V平台 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 隆基绿能 | 601012 | BC电池 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 30：HJT电池

- **标准概念**：HJT电池
- **申万一级**：电力设备
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.24%，边际量 13.23%，成交额 565.46 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（3），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.24%，边际量13.23%，成交565.46亿 |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| HJT电池 | 10 |
| 4C电池 | 2 |
| BBU电池备份单元 | 2 |
| BC电池 | 2 |
| HJT | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 帝科股份 | 300842 | HJT电池 | HJT异质结电池银浆供应商，银包铜浆料降本方案推动者 | peripheral | L1 | 10 |
| 聚和材料 | 688503 | HJT电池 | 图谱弱关联 | peripheral | graph_only | 10 |
| 迈为股份 | 300751 | 光伏辅材 | HJT电池整线装备厂商，潜在受益北美/太空光伏扩产 | related | L1_L3_candidate | 1 |

## 候选 31：MR(混合现实)

- **标准概念**：MRAM
- **申万一级**：电子
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 1.08%，边际量 10.83%，成交额 880.53 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（11），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.08%，边际量10.83%，成交880.53亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MRAM | 5 |
| MRI设备 | 5 |
| MRI超导磁体 | 5 |
| MR芯片 | 5 |
| mRNA技术 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 健信超导 | - | MRI超导磁体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 瑞普生物 | 300119 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 5 |
| 科前生物 | 688526 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 5 |
| 金河生物 | 002688 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 5 |
| 科华数据 | 002335 | 储能 | 数据中心电源、HVDC、液冷与储能设备供应商，服务互联网大厂与海外能源市... | related | L1_L3_candidate | 1 |
| 东富龙 | 300171 | 动物疫苗 | 产业链供应商 | related | L1 | 1 |
| 中国广核 | 003816 | 核电 | 核电/SMR/AIDC供能受益名单 | peripheral | graph_only | 1 |
| 中国核建 | 601611 | 核电 | 核电/SMR/AIDC供能受益名单 | peripheral | graph_only | 1 |

## 候选 32：可控核聚变

- **标准概念**：可控核聚变
- **申万一级**：电力设备
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.27%，边际量 13.25%，成交额 1058.85 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.27%，边际量13.25%，成交1058.85亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 可控核聚变 | 10 |
| 核电 | 2 |
| 核聚变 | 2 |
| 管道 | 2 |
| 超导 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 可控核聚变 | 聚变托卡马克装置大型超导线圈及腔体外延设备集成商 | peripheral | graph_only | 10 |
| 中国核建 | 601611 | 可控核聚变 | 聚变堆（如ITER、CFETR）核岛安装与高难度工程总包商 | peripheral | graph_only | 10 |
| 中国核电 | 601985 | 可控核聚变 | 核聚变商业化国家级平台战略参股及未来运营方 | peripheral | graph_only | 10 |
| 中矿资源 | 002738 | 可控核聚变 | 上游材料 | peripheral | L1 | 10 |
| 久立特材 | 002318 | 可控核聚变 | 托卡马克超导磁体导管（特种合金管）供应商 | peripheral | L1 | 10 |
| 永鼎股份 | 600105 | 可控核聚变 | 上游材料 | related | L2_candidate | 10 |
| 西部超导 | 688122 | 可控核聚变 | 航空高端钛合金、NbTi/Nb3Sn低温超导线材和高温合金供应商 | related | L1_L3_candidate | 10 |
| 上海电气 | 601727 | 核电与可控核聚变 | 受益标的 | related | - | 5 |

## 候选 33：芯片

- **标准概念**：AI推理芯片
- **申万一级**：电子
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 2.19%，边际量 16.05%，成交额 14989.4 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.19%，边际量16.05%，成交14989.4亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI推理芯片 | 5 |
| AI算力核心赛道：ASIC芯片产业链 | 5 |
| AI芯片 | 5 |
| AI芯片电感 | 5 |
| BMS芯片 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中芯国际 | 688981 | AI算力核心赛道：ASIC芯片产业链 | 中游制造 | peripheral | graph_only | 20 |
| 华天科技 | 002185 | AI算力核心赛道：ASIC芯片产业链 | 中游封装测试 | peripheral | graph_only | 20 |
| 寒武纪 | 688256 | AI算力核心赛道：ASIC芯片产业链 | 6.1 重点推荐标的 | peripheral | graph_only | 20 |
| 海光信息 | 688041 | AI算力核心赛道：ASIC芯片产业链 | 4.1 设计领域龙头企业 | peripheral | graph_only | 20 |
| 芯原股份 | 688521 | AI算力核心赛道：ASIC芯片产业链 | 885431.TI | peripheral | graph_only | 20 |
| 通富微电 | 002156 | AI算力核心赛道：ASIC芯片产业链 | 中游封装测试 | peripheral | graph_only | 20 |
| 长电科技 | 600584 | AI算力核心赛道：ASIC芯片产业链 | 中游封装测试 | peripheral | graph_only | 20 |
| 东芯股份 | 688110 | AI芯片 | 存算联一体化探索潜在相关 | peripheral | L2_candidate | 10 |

## 候选 34：铜缆高速连接

- **标准概念**：铜缆高速连接
- **申万一级**：电力设备
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 1.69%，边际量 11.99%，成交额 943.74 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.69%，边际量11.99%，成交943.74亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 35：人工智能

- **标准概念**：人工智能
- **申万一级**：计算机
- **评分**：125.6
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.1%，边际量 11.41%，成交额 6510.46 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.1%，边际量11.41%，成交6510.46亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比15.53，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人工智能 | 10 |
| AI人工智能 | 5 |
| 人工智能AI | 5 |
| 5G通信 | 2 |
| AI+办公 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东华软件 | 002065 | 人工智能 | AI行业应用系统集成潜在相关 | peripheral | L1 | 10 |
| 东方国信 | 300166 | 人工智能 | AI软件和智算服务潜在相关 | related | L1 | 10 |
| 中控技术 | 688777 | 人工智能 | 工业智能制造场景潜在AI应用方 | peripheral | L2_candidate | 10 |
| 云从科技 | 688327 | 人工智能 | 人工智能算法、软件及系统集成服务商 | core | L1 | 10 |
| 华泰股份 | 600308 | 人工智能 | 图谱弱关联 | peripheral | graph_only | 10 |
| 宏景科技 | 301396 | 人工智能 | 算力服务与智慧城市综合服务商，提供GPU硬件采购、算力组网和算力租赁相关... | related | L1_L3_candidate | 10 |
| 强瑞技术 | 301128 | 人工智能 | AI服务器液冷检测设备、散热结构件、智能汽车测试设备与机器人无刷电机供应... | related | L1_L3_candidate | 10 |
| 松霖科技 | 603992 | 人工智能 | 智能厨卫和健康硬件IDM厂商，拓展康养服务机器人与AI陪伴类机器人业务 | related | L1_L3_candidate | 10 |

## 候选 36：低空经济

- **标准概念**：低空经济
- **申万一级**：国防军工
- **评分**：123.5
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.29%，边际量 11.89%，成交额 3207.59 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.29%，边际量11.89%，成交3207.59亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比9.71，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 低空经济 | 10 |
| 中国低空经济 | 5 |
| eVTOL电机 | 2 |
| 无人机 | 2 |
| 深地经济 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光威复材 | 300699 | 中国低空经济 | 上游材料 | peripheral | graph_only | 10 |
| 航天彩虹 | 002389 | 中国低空经济 | 上游材料 | peripheral | graph_only | 10 |
| 万丰奥威 | 002085 | 低空经济 | 通航固定翼飞机制造平台 | related | L1 | 10 |
| 中信海直 | 000099 | 低空经济 | 通航运营服务商 | core | L1 | 10 |
| 中直股份 | 600038 | 低空经济 | 低空飞行器及民用直升机航空器供应商 | related | L1 | 10 |
| 亿航智能 | - | 低空经济 | 运营端 | core | - | 10 |
| 华设集团 | 603018 | 低空经济 | 基建/规划设计/设备 | core | - | 10 |
| 卧龙电驱 | 600580 | 低空经济 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 37：军工

- **标准概念**：军工
- **申万一级**：国防军工
- **评分**：123.5
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.15%，边际量 12.33%，成交额 4236.79 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.15%，边际量12.33%，成交4236.79亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比9.71，排名18 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 军工 | 10 |
| 军工电子 | 5 |
| 军工装备 | 5 |
| 国防军工 | 5 |
| FPGA | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中电兴发 | 002298 | 军工 | 边防信息化及特种高可靠弱电工程集成配套商 | peripheral | graph_only | 10 |
| 中航光电 | 002179 | 军工 | 军工防务光电连接器龙头 | peripheral | graph_only | 10 |
| 中航西飞 | 000768 | 军工 | 特种重型运输机（运-20）及军用战略航空器整机总装厂 | peripheral | graph_only | 10 |
| 中航重机 | 600765 | 军工 | 军工防务航空锻铸件配套商 | peripheral | graph_only | 10 |
| 中船防务 | 600685 | 军工 | 军工舰船装备供应商 | related | L2 | 10 |
| 光电股份 | 600184 | 军工 | 中国兵器集团旗下精密防务光电设备、武器制导控制系统唯一上市平台 | peripheral | graph_only | 10 |
| 北摩高科 | 002985 | 军工 | 航空刹车制动与起落架相关产品供应商，推进起落架批产交付和国产大飞机刹车盘... | related | L1_L3_candidate | 10 |
| 宏达电子 | 300726 | 军工 | 钽电容器相关产品供应商 | related | L2 | 10 |

## 候选 38：AI智能体

- **标准概念**：AI智能体
- **申万一级**：计算机
- **评分**：122.8
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.14%，边际量 11.91%，成交额 2465.46 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.14%，边际量11.91%，成交2465.46亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比7.77，排名22 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI智能体 | 10 |
| AI智能体产业链 | 5 |
| AIoT | 2 |
| AI大模型 | 2 |
| AI平台 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东阳光 | 600673 | AI智能体 | OpenClaw算力链与国产算力/华为系/字节系受益名单 | peripheral | graph_only | 10 |
| 优刻得 | 688158 | AI智能体 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 光庭信息 | 301221 | AI智能体 | 图谱弱关联 | peripheral | graph_only | 10 |
| 协创数据 | 300857 | AI智能体 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 宏景科技 | 301396 | AI智能体 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 寒武纪 | 688256 | AI智能体 | OpenClaw算力链与国产算力/华为系/字节系受益名单 | peripheral | graph_only | 10 |
| 智微智能 | 001339 | AI智能体 | 智算中心建设与算力服务商，布局高性能服务器、算力调度、MaaS和AI推理... | related | L3 | 10 |
| 汉得信息 | 300170 | AI智能体 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 39：电力

- **标准概念**：新型电力系统
- **申万一级**：公用事业
- **评分**：122.8
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 2.4%，边际量 17.03%，成交额 743.6 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4%，边际量17.03%，成交743.6亿 |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| limit_heat | 6.8 | 涨停8只，市场占比7.77，排名26 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新型电力系统 | 5 |
| 电力巡检 | 5 |
| 电力现货 | 5 |
| 电力芯片 | 5 |
| 电力设备 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国能建 | 601868 | 新型电力系统 | 算电协同/三电协同 | core | - | 10 |
| 中国西电 | 601179 | 新型电力系统 | 全产业链 | core | - | 10 |
| 国电南瑞 | 600406 | 新型电力系统 | 算电协同/三电协同 | core | - | 10 |
| 国网信通 | 600131 | 新型电力系统 | 电力运营/交易软件 | core | - | 10 |
| 威胜信息 | 688100 | 新型电力系统 | 电力设备全链 | core | - | 10 |
| 平高电气 | 600312 | 新型电力系统 | 特高压设备 | core | - | 10 |
| 朗新集团 | 300682 | 新型电力系统 | 电力运营/交易软件 | core | - | 10 |
| 泽宇智能 | 301179 | 新型电力系统 | 电力信息系统、数智化解决方案与电网AI巡检服务商 | related | L1_L3_candidate | 10 |

## 候选 40：DeepSeek

- **标准概念**：DeepSeek
- **申万一级**：计算机
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 10.66%，成交额 4528.74 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量10.66%，成交4528.74亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华胜天成 | 600410 | 华为昇腾 | AI基础设施与智能联络中心服务商，华为昇腾生态合作方 | related | L1_L3_candidate | 1 |

## 候选 41：云计算

- **标准概念**：云计算
- **申万一级**：计算机
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.01%，边际量 14.8%，成交额 1704.68 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.01%，边际量14.8%，成交1704.68亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 云计算 | 10 |
| ABF载板 | 2 |
| AI容器 | 2 |
| AI应用 | 2 |
| AI智能体 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国电信 | 601728 | 云计算 | 产业数字化和云网服务潜在平台 | related | L2_candidate | 10 |
| 中电鑫龙 | 002298 | 云计算 | 智慧城市信息化及云底座解决方案商 | related | L1 | 10 |
| 云赛智联 | 600602 | 云计算 | 云服务、MSP云管理平台及技术服务商 | core | L2_candidate | 10 |
| 优刻得 | 688158 | 云计算 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 协创数据 | 300857 | 云计算 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 南威软件 | 603636 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |
| 博睿数据 | 688229 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |
| 品高股份 | 688227 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 42：信创

- **标准概念**：信创
- **申万一级**：计算机
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.25%，边际量 17.62%，成交额 1884.8 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.25%，边际量17.62%，成交1884.8亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 信创 | 10 |
| 信创产业 | 5 |
| 金融信创 | 5 |
| FPGA | 2 |
| IT服务 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三六零 | 601360 | 信创 | 信创安全防护潜在参与方 | related | L1 | 10 |
| 中国软件 | 600536 | 信创 | 党政信创基础软件和解决方案平台 | core | L1 | 10 |
| 中国长城 | 000066 | 信创 | 信创整机和计算设备供应商 | core | L1 | 10 |
| 中望软件 | 688083 | 信创 | 国产工业软件替代潜在参与者 | related | L1 | 10 |
| 优刻得 | 688158 | 信创 | 中立云计算与国产化适配云平台 | core | L1 | 10 |
| 佰维存储 | 688525 | 信创 | 国产整机和服务器存储模块厂商 | core | L1 | 10 |
| 品高股份 | 688227 | 信创 | 图谱弱关联 | peripheral | graph_only | 10 |
| 恒生电子 | 600570 | 信创 | 产业链供应商 | peripheral | graph_only | 10 |

## 候选 43：军工装备

- **标准概念**：军工装备
- **申万一级**：国防军工
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.1%，边际量 14.22%，成交额 562.06 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（8），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.1%，边际量14.22%，成交562.06亿 |
| new_high_cluster | 26.0 | 题材内新高股8只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 军工装备 | 10 |
| eVTOL | 2 |
| 信息化 | 2 |
| 全球海上油气 | 2 |
| 全球航运 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国海防 | 600764 | 军工装备 | 海洋防务电子装备供应商 | related | L2 | 10 |
| 中国重工 | 601989 | 军工装备 | 军工舰船装备供应商 | related | L2 | 10 |
| 中直股份 | 600038 | 军工装备 | 直升机整机与航空装备主机厂 | peripheral | graph_only | 10 |
| 中船防务 | 600685 | 军工装备 | 军工舰船装备供应商 | related | L2 | 10 |
| 天和防务 | 300397 | 军工装备 | 海洋防务电子装备供应商 | related | L2 | 10 |
| 泰豪科技 | 600590 | 军工装备 | 数据中心备用电源与军工/应急装备供应商 | related | L1_L3_candidate | 10 |
| 中兵红箭 | 000519 | 国防军工 | 军工装备企业 | peripheral | graph_only | 1 |
| 中无人机 | 688297 | 空天信息与新型基础设施 | 受益标的 | related | - | 1 |

## 候选 44：软件开发

- **标准概念**：AIGC
- **申万一级**：计算机
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 1.0%，边际量 12.22%，成交额 583.29 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（6），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.0%，边际量12.22%，成交583.29亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AIGC | 2 |
| IT服务 | 2 |
| 区块链 | 2 |
| 垂直应用软件 | 2 |
| 应用软件 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华大九天 | 301269 | EDA | EDA相关产品/材料供应商 | related | L2 | 1 |
| 东华软件 | 002065 | IT服务 | 行业IT服务和系统集成商 | peripheral | graph_only | 1 |
| 四方精创 | 300468 | 区块链 | 软件开发及维护供应商/运营商 | related | L2 | 1 |
| 中望软件 | 688083 | 垂直应用软件 | 垂直应用软件企业 | peripheral | graph_only | 1 |
| 光庭信息 | 301221 | 智能驾驶 | 高级自动驾驶、AEB电控及ADAS算法应用开发与测试代工商 | core | L1 | 1 |
| 恒生电子 | 600570 | 软件 | 垂直应用软件服务商 | related | L2 | 1 |

## 候选 45：雅下水电

- **标准概念**：雅下水电
- **申万一级**：电力设备
- **评分**：116.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.26%，边际量 20.32%，成交额 546.88 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.26%，边际量20.32%，成交546.88亿 |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 46：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：115.0
- **触发类型**：limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 算力租赁 | 10 |
| AI应用 | 2 |
| AI服务器电源 | 2 |
| AI算力 | 2 |
| LPU推理芯片 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| CoreWeave | - | 算力租赁 | 图谱弱关联 | peripheral | graph_only | 10 |
| 中国电信 | 601728 | 算力租赁 | 算力服务套餐潜在运营方 | peripheral | L2_candidate | 10 |
| 中科曙光 | 603019 | 算力租赁 | 上游材料/设备 | peripheral | L1 | 10 |
| 云赛智联 | 600602 | 算力租赁 | 城市计算大数据租赁与技术服务商 | related | L2_candidate | 10 |
| 协创数据 | 300857 | 算力租赁 | 算力中心运营与智能算力服务商 | related | L1_L3_candidate | 10 |
| 奥飞数据 | 300738 | 算力租赁 | 中游制造 | related | L1_L3_candidate | 10 |
| 寒武纪 | 688256 | 算力租赁 | 中游制造 | related | L1_L3_candidate | 10 |
| 工业富联 | 601138 | 算力租赁 | 上游材料/设备 | related | L1_L3_candidate | 10 |

## 候选 47：华为昇腾

- **标准概念**：华为昇腾
- **申万一级**：计算机
- **评分**：112.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.08%，边际量 14.49%，成交额 706.23 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.08%，边际量14.49%，成交706.23亿 |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 华为昇腾 | 10 |
| CANN（华为昇腾异构计算架构） | 5 |
| CANN | 2 |
| 华为算力 | 2 |
| 异构计算 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 博创科技 | 300548 | CANN | 市场信号弱关联 | related | L2_candidate | 10 |
| 四川长虹 | 600839 | CANN | 图谱弱关联 | peripheral | graph_only | 10 |
| 安集科技 | 688019 | CANN | 上游材料 | peripheral | graph_only | 10 |
| 拓维信息 | 002261 | CANN | 3.3 产业链价值分布与集中度分析 | peripheral | graph_only | 10 |
| 东华软件 | 002065 | 华为昇腾 | 智算中心集成潜在相关 | related | L1 | 10 |
| 东方国信 | 300166 | 华为昇腾 | 昇腾生态适配潜在相关 | peripheral | L1 | 10 |
| 中芯国际 | 688981 | 华为昇腾 | 中游制造 | related | L1 | 10 |
| 中际旭创 | 300308 | 华为昇腾 | 昇腾超节点高速光模块核心供应商 | related | L1 | 10 |

## 候选 48：光通信

- **标准概念**：光通信
- **申万一级**：电力设备
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

## 候选 49：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：100.8
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股93只，新高成交1738.9499999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比7.77，排名23 |

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

## 候选 50：传感器

- **标准概念**：传感器
- **申万一级**：机械设备
- **评分**：100.45
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股74只，新高成交1798.41亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比6.8，排名27 |

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
