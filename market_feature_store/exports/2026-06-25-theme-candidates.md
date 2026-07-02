# 2026-06-25 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：探底阶段
- **成交额**：35940.04
- **上涨家数**：1231
- **涨停 / 跌停**：86 / 17
- **容量前三行业**：1.电子(33.5%, super_capacity)、2.通信(8.7%, normal)、3.机械设备(7.9%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PCB | PCB | 电子 | 301.0 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 2 | 光纤 | 光纤 | 通信 | 287.0 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 半导体 | 半导体 | 电子 | 215.1 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 4 | 共封装光学(CPO) | CPO | 电子 | 202.2 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 5 | AI眼镜 | AI眼镜 | 电子 | 201.15 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 6 | 先进封装 | 先进封装 | 电子 | 200.8 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 7 | AI PC | AI PC | 电子 | 192.9 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | MCU芯片 | MCU芯片 | 电子 | 190.5 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 4 | 1 | - |
| 9 | 元件 | 光学元件 | 电子 | 188.09 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 10 | AI手机 | AI手机 | 电子 | 174.57 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 4 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 超级电容 | 超级电容 | 电力设备 | 168.11 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 164.69 | double_red、new_high_direction、new_high_cluster | 0 | 6 | 0 | missing_concept、missing_evidence |
| 13 | 算力租赁 | 算力租赁 | 计算机 | 160.89 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 14 | 电子化学品 | 电子化学品 | 基础化工 | 160.75 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | PET铜箔 | PET铜箔 | 电力设备 | 156.16 | double_red、new_high_direction、new_high_cluster | 5 | 10 | 1 | - |
| 16 | 存储芯片 | 存储芯片 | 电子 | 133.6 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 17 | 芯片 | 芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 18 | 英伟达 | 英伟达 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 19 | BC电池 | BC电池 | 电力设备 | 116.0 | double_red、new_high_cluster | 5 | 10 | 1 | - |
| 20 | 证券 | 证券 | 非银金融 | 116.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 21 | 传感器 | 传感器 | 机械设备 | 101.5 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 22 | 人形机器人 | 人形机器人 | 机械设备 | 101.15 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 23 | 数据中心 | 数据中心 | 计算机 | 94.65 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 商业航天 | 商业航天 | 国防军工 | 91.85 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 25 | 液冷服务器 | 液冷服务器 | 电力设备 | 91.85 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 海峡两岸 | 海峡两岸 | 综合 | 90.72 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 27 | 3D打印 | 3D打印 | 机械设备 | 90.49 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 28 | 无人驾驶 | 无人驾驶 | 汽车 | 89.25 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 29 | 电容器/MLCC | MLCC | 国防军工 | 89.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 30 | 风电 | 风电 | 电力设备 | 86.46 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 光学光电子 | LED芯片 | 电子 | 86.09 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 32 | 消费电子 | 消费电子 | 电子 | 84.67 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 33 | 光刻胶 | 光刻胶 | 电子 | 84.19 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 34 | 氢能源 | 氢能源 | 电力设备 | 84.04 | limit_heat、new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 35 | 半导体设备 | 半导体设备 | 电子 | 83.67 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 36 | 机器视觉 | 机器视觉 | 机械设备 | 83.2 | new_high_direction、new_high_cluster、capacity_industry | 2 | 9 | 0 | missing_evidence |
| 37 | 新型工业化 | 新型工业化 | 机械设备 | 82.28 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 38 | MLCC | MLCC | 电子 | 81.93 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 39 | 智能座舱 | 智能座舱 | 汽车 | 81.92 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 通用设备 | 金属制品 | 机械设备 | 81.47 | new_high_direction、new_high_cluster、capacity_industry | 1 | 8 | 0 | missing_evidence |
| 41 | 通信设备 | 通信设备 | 通信 | 80.92 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 42 | 毫米波雷达 | 毫米波雷达 | 汽车 | 80.51 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 信创 | 信创 | 计算机 | 79.44 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 小金属 | 小金属 | 有色金属 | 79.44 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 45 | 6G | 6G | 通信 | 76.42 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 46 | 氟化工 | 氟化工 | 基础化工 | 74.4 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 数据要素 | 数据要素 | 计算机 | 72.73 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 量子科技 | 量子科技 | 计算机 | 72.38 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 49 | 长安汽车 | 长安汽车 | 汽车 | 71.83 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | 可控核聚变 | 可控核聚变 | 电力设备 | 70.56 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：301.0
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.35%，边际量 15.69%，成交额 4693.58 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |
| double_red | 90.0 | 涨幅1.35%，边际量15.69%，成交4693.58亿 |
| new_high_direction | 68.0 | 新高股52只，新高成交1548.0400000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 10 |
| 1.6T交换机PCB | 5 |
| AI PCB | 5 |
| AIPCB专用油墨 | 5 |
| PCB印制电路板 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东威科技 | 688700 | AI PCB | PCB精密电镀设备（核心） | related | L1_L3_candidate | 20 |
| 东山精密 | 002384 | AI PCB | 光芯片自供+光模块+AI PCB量产供应商 | core | L1_L3_candidate | 20 |
| 中京电子 | 002579 | AI PCB | - | - | - | 20 |
| 中国巨石 | 600176 | AI PCB | 待补充 | related | L3 | 20 |
| 中富电路 | 300814 | AI PCB | AI服务器三次电源PCB、二次电源PCB（HVDC）、埋感埋容嵌入式PC... | related | L1_L3_candidate | 20 |
| 中钨高新 | 000657 | AI PCB | PCB微钻、铣刀（金洲公司，AI+光模块耗材） | related | L1_L3_candidate | 20 |
| 兴森科技 | 002436 | AI PCB | 待补充 | related | L3 | 20 |
| 南亚新材 | 688519 | AI PCB | 高频高速CCL国产替代和涨价弹性标的 | peripheral | - | 20 |

## 候选 2：光纤

- **标准概念**：光纤
- **申万一级**：通信
- **评分**：287.0
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.5%，边际量 17.02%，成交额 4024.12 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 93.0 | 连板股2只，最高3板，容量前三=False |
| double_red | 90.0 | 涨幅1.5%，边际量17.02%，成交4024.12亿 |
| new_high_direction | 68.0 | 新高股33只，新高成交1743.1099999999994亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光纤 | 10 |
| AI算力驱动下的MPO光纤连接器产业 | 5 |
| G.654.E光纤 | 5 |
| MPO光纤连接器 | 5 |
| 光棒光纤一体化 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | AI算力驱动下的MPO光纤连接器产业 | 4.4 国产替代进程分析 | peripheral | graph_only | 10 |
| 仕佳光子 | 688313 | AI算力驱动下的MPO光纤连接器产业 | 2025 年净利润预计 4.77-5.1 亿元，对应 PE 约 33 倍 | peripheral | graph_only | 10 |
| 光库科技 | 300620 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 太辰光 | 300570 | AI算力驱动下的MPO光纤连接器产业 | 3.2.1 太辰光（300570） | peripheral | graph_only | 10 |
| 长芯博创 | 300548 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 通光线缆 | 300265 | G.654.E光纤 | 光纤光缆（含OPGW、ADSS电力光缆、G.654.E高端光纤）、输电线... | related | L1_L3_candidate | 10 |
| 华丰科技 | 688629 | MPO光纤连接器 | 高速线模组、高速背板连接器、NPO连接器 | related | L1_L3_candidate | 10 |
| 唯科科技 | 301196 | MPO光纤连接器 | MPO光通信零部件、机器人轻量化部件、新能源汽车零部件、精密注塑模具 | related | L1_L3_candidate | 10 |

## 候选 3：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：215.1
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股3只，最高2板，容量前三=True |
| new_high_direction | 68.0 | 新高股75只，新高成交3880.4199999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比6.98，排名29 |

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
| 华天科技 | 002185 | 功率半导体 | - | - | - | 10 |
| 华润微 | 688396 | 功率半导体 | 功率器件（MOSFET/IGBT）、制造与代工服务（12寸晶圆）、第三代... | related | L1_L3_candidate | 10 |
| 华虹宏力 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 士兰微 | 600460 | 功率半导体 | 国内极成熟、拥有多代特色晶圆制造代工线的一流功率分立器件IDM全产业链巨... | core | L1 | 10 |
| 天岳先进 | 688234 | 功率半导体 | 弱相关，待验证 | related | L2 | 10 |
| 宏微科技 | 688711 | 功率半导体 | IGBT模块、SiC模块、GaN器件 | related | L1_L3_candidate | 10 |
| 富乐德 | 301297 | 功率半导体 | 覆铜陶瓷载板（DCB/AMB/DPC）、泛半导体精密洗净服务、半导体核心... | core | L1_L3_candidate | 10 |

## 候选 4：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：202.2
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.75%，边际量 15.54%，成交额 8006.66 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.75%，边际量15.54%，成交8006.66亿 |
| new_high_direction | 68.0 | 新高股52只，新高成交3122.0099999999993亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比13.95，排名10 |

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

## 候选 5：AI眼镜

- **标准概念**：AI眼镜
- **申万一级**：电子
- **评分**：201.15
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.57%，边际量 15.74%，成交额 3910.2 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.57%，边际量15.74%，成交3910.2亿 |
| new_high_direction | 68.0 | 新高股38只，新高成交2236.7099999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.15 | 涨停9只，市场占比10.47，排名20 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI眼镜 | 10 |
| AI眼镜产业链 | 5 |
| AR眼镜 | 2 |
| OCS（光电路交换机） | 2 |
| 全景相机产业 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 京东方A | 000725 | AI眼镜 | 近眼显示/显示面板 | related | L2_curated_research | 10 |
| 佰维存储 | 688525 | AI眼镜 | 存储模组/可穿戴存储 | related | L2_curated_research | 10 |
| 佳禾智能 | 300793 | AI眼镜 | 电声产品设计研发、制造、销售 | core | L1_L3_candidate | 10 |
| 光库科技 | 300620 | AI眼镜 | 市场信号弱关联 | related | L2_candidate | 10 |
| 全志科技 | 300458 | AI眼镜 | 高性价比AI眼镜SoC及高性能AI-ISP处理芯片设计商 | core | L1 | 10 |
| 华勤技术 | 603296 | AI眼镜 | 智能硬件ODM | related | L2_curated_research | 10 |
| 华灿光电 | 300323 | AI眼镜 | Micro LED/显示芯片 | related | L2_curated_research | 10 |
| 卓兆点胶 | 920026 | AI眼镜 | 消费电子点胶设备/阀体（果链核心供应商）、Meta AI眼镜点胶阀、点胶... | core | L1_L3_candidate | 10 |

## 候选 6：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：200.8
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.8%，边际量 16.16%，成交额 5809.39 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.8%，边际量16.16%，成交5809.39亿 |
| new_high_direction | 68.0 | 新高股67只，新高成交3155.6099999999974亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比9.3，排名24 |

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

## 候选 7：AI PC

- **标准概念**：AI PC
- **申万一级**：电子
- **评分**：192.9
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.27%，边际量 25.79%，成交额 2130.95 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.27%，边际量25.79%，成交2130.95亿 |
| new_high_direction | 66.9 | 新高股15只，新高成交1432.2999999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI PC | 20 |
| AI PCB | 15 |
| AIPCB专用油墨 | 15 |
| AIPC液冷 | 15 |
| AI智能化 | 9 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 传艺科技 | 002866 | AI PC | FPC柔性线路板 | related | L1_L3_candidate | 20 |
| 奥士康 | 002913 | AI PC | AI服务器高多层板、AIPC高阶HDI板、汽车电子PCB | related | L1_L3_candidate | 20 |
| 慧为智能 | 920876 | AI PC | 智能终端ODM（AI PC、边缘计算设备、信创终端） | core | L2 | 20 |
| 泓淋电力 | 301439 | AI PC | 电源线组件（计算机/家电）、特种线缆、新能源汽车充电连接产品、高速铜缆（... | related | L1_L3_candidate | 20 |
| 泰嘉股份 | 002843 | AI PC | 电源业务（AI服务器电源 | related | L1_L3_candidate | 20 |
| 苏大维格 | 300331 | AI PC | 半导体光掩模缺陷检测设备、激光直写光刻设备、纳米压印光刻设备 | related | L1_L3_candidate | 20 |
| 英力股份 | 300956 | AI PC | 笔记本电脑结构件模组及精密模具 | related | L2 | 20 |
| 软通动力 | 301236 | AI PC | AI服务器（昇腾/鲲鹏）、AI PC（机械革命品牌）、信创PC与服务器（... | core | L1_L3_candidate | 20 |

## 候选 8：MCU芯片

- **标准概念**：MCU芯片
- **申万一级**：电子
- **评分**：190.5
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.99%，边际量 10.84%，成交额 1859.05 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（4），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.99%，边际量10.84%，成交1859.05亿 |
| new_high_direction | 64.5 | 新高股24只，新高成交1159.9699999999996亿，容量前三=True |
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
| 乐鑫科技 | 688018 | MCU芯片 | 物联网Wi-Fi MCU芯片设计 | related | L1_L3_candidate | 10 |
| 力源信息 | 300184 | MCU芯片 | AI服务器MLCC分销、华为海思芯片代理、存储芯片分销、碳化硅（SiC）... | related | L1_L3_candidate | 10 |
| 恒烁股份 | 688416 | MCU芯片 | MCU芯片 | related | L1_L3_candidate | 10 |
| 兆易创新 | 603986 | 半导体涨价潮 | 存储+MCU芯片厂商，券商研判其可能受益于半导体涨价潮 | peripheral | L1 | 1 |

## 候选 9：元件

- **标准概念**：光学元件
- **申万一级**：电子
- **评分**：188.09
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.14%，边际量 19.38%，成交额 1982.79 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.14%，边际量19.38%，成交1982.79亿 |
| new_high_direction | 55.29 | 新高股15只，新高成交503.38亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比9.3，排名25 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光学元件 | 5 |
| 电子元件 | 5 |
| 磁性元件 | 5 |
| 被动元件 | 5 |
| 1.6T CPO | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 腾景科技 | 688195 | 光学元件 | 精密光学元组件相关产品供应商 | related | L2 | 10 |
| 茂莱光学 | 688502 | 光学元件 | 精密光学器件相关产品供应商 | related | L2 | 10 |
| 蓝特光学 | 688127 | 光学元件 | 光学元件供应商 | peripheral | L1 | 10 |
| 三环集团 | 300408 | 电子元件 | 电子元件和基础材料生产商 | core | L1 | 10 |
| 博迁新材 | 605376 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 国瓷材料 | 300285 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 洁美科技 | 002859 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 深圳华强 | 000062 | 电子元件 | 半导体授权分销/边缘AI计算系统 | peripheral | L1_L3_candidate | 10 |

## 候选 10：AI手机

- **标准概念**：AI手机
- **申万一级**：电子
- **评分**：174.57
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.07%，边际量 33.12%，成交额 1601.95 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.07%，边际量33.12%，成交1601.95亿 |
| new_high_direction | 48.57 | 新高股8只，新高成交749.2400000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI手机 | 10 |
| 端侧AI | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中兴通讯 | 000063 | AI手机 | 整机品牌/AI入口/豆包生态合作方 | core | L2_curated_research | 10 |
| 中石科技 | 300684 | AI手机 | VC均热板/散热材料 | related | L2_curated_research | 10 |
| 传音控股 | 688036 | AI手机 | 新兴市场整机品牌 | related | L2_curated_research | 10 |
| 佰维存储 | 688525 | AI手机 | 存储模组/LPDDR升级 | related | L2_curated_research | 10 |
| 兆易创新 | 603986 | AI手机 | 存储芯片/DRAM周期弹性 | related | L2_curated_research | 10 |
| 光大同创 | - | AI手机 | 间接合作传闻线索 | peripheral | L1_exposure | 10 |
| 思泉新材 | 301489 | AI手机 | AIDC液冷散热系统、AI终端散热材料、机器人散热 | related | L1_L3_candidate | 10 |
| 昀冢科技 | 688260 | AI手机 | CMI组件传闻线索 | peripheral | L1_exposure | 10 |
