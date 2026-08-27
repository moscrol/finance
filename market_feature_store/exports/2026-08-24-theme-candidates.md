# 2026-08-24 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：20072.28
- **上涨家数**：1460
- **涨停 / 跌停**：47 / 17
- **容量前三行业**：1.电子(26.4%, super_capacity)、2.通信(9.0%, normal)、3.有色金属(8.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 贵金属 | 贵金属 | 有色金属 | 304.24 | limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 1 | - |
| 2 | 黄金概念 | 黄金 | - | 180.22 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 3 | 小金属 | 小金属 | 有色金属 | 177.08 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 4 | 有色 | 有色冶炼装备 | - | 174.81 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 5 | 工业金属 | 工业金属 | 有色金属 | 174.12 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 6 | 中特估 | 中特估 | - | 153.92 | double_red、new_high_direction、new_high_cluster | 1 | 0 | 1 | missing_entity_exposures |
| 7 | 锂矿 | 锂矿 | - | 152.34 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 8 | 黄金 | 黄金 | 有色金属 | 140.21 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 9 | 医药 | 医药 | 医药生物 | 128.4 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 锂 | 锂 | 有色金属 | 96.27 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 2 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 数字人民币 | 数字人民币 | 计算机 | 89.0 | limit_advance_cluster | 1 | 11 | 1 | - |
| 12 | 石油化工 | 化工 | - | 84.8 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 13 | 煤炭 | 煤炭 | - | 82.8 | multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 14 | 银行 | 银行 | - | 81.2 | multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 15 | 一带一路 | 一带一路 | - | 79.89 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 16 | 新能源车 | 新能源车 | - | 79.82 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | 锂电池概念 | 锂 | - | 78.74 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 18 | 铅锌 | 铅锌 | - | 77.6 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 10 | 1 | - |
| 19 | 数据中心 | 数据中心 | 计算机 | 75.75 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 无人机 | 无人机 | - | 75.54 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 21 | 能源金属 | 能源金属 | 有色金属 | 75.47 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 0 | 6 | 0 | missing_concept、missing_evidence |
| 22 | 绿色电力 | 绿色电力 | - | 74.87 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 23 | 风电 | 风电 | 电力设备 | 74.54 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 24 | AI眼镜 | AI眼镜 | 电子 | 74.0 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 25 | 机械设备 | 机械设备 | - | 73.6 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 26 | 电力设备 | 电力设备 | - | 73.31 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 27 | 粤港澳 | 粤港澳 | - | 73.28 | limit_heat、new_high_direction、new_high_cluster | 0 | 10 | 0 | missing_concept、missing_evidence |
| 28 | 物联网 | 物联网 | - | 73.22 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 29 | 稀土永磁 | 稀土永磁 | 有色金属 | 72.1 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 2 | - |
| 30 | 先进封装 | 先进封装 | 电子 | 71.95 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 通信设备 | 通信设备 | 通信 | 70.96 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 32 | 电子 | EDA（电子设计自动化） | - | 69.85 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 33 | 小米概念 | 小米概念 | - | 69.46 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 34 | 特斯拉概念 | 特斯拉概念 | - | 69.23 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 人形机器人 | 人形机器人 | 机械设备 | 68.82 | new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 36 | 氢能源 | 氢能源 | 电力设备 | 68.76 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 37 | 化工 | 化工 | - | 68.55 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 38 | 国防军工 | 国防军工 | - | 68.3 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 39 | 半导体 | 半导体 | 电子 | 68.27 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 40 | 充电桩 | 充电桩 | - | 68.15 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 41 | 核电核能 | 核电 | - | 67.97 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 42 | 智能穿戴 | 智能穿戴 | - | 67.96 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 43 | 智能电网 | 智能电网 | - | 67.85 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 44 | 种植业 | 种植业 | - | 67.2 | multi_period_rank | 1 | 5 | 1 | - |
| 45 | 3D打印 | 3D打印 | 机械设备 | 66.63 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 苹果概念 | 苹果概念 | - | 65.84 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 铜 | 铜 | - | 64.33 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 48 | 大数据 | 大数据 | - | 63.86 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 49 | PCB概念 | PCB概念 | - | 63.78 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 50 | 液冷服务器 | 液冷服务器 | 电力设备 | 62.41 | new_high_direction、new_high_cluster | 3 | 12 | 2 | - |

## 五、核心候选明细

## 候选 1：贵金属

- **标准概念**：贵金属
- **申万一级**：有色金属
- **评分**：304.24
- **触发类型**：limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 119.0 | 连板股3只，最高3板，容量前三=True |
| new_high_direction | 48.84 | 新高股11只，新高成交434.86999999999995亿，容量前三=True |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅8.83% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅12.25% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅14.03% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.4 | daily排名第8，区间涨幅1.61% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 贵金属 | 20 |
| 贵金属催化 | 5 |
| 贵金属催化剂 | 5 |
| 贵金属回收 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 有研新材 | 600206 | 贵金属 | 铂族金属及稀贵金属功能材料供应商（电板块） | core | L2 | 20 |
| 凯大催化 | 830974 | 贵金属 | 贵金属催化相关产品/材料供应商 | related | L2 | 20 |
| 凯立新材 | 688269 | 贵金属 | 贵金属催化剂相关产品/材料供应商 | related | L2 | 20 |
| 浩通科技 | 301026 | 贵金属 | 贵金属回收相关产品/材料供应商 | related | L2 | 20 |
| 贵研铂业 | 600459 | 贵金属 | 贵金属相关产品/材料供应商 | related | L2 | 20 |
| 中触媒 | 688267 | 催化剂 | 特种分子筛与催化新材料平台（钛硅催化剂开拓己内酰胺/环氧丙烷市场） | core | L2 | 10 |
| 肯特催化 | 603120 | 催化剂 | 季铵（鏻）化合物厂商，在相转移催化剂、分子筛模板剂细分领域具技术领先优势... | core | L2 | 10 |
| 齐鲁华信 | 920832 | 催化剂 | 国内主要的催化剂分子筛供应商：石油化工催化分子筛、环保催化分子筛（汽车尾... | core | L2 | 10 |

## 候选 2：黄金概念

- **标准概念**：黄金
- **申万一级**：-
- **评分**：180.22
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.05%，边际量 27.55%，成交额 1089.26 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.05%，边际量27.55%，成交1089.26亿 |
| new_high_direction | 48.82 | 新高股28只，新高成交705.4999999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 10.0 | day3排名第6，区间涨幅5.57% |
| limit_heat | 5.4 | 涨停4只，市场占比8.51，排名18 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 黄金 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中金黄金 | 600489 | 黄金 | 央企黄金龙头（保有金资源量917.35吨） | core | L2 | 20 |
| 宝鼎科技 | 002552 | 黄金 | AI铜箔（HVLP、HTE铜箔）、金矿业务 | core | L1_L3_candidate | 20 |
| 山东黄金 | 600947 | 黄金 | 黄金矿业龙头企业 | core | L2 | 20 |
| 山金国际 | 000975 | 黄金 | 黄金矿采选企业（山东黄金集团旗下，原银泰黄金）：玉龙矿业、黑河银泰等矿山 | core | L2 | 20 |
| 明牌珠宝 | 002574 | 黄金 | 明牌珠宝品牌黄金首饰设计、生产与连锁经营商（黄金饰品为第一大产品） | core | L2 | 20 |
| 晓程科技 | 300139 | 黄金 | 加纳AKROMA/AKOASE/FGM金矿开采冶炼销售，黄金收入占比82... | core | L2 | 20 |
| 曼卡龙 | 300945 | 黄金 | 黄金饰品零售连锁品牌商（创意+经典黄金饰品占营收约97%，向金交所现货采... | core | L2 | 20 |
| 白银有色 | 601212 | 黄金 | 黄金生产商，年产金50吨生产能力 | core | L2 | 20 |

## 候选 3：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：177.08
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.12%，边际量 24.53%，成交额 833.31 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.12%，边际量24.53%，成交833.31亿 |
| new_high_direction | 51.08 | 新高股14只，新高成交278.70000000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小金属 | 20 |
| 小金属材料 | 5 |
| 钨钼小金属 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 盛龙股份 | 001257 | 小金属 | 南泥湖钼矿特大型钼钨矿床，伴生三氧化钨量5.53万吨、铜/铅金属 | core | L2 | 20 |
| 中金岭南 | 000060 | 小金属 | 电镓金属提取和销售企业 | core | L1 | 20 |
| 厦门钨业 | 600549 | 小金属 | 钨钼稀土综合有色平台 | core | L1 | 20 |
| 东方钽业 | 000962 | 小金属 | 钽铌材料/钽电容材料 | core | L1 | 20 |
| 中钨高新 | 000657 | 小金属 | 钨产业链/硬质合金刀具 | core | L1_L3_candidate | 20 |
| 华钰矿业 | 601020 | 小金属 | 锑资源 | core | L1 | 20 |
| 华锡有色 | 600301 | 小金属 | 锑/锡资源端 | core | L1 | 20 |
| 章源钨业 | 002378 | 小金属 | 钨资源/钨制品 | core | L1 | 20 |

## 候选 4：有色

- **标准概念**：有色冶炼装备
- **申万一级**：-
- **评分**：174.81
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.24%，边际量 20.35%，成交额 1874.58 亿，容量前三=否
- **知识库状态**：concept=是（4），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.24%，边际量20.35%，成交1874.58亿 |
| new_high_direction | 52.01 | 新高股37只，新高成交960.7899999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 6.8 | day3排名第10，区间涨幅4.24% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 有色冶炼装备 | 5 |
| 有色加工 | 5 |
| 有色工程 | 5 |
| 有色金属 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三友科技 | 920475 | 有色冶炼装备 | 有色金属电化学精炼专用新型电极材料及成套智能装备供应商（北交所） | core | L2 | 20 |
| 中金岭南 | 000060 | 有色加工 | 有色材料精深加工商 | peripheral | graph_only | 20 |
| 中铝国际 | 601068 | 有色工程 | 有色金属工程设计与EPC龙头（中铝系） | core | L2 | 20 |
| 上海物贸 | 600822 | 有色金属 | 有色/黑色金属现货交易市场及仓储物流平台 | core | L2 | 20 |
| 厦门信达 | 000701 | 有色金属 | 有色及黑色大宗商品贸易供应链 | core | L2 | 20 |
| 厦门国贸 | 600755 | 有色金属 | 冶金/有色等大宗商品供应链运营 | core | L2 | 20 |
| 厦门象屿 | 600057 | 有色金属 | 金属矿产大宗供应链(铜铝镍/不锈钢/黑色) | core | L2 | 20 |
| 昆工科技 | 920152 | 有色金属 | 有色金属湿法冶金电极材料（阴阳极板）行业龙头，栅栏型铝基铅合金复合材料阳... | core | L2 | 20 |

## 候选 5：工业金属

- **标准概念**：工业金属
- **申万一级**：有色金属
- **评分**：174.12
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.16%，边际量 11.64%，成交额 592.37 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.16%，边际量11.64%，成交592.37亿 |
| new_high_direction | 48.12 | 新高股12只，新高成交265.79999999999995亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

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

## 候选 6：中特估

- **标准概念**：中特估
- **申万一级**：-
- **评分**：153.92
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.74%，边际量 20.76%，成交额 985.53 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=否（0），evidence=是（1）
- **缺口标记**：missing_entity_exposures

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.74%，边际量20.76%，成交985.53亿 |
| new_high_direction | 37.92 | 新高股12只，新高成交249.64亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中特估 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：锂矿

- **标准概念**：锂矿
- **申万一级**：-
- **评分**：152.34
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.3%，边际量 18.58%，成交额 559.15 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.3%，边际量18.58%，成交559.15亿 |
| new_high_direction | 36.34 | 新高股11只，新高成交235.17000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 锂矿 | 20 |
| 锂 | 10 |
| 全球锂矿 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天齐锂业 | 002466 | 全球锂矿 | 锂矿龙头，碳酸锂价格弹性受益 | peripheral | L1 | 20 |
| 天赐材料 | 002709 | 全球锂矿 | 电解液龙头，六氟磷酸锂价格弹性受益 | peripheral | L1 | 20 |
| 容百科技 | 688005 | 全球锂矿 | 上游材料 | peripheral | graph_only | 20 |
| 恩捷股份 | 002812 | 全球锂矿 | 上游材料 | peripheral | graph_only | 20 |
| 星源材质 | 300568 | 全球锂矿 | 上游材料 | peripheral | graph_only | 20 |
| 天华新能 | 300390 | 锂矿 | 锂矿+碳酸锂加工 | core | L1_L3_candidate | 20 |
| 威领股份 | 002667 | 锂矿 | 锂云母选矿业务（领辉科技） | core | L2 | 20 |
| 国城矿业 | 000688 | 锂矿 | 锂矿采选及锂盐加工 | related | L1_L3_candidate | 20 |

## 候选 8：黄金

- **标准概念**：黄金
- **申万一级**：有色金属
- **评分**：140.21
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 44.61 | 新高股9只，新高成交320.53000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| multi_period_rank | 23.2 | day10排名第2，区间涨幅8.34% |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅11.06% |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅13.47% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 黄金 | 20 |
| 黄金珠宝 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中金黄金 | 600489 | 黄金 | 央企黄金龙头（保有金资源量917.35吨） | core | L2 | 20 |
| 宝鼎科技 | 002552 | 黄金 | AI铜箔（HVLP、HTE铜箔）、金矿业务 | core | L1_L3_candidate | 20 |
| 山东黄金 | 600947 | 黄金 | 黄金矿业龙头企业 | core | L2 | 20 |
| 山金国际 | 000975 | 黄金 | 黄金矿采选企业（山东黄金集团旗下，原银泰黄金）：玉龙矿业、黑河银泰等矿山 | core | L2 | 20 |
| 明牌珠宝 | 002574 | 黄金 | 明牌珠宝品牌黄金首饰设计、生产与连锁经营商（黄金饰品为第一大产品） | core | L2 | 20 |
| 晓程科技 | 300139 | 黄金 | 加纳AKROMA/AKOASE/FGM金矿开采冶炼销售，黄金收入占比82... | core | L2 | 20 |
| 曼卡龙 | 300945 | 黄金 | 黄金饰品零售连锁品牌商（创意+经典黄金饰品占营收约97%，向金交所现货采... | core | L2 | 20 |
| 白银有色 | 601212 | 黄金 | 黄金生产商，年产金50吨生产能力 | core | L2 | 20 |

## 候选 9：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：128.4
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股2只，最高4板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比8.51，排名24 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医药 | 20 |
| AI+医药 | 5 |
| AI+生物医药 | 5 |
| 中医药 | 5 |
| 医药CDMO | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | AI+医药 | 一心智云AI中台赋能万店运营（探索期） | related | L2 | 20 |
| 瑞康医药 | 002589 | 中医药 | 中医药种植/饮片/药食同源布局 | related | L2 | 20 |
| 寿仙谷 | 603896 | 医药 | 灵芝、铁皮石斛等名贵中药材育种-栽培-饮片炮制-深加工全产业链中药企业 | core | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 康芝药业 | 300086 | 医药 | 国内领先的儿童药生产销售企业（儿童大健康） | core | L2 | 20 |
| 振东制药 | 300158 | 医药 | 肿瘤/皮科/消化/泌尿/心脑管线中西药生产销售企业，拥有592个批文、4... | core | L2 | 20 |
| 柳药集团 | 603368 | 医药 | 综合性医药大健康产业集团（医药商业为主业+中药工业：中药饮片、中药配方颗... | core | L2 | 20 |
| 梓橦宫 | 920566 | 医药 | 神经系统/消化系统处方药研发生产企业，胞磷胆碱钠片为拳头品种（占营收约7... | core | L2 | 20 |

## 候选 10：锂

- **标准概念**：锂
- **申万一级**：有色金属
- **评分**：96.27
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（2），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.87 | 新高股8只，新高成交213.43亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 16.6 | day3排名第4，区间涨幅6.53% |
| multi_period_rank | 11.8 | daily排名第10，区间涨幅1.31% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 锂 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中矿资源 | 002738 | 锂 | 锂矿资源与海外锂盐项目企业 | related | L1_L3_candidate | 10 |
| 天齐锂业 | 002466 | 锂 | 氢氧化锂相关产品/材料供应商 | related | L2 | 10 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-bac10b3982713f79394d artifact_sha=346dd0873c702e4c211d63a5449fd87b5f6f727b31683fbab5993c6c4737b69b manifest_sha=6c024417858edbcb16aa90370d5b8a6a6e6dc4f9fec5719520d040c45b99da3f -->
