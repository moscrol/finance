# 2026-08-26 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：18083.81
- **上涨家数**：2946
- **涨停 / 跌停**：52 / 0
- **容量前三行业**：1.电子(23.6%, capacity)、2.有色金属(8.2%, normal)、3.机械设备(8.1%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 工业金属 | 工业金属 | 有色金属 | 191.45 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 2 | 非银金融 | 非银金融 | - | 183.65 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 1 | 11 | 1 | - |
| 3 | 黄金概念 | 黄金 | - | 165.63 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 4 | 中特估 | 中特估 | - | 147.93 | double_red、new_high_direction、new_high_cluster | 1 | 0 | 1 | missing_entity_exposures |
| 5 | 互联金融 | 互联金融 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 6 | 医药 | 医药 | 医药生物 | 97.21 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 数字货币/跨境支付 | 数字货币 | 计算机 | 97.0 | limit_advance_cluster | 2 | 9 | 0 | missing_evidence |
| 8 | 光通信 | 光通信 | 计算机 | 94.07 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 9 | 液冷 | 液冷 | 电力设备 | 89.0 | limit_advance_cluster | 5 | 12 | 5 | - |
| 10 | 疫苗 | 疫苗 | - | 86.0 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 光纤光缆 | 光纤光缆 | - | 83.4 | multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 12 | 新能源车 | 新能源车 | - | 78.62 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 人形机器人 | 人形机器人 | 机械设备 | 78.33 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 14 | 数据中心 | 数据中心 | 计算机 | 77.62 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 新型工业化 | 新型工业化 | 机械设备 | 77.45 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 16 | 一带一路 | 一带一路 | - | 76.69 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 17 | 锂电池概念 | 锂 | - | 75.57 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 18 | 充电桩 | 充电桩 | - | 75.09 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 19 | 风电 | 风电 | 电力设备 | 74.96 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 20 | 液冷服务器 | 液冷服务器 | 电力设备 | 74.63 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 21 | 医药医疗 | 医疗 | - | 74.38 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 22 | 工业互联 | 工业互联网 | - | 73.84 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 23 | 乡村振兴 | 乡村振兴 | - | 73.72 | limit_heat、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 24 | 有色 | 有色冶炼装备 | - | 73.71 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 25 | 绿色电力 | 绿色电力 | - | 73.48 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 26 | 新零售 | 零售 | - | 73.3 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 27 | 电力设备 | 电力设备 | - | 73.23 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 28 | 智能家居 | 智能家居 | - | 72.87 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 29 | 东数西算 | 东数西算 | - | 69.21 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 30 | 机械设备 | 机械设备 | - | 68.56 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 抖音概念 | 抖音概念 | - | 68.5 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 32 | 智能电网 | 智能电网 | - | 68.33 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 33 | 电子 | EDA（电子设计自动化） | - | 68.0 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 34 | 商业航天 | 商业航天 | 国防军工 | 67.9 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 35 | 大数据 | 大数据 | - | 67.85 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 36 | 冷链物流 | 冷链物流 | - | 67.73 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 37 | 特斯拉概念 | 特斯拉概念 | - | 67.72 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 虚拟现实 | 虚拟现实 | - | 67.67 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 39 | 阿里概念 | 阿里概念 | - | 67.67 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 40 | 小米概念 | 小米概念 | - | 67.61 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 创新药 | 创新药 | 医药生物 | 67.58 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 42 | 化工 | 化工 | - | 67.55 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 43 | 高端装备 | 高端装备 | - | 67.52 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 44 | 口罩防护 | 口罩防护 | - | 67.5 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 粤港澳 | 粤港澳 | - | 67.47 | new_high_direction、new_high_cluster | 0 | 10 | 0 | missing_concept、missing_evidence |
| 46 | 腾讯概念 | 腾讯概念 | - | 67.47 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 国防军工 | 国防军工 | - | 67.43 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 48 | 特高压 | 特高压 | 电力设备 | 67.35 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 49 | 智能穿戴 | 智能穿戴 | - | 66.65 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 50 | PCB概念 | PCB概念 | - | 66.43 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：工业金属

- **标准概念**：工业金属
- **申万一级**：有色金属
- **评分**：191.45
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.96%，边际量 29.73%，成交额 626.36 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.96%，边际量29.73%，成交626.36亿 |
| new_high_direction | 47.65 | 新高股13只，新高成交116.24999999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 12.4 | daily排名第3，区间涨幅2.96% |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |
| limit_heat | 5.4 | 涨停4只，市场占比7.69，排名21 |

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

## 候选 2：非银金融

- **标准概念**：非银金融
- **申万一级**：-
- **评分**：183.65
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.45%，边际量 84.63%，成交额 599.75 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（11），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.45%，边际量84.63%，成交599.75亿 |
| new_high_direction | 41.65 | 新高股16只，新高成交132.20000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 14.2 | daily排名第7，区间涨幅2.45% |
| multi_period_rank | 11.8 | day3排名第10，区间涨幅3.61% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 非银金融 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中油资本 | 000617 | 非银金融 | 中国石油集团旗下全方位综合性金融服务平台（昆仑银行、中油财务、昆仑金融租... | core | L2 | 20 |
| 永安期货 | 600927 | 非银金融 | 头部全牌照期货公司（期货经纪+风险管理+资管+基金销售，分类监管评价连续... | core | L2 | 20 |
| 浙江东方 | 600120 | 非银金融 | 浙江省国有上市金融控股平台（旗下浙商金汇信托、大地期货、东方嘉富人寿、国... | core | L2 | 20 |
| 越秀资本 | 000987 | 非银金融 | 广州市国资委下属多元金融控股平台（融资租赁+不良资产管理+投资管理+战略... | core | L2 | 20 |
| 长城证券 | 002939 | 非银金融 | 非银金融（证券）标的，参控股覆盖公募基金、期货、私募、资管、国际金融的长... | core | L2 | 20 |
| 香溢融通 | 600830 | 非银金融 | 以融资租赁为核心引擎的类金融控股平台（融资租赁+典当+担保+特殊资产+私... | core | L2 | 20 |
| 东方财富 | 300059 | 非银金融 | 证券经纪、两融业务、基金代销（天天基金） | related | L1_L3_candidate | 20 |
| 中信证券 | 600030 | 非银金融 | 证券经纪、投资银行、资产管理 | related | L1_L3_candidate | 20 |

## 候选 3：黄金概念

- **标准概念**：黄金
- **申万一级**：-
- **评分**：165.63
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.74%，边际量 17.11%，成交额 990.42 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.74%，边际量17.11%，成交990.42亿 |
| new_high_direction | 36.73 | 新高股12只，新高成交154.76000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 6.8 | day5排名第10，区间涨幅5.8% |
| limit_heat | 6.1 | 涨停6只，市场占比11.54，排名10 |

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

## 候选 4：中特估

- **标准概念**：中特估
- **申万一级**：-
- **评分**：147.93
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.94%，边际量 10.71%，成交额 893.64 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=否（0），evidence=是（1）
- **缺口标记**：missing_entity_exposures

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.94%，边际量10.71%，成交893.64亿 |
| new_high_direction | 31.93 | 新高股9只，新高成交106.05999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股9只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中特估 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：互联金融

- **标准概念**：互联金融
- **申万一级**：-
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.85%，边际量 24.21%，成交额 671.14 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.85%，边际量24.21%，成交671.14亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 6：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：97.21
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.81 | 新高股25只，新高成交144.48亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 5.4 | 涨停4只，市场占比7.69，排名20 |

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

## 候选 7：数字货币/跨境支付

- **标准概念**：数字货币
- **申万一级**：计算机
- **评分**：97.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股2只，最高4板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数字货币 | 22 |
| 跨境支付 | 22 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 先进数通 | 300541 | 数字货币 | 数字货币 | related | L1_L3_candidate | 21 |
| 四方精创 | 300468 | 数字货币 | 软件开发及维护供应商/运营商 | related | L2 | 20 |
| 信雅达 | 600571 | 跨境支付 | SWIFT全球合作伙伴（ISO 20022报文迁移服务） | related | L2 | 20 |
| 广电运通 | 002152 | 跨境支付 | 跨境支付 | related | L1_L3_candidate | 20 |
| 天阳科技 | 300872 | 跨境支付 | 跨境支付 | related | L1_L3_candidate | 20 |
| 拉卡拉 | 300773 | 跨境支付 | 跨境支付相关产品/材料供应商 | related | L2 | 20 |
| 彩讯股份 | 300634 | 信创 | 智算服务与数据智能、Voice AI Agent、协同办公 | related | L1_L3_candidate | 1 |
| 宇信科技 | 300674 | 数字人民币 | 与央行及各大行深度合作的数字人民币系统建设与数币全球化输出厂商 | related | L2 | 1 |

## 候选 8：光通信

- **标准概念**：光通信
- **申万一级**：计算机
- **评分**：94.07
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 38.32 | 新高股12只，新高成交281.90999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 5.75 | 涨停5只，市场占比9.62，排名13 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光通信 | 20 |
| 通信 | 10 |
| 光通信与AI网络基础设施 | 5 |
| 光通信测试仪器 | 5 |
| 光通信滤光片 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | 光通信 | MLCC（片式多层陶瓷电容器）、光通信陶瓷组件（光纤插芯、MT插芯、陶瓷... | core | L1_L3_candidate | 20 |
| 久之洋 | 300516 | 光通信 | 星间激光通信核心部件（光纤放大器EDFA、捕跟相机）、低空经济/反无人机... | core | L1_L3_candidate | 20 |
| 天邑股份 | 300504 | 光通信 | 接入网宽带网络终端与智能组网产品 | core | L2 | 20 |
| 腾景科技 | 688195 | 光通信 | 光模块/光器件上游精密光学元组件供应商，受益数通算力需求 | core | L2 | 20 |
| 中瓷电子 | 003031 | 光通信 | 光通信陶瓷外壳及器件外壳供应商 | core | L1 | 20 |
| 华脉科技 | 603042 | 光通信 | 光通信网络设备制造、无线通信网络设备制造 | core | L2 | 20 |
| 国缆检测 | 301289 | 光通信 | 电线电缆及光纤光缆检验检测、电化学储能检测、超高压、特高压检测 | core | L1_L3_candidate | 20 |
| 兆驰股份 | 002429 | 光通信 | 光通信产业链业务板块 | related | L2 | 20 |

## 候选 9：液冷

- **标准概念**：液冷
- **申万一级**：电力设备
- **评分**：89.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 液冷 | 20 |
| AIPC液冷 | 5 |
| 冷板式液冷 | 5 |
| 微泵液冷 | 5 |
| 数据中心液冷 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 春秋电子 | 603890 | AIPC液冷 | 电子结构件/液冷解决方案 | peripheral | L1_L3_candidate | 20 |
| 真视通 | 002771 | 冷板式液冷 | 泵驱两相冷板式液冷散热技术入选北京市节能技术产品推荐目录，应用于智算中心... | related | L2 | 20 |
| 冰轮环境 | 000811 | 冷板式液冷 | 液冷一次侧/二次侧设备相关标的 | related | graph_only | 20 |
| 南风股份 | 300004 | 冷板式液冷 | CDU/Manifold/冷板/UQD等液冷零部件相关标的 | related | graph_only | 20 |
| 同飞股份 | 300990 | 冷板式液冷 | 液冷集成商相关标的 | related | graph_only | 20 |
| 奕东电子 | 301123 | 冷板式液冷 | CDU/Manifold/冷板/UQD等液冷零部件相关标的 | related | graph_only | 20 |
| 强瑞技术 | 301128 | 冷板式液冷 | CDU/Manifold/冷板/UQD等液冷零部件相关标的 | related | graph_only | 20 |
| 汉钟精机 | 002158 | 冷板式液冷 | 液冷一次侧/二次侧设备相关标的 | related | graph_only | 20 |

## 候选 10：疫苗

- **标准概念**：疫苗
- **申万一级**：-
- **评分**：86.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 24.0 | daily排名第1，区间涨幅6.14% |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅12.71% |
| multi_period_rank | 20.0 | day10排名第6，区间涨幅7.2% |
| new_high_cluster | 18.0 | 题材内新高股3只 |

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


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-44ffb104818165f6d8f5 artifact_sha=684235968ba34879468af03da2c4536d34215b4746eec2d57989020e211aaf4f manifest_sha=1ded839352e71aa6bb568c94846193e0ce6f2a9e0ab499c43799df62e8953435 -->
