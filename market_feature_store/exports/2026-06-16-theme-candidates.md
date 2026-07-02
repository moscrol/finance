# 2026-06-16 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：30645.34
- **上涨家数**：2730
- **涨停 / 跌停**：117 / 7
- **容量前三行业**：1.电子(29.5%, super_capacity)、2.电力设备(9.9%, normal)、3.通信(8.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | MLCC | MLCC | 电子 | 272.18 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 2 | 元件 | 电子元件 | 电子 | 199.75 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 先进封装 | 先进封装 | 电子 | 195.82 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 4 | PCB | PCB | 电子 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 5 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 燃料电池 | 燃料电池 | 电力设备 | 187.98 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 商业航天 | 商业航天 | 国防军工 | 184.3 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 8 | 高压快充 | 超充 | 电力设备 | 178.97 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 5 | 0 | missing_evidence |
| 9 | 钠离子电池 | 储能 | 电力设备 | 176.34 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 10 | 消费电子 | 消费电子 | 电子 | 175.44 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 超级电容 | 超级电容 | 电力设备 | 174.86 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 电池 | 4C电池 | 电力设备 | 174.13 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 13 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 174.07 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 14 | 小金属 | 小金属 | 有色金属 | 174.0 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 15 | TOPCON电池 | TOPCon电池 | 电力设备 | 169.83 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 7 | 0 | missing_evidence |
| 16 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 168.75 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 5 | 0 | missing_concept、missing_evidence |
| 17 | 3D打印 | 3D打印 | 机械设备 | 164.51 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 毫米波雷达 | 毫米波雷达 | 汽车 | 163.93 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 锂电池 | 锂电池 | 电力设备 | 163.71 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 20 | AI手机 | AI手机 | 电子 | 162.4 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 4 | - |
| 21 | 新型工业化 | 新型工业化 | 机械设备 | 161.58 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 22 | 机器视觉 | 机器视觉 | 机械设备 | 160.3 | double_red、new_high_direction、new_high_cluster | 0 | 7 | 0 | missing_concept、missing_evidence |
| 23 | 氟化工 | 氟化工 | 基础化工 | 158.15 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 储能 | 储能 | 电力设备 | 142.6 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 超导 | 超导 | 国防军工 | 140.46 | double_red、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 26 | 固态电池 | 固态电池 | 电力设备 | 135.25 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 4 | - |
| 27 | BC电池 | BC电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 5 | 1 | - |
| 28 | 华为手机 | 华为手机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 29 | 低空经济 | 低空经济 | 国防军工 | 124.55 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 30 | HJT电池 | HJT电池 | 电力设备 | 124.0 | double_red、capacity_industry、new_high_cluster | 5 | 2 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 英伟达 | 英伟达GB200 | 电子 | 124.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 32 | 电池化学品 | 电池化学品 | 电力设备 | 120.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 33 | 铜箔 | 铜箔 | 电力设备 | 119.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 3 | - |
| 34 | 光伏设备 | 光伏设备 | 电力设备 | 118.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 35 | 飞行汽车(eVTOL) | 飞行汽车 | 汽车 | 116.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 36 | 电子布 | 电子布 | 电力设备 | 115.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 | - |
| 37 | 算力租赁 | 算力租赁 | 计算机 | 115.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 4 | - |
| 38 | 半导体 | 半导体 | 计算机 | 112.2 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 39 | CCL | CCL | 电子 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 | - |
| 40 | 光通信 | 光通信 | 电力设备 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 4 | - |
| 41 | 液冷 | 液冷 | 电子 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 1 | - |
| 42 | 电容器 | MLCC材料 | 电力设备 | 107.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 43 | 太赫兹 | 6G产业 | 国防军工 | 106.0 | double_red、new_high_cluster | 1 | 4 | 0 | missing_evidence |
| 44 | 共封装光学(CPO) | CPO | 电子 | 100.8 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 45 | 数据中心 | 数据中心 | 计算机 | 98.15 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 风电 | 风电 | 电力设备 | 96.2 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 47 | 存储芯片 | 存储芯片 | 电子 | 94.9 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 48 | 可控核聚变 | 可控核聚变 | 电力设备 | 89.09 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 49 | AI眼镜 | AI眼镜 | 电子 | 88.84 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 50 | 液冷服务器 | 液冷服务器 | 电力设备 | 88.24 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：MLCC

- **标准概念**：MLCC
- **申万一级**：电子
- **评分**：272.18
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.87%，边际量 23.98%，成交额 1079.22 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.87%，边际量23.98%，成交1079.22亿 |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_direction | 57.18 | 新高股17只，新高成交574.13亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MLCC | 10 |
| MLCC微型化 | 5 |
| MLCC材料 | 5 |
| MLCC镍粉 | 5 |
| Rubin MLCC | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | Rubin MLCC | 高端MLCC制造 / 垂直一体化 | core | L1_image_extraction | 20 |
| 利和兴 | 301013 | Rubin MLCC | 107高容算力MLCC落地标的 | related | L1_image_extraction | 20 |
| 博迁新材 | 605376 | Rubin MLCC | 纳米镍粉 / 内电极材料 | core | L1_image_extraction | 20 |
| 国瓷材料 | 300285 | Rubin MLCC | 上游陶瓷粉体龙头 | core | L1_image_extraction | 20 |
| 昀冢科技 | 688260 | Rubin MLCC | 高容MLCC扩产观察 / 非Rubin直接验证 | peripheral | L1_image_extraction_with_L3_official_conflict | 20 |
| 风华高科 | 000636 | Rubin MLCC | MLCC制造龙头 / AI服务器供应链 | core | L1_image_extraction | 20 |
| 中电港 | 001287 | MLCC | MLCC 产业链（国联民生推荐） | related | L3 | 10 |
| 中金岭南 | 000060 | MLCC | MLCC电极粉体（中金科技） | related | L1_L3_candidate | 10 |

## 候选 2：元件

- **标准概念**：电子元件
- **申万一级**：电子
- **评分**：199.75
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.84%，边际量 22.25%，成交额 2026.29 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.84%，边际量22.25%，成交2026.29亿 |
| new_high_direction | 66.6 | 新高股22只，新高成交1328.29亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.15 | 涨停9只，市场占比7.69，排名20 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元件 | 5 |
| 磁性元件 | 5 |
| 被动元件 | 5 |
| 1.6T CPO | 2 |
| AI眼镜 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | 电子元件 | 电子元件和基础材料生产商 | core | L1 | 10 |
| 博迁新材 | 605376 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 国瓷材料 | 300285 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 洁美科技 | 002859 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 深圳华强 | 000062 | 电子元件 | 半导体授权分销/边缘AI计算系统 | peripheral | L1_L3_candidate | 10 |
| 铜冠铜箔 | 301217 | 电子元件 | 市场信号弱关联 | related | L2_candidate | 10 |
| 风华高科 | 000636 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 鸿远电子 | 603267 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 3：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：195.82
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.15%，边际量 10.97%，成交额 4159.17 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.15%，边际量10.97%，成交4159.17亿 |
| new_high_direction | 62.32 | 新高股38只，新高成交985.52亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.5 | 涨停10只，市场占比8.55，排名14 |

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
| 三安光电 | 600703 | 先进封装 | 光芯片（AI算力光互联）、碳化硅（SiC功率器件）、Mini | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 先进封装 | 投资潜在相关（非直接产业链） | peripheral | L2_candidate | 10 |
| 上海新阳 | 300236 | 先进封装 | 集成电路制造及先进封装用关键工艺材料（电镀液 | related | L1_L3_candidate | 10 |
| 东威科技 | 688700 | 先进封装 | 半导体封装电镀设备 | related | L1_L3_candidate | 10 |
| 中京电子 | 002579 | 先进封装 | - | - | - | 10 |
| 中国巨石 | 600176 | 先进封装 | 先进封装上游高端电子布潜在相关 | peripheral | L2_candidate | 10 |
| 中微公司 | 688012 | 先进封装 | 封装设备 | related | L2_candidate | 10 |
| 中材科技 | 002080 | 先进封装 | Low-CTE电子布供应商，AI先进封装关键材料 | peripheral | L1 | 10 |

## 候选 4：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：194.0
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.97%，边际量 15.68%，成交额 4373.99 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.97%，边际量15.68%，成交4373.99亿 |
| new_high_direction | 68.0 | 新高股70只，新高成交2520.050000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 10 |
| AI PCB | 5 |
| AIPCB专用油墨 | 5 |
| PCB印制电路板 | 5 |
| PCB微钻 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东威科技 | 688700 | AI PCB | PCB精密电镀设备（核心） | related | L1_L3_candidate | 20 |
| 东山精密 | 002384 | AI PCB | 光模块（含光芯片，索尔思光电）、AI PCB（高多层硬板/RPCB）、F... | core | L1_L3_candidate | 20 |
| 中京电子 | 002579 | AI PCB | - | - | - | 20 |
| 中富电路 | 300814 | AI PCB | AI服务器三次电源PCB、二次电源PCB（HVDC）、埋感埋容嵌入式PC... | related | L1_L3_candidate | 20 |
| 中钨高新 | 000657 | AI PCB | PCB微钻、铣刀（金洲公司，AI+光模块耗材） | related | L1_L3_candidate | 20 |
| 南亚新材 | 688519 | AI PCB | 高频高速CCL国产替代和涨价弹性标的 | related | - | 20 |
| 嘉元科技 | 688388 | AI PCB | 高端电子电路铜箔（PCB铜箔/HVLP/RTF） | related | L1_L3_candidate | 20 |
| 大族数控 | 301200 | AI PCB | PCB钻孔设备核心受益标的 | core | - | 20 |

## 候选 5：光纤

- **标准概念**：AI算力驱动下的MPO光纤连接器产业
- **申万一级**：通信
- **评分**：194.0
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.86%，边际量 16.32%，成交额 3623.89 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.86%，边际量16.32%，成交3623.89亿 |
| new_high_direction | 68.0 | 新高股25只，新高成交1554.1099999999997亿，容量前三=True |
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
| 太辰光 | 300570 | AI算力驱动下的MPO光纤连接器产业 | 3.2.1 太辰光（300570） | peripheral | graph_only | 10 |
| 长芯博创 | 300548 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 通光线缆 | 300265 | G.654.E光纤 | 光纤光缆（含OPGW、ADSS电力光缆、G.654.E高端光纤）、输电线... | related | L1_L3_candidate | 10 |
| 华丰科技 | 688629 | MPO光纤连接器 | 高速线模组、高速背板连接器、NPO连接器 | related | L1_L3_candidate | 10 |
| 唯科科技 | 301196 | MPO光纤连接器 | MPO光通信零部件、机器人轻量化部件、新能源汽车零部件、精密注塑模具 | related | L1_L3_candidate | 10 |

## 候选 6：燃料电池

- **标准概念**：燃料电池
- **申万一级**：电力设备
- **评分**：187.98
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.65%，边际量 12.8%，成交额 1597.4 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.65%，边际量12.8%，成交1597.4亿 |
| new_high_direction | 55.53 | 新高股19只，新高成交442.22亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 6.45 | 涨停7只，市场占比5.98，排名31 |

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

## 候选 7：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：184.3
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.55%，边际量 13.29%，成交额 5526.93 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.55%，边际量13.29%，成交5526.93亿 |
| new_high_direction | 58.0 | 新高股43只，新高成交1859.3600000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 10.3 | 涨停18只，市场占比15.38，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| AI基础设施与国产算力 | 2 |
| AI算力基础设施 | 2 |
| 低轨卫星星座 | 2 |
| 光伏 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 受益标的 | core | L3 | 10 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 10 |
| 上海瀚讯 | 300762 | 商业航天 | 卫星通信载荷、地面信关站、用户终端 | core | L1_L3_candidate | 10 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 10 |
| 中国卫通 | 601698 | 商业航天 | 应用端 | core | L2 | 10 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 商业航天 | 商业航天高性能碳纤维本土供应商，推进卫星端验证 | related | L1_L3_candidate | 10 |
| 中海油服 | 601808 | 商业航天 | 钻井服务、油田技术服务、船舶服务 | related | L1_L3_candidate | 10 |

## 候选 8：高压快充

- **标准概念**：超充
- **申万一级**：电力设备
- **评分**：178.97
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.64%，边际量 15.93%，成交额 1215.99 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（5），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.64%，边际量15.93%，成交1215.99亿 |
| new_high_direction | 46.52 | 新高股9只，新高成交473.65999999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 6.45 | 涨停7只，市场占比5.98，排名32 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 超充 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 真视通 | 002771 | AIDC发电设备 | AIDC液冷算力、新能源充电桩、多媒体视讯 | related | L2 | 1 |
| 铜峰电子 | 600237 | 储能系统 | 电子级BOPP薄膜、金属化膜、薄膜电容器 | related | L1_L3_candidate | 1 |
| 银河电子 | 002519 | 充电桩 | 充电桩） | related | L2 | 1 |
| 比亚迪 | 002594 | 新能源车 | 乘用车、商用车、动力电池 | related | L1_L3_candidate | 1 |
| 盛弘股份 | 300693 | 超充 | 产业链供应商 | peripheral | L1 | 1 |

## 候选 9：钠离子电池

- **标准概念**：储能
- **申万一级**：电力设备
- **评分**：176.34
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.64%，边际量 20.01%，成交额 1642.32 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（10），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.64%，边际量20.01%，成交1642.32亿 |
| new_high_direction | 50.34 | 新高股13只，新高成交331.23亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 储能 | 2 |
| 储能电池 | 2 |
| 动力电池 | 2 |
| 固态电池 | 2 |
| 电解液 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科电气 | 300035 | 钠离子电池 | 钠电硬碳负极及电极活性材料潜在研发布局商 | related | L1 | 10 |
| 亿纬锂能 | 300014 | 钠离子电池 | 中游制造/电池 | related | L3_candidate | 10 |
| 传艺科技 | 002866 | 钠离子电池 | 钠离子电池电芯、正负极材料及储能/动力电池系统集成全流程生产商 | related | L1 | 10 |
| 华阳股份 | 600348 | 钠离子电池 | 钠离子电池一体化（正极/负极/电芯及PACK）国内最先量产释放的战略布局... | related | L1 | 10 |
| 振华新材 | 688707 | 钠离子电池 | 钠离子电池相关产品/材料供应商 | related | L2 | 10 |
| 宁德时代 | 300750 | 储能电池 | 储能电池 | related | L1_L3_candidate | 1 |
| 普利特 | 002324 | 化工 | 通用材料类相关产品供应商 | related | L2 | 1 |
| 同兴科技 | 300490 | 环保 | 环保相关产品/材料供应商 | related | L2 | 1 |

## 候选 10：消费电子

- **标准概念**：消费电子
- **申万一级**：电子
- **评分**：175.44
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.65%，边际量 12.26%，成交额 1034.23 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.65%，边际量12.26%，成交1034.23亿 |
| new_high_direction | 49.44 | 新高股13只，新高成交259.0亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费电子 | 10 |
| 消费电子设备 | 5 |
| 3C制造 | 2 |
| 3D打印钛合金 | 2 |
| 8.6代OLED产线 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三利谱 | 002876 | 消费电子 | 显示面板材料间接相关 | peripheral | L1 | 10 |
| 东山精密 | 002384 | 消费电子 | FPC/PCB精密制造 | related | L1 | 10 |
| 东睦股份 | 600114 | 消费电子 | 消费电子MIM结构件供应商 | related | L1 | 10 |
| 中石科技 | 300684 | 消费电子 | 消费电子高导热材料供应商 | core | L1 | 10 |
| 中科蓝讯 | 688332 | 消费电子 | 蓝牙耳机及音箱音频SoC芯片供应商 | core | L1 | 10 |
| 乐凯胶片 | 600135 | 消费电子 | 偏光片/显示薄膜及锂电外包装铝塑膜供应商 | related | L1 | 10 |
| 乐鑫科技 | 688018 | 消费电子 | 消费级及智能家居IoT芯片供应商 | core | L1 | 10 |
| 乾照光电 | 300102 | 消费电子 | 图谱弱关联 | peripheral | graph_only | 10 |
