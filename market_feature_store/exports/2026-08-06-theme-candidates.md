# 2026-08-06 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：25286.07
- **上涨家数**：2789
- **涨停 / 跌停**：79 / 1
- **容量前三行业**：1.电子(28.8%, super_capacity)、2.通信(8.5%, normal)、3.有色金属(7.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 小金属 | 小金属 | 有色金属 | 179.05 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 2 | 稀土永磁 | 稀土永磁 | 有色金属 | 178.13 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 3 | 有色 | 有色冶炼装备 | - | 168.49 | double_red、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 4 | 黄金概念 | 黄金 | - | 166.94 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 5 | 钠电池 | 钠电池 | - | 159.06 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 3 | - |
| 6 | 钴金属 | 钴金属 | - | 154.63 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | 稀有金属 | 稀有金属 | - | 150.11 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 8 | 半导体封测 | 半导体封测 | - | 125.6 | double_red、multi_period_rank | 3 | 12 | 0 | missing_evidence |
| 9 | 电子化学品 | 电子化学品 | 基础化工 | 124.8 | double_red、multi_period_rank | 2 | 12 | 1 | - |
| 10 | 氟概念 | 氟概念 | - | 122.8 | double_red、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 股权 | 私募股权投资 | 机械设备 | 121.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 12 | 磷化铟 | 磷化铟 | 电子 | 119.0 | limit_advance_cluster、capacity_industry | 2 | 12 | 5 | - |
| 13 | 化工原料 | 化工 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 14 | 其他材料 | 其他材料 | 电子 | 107.0 | limit_advance_cluster、capacity_industry | 0 | 1 | 0 | missing_concept、missing_evidence |
| 15 | 贵金属 | 贵金属 | 计算机 | 105.57 | limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 16 | AI应用 | AI应用 | 传媒 | 93.0 | limit_advance_cluster | 1 | 12 | 5 | - |
| 17 | 工业金属 | 工业金属 | 有色金属 | 81.82 | new_high_direction、new_high_cluster、capacity_industry | 0 | 9 | 0 | missing_concept、missing_evidence |
| 18 | 锂电池概念 | 锂 | - | 81.79 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 19 | 一带一路 | 一带一路 | - | 80.56 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 20 | 新能源车 | 新能源车 | - | 79.8 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | 黄金 | 黄金 | 有色金属 | 78.79 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 22 | 物联网 | 物联网 | - | 78.25 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 23 | 计算机 | 计算机外设 | - | 77.87 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 24 | 阿里概念 | 阿里概念 | - | 77.4 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 25 | 华为鸿蒙 | 华为鸿蒙 | - | 77.07 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 26 | 互联金融 | 互联金融 | - | 77.02 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | 区块链 | 区块链 | - | 76.93 | limit_heat、new_high_direction、new_high_cluster | 1 | 6 | 1 | - |
| 28 | 无人驾驶 | 无人驾驶 | 汽车 | 76.58 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 29 | 化工 | 化工 | - | 76.28 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 30 | 国防军工 | 国防军工 | - | 75.75 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 绿色电力 | 绿色电力 | - | 75.26 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 32 | 软件服务 | 软件 | - | 70.26 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 33 | 信创 | 信创 | 计算机 | 70.22 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 数据要素 | 数据要素 | 计算机 | 70.11 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 35 | 特斯拉概念 | 特斯拉概念 | - | 69.56 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 36 | 氢能源 | 氢能源 | 电力设备 | 69.39 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 37 | 国产软件 | 软件 | - | 69.36 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 38 | 大数据 | 大数据 | - | 69.36 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 39 | 电力设备 | 电力设备 | - | 69.3 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 40 | AIGC概念 | AIGC | - | 69.27 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 41 | 信息安全 | 信息安全 | - | 69.16 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 42 | 海峡西岸 | 海峡西岸 | - | 69.15 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 43 | 数据中心 | 数据中心 | 计算机 | 69.0 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 腾讯概念 | 腾讯概念 | - | 68.87 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 跨境电商 | 跨境电商 | - | 68.76 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 46 | 工业互联 | 工业互联网 | - | 68.7 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 47 | 云计算 | 云计算 | 计算机 | 68.63 | new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 48 | 东数西算 | 东数西算 | - | 68.6 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 49 | 车联网 | 车联网 | - | 68.21 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 50 | 智慧城市 | 智慧城市 | - | 68.19 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：179.05
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.12%，边际量 30.54%，成交额 974.87 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.12%，边际量30.54%，成交974.87亿 |
| new_high_direction | 53.05 | 新高股19只，新高成交244.18亿，容量前三=True |
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
| 东方钽业 | 000962 | 小金属 | 钽铌材料/钽电容材料 | core | - | 20 |
| 中钨高新 | 000657 | 小金属 | 钨产业链/硬质合金刀具 | core | - | 20 |
| 华钰矿业 | 601020 | 小金属 | 锑资源 | core | - | 20 |
| 华锡有色 | 600301 | 小金属 | 锑/锡资源端 | core | - | 20 |
| 章源钨业 | 002378 | 小金属 | 钨资源/钨制品 | core | - | 20 |

## 候选 2：稀土永磁

- **标准概念**：稀土永磁
- **申万一级**：有色金属
- **评分**：178.13
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.22%，边际量 22.8%，成交额 696.87 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.22%，边际量22.8%，成交696.87亿 |
| new_high_direction | 52.13 | 新高股19只，新高成交170.29999999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 稀土永磁 | 20 |
| 稀土 | 12 |
| 稀土永磁材料 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 厦门钨业 | 600549 | 稀土 | 稀土深加工产业布局（磁材等） | core | L2 | 20 |
| 宁波韵升 | 600366 | 稀土 | 上游材料 | related | L1_L3_candidate | 20 |
| 爱迪特 | 301580 | 稀土 | 数字化齿科材料供应商，主营氧化锆瓷块等口腔修复材料，并向口腔种植手术机器... | related | L1_L3_candidate | 20 |
| 天和磁材 | 603072 | 稀土永磁 | 烧结钕铁硼/烧结钐钴等高性能稀土永磁材料及磁组件供应商 | core | L2 | 20 |
| 英思特 | 301622 | 稀土永磁 | 稀土永磁材料应用器件厂商，提供磁路设计、精密加工、表面处理、智能组装综合... | core | L2 | 20 |
| 中科三环 | 000970 | 稀土永磁 | 钕铁硼永磁材料龙头 | core | L1_L3_candidate | 20 |
| 中国稀土 | 000831 | 稀土永磁 | 中重稀土集团平台/冶炼分离 | core | - | 20 |
| 中稀有色 | 600259 | 稀土永磁 | 中重稀土资产整合平台 | core | - | 20 |

## 候选 3：有色

- **标准概念**：有色冶炼装备
- **申万一级**：-
- **评分**：168.49
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.96%，边际量 22.53%，成交额 2055.82 亿，容量前三=否
- **知识库状态**：concept=是（4），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.96%，边际量22.53%，成交2055.82亿 |
| new_high_direction | 52.49 | 新高股58只，新高成交999.2300000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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
| 盛达资源 | 000603 | 有色金属 | 有色金属采选收入20.69亿元占84.04%，毛利率71.26% | core | L2 | 20 |

## 候选 4：黄金概念

- **标准概念**：黄金
- **申万一级**：-
- **评分**：166.94
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.67%，边际量 15.78%，成交额 1033.27 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.67%，边际量15.78%，成交1033.27亿 |
| new_high_direction | 50.94 | 新高股46只，新高成交875.5899999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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
| 晓程科技 | 300139 | 黄金 | 加纳AKROMA/AKOASE/FGM金矿开采冶炼销售，黄金收入占比82... | core | L2 | 20 |
| 白银有色 | 601212 | 黄金 | 黄金生产商，年产金50吨生产能力 | core | L2 | 20 |
| 紫金矿业 | 601899 | 黄金 | 全球金属矿企黄金龙头（2025年《福布斯》全球黄金企业第1位），保有资源... | core | L2 | 20 |
| 华钰矿业 | 601020 | 黄金 | 黄金业务（泥堡金矿 | related | L1_L3_candidate | 20 |

## 候选 5：钠电池

- **标准概念**：钠电池
- **申万一级**：-
- **评分**：159.06
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 10.82%，成交额 928.03 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量10.82%，成交928.03亿 |
| new_high_direction | 43.06 | 新高股18只，新高成交244.51999999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 钠电池 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 容百科技 | 688005 | 钠电池 | 上游材料 | core | L1_L3_candidate | 20 |
| 振华新材 | 688707 | 钠电池 | 上游材料 | core | L1_L3_candidate | 20 |
| 星源材质 | 300568 | 钠电池 | 产业链供应商 | core | L2_candidate | 20 |
| 贝特瑞 | 835185 | 钠电池 | 上游材料 | core | L1_L3_candidate | 20 |
| 中科电气 | 300035 | 钠电池 | 钠电硬碳负极材料量产企业 | related | L2 | 20 |
| 宁德时代 | 300750 | 钠电池 | 动力电池、储能电池、电池材料 | related | L1_L3_candidate | 20 |
| 万顺新材 | 300057 | 钠电池 | 上游设备 | related | L2_candidate | 20 |
| 中盐化工 | 600328 | 钠电池 | 世界最大金属钠制造商（钠电池上游关键原料） | related | L2 | 20 |

## 候选 6：钴金属

- **标准概念**：钴金属
- **申万一级**：-
- **评分**：154.63
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.06%，边际量 16.64%，成交额 644.87 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.06%，边际量16.64%，成交644.87亿 |
| new_high_direction | 38.63 | 新高股12只，新高成交306.43亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：稀有金属

- **标准概念**：稀有金属
- **申万一级**：-
- **评分**：150.11
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.84%，边际量 37.2%，成交额 693.36 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.84%，边际量37.2%，成交693.36亿 |
| new_high_direction | 34.11 | 新高股10只，新高成交168.56亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 稀有金属 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科三环 | 000970 | 稀有金属 | 上游材料 | core | L1_L3_candidate | 20 |
| 厦门钨业 | 600549 | 稀有金属 | 5.2 钨产业链企业分析 | core | L2_candidate | 20 |
| 新金路 | 000510 | 稀有金属 | 广西栗木锡钨钽铌矿、高纯石英砂 | core | L1_L3_candidate | 20 |
| 株冶集团 | 600961 | 稀有金属 | 产业链供应商 | core | L1_L3_candidate | 20 |
| 欧莱新材 | 688530 | 稀有金属 | 溅射靶材+高纯铟供应商 | core | L1_L3_candidate | 20 |
| 金石资源 | 603505 | 稀有金属 | 萤石开采、无水氟化氢、无水氟化铝 | related | L1_L3_candidate | 20 |
| 中矿资源 | 002738 | 稀有金属 | 全球铷矿端资源及铷盐精细化工领域龙头 | related | L1_L3_candidate | 20 |
| 国泰集团 | 603977 | 稀有金属 | 钽铌氧化物、含能材料（军工新材料）、民爆一体化、小型固体火箭发动机 | related | L1_L3_candidate | 20 |

## 候选 8：半导体封测

- **标准概念**：半导体封测
- **申万一级**：-
- **评分**：125.6
- **触发类型**：double_red、multi_period_rank
- **盘面信号**：涨幅 6.1%，边际量 14.58%，成交额 532.21 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅6.1%，边际量14.58%，成交532.21亿 |
| multi_period_rank | 19.0 | daily排名第1，区间涨幅6.1% |
| multi_period_rank | 16.6 | day3排名第4，区间涨幅20.46% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体封测 | 20 |
| 半导体 | 10 |
| 封测 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亚翔集成 | 603929 | 半导体 | IC半导体洁净室工程服务商（建厂工程核心配套） | core | L2 | 20 |
| 英唐智控 | 300131 | 半导体 | 全资子公司英唐微技术采用IDM模式研发生产光电转换和图像处理IC，提供光... | core | L2 | 20 |
| 英集芯 | 688209 | 半导体 | 专注高性能、高品质数模混合芯片设计，受益半导体国产替代与新兴应用领域拓展 | core | L2 | 20 |
| 裕太微 | 688515 | 半导体 | 以太网物理层/交换机/网卡芯片国产供应商，覆盖网通、车载、工业以太网场景... | core | L2 | 20 |
| 东芯股份 | 688110 | 半导体 | 半导体集成电路设计企业 | core | L1 | 20 |
| 中芯国际 | 688981 | 半导体 | 半导体制造和晶圆代工核心龙头 | core | L1 | 20 |
| 乐鑫科技 | 688018 | 半导体 | 数模混合物联网芯片设计商 | core | L1 | 20 |
| 线上线下 | 300959 | 半导体 | 移动信息服务（企业短信）、数字营销、深蕾科技（控股股东）— 半导体元器件... | core | L1 | 20 |

## 候选 9：电子化学品

- **标准概念**：电子化学品
- **申万一级**：基础化工
- **评分**：124.8
- **触发类型**：double_red、multi_period_rank
- **盘面信号**：涨幅 4.83%，边际量 20.51%，成交额 629.95 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.83%，边际量20.51%，成交629.95亿 |
| multi_period_rank | 17.4 | daily排名第3，区间涨幅4.83% |
| multi_period_rank | 17.4 | day3排名第3，区间涨幅20.94% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子化学品 | 20 |
| 湿电子化学品 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 上海新阳 | 300236 | 湿电子化学品 | 晶圆制造用电镀液/清洗液/研磨液/蚀刻液供应商 | core | L2 | 20 |
| 天承科技 | 688603 | 湿电子化学品 | PCB/封装载板/先进封装专用功能性湿电子化学品供应商 | core | L2 | 20 |
| 翰博高新 | - | 湿电子化学品 | 受益标的 | core | L2 | 20 |
| 江化微 | 603078 | 湿电子化学品 | 湿电子化学品相关产品/材料供应商 | related | L2 | 20 |
| 扬帆新材 | 300637 | 电子化学品 | 光引发剂907/ITX/369等系列产品，下游PCB光刻胶专用电子化学品... | core | L2 | 20 |
| 万润股份 | 002643 | 电子化学品 | 电子信息材料平台（液晶/OLED/半导体制造材料/聚酰亚胺），研发投入占... | core | L2 | 20 |
| 百合花 | 603823 | 电子化学品 | 高性能有机颜料、电子化学品级颜料（光刻胶颜料）、PEEK特种工程塑料、新... | core | L1_L3_candidate | 20 |
| 三友化工 | 600409 | 电子化学品 | 电子化学品（G5级湿电子化学品，试生产阶段） | related | L1_L3_candidate | 20 |

## 候选 10：氟概念

- **标准概念**：氟概念
- **申万一级**：-
- **评分**：122.8
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 2.78%，边际量 28.83%，成交额 803.37 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.78%，边际量28.83%，成交803.37亿 |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| limit_heat | 6.8 | 涨停8只，市场占比10.13，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-c3554417716550628ebf artifact_sha=d4dc9c7c3c5b013900e1da964498c8f85ac354e2a3ae10e927d0d46bb780e860 manifest_sha=6271a38f260370afe16392f4e24af7989b29a9d7826cba0d007ad1f3f11598f2 -->
