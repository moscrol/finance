# 2026-07-22 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：26531.66
- **上涨家数**：1530
- **涨停 / 跌停**：47 / 8
- **容量前三行业**：1.电子(33.0%, super_capacity)、2.通信(9.0%, normal)、3.计算机(6.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 电力 | 电力 | 电力设备 | 287.93 | limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | 算力租赁 | 算力租赁 | 计算机 | 205.67 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 3 | 贵金属 | 贵金属 | 有色金属 | 184.35 | limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 黄金 | 黄金 | 有色金属 | 179.13 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 5 | 金属铅 | 金属铅 | 有色金属 | 168.7 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 6 | 金属锌 | 有色金属 | 有色金属 | 166.73 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 7 | 半导体 | 半导体 | 电子 | 165.56 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 8 | 金属铜 | 铜 | 有色金属 | 150.54 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 9 | 工业金属 | 锻件 | 有色金属 | 148.6 | double_red、new_high_direction、new_high_cluster | 2 | 9 | 0 | missing_evidence |
| 10 | 油气开采及服务 | 油气 | - | 138.8 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 137.7 | double_red、new_high_direction、new_high_cluster | 5 | 9 | 2 | - |
| 12 | 煤炭开采加工 | 煤炭 | - | 131.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 13 | 金属钴 | 金属钴 | 有色金属 | 106.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 14 | 保险 | 低空经济 | - | 105.6 | multi_period_rank | 5 | 7 | 0 | missing_evidence |
| 15 | 白酒 | 白酒 | - | 97.6 | multi_period_rank | 2 | 12 | 2 | - |
| 16 | 黄金概念 | 黄金 | - | 95.05 | double_red、limit_heat | 1 | 12 | 0 | missing_evidence |
| 17 | 数据中心 | 数据中心 | 计算机 | 94.05 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 18 | 半导体封测 | 半导体封测 | - | 90.0 | double_red | 5 | 12 | 0 | missing_evidence |
| 19 | 国资云 | 国资云 | - | 90.0 | double_red | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 20 | 有色 | 有色冶炼装备 | - | 90.0 | double_red | 5 | 12 | 0 | missing_evidence |
| 21 | 钴金属 | 钴金属 | - | 90.0 | double_red | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 22 | 镍金属 | 镍金属 | - | 90.0 | double_red | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 23 | 云计算 | 云计算 | 计算机 | 88.87 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 3 | - |
| 24 | 信创 | 信创 | 计算机 | 86.82 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 25 | 数据要素 | 数据要素 | 计算机 | 86.12 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 26 | 数字货币 | 数字货币 | 计算机 | 79.46 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 3 | 1 | - |
| 27 | 风电 | 风电 | 电力设备 | 76.47 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 28 | IT服务 | IT服务 | 计算机 | 73.6 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 29 | 软件开发 | 软件 | 计算机 | 67.85 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 30 | 无人驾驶 | 无人驾驶 | 汽车 | 67.53 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 英伟达 | 英伟达 | 电子 | 67.08 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 32 | AIGC | AIGC | 传媒 | 66.69 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 创新药 | 创新药 | 医药生物 | 66.65 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 34 | 液冷服务器 | 液冷服务器 | 电力设备 | 65.67 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 35 | 共封装光学(CPO) | CPO | 电子 | 63.99 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 36 | 小金属 | 小金属 | 有色金属 | 63.64 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 37 | 海峡两岸 | 海峡两岸 | 综合 | 63.47 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 38 | AI眼镜 | AI眼镜 | 电子 | 61.64 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 39 | 计算机设备 | 计算机设备 | 计算机 | 59.45 | new_high_direction、new_high_cluster、capacity_industry | 1 | 9 | 1 | - |
| 40 | 6G | 6G | 通信 | 58.14 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 41 | 氢能源 | 氢能源 | 电力设备 | 58.04 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 通信设备 | 通信设备 | 通信 | 55.52 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 43 | 商业航天 | 商业航天 | 国防军工 | 54.96 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 44 | 星闪 | 星闪 | 通信 | 54.68 | new_high_direction、new_high_cluster、capacity_industry | 5 | 4 | 0 | missing_evidence |
| 45 | 港口航运 | 港口航运 | - | 48.8 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 毫米波雷达 | 毫米波雷达 | 汽车 | 48.68 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 新型工业化 | 新型工业化 | 机械设备 | 48.04 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 48 | PCB | PCB | 电子 | 47.83 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 49 | 磷化工 | 磷化工 | 基础化工 | 45.09 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 50 | 稀土永磁 | 稀土永磁 | 有色金属 | 44.79 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |

## 五、核心候选明细

## 候选 1：电力

- **标准概念**：电力
- **申万一级**：电力设备
- **评分**：287.93
- **触发类型**：limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 109.0 | 连板股3只，最高5板，容量前三=False |
| new_high_direction | 40.88 | 新高股15只，新高成交150.48000000000002亿，容量前三=False |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅6.03% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅7.4% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | day3排名第5，区间涨幅5.79% |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅2.25% |
| limit_heat | 6.45 | 涨停7只，市场占比14.89，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电力 | 20 |
| 数据中心电力设备 | 5 |
| 新型电力系统 | 5 |
| 新能源电力 | 5 |
| 新能源电力系统与能源技术革命 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中恒电气 | 002364 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 四方股份 | 601126 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 科士达 | 002518 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 金盘科技 | 688676 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 中国西电 | 601179 | 新型电力系统 | 全产业链 | core | - | 20 |
| 中国能建 | 601868 | 新型电力系统 | 算电协同/三电协同 | core | - | 20 |
| 卧龙电驱 | 600580 | 新型电力系统 | 机器人组件及系统应用、数据中心HVAC电机、电动航空电推进系统 | related | L1_L3_candidate | 20 |
| 国电南瑞 | 600406 | 新型电力系统 | 算电协同/三电协同 | core | - | 20 |

## 候选 2：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：205.67
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 119.0 | 连板股3只，最高3板，容量前三=True |
| new_high_direction | 54.92 | 新高股14只，新高成交585.31亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比10.64，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 算力租赁 | 20 |
| 算力 | 12 |
| AI基础设施与国产算力 | 2 |
| AI处理器 | 2 |
| AI服务器电源 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中电港 | 001287 | 算力 | AI处理器/GPU等算力芯片分销与方案服务商 | related | L2 | 20 |
| 中石科技 | 300684 | 算力 | 热管理材料（导热石墨、VC均热板、TIM | related | L1_L3_candidate | 20 |
| 中航重机 | 600765 | 算力 | 航空锻铸、液压环控、永红换热（液冷） | related | L1_L3_candidate | 20 |
| 中远通 | 301516 | 算力 | 服务器电源产品线（ATX/SSI标准，80Plus钛金） | related | L2 | 20 |
| 云天励飞 | 688343 | 算力 | 智算集群与AI训练推理算力服务商 | core | L2 | 20 |
| 信维通信 | 300136 | 算力 | 商业卫星通信器件、AI终端天线及模组、车载射频 | related | L1_L3_candidate | 20 |
| 华策影视 | 300133 | 算力 | 算力租赁 | related | L1_L3_candidate | 20 |
| 协创数据 | 300857 | 算力 | 服务器再制造业务延伸布局云平台领域客户 | related | L2 | 20 |

## 候选 3：贵金属

- **标准概念**：贵金属
- **申万一级**：有色金属
- **评分**：184.35
- **触发类型**：limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅5.7% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅13.42% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅6.51% |
| new_high_direction | 28.75 | 新高股5只，新高成交300.11亿，容量前三=False |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| multi_period_rank | 22.6 | day10排名第9，区间涨幅3.97% |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 贵金属 | 20 |
| 贵金属催化 | 5 |
| 贵金属催化剂 | 5 |
| 贵金属回收 | 5 |
| 小金属 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凯大催化 | 830974 | 贵金属 | 贵金属催化相关产品/材料供应商 | related | L2 | 20 |
| 凯立新材 | 688269 | 贵金属 | 贵金属催化剂相关产品/材料供应商 | related | L2 | 20 |
| 浩通科技 | 301026 | 贵金属 | 贵金属回收相关产品/材料供应商 | related | L2 | 20 |
| 贵研铂业 | 600459 | 贵金属 | 贵金属相关产品/材料供应商 | related | L2 | 20 |
| 中触媒 | 688267 | 催化剂 | 特种分子筛与催化新材料平台（钛硅催化剂开拓己内酰胺/环氧丙烷市场） | core | L2 | 10 |
| 瑞华技术 | 920099 | 催化剂 | 工艺路线和催化剂开发一体化，新型铜基催化剂、烷基化催化剂等研发项目已完成... | core | L2 | 10 |
| 肯特催化 | 603120 | 催化剂 | 季铵（鏻）化合物厂商，在相转移催化剂、分子筛模板剂细分领域具技术领先优势... | core | L2 | 10 |
| 齐鲁华信 | 920832 | 催化剂 | 国内主要的催化剂分子筛供应商：石油化工催化分子筛、环保催化分子筛（汽车尾... | core | L2 | 10 |

## 候选 4：黄金

- **标准概念**：黄金
- **申万一级**：有色金属
- **评分**：179.13
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.86%，边际量 41.78%，成交额 923.13 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.86%，边际量41.78%，成交923.13亿 |
| new_high_direction | 37.93 | 新高股10只，新高成交474.52亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 13.4 | daily排名第8，区间涨幅1.86% |
| multi_period_rank | 11.8 | day3排名第10，区间涨幅3.58% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 黄金 | 20 |
| 黄金珠宝 | 5 |
| EML激光器 | 2 |
| 乳制品 | 2 |
| 儿童用药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中金黄金 | 600489 | 黄金 | 央企黄金龙头（保有金资源量917.35吨） | core | L2 | 20 |
| 华钰矿业 | 601020 | 黄金 | 黄金业务（泥堡金矿 | related | L1_L3_candidate | 20 |
| 宝鼎科技 | 002552 | 黄金 | AI铜箔（HVLP、HTE铜箔）、金矿业务 | core | L1_L3_candidate | 20 |
| 山东黄金 | 600947 | 黄金 | 黄金矿业龙头企业 | core | L2 | 20 |
| 山金国际 | 000975 | 黄金 | 黄金矿采选企业（山东黄金集团旗下，原银泰黄金）：玉龙矿业、黑河银泰等矿山 | core | L2 | 20 |
| 晓程科技 | 300139 | 黄金 | 加纳AKROMA/AKOASE/FGM金矿开采冶炼销售，黄金收入占比82... | core | L2 | 20 |
| 洛阳钼业 | 603993 | 黄金 | 黄金等矿山采掘及加工 | related | L1_L3_candidate | 20 |
| 深中华A | 000017 | 黄金 | 黄金相关产品/材料供应商 | related | L2 | 20 |

## 候选 5：金属铅

- **标准概念**：金属铅
- **申万一级**：有色金属
- **评分**：168.7
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.54%，边际量 40.97%，成交额 545.97 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.54%，边际量40.97%，成交545.97亿 |
| new_high_direction | 27.1 | 新高股4只，新高成交280.33000000000004亿，容量前三=False |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| multi_period_rank | 16.6 | daily排名第4，区间涨幅2.54% |
| multi_period_rank | 15.0 | day3排名第6，区间涨幅5.01% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 6：金属锌

- **标准概念**：有色金属
- **申万一级**：有色金属
- **评分**：166.73
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.43%，边际量 39.61%，成交额 521.15 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.43%，边际量39.61%，成交521.15亿 |
| new_high_direction | 26.73 | 新高股4只，新高成交250.22亿，容量前三=False |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| multi_period_rank | 15.8 | daily排名第5，区间涨幅2.43% |
| multi_period_rank | 14.2 | day3排名第7，区间涨幅4.05% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 有色金属 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 锌业股份 | 000751 | 有色金属 | 锌铜冶炼及深加工企业 | core | L2 | 1 |

## 候选 7：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：165.56
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |
| new_high_direction | 35.51 | 新高股3只，新高成交265.19亿，容量前三=True |
| new_high_cluster | 18.0 | 题材内新高股3只 |
| limit_heat | 5.05 | 涨停3只，市场占比6.38，排名18 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体 | 20 |
| 功率半导体 | 5 |
| 化合物半导体 | 5 |
| 半导体IP | 5 |
| 半导体产业链 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三安光电 | 600703 | 功率半导体 | 碳化硅功率半导体材料/器件相关厂商 | peripheral | L1 | 20 |
| 上海合晶 | 688584 | 功率半导体 | 为功率器件/模拟芯片提供外延片衬底 | related | L2 | 20 |
| 东微半导 | 688261 | 功率半导体 | 受益标的 | core | pricing | 20 |
| 中晶科技 | 003026 | 功率半导体 | 半导体功率芯片及器件制造商（广泛应用于微波炉、激光打印机、X光机、高压电... | core | L2 | 20 |
| 华天科技 | 002185 | 功率半导体 | - | - | - | 20 |
| 华润微 | 688396 | 功率半导体 | 功率半导体相关产品/材料供应商 | related | L2 | 20 |
| 华虹宏力 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 20 |
| 协昌科技 | 301418 | 功率半导体 | 功率芯片（晶圆/封装成品）设计销售并向封测领域延伸 | core | L2 | 20 |

## 候选 8：金属铜

- **标准概念**：铜
- **申万一级**：有色金属
- **评分**：150.54
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.34%，边际量 28.08%，成交额 996.78 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.34%，边际量28.08%，成交996.78亿 |
| new_high_direction | 34.54 | 新高股8只，新高成交427.39000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股8只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 铜 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 铜陵有色金属 | 000630 | 铜 | 铜矿开采、冶炼及铜加工业务 | related | L1_L3_candidate | 11 |
| 三友科技 | 920475 | 铜 | 电解铜生产用阴极板 | related | L2 | 10 |
| 中国有色矿业 | 01258.HK | 铜 | 港股铜矿自给率提升观察标的 | peripheral | L2_candidate | 10 |
| 中矿资源 | 002738 | 铜 | 锂电新能源业务、铜矿业务、铯铷业务 | related | L1_L3_candidate | 10 |
| 中金岭南 | 000060 | 铜 | 阴极铜生产商（铜采选冶延伸） | related | L2 | 10 |
| 中金黄金 | 600489 | 铜 | 矿山铜与钼资源持有者（铜234万吨/钼61万吨） | related | L2 | 10 |
| 云南铜业 | 000878 | 铜 | 铜冶炼反内卷观察标的 | peripheral | L2_candidate | 10 |
| 五矿资源 | 01208.HK | 铜 | 港股铜矿反转观察标的 | peripheral | L2_candidate | 10 |

## 候选 9：工业金属

- **标准概念**：锻件
- **申万一级**：有色金属
- **评分**：148.6
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.12%，边际量 21.56%，成交额 702.41 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.12%，边际量21.56%，成交702.41亿 |
| new_high_direction | 32.6 | 新高股7只，新高成交383.92亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 锻件 | 2 |
| 风电 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 株冶集团 | 600961 | 800G_1.6T光模块 | 铟（高纯铟、磷化铟衬底原料）、贵金属（金 | related | L1_L3_candidate | 1 |
| 海亮股份 | 002203 | AI PCB | AI热管理 | related | L1_L3_candidate | 1 |
| 云铝股份 | 000807 | AI算力 | 电解铝冶炼、铝加工、氧化铝 | related | L1_L3_candidate | 1 |
| 华钰矿业 | 601020 | AI算力 | 锑业务（全球龙头）、黄金业务（泥堡金矿、塔铝金业） | related | L1_L3_candidate | 1 |
| 铜陵有色金属 | 000630 | HVLP铜箔 | 铜矿开采、冶炼及铜加工业务 | related | L1_L3_candidate | 1 |
| 鼎胜新材 | 603876 | 储能系统 | 电池铝箔业务（核心）、空调箔业务、包装铝箔业务 | related | L1_L3_candidate | 1 |
| 中金岭南 | 000060 | 有色金属 | 有色金属矿产品及冶炼深加工商 | core | L2_candidate | 1 |
| 南山铝业 | 600219 | 汽车板 | 高端铝加工（汽车板 | related | L1_L3_candidate | 1 |

## 候选 10：油气开采及服务

- **标准概念**：油气
- **申万一级**：-
- **评分**：138.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅9.88% |
| multi_period_rank | 28.2 | daily排名第2，区间涨幅4.03% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅7.18% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅3.77% |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 油气 | 10 |
| 油气开采 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国海油 | 600938 | 油气 | 海上原油与天然气勘探开发（纯上游E&P） | related | L1_L3_candidate | 20 |
| 中油工程 | 600339 | 油气 | 油气开采地面设施及大型储运炼化工程集成服务商 | peripheral | graph_only | 20 |
| 中海油服 | 601808 | 油气 | 钻井服务、油田技术服务、船舶服务 | related | L1_L3_candidate | 20 |
| 久立特材 | 002318 | 油气 | 油气用高端管材（含海外EBK复合管） | related | L1_L3_candidate | 20 |
| 卫星化学 | 002648 | 油气 | C2乙烷裂解制乙烯、C3丙烷脱氢制丙烯、α-烯烃 | related | L1_L3_candidate | 20 |
| 宁波中百 | 600857 | 油气 | 百货零售、黄金珠宝批发、金融资产投资、资产注入预期（海外油气田） | core | L2 | 20 |
| 广汇能源 | 600256 | 油气 | 煤炭、煤化工、天然气(LNG) | related | L1_L3_candidate | 20 |
| 杰瑞股份 | 002353 | 油气 | 燃气轮机发电机组业务、天然气业务、数据中心一体化业务 | related | L1_L3_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-5a5b6cf73a83744de536 artifact_sha=c140081677b977e29f1bcc0e0dad2c49061ad735a43551b58a4dc5b0d5fd34fa manifest_sha=1905c525a5ed4fddd28df4c8b4dded26c75a9eac6647502dd9c676589a521faa -->
