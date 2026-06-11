# 2026-04-07 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：横盘
- **成交额**：16142.0
- **上涨家数**：3977
- **涨停 / 跌停**：93 / 73
- **容量前三行业**：1.电子(16.8%, capacity)、2.电力设备(10.8%, normal)、3.通信(8.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 先进封装 | 先进封装 | 电子 | 166.5 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 2 | 存储芯片 | 存储芯片 | 电子 | 127.75 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 3 | 光通信 | 光通信 | 电力设备 | 119.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 | - |
| 4 | 半导体 | 半导体 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 5 | PCB | PCB | 电力设备 | 101.14 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 6 | 共封装光学(CPO) | CPO | 电子 | 85.26 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 7 | 风电 | 风电 | 电力设备 | 82.35 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 8 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 82.14 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 9 | 通信设备 | 通信设备 | 通信 | 81.12 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 10 | 数据中心 | 数据中心 | 计算机 | 78.94 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 液冷服务器 | 液冷服务器 | 电力设备 | 75.16 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 12 | 创新药 | 创新药 | 医药生物 | 74.73 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 氢能源 | 氢能源 | 电力设备 | 74.66 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 4 | 1 | - |
| 14 | 6G | 6G | 通信 | 72.39 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 15 | 无人驾驶 | 无人驾驶 | 汽车 | 70.58 | new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 16 | 特高压 | 特高压 | 电力设备 | 70.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 17 | 电网设备 | 电网设备 | 电力设备 | 67.97 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 18 | 人形机器人 | 人形机器人 | 机械设备 | 66.27 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 19 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 63.42 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 20 | 商业航天 | 商业航天 | 国防军工 | 62.84 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 海峡两岸 | 海峡两岸 | 综合 | 60.41 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 22 | 机器视觉 | 机器视觉 | 机械设备 | 59.39 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 23 | 光刻机 | 光刻机 | 电子 | 58.32 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 24 | PET铜箔 | PET铜箔 | 电力设备 | 58.3 | new_high_direction、new_high_cluster、capacity_industry | 5 | 9 | 1 | - |
| 25 | 新型工业化 | 新型工业化 | 机械设备 | 56.34 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 26 | TOPCON电池 | TOPCon电池 | 电力设备 | 54.67 | new_high_direction、new_high_cluster、capacity_industry | 5 | 7 | 0 | missing_evidence |
| 27 | 可控核聚变 | 可控核聚变 | 电力设备 | 52.22 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 28 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 51.7 | new_high_direction、new_high_cluster、capacity_industry | 0 | 4 | 0 | missing_concept、missing_evidence |
| 29 | 传感器 | 传感器 | 机械设备 | 51.45 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 30 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 51.27 | new_high_direction、new_high_cluster、capacity_industry | 1 | 1 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 量子科技 | 量子科技 | 计算机 | 49.64 | new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 32 | 毫米波雷达 | 毫米波雷达 | 汽车 | 48.16 | new_high_direction、new_high_cluster | 5 | 11 | 1 | - |
| 33 | 太赫兹 | 6G产业 | 国防军工 | 46.57 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 34 | 小米汽车 | 小米汽车 | 汽车 | 41.53 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 数据要素 | 数据要素 | 计算机 | 41.27 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 医药 | 医药 | 医药生物 | 39.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 37 | 储能 | 储能 | - | 36.65 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 固态电池 | 固态电池 | - | 32.8 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 39 | 人工智能 | 人工智能 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 低空经济 | 低空经济 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 41 | 军工 | 军工 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 化学制药 | 原料药 | - | 31.4 | limit_heat、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 43 | 化学制品 | 化工周期 | - | 26.8 | limit_heat、new_high_cluster | 3 | 7 | 0 | missing_evidence |
| 44 | 地缘冲突 | 地缘冲突 | 计算机 | 24.0 | limit_advance_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 45 | 算力 | 算力 | 计算机 | 24.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 46 | 化学原料 | 仿制药 | - | 23.85 | limit_heat、new_high_cluster | 5 | 6 | 0 | missing_evidence |
| 47 | 建筑装饰 | 工程 | - | 23.75 | limit_heat、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 48 | 家居用品 | 家居用品 | - | 21.75 | limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 芯片概念 | 芯片概念 | - | 8.9 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | 光伏概念 | 光伏概念 | - | 8.2 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 五、核心候选明细

## 候选 1：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：166.5
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.56%，边际量 12.29%，成交额 1180.54 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.56%，边际量12.29%，成交1180.54亿 |
| new_high_direction | 40.5 | 新高股8只，新高成交103.93亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
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

## 候选 2：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：127.75
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_cluster
- **盘面信号**：涨幅 1.79%，边际量 12.76%，成交额 1214.06 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.79%，边际量12.76%，成交1214.06亿 |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比5.38，排名18 |

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

## 候选 3：光通信

- **标准概念**：光通信
- **申万一级**：电力设备
- **评分**：119.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 119.0 | 连板股3只，最高3板，容量前三=True |

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

## 候选 4：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：116.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 1.32%，边际量 17.27%，成交额 1278.31 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.32%，边际量17.27%，成交1278.31亿 |
| new_high_cluster | 16.0 | 题材内新高股2只 |
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

## 候选 5：PCB

- **标准概念**：PCB
- **申万一级**：电力设备
- **评分**：101.14
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.14 | 新高股11只，新高成交138.91000000000003亿，容量前三=True |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 6：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：85.26
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.86 | 新高股14只，新高成交501.12亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比4.3，排名24 |

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
- **评分**：82.35
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 50.25 | 新高股13只，新高成交324.29999999999995亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比6.45，排名14 |

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

## 候选 8：光纤

- **标准概念**：AI算力驱动下的MPO光纤连接器产业
- **申万一级**：通信
- **评分**：82.14
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 56.14 | 新高股17只，新高成交491.01亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 9：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：81.12
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 49.72 | 新高股12只，新高成交393.29亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比4.3，排名21 |

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

## 候选 10：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：78.94
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 46.49 | 新高股23只，新高成交518.84亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比7.53，排名10 |

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
