# 2026-08-19 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：25108.68
- **上涨家数**：449
- **涨停 / 跌停**：37 / 144
- **容量前三行业**：1.电子(30.4%, super_capacity)、2.通信(8.0%, normal)、3.机械设备(7.3%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 粮食概念 | 粮食概念 | - | 140.59 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 2 | 种植业 | 种植业 | - | 135.2 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 5 | 1 | - |
| 3 | 连板未映射 | - | 国防军工 | 117.0 | limit_advance_cluster | 0 | 0 | 0 | placeholder_market_theme |
| 4 | 化工 | 化工 | - | 101.94 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 5 | 航运 | 航运 | - | 90.8 | multi_period_rank、new_high_cluster | 4 | 12 | 2 | - |
| 6 | 机器人 | 机器人 | 电力设备 | 88.8 | limit_advance_cluster、multi_period_rank | 5 | 12 | 2 | - |
| 7 | 石油 | 石油 | - | 84.0 | multi_period_rank、new_high_cluster | 4 | 12 | 1 | - |
| 8 | 煤炭 | 煤炭 | - | 82.6 | limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 9 | 涤纶 | 涤纶 | - | 82.0 | multi_period_rank、new_high_cluster | 4 | 12 | 1 | - |
| 10 | 石油开采 | 石油 | - | 80.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 存储芯片 | 存储芯片 | 电子 | 79.02 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 12 | 人形机器人 | 人形机器人 | 机械设备 | 78.44 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 13 | 新能源车 | 新能源车 | - | 77.38 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 电子 | EDA（电子设计自动化） | - | 76.81 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 15 | 数据中心 | 数据中心 | 计算机 | 75.8 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | 半导体 | 半导体 | 电子 | 75.75 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 17 | 乡村振兴 | 乡村振兴 | - | 74.76 | limit_heat、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 18 | 氢能源 | 氢能源 | 电力设备 | 74.22 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 19 | 先进封装 | 先进封装 | 电子 | 73.95 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 20 | 商业航天 | 商业航天 | 国防军工 | 73.92 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 21 | 国防军工 | 国防军工 | - | 73.67 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 22 | 农林牧渔 | 农林牧渔 | - | 73.51 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 23 | 新零售 | 零售 | - | 73.44 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 24 | 电力设备 | 电力设备 | - | 73.42 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 25 | 医药医疗 | 医疗 | - | 73.24 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 26 | 医药 | 医药 | - | 73.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 机械设备 | 机械设备 | - | 73.06 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 28 | 无人机 | 无人机 | - | 71.11 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 29 | 风电 | 风电 | 电力设备 | 70.73 | new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 30 | 卫星导航 | 卫星导航 | - | 70.57 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 第三代半导体 | 第三代半导体 | - | 70.3 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 32 | 一带一路 | 一带一路 | - | 69.99 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 33 | 锂电池概念 | 锂 | - | 69.48 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 34 | 工业互联 | 工业互联网 | - | 69.44 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 35 | 绿色电力 | 绿色电力 | - | 69.39 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 36 | 小米概念 | 小米概念 | - | 69.16 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 东数西算 | 东数西算 | - | 69.08 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 38 | 物联网 | 物联网 | - | 68.85 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 39 | 化工原料 | 化工 | - | 68.6 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 40 | 军民融合 | 军民融合 | - | 68.55 | new_high_direction、new_high_cluster | 1 | 3 | 1 | - |
| 41 | 充电桩 | 充电桩 | - | 68.38 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 42 | 高端装备 | 高端装备 | - | 68.19 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 43 | 核电核能 | 核电 | - | 68.0 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 44 | 碳中和 | 碳中和 | - | 67.92 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 45 | 水利建设 | 水利 | - | 67.69 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 46 | 光刻机 | 光刻机 | 电子 | 67.28 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 2 | - |
| 47 | MCU芯片 | MCU芯片 | 电子 | 65.73 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 1 | - |
| 48 | 大飞机 | 大飞机 | 国防军工 | 65.65 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 49 | 智能电网 | 智能电网 | - | 65.2 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 50 | 6G概念 | 6G | - | 65.18 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：粮食概念

- **标准概念**：粮食概念
- **申万一级**：-
- **评分**：140.59
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.99 | 新高股22只，新高成交158.90000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅8.35% |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅6.37% |
| multi_period_rank | 20.8 | day10排名第5，区间涨幅9.88% |
| limit_heat | 5.4 | 涨停4只，市场占比10.81，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 2：种植业

- **标准概念**：种植业
- **申万一级**：-
- **评分**：135.2
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（5），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 38.0 | 新高股13只，新高成交144.31亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅13.59% |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅10.82% |
| multi_period_rank | 23.2 | day10排名第2，区间涨幅12.51% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 种植业 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 雪榕生物 | 300511 | 种植业 | 工厂化食用菌种植企业（设施农业），农业产业化国家重点龙头企业 | core | L2 | 20 |
| 登海种业 | 002041 | 种植业 | 玉米种子业务（特别是转基因玉米种子） | related | L1_L3_candidate | 20 |
| 荃银高科 | 300087 | 种植业 | 种子业务（水稻、玉米、小麦等） | related | L1_L3_candidate | 20 |
| 浙农股份 | 002758 | 种植业 | 农场运营与土地托管服务方（流转类运营约8万亩、托管类运营约2万亩，「万亩... | peripheral | L2 | 20 |
| 苏垦农发 | 601952 | 粮食安全 | 大型国有农业平台，稻麦种植及粮油加工一体化 | related | L2 | 1 |

## 候选 3：连板未映射

- **标准概念**：-
- **申万一级**：国防军工
- **评分**：117.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 117.0 | 连板股5只，最高3板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 4：化工

- **标准概念**：化工
- **申万一级**：-
- **评分**：101.94
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.89 | 新高股58只，新高成交310.8000000000001亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比8.11，排名22 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 化工 | 20 |
| C4化工 | 5 |
| 中国化工全球份额提升 | 5 |
| 化工出海 | 5 |
| 化工周期 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万华化学 | 600309 | 中国化工全球份额提升 | 化工龙头与全球份额提升受益企业 | peripheral | graph_only | 20 |
| 鲁西化工 | 000830 | 中国化工全球份额提升 | 化工龙头与全球份额提升受益企业 | peripheral | graph_only | 20 |
| 宇新股份 | 002986 | 化工 | 以LPG为原料的深加工有机化工产品生产商（化工行业收入占比99.99%） | core | L2 | 20 |
| 正丹股份 | 300641 | 化工 | 石油化工行业酸酐及酯类产品生产商（酸酐及酯类设计产能18.5万吨/年、在... | core | L2 | 20 |
| 皖维高新 | 600063 | 化工 | 聚乙烯醇（PVA）行业龙头 | core | L2 | 20 |
| 长华化学 | 301518 | 化工 | 国内聚醚多元醇行业头部企业（POP/软泡用PPG/CASE用聚醚及特种聚... | core | L2 | 20 |
| 东岳硅材 | 300821 | 化工 | 基础化工材料企业 | core | L1 | 20 |
| 中欣氟材 | 002915 | 化工 | 基础化工企业 | core | L1 | 20 |

## 候选 5：航运

- **标准概念**：航运
- **申万一级**：-
- **评分**：90.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅6.75% |
| multi_period_rank | 22.4 | day5排名第3，区间涨幅6.11% |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅1.63% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 航运 | 20 |
| 全球航运 | 5 |
| 化学品航运 | 5 |
| 港口航运 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国动力 | 600482 | 全球航运 | 上游设备 | peripheral | graph_only | 20 |
| 中国海防 | 600764 | 全球航运 | 图谱弱关联 | peripheral | graph_only | 20 |
| 中国船舶 | 600150 | 全球航运 | 上游设备 | peripheral | graph_only | 20 |
| 中船科技 | 600072 | 全球航运 | 图谱弱关联 | peripheral | graph_only | 20 |
| 中船防务 | 600685 | 全球航运 | 图谱弱关联 | peripheral | graph_only | 20 |
| 中集集团 | 000039 | 全球航运 | 上游设备 | peripheral | graph_only | 20 |
| 亚星锚链 | 601890 | 全球航运 | 中游制造 | peripheral | graph_only | 20 |
| 振华重工 | 600320 | 全球航运 | 上游设备 | peripheral | graph_only | 20 |

## 候选 6：机器人

- **标准概念**：机器人
- **申万一级**：电力设备
- **评分**：88.8
- **触发类型**：limit_advance_cluster、multi_period_rank
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅10.28% |
| multi_period_rank | 21.6 | day3排名第4，区间涨幅6.69% |
| multi_period_rank | 21.6 | day5排名第4，区间涨幅5.93% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 机器人 | 20 |
| AI机器人 | 5 |
| 人形机器人 | 5 |
| 人形机器人丝杠 | 5 |
| 割草机器人 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 德赛西威 | 002920 | AI机器人 | 智能座舱、智能驾驶、网联服务 | core | L1_L3_candidate | 20 |
| 泽宇智能 | 301179 | AI机器人 | AI机器人 | core | L1_L3_candidate | 20 |
| 移远通信 | 603236 | AI机器人 | 蜂窝模组、车载模组、AI模组 | related | L1_L3_candidate | 20 |
| 宜通世纪 | 300310 | AI机器人 | 通信网络工程服务、通信网络维护服务、通信网络优化服务 | related | L2 | 20 |
| 富奥股份 | 000030 | AI机器人 | - | related | L1 | 20 |
| 三瑞智能 | 301696 | 人形机器人 | CubeMars品牌深耕机器人关节：机器人电机、驱动板、高度集成动力模组 | core | L2 | 20 |
| 东阳光 | 600673 | 人形机器人 | 具身智能（人形机器人） | core | L1_L3_candidate | 20 |
| 中控技术 | 688777 | 人形机器人 | TPT工业大模型、DCS、SIS控制系统、UCS通用控制系统 | core | L1_L3_candidate | 20 |

## 候选 7：石油

- **标准概念**：石油
- **申万一级**：-
- **评分**：84.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| multi_period_rank | 22.4 | daily排名第3，区间涨幅2.08% |
| multi_period_rank | 20.0 | day5排名第6，区间涨幅4.04% |
| multi_period_rank | 17.6 | day3排名第9，区间涨幅4.63% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 石油 | 20 |
| 石油工程 | 5 |
| 石油机械 | 5 |
| 石油钻头 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中信海直 | 000099 | 石油 | 海上石油服务 | related | L1_L3_candidate | 20 |
| 中国海油 | 600938 | 石油 | 上游油气资源开发运营商 | related | L2 | 20 |
| 广汇能源 | 600256 | 石油 | 石油勘探开发 | related | L1_L3_candidate | 20 |
| 开滦股份 | 600997 | 石油 | 煤炭业务（炼焦煤）、焦化业务、煤化工业务 | related | L1_L3_candidate | 20 |
| 德石股份 | 301158 | 石油 | 石油钻井专用工具及设备的研发 | related | L2 | 20 |
| 洲际油气 | 600759 | 石油 | 境外原油生产销售商（2025年原油产量64.89万吨、销量63.84万吨... | related | L2 | 20 |
| 荣盛石化 | 002493 | 石油 | 硫磺副产物、PX、PTA聚酯产业链 | related | L1_L3_candidate | 20 |
| 齐翔腾达 | 002408 | 石油 | 碳四深加工（甲乙酮、顺酐等）、碳三深加工（丙烯 | related | L1_L3_candidate | 20 |

## 候选 8：煤炭

- **标准概念**：煤炭
- **申万一级**：-
- **评分**：82.6
- **触发类型**：limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 17.6 | day10排名第9，区间涨幅7.94% |
| multi_period_rank | 16.8 | daily排名第10，区间涨幅0.77% |
| multi_period_rank | 16.8 | day5排名第10，区间涨幅2.97% |
| limit_heat | 5.4 | 涨停4只，市场占比10.81，排名6 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 煤炭 | 20 |
| 煤炭机械 | 5 |
| 煤炭物流 | 5 |
| 煤炭贸易 | 5 |
| 煤炭运输 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 伊泰B股 | 900948 | 煤炭 | 动力煤生产运输销售一体化大型能源企业（10座煤矿+3条自营铁路） | core | L2 | 20 |
| 山煤国际 | 600546 | 煤炭 | 山西煤炭生产与贸易一体化企业（山西焦煤集团旗下） | core | L2 | 20 |
| 山西焦煤 | 000983 | 煤炭 | 炼焦煤龙头煤炭生产商（原煤产量4687万吨、商品煤销量2672万吨） | core | L2 | 20 |
| 平煤股份 | 601666 | 煤炭 | 特大型煤炭基地的煤炭开采洗选销售企业 | core | L2 | 20 |
| 恒源煤电 | 600971 | 煤炭 | 煤炭（动力煤、焦煤）、电力（钱营孜电厂）、煤化工 | core | L1_L3_candidate | 20 |
| 新大洲A | 000571 | 煤炭 | 煤炭采选为绝对主业（2025年收入占比94.71%），收入随煤价大幅下滑 | core | L2 | 20 |
| 昊华能源 | 601101 | 煤炭 | 动力煤生产销售、甲醇（煤化工）、铁路运输、煤炭物流 | core | L1_L3_candidate | 20 |
| 永泰能源 | 600157 | 煤炭 | 千万吨级煤炭生产商（煤炭资源量50.31亿吨，海则滩化工煤/动力煤矿20... | core | L2 | 20 |

## 候选 9：涤纶

- **标准概念**：涤纶
- **申万一级**：-
- **评分**：82.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 24.0 | daily排名第1，区间涨幅3.09% |
| multi_period_rank | 20.8 | day3排名第5，区间涨幅5.97% |
| multi_period_rank | 19.2 | day5排名第7，区间涨幅3.65% |
| new_high_cluster | 18.0 | 题材内新高股3只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 涤纶 | 20 |
| 再生涤纶 | 5 |
| 涤纶短纤 | 5 |
| 涤纶长丝 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 优彩资源 | 002998 | 再生涤纶 | 再生涤纶纤维厂商（低熔点纤维+再生有色涤纶短纤，设计产能15.2万吨） | core | L2 | 20 |
| 尤夫股份 | 002427 | 涤纶 | 涤纶工业丝生产商（设计产能30万吨、全球行业前列，熔体直纺差别化工业丝，... | core | L2 | 20 |
| 新凤鸣 | 603225 | 涤纶 | 涤纶长丝、涤纶短纤 | related | L1_L3_candidate | 20 |
| 桐昆股份 | 601233 | 涤纶 | 涤纶长丝制造与销售 | related | L1_L3_candidate | 20 |
| 天富龙 | 603406 | 涤纶 | 聚酯材料相关产品供应商 | related | L2 | 20 |
| 三房巷 | 600370 | 涤纶 | 涤纶化纤产业链相关 | peripheral | graph_only | 20 |
| 东方盛虹 | 000301 | 涤纶长丝 | 聚酯链/PX-PTA-涤纶长丝相关标的 | peripheral | graph_only | 20 |
| 恒力石化 | 600346 | 涤纶长丝 | 涤纶长丝相关标的 | peripheral | graph_only | 20 |

## 候选 10：石油开采

- **标准概念**：石油
- **申万一级**：-
- **评分**：80.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 21.6 | daily排名第4，区间涨幅2.06% |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅4.53% |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅4.79% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 石油 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中信海直 | 000099 | 石油 | 海上石油服务 | related | L1_L3_candidate | 20 |
| 中国海油 | 600938 | 石油 | 上游油气资源开发运营商 | related | L2 | 20 |
| 广汇能源 | 600256 | 石油 | 石油勘探开发 | related | L1_L3_candidate | 20 |
| 开滦股份 | 600997 | 石油 | 煤炭业务（炼焦煤）、焦化业务、煤化工业务 | related | L1_L3_candidate | 20 |
| 德石股份 | 301158 | 石油 | 石油钻井专用工具及设备的研发 | related | L2 | 20 |
| 洲际油气 | 600759 | 石油 | 境外原油生产销售商（2025年原油产量64.89万吨、销量63.84万吨... | related | L2 | 20 |
| 荣盛石化 | 002493 | 石油 | 硫磺副产物、PX、PTA聚酯产业链 | related | L1_L3_candidate | 20 |
| 齐翔腾达 | 002408 | 石油 | 碳四深加工（甲乙酮、顺酐等）、碳三深加工（丙烯 | related | L1_L3_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-875c3fe405eaf248da22 artifact_sha=19e870095ad829de8585c71fe7e9cb9642926bcf97b23faa2035a1da7743303b manifest_sha=cf323b676da5a252537f783fcbeca630450dd7a42e115e1c1a8b529ec6b55783 -->
