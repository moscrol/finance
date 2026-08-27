# 2026-08-21 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：18791.51
- **上涨家数**：2505
- **涨停 / 跌停**：54 / 15
- **容量前三行业**：1.电子(25.8%, super_capacity)、2.医药生物(10.4%, normal)、3.通信(9.3%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 贵金属 | 贵金属 | 有色金属 | 164.02 | multi_period_rank、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 2 | 航运 | 航运 | - | 163.5 | multi_period_rank、new_high_direction、new_high_cluster | 4 | 12 | 2 | - |
| 3 | 黄金 | 黄金 | 有色金属 | 161.69 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 4 | 连板未映射 | - | 医药生物 | 135.0 | limit_advance_cluster、capacity_industry | 0 | 0 | 0 | placeholder_market_theme |
| 5 | 消费电子 | 消费电子 | 机械设备 | 121.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 5 | - |
| 6 | 疫苗 | 疫苗 | - | 112.43 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 7 | 小金属 | 小金属 | 有色金属 | 110.0 | double_red、new_high_cluster | 3 | 12 | 2 | - |
| 8 | 动力电池回收 | 动力电池回收 | - | 108.0 | double_red、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 9 | 医药 | 医药 | 医药生物 | 104.76 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 10 | 通信 | 通信 | 电力设备 | 88.42 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 创新药 | 创新药 | 医药生物 | 83.73 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 12 | 新能源车 | 新能源车 | - | 78.75 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 数据中心 | 数据中心 | 计算机 | 77.0 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 医药医疗 | 医疗 | - | 75.77 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 15 | 电子 | EDA（电子设计自动化） | - | 75.39 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 16 | 有色 | 有色冶炼装备 | - | 75.19 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 17 | 通信设备 | 通信设备 | 通信 | 74.42 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 18 | 锂电池概念 | 锂 | - | 74.41 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 19 | 化工 | 化工 | - | 74.03 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 20 | 机械设备 | 机械设备 | - | 73.98 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 21 | 风电 | 风电 | 电力设备 | 73.48 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 22 | 核电核能 | 核电 | - | 71.27 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 23 | 小米概念 | 小米概念 | - | 70.85 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | CPO概念 | CPO | - | 69.69 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 25 | 一带一路 | 一带一路 | - | 69.53 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 26 | 合成生物 | 合成生物 | 医药生物 | 68.48 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 27 | 交通运输 | 交通运输 | - | 67.38 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 28 | 绿色电力 | 绿色电力 | - | 67.18 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 29 | 物联网 | 物联网 | - | 67.06 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 30 | 氢能源 | 氢能源 | 电力设备 | 66.08 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 无人机 | 无人机 | - | 65.93 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 32 | 生物制药 | 生物制药 | - | 65.55 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 33 | 人形机器人 | 人形机器人 | 机械设备 | 65.17 | new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 34 | 商业航天 | 商业航天 | 国防军工 | 65.12 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 35 | 大数据 | 大数据 | - | 63.93 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 36 | 光通信 | 光通信 | - | 63.34 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 37 | 涤纶 | 涤纶 | - | 62.4 | multi_period_rank | 4 | 12 | 1 | - |
| 38 | 航运概念 | 航运 | - | 62.13 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 39 | 黄金概念 | 黄金 | - | 61.98 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 40 | 基因概念 | 基因概念 | - | 61.93 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 第三代半导体 | 第三代半导体 | - | 60.9 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 42 | 电力设备 | 电力设备 | - | 60.61 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 43 | 生物疫苗 | 疫苗 | - | 58.15 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 运输服务 | 运输服务 | - | 57.9 | new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 45 | 天然气 | 天然气 | - | 57.77 | new_high_direction、new_high_cluster | 1 | 12 | 3 | - |
| 46 | 稀土永磁 | 稀土永磁 | 有色金属 | 55.34 | new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 47 | 特高压 | 特高压 | 电力设备 | 55.06 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 48 | 铜缆高速连接 | 铜 | 电力设备 | 51.75 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 49 | 智能电网 | 智能电网 | - | 51.44 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 50 | 化纤 | 化纤 | - | 47.2 | multi_period_rank、new_high_cluster | 1 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：贵金属

- **标准概念**：贵金属
- **申万一级**：有色金属
- **评分**：164.02
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 28.82 | 新高股6只，新高成交193.97亿，容量前三=False |
| multi_period_rank | 28.2 | day10排名第2，区间涨幅11.35% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅11.35% |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅16.11% |
| multi_period_rank | 26.6 | daily排名第4，区间涨幅4.64% |
| new_high_cluster | 24.0 | 题材内新高股6只 |

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

## 候选 2：航运

- **标准概念**：航运
- **申万一级**：-
- **评分**：163.5
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.9 | 新高股9只，新高成交103.72亿，容量前三=False |
| multi_period_rank | 27.4 | day10排名第3，区间涨幅8.37% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅11.0% |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| multi_period_rank | 25.8 | day3排名第5，区间涨幅5.68% |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅3.87% |

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

## 候选 3：黄金

- **标准概念**：黄金
- **申万一级**：有色金属
- **评分**：161.69
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅11.45% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅11.42% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅16.17% |
| new_high_direction | 26.89 | 新高股5只，新高成交150.84亿，容量前三=False |
| multi_period_rank | 25.8 | daily排名第5，区间涨幅4.2% |
| new_high_cluster | 22.0 | 题材内新高股5只 |

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

## 候选 4：连板未映射

- **标准概念**：-
- **申万一级**：医药生物
- **评分**：135.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 135.0 | 连板股5只，最高3板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：消费电子

- **标准概念**：消费电子
- **申万一级**：机械设备
- **评分**：121.0
- **触发类型**：limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股3只，最高2板，容量前三=False |
| new_high_cluster | 24.0 | 题材内新高股6只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费电子 | 20 |
| 消费 | 10 |
| 消费电子材料 | 5 |
| 消费电子渠道 | 5 |
| 消费电子设备 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 张小泉 | 301055 | 消费 | 刀剪具/厨房五金/家居五金生活五金消费品制造与全渠道零售商 | core | L2 | 20 |
| 盈趣科技 | 002925 | 消费 | 电子烟（创新消费电子）、健康环境产品、汽车电子、智能控制部件 | core | L1_L3_candidate | 20 |
| 酒鬼酒 | 000799 | 消费 | 深度联动胖东来联合开发「酒鬼酒・自由爱」新品成为核心增长引擎，启动光瓶湘... | related | L2 | 20 |
| 华夏航空 | 002928 | 消费 | 支线航空运营商，地方政府采购+中央支线补贴商业模式，覆盖下沉市场 | related | L1_L3_candidate | 20 |
| 中体产业 | 600158 | 消费 | 体育赛事运营与场馆经营受益名单 | peripheral | graph_only | 20 |
| 立华股份 | 300761 | 消费 | 图谱弱关联 | peripheral | graph_only | 20 |
| 锦江酒店 | 600754 | 消费 | 连锁酒店集团，受益休闲需求与RevPAR修复 | peripheral | graph_only | 20 |
| 首旅酒店 | 600258 | 消费 | 连锁酒店集团，受益休闲需求与RevPAR修复 | peripheral | graph_only | 20 |

## 候选 6：疫苗

- **标准概念**：疫苗
- **申万一级**：-
- **评分**：112.43
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 26.43 | 新高股5只，新高成交114.43亿，容量前三=False |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅8.82% |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅6.86% |
| multi_period_rank | 20.0 | day5排名第6，区间涨幅6.79% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 疫苗 | 20 |
| DC疫苗 | 5 |
| HIV疫苗 | 5 |
| HPV疫苗 | 5 |
| mRNA疫苗 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 生物股份 | 600201 | mRNA疫苗 | 兽用生物制品（猪、牛、禽 | related | L1_L3_candidate | 20 |
| 智飞生物 | 300122 | mRNA疫苗 | mRNA技术平台布局者（带状疱疹/新冠mRNA疫苗获临床批件） | peripheral | L2 | 20 |
| 瑞普生物 | 300119 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |
| 科前生物 | 688526 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |
| 金河生物 | 002688 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |
| 万泰生物 | 603392 | 疫苗 | 疫苗相关产品/材料供应商 | related | L2 | 20 |
| 中牧股份 | 600195 | 动物疫苗 | 重大动物疫病疫苗国家队（口蹄疫、高致病性禽流感定点生产企业） | core | L2 | 5 |
| 天康生物 | 002100 | 动物疫苗 | 动物疫苗与动物药品业务（畜禽病害防治环节） | core | L2 | 5 |

## 候选 7：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：110.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 2.52%，边际量 14.11%，成交额 669.17 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.52%，边际量14.11%，成交669.17亿 |
| new_high_cluster | 20.0 | 题材内新高股4只 |

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

## 候选 8：动力电池回收

- **标准概念**：动力电池回收
- **申万一级**：-
- **评分**：108.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.81%，边际量 12.83%，成交额 539.84 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.81%，边际量12.83%，成交539.84亿 |
| new_high_cluster | 18.0 | 题材内新高股3只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 动力电池回收 | 20 |
| 动力电池 | 10 |
| 电池回收 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 壹连科技 | 301631 | 动力电池 | 电芯连接组件/动力传输组件等电连接组件供应商，以新能源汽车为发展主轴 | core | L2 | 20 |
| 宁德时代 | 300750 | 动力电池 | 全球动力电池龙头 | core | L1_L3_candidate | 20 |
| 四川长虹 | 600839 | 动力电池 | ICT综合服务（华为昇腾算力分销/服务器）、智慧家居（AI家电）、特种电... | core | L1_L3_candidate | 20 |
| 卓兆点胶 | 920026 | 动力电池 | 消费电子点胶设备/阀体（果链核心供应商）、Meta AI眼镜点胶阀、点胶... | related | L1_L3_candidate | 20 |
| 比亚迪 | 002594 | 动力电池 | 动力电池 | related | L1_L3_candidate | 20 |
| 鹏辉能源 | 300438 | 动力电池 | 动力电池 | related | L1_L3_candidate | 20 |
| 亿纬锂能 | 300014 | 动力电池 | 动力电池相关产品/材料供应商 | related | L2 | 20 |
| 国轩高科 | 002074 | 动力电池 | 动力电池相关产品/材料供应商 | related | L2 | 20 |

## 候选 9：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：104.76
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.66 | 新高股23只，新高成交212.48000000000002亿，容量前三=False |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比11.11，排名19 |

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

## 候选 10：通信

- **标准概念**：通信
- **申万一级**：电力设备
- **评分**：88.42
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 32.67 | 新高股8只，新高成交277.49亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 5.75 | 涨停5只，市场占比9.26，排名29 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 通信 | 20 |
| 5G_6G通信 | 5 |
| 5G通信 | 5 |
| 6G通信 | 5 |
| 专网通信 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中兴通讯 | 000063 | 5G通信 | 全球主要通信设备商，“连接+算力”双轮驱动 | core | L2 | 20 |
| 中国卫通 | 601698 | 5G通信 | 通信网络卫星补充环节 | peripheral | L1 | 20 |
| 信科移动 | 688387 | 5G通信 | 图谱弱关联 | peripheral | graph_only | 20 |
| 信维通信 | 300136 | 5G通信 | 5G-A终端多天线及高精密LCP、射频电磁兼容件供应商 | core | L1 | 20 |
| 中国移动 | 600941 | 5G通信 | 5G通信运营商 | related | L2_candidate | 20 |
| 中英科技 | 300936 | 5G通信 | 高频覆铜板（PTFE）、VC散热片、引线框架 | related | L1 | 20 |
| 瑞玛精密 | 002976 | 5G通信 | 5G通讯滤波器与天线设备，通信设备收入同比+365.66% | related | L2 | 20 |
| 神宇股份 | 300563 | 5G通信 | - | related | L1 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-25dfaf852d2c496774bd artifact_sha=37cc65c0b20dd1418d9d28e21b2ac19b963f7cdb0854edef45d288cdb248a1c6 manifest_sha=218dff892c464a3e3d89b5e223a3cef74a9c4def731500b61cac352c2da7ccca -->
