# 2026-07-23 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：21949.97
- **上涨家数**：4260
- **涨停 / 跌停**：116 / 2
- **容量前三行业**：1.电子(29.1%, super_capacity)、2.电力设备(8.5%, normal)、3.通信(7.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 电网设备 | 电网设备 | 电力设备 | 237.72 | double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 2 | 算力租赁 | 算力租赁 | 计算机 | 165.88 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 3 | 贵金属 | 贵金属 | 有色金属 | 143.8 | limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 电站 | 储能电站 | 电力设备 | 139.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 5 | 油气开采及服务 | 油气 | 石油石化 | 132.99 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 6 | 金属锌 | 有色金属 | 有色金属 | 111.52 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 7 | 电力 | 电力 | 公用事业 | 109.62 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 8 | 煤炭开采加工 | 煤炭 | 煤炭 | 101.98 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 9 | 工业金属 | 锻件 | 有色金属 | 100.75 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 9 | 0 | missing_evidence |
| 10 | 风电 | 风电 | 电力设备 | 95.26 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 特高压 | 特高压 | 电力设备 | 94.3 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 12 | 股权 | 私募股权投资 | 医药生物 | 93.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 13 | 医药 | 医药 | 医药生物 | 89.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 14 | 氢能源 | 氢能源 | 电力设备 | 87.35 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 15 | 数据中心 | 数据中心 | 计算机 | 86.24 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 86.11 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 1 | - |
| 17 | 金属铅 | 金属铅 | 有色金属 | 81.13 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 18 | 金属铜 | 铜 | 有色金属 | 80.62 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 19 | 小金属 | 小金属 | 有色金属 | 72.06 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 20 | 黄金 | 黄金 | 有色金属 | 69.53 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 农化制品 | 农化制品 | 基础化工 | 68.61 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 22 | 液冷服务器 | 液冷服务器 | 电力设备 | 66.63 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 23 | 钒电池 | 钒电池 | 电力设备 | 66.27 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | 海峡两岸 | 海峡两岸 | 综合 | 66.2 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 25 | 数据要素 | 数据要素 | 计算机 | 65.95 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 无人驾驶 | 无人驾驶 | 汽车 | 62.68 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 云计算 | 云计算 | 计算机 | 61.21 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 28 | 人形机器人 | 人形机器人 | 机械设备 | 60.23 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 29 | 信创 | 信创 | 计算机 | 58.74 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 30 | 共封装光学(CPO) | CPO | 电子 | 58.36 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | AIGC | AIGC | 传媒 | 57.01 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 英伟达 | 英伟达 | 电子 | 55.54 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 33 | PCB | PCB | 电子 | 55.19 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 34 | 金属镍 | 金属镍 | 有色金属 | 55.15 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 港口航运 | 港口航运 | - | 54.4 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 6G | 6G | 通信 | 54.22 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 37 | 金属钴 | 金属钴 | 有色金属 | 54.05 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 53.95 | new_high_direction、new_high_cluster | 5 | 9 | 2 | - |
| 39 | IT服务 | IT服务 | 计算机 | 53.54 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 通信设备 | 通信设备 | 通信 | 52.13 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 41 | 磷化工 | 磷化工 | 基础化工 | 51.64 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 42 | 保险 | 低空经济 | - | 49.2 | multi_period_rank、new_high_cluster | 5 | 7 | 0 | missing_evidence |
| 43 | AI眼镜 | AI眼镜 | 电子 | 48.57 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 44 | 智能座舱 | 智能座舱 | 汽车 | 45.87 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 45 | 毫米波雷达 | 毫米波雷达 | 汽车 | 44.8 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 储能 | 储能 | - | 44.0 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 47 | 稀土永磁 | 稀土永磁 | 有色金属 | 41.47 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 48 | 锂 | 锂 | - | 37.2 | multi_period_rank | 1 | 2 | 1 | - |
| 49 | 人工智能 | 人工智能 | - | 36.3 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 军工 | 军工 | - | 34.9 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：电网设备

- **标准概念**：电网设备
- **申万一级**：电力设备
- **评分**：237.72
- **触发类型**：double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 6.65%，边际量 55.2%，成交额 501.52 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅6.65%，边际量55.2%，成交501.52亿 |
| new_high_direction | 51.37 | 新高股18只，新高成交109.83999999999999亿，容量前三=True |
| limit_advance_cluster | 33.0 | 连板股1只，最高3板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 14.15 | 涨停29只，市场占比25.0，排名3 |
| multi_period_rank | 13.2 | daily排名第2，区间涨幅6.65% |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电网设备 | 20 |
| 电网设备出海 | 5 |
| 变压器 | 2 |
| 换流变压器 | 2 |
| 换流阀 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万控智造 | 603070 | 电网设备 | 配电开关控制设备相关产品供应商 | related | L2 | 20 |
| 东方电缆 | 603606 | 电网设备 | 智能电网线缆和高端装备供应商 | peripheral | graph_only | 20 |
| 中国西电 | 601179 | 电网设备 | 电网输配电设备供应商 | peripheral | graph_only | 20 |
| 中辰股份 | 300933 | 电网设备 | 国家线缆骨干企业（两网体系内电缆供应商） | core | L2 | 20 |
| 伊戈尔 | 002922 | 电网设备 | 中游变压器 | related | - | 20 |
| 安靠智电 | - | 电网设备 | 中游电缆连接/GIL | related | - | 20 |
| 平高电气 | 600312 | 电网设备 | 涵盖输配电设备相关产品供应商 | related | L2 | 20 |
| 思源电气 | 002028 | 电网设备 | 中游输变电设备出海 | core | - | 20 |

## 候选 2：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：165.88
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股2只，最高4板，容量前三=False |
| new_high_direction | 36.08 | 新高股9只，新高成交438.36亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| limit_heat | 6.8 | 涨停8只，市场占比6.9，排名17 |

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
- **评分**：143.8
- **触发类型**：limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 28.4 | 新高股5只，新高成交271.97亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅15.77% |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅9.69% |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| multi_period_rank | 19.2 | day10排名第7，区间涨幅5.94% |

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

## 候选 4：电站

- **标准概念**：储能电站
- **申万一级**：电力设备
- **评分**：139.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 139.0 | 连板股4只，最高6板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 储能电站 | 5 |
| 光伏电站运营 | 5 |
| 储能 | 2 |
| 充电桩 | 2 |
| 光伏 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 同力天启 | - | 储能电站 | 算电一体化平台与储能系统服务商 | related | L1_L3_candidate | 20 |
| 露笑科技 | 002617 | 光伏电站运营 | 旗下顺宇洁能从事光伏电站投资、建设与运营，电站集中于华北区域（北京/河北... | core | L2 | 20 |
| 三峡水利 | 600116 | 储能 | 储能电站运营（综合能源） | related | L2 | 11 |
| 中国能建 | 601868 | 储能 | 储能 | related | L1_L3_candidate | 11 |
| 冰山冷热 | 000530 | 储能 | 新事业（储能热管理） | related | L2 | 11 |
| 国网信通 | 600131 | 储能 | 储能 | core | L1_L3_candidate | 11 |
| 天宏锂电 | 920252 | 储能 | 储能模组与独立储能电站业务布局（河北天宏国信等） | related | L2 | 11 |
| 英维克 | 002837 | 储能 | 机柜温控节能产品面向储能电站、通信基站、智能电网输配电设备柜、充电桩等户... | related | L2 | 11 |

## 候选 5：油气开采及服务

- **标准概念**：油气
- **申万一级**：石油石化
- **评分**：132.99
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 38.99 | 新高股14只，新高成交111.42亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | day10排名第1，区间涨幅13.38% |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅11.34% |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅4.35% |

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

## 候选 6：金属锌

- **标准概念**：有色金属
- **申万一级**：有色金属
- **评分**：111.52
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 27.92 | 新高股5只，新高成交233.35亿，容量前三=False |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| multi_period_rank | 21.6 | day3排名第4，区间涨幅10.67% |
| multi_period_rank | 20.8 | daily排名第5，区间涨幅4.53% |
| multi_period_rank | 19.2 | day5排名第7，区间涨幅4.15% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 有色金属 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 锌业股份 | 000751 | 有色金属 | 锌铜冶炼及深加工企业 | core | L2 | 1 |

## 候选 7：电力

- **标准概念**：电力
- **申万一级**：公用事业
- **评分**：109.62
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.82 | 新高股33只，新高成交225.54999999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 17.4 | day5排名第3，区间涨幅8.97% |
| multi_period_rank | 16.6 | day10排名第4，区间涨幅9.47% |
| limit_heat | 6.8 | 涨停8只，市场占比6.9，排名15 |

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

## 候选 8：煤炭开采加工

- **标准概念**：煤炭
- **申万一级**：煤炭
- **评分**：101.98
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.18 | 新高股21只，新高成交94.1亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 18.2 | day10排名第2，区间涨幅10.04% |
| multi_period_rank | 16.6 | day5排名第4，区间涨幅6.12% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 煤炭 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国神华 | 601088 | 煤炭 | 煤炭相关产品/材料供应商 | related | L2 | 20 |
| 中煤能源 | 601898 | 煤炭 | 煤炭相关产品/材料供应商 | related | L2 | 20 |
| 伊泰B股 | 900948 | 煤炭 | 动力煤生产运输销售一体化大型能源企业（10座煤矿+3条自营铁路） | core | L2 | 20 |
| 兖矿能源 | 600188 | 煤炭 | 煤炭开采龙头 | core | L1 | 20 |
| 兰花科创 | 600123 | 煤炭 | 无烟煤开采与销售、尿素（化肥）、己内酰胺（化工）、煤化工节能环保升级改造 | related | L1_L3_candidate | 20 |
| 冀中能源 | 000937 | 煤炭 | 煤炭相关产品/材料供应商 | related | L2 | 20 |
| 华电国际 | 600027 | 煤炭 | 火力发电、供热、新能源 | related | L1_L3_candidate | 20 |
| 华能国际 | 600011 | 煤炭 | 火电、新能源（风电、光伏） | related | L1_L3_candidate | 20 |

## 候选 9：工业金属

- **标准概念**：锻件
- **申万一级**：有色金属
- **评分**：100.75
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.8 | 新高股14只，新高成交495.94000000000005亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 12.6 | daily排名第9，区间涨幅4.21% |
| multi_period_rank | 12.6 | day5排名第9，区间涨幅2.39% |
| limit_heat | 5.75 | 涨停5只，市场占比4.31，排名26 |

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

## 候选 10：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：95.26
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 55.11 | 新高股46只，新高成交408.5亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 14.15 | 涨停29只，市场占比25.0，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电 | 20 |
| 海上风电 | 5 |
| 深远海风电 | 5 |
| 漂浮式风电 | 5 |
| 陆上风电 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三峡能源 | 600905 | 海上风电 | 三峡集团新能源平台：海上风电引领战略，协同推进沙戈荒风电光伏基地 | core | L2 | 20 |
| 东方电气 | 600875 | 海上风电 | 中游制造 | core | L1_L3_candidate | 20 |
| 东方电缆 | 603606 | 海上风电 | 5.2.3 海缆系统企业 | core | L1_L3_candidate | 20 |
| 中信海直 | 000099 | 海上风电 | 海上风电通航服务潜在相关 | related | L1 | 20 |
| 中天科技 | 600522 | 海上风电 | 5.2.3 海缆系统企业 | related | L1_L3_candidate | 20 |
| 中闽能源 | 600163 | 海上风电 | 海上风电运营商（装机29.6万千瓦） | related | L2 | 20 |
| 亨通光电 | 600487 | 海上风电 | 3.4 海缆系统环节 | related | L1_L3_candidate | 20 |
| 大金重工 | 002487 | 海上风电 | 海上风电塔筒/基础及出口海工装备供应商，具备欧洲项目交付和海工运输能力 | related | L3 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-2e5874ae5a1eef190a67 artifact_sha=9b240992fb7aac569fe3c64b3ae18ae090c339632cf16436c31109313b27471b manifest_sha=0a9e6c1bb9d6001a6a826814f91d7230865a39dc6a5723657fde755cd5accc4d -->
