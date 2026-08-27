# 2026-08-25 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：18316.26
- **上涨家数**：4234
- **涨停 / 跌停**：65 / 2
- **容量前三行业**：1.电子(24.8%, capacity)、2.通信(8.8%, normal)、3.机械设备(7.9%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 碳中和 | 碳中和 | - | 158.04 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 2 | 特高压 | 特高压 | 电力设备 | 153.45 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 3 | 光纤光缆 | 光纤光缆 | - | 115.57 | multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 4 | 股权 | 私募股权投资 | 机械设备 | 115.0 | limit_advance_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 5 | 贵金属 | 贵金属 | - | 80.8 | limit_advance_cluster、multi_period_rank、new_high_cluster | 4 | 12 | 1 | - |
| 6 | 新能源车 | 新能源车 | - | 80.32 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 数据中心 | 数据中心 | 计算机 | 79.16 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 人形机器人 | 人形机器人 | 机械设备 | 78.74 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 9 | 一带一路 | 一带一路 | - | 78.0 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 10 | 通用设备 | 通用设备 | 机械设备 | 77.16 | new_high_direction、new_high_cluster、capacity_industry | 0 | 7 | 0 | missing_concept、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 东数西算 | 东数西算 | - | 76.8 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 12 | 石油化工 | 化工 | - | 76.8 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 13 | 液冷服务器 | 液冷服务器 | 电力设备 | 76.2 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 14 | 煤炭 | 煤炭 | 电力设备 | 76.0 | limit_advance_cluster、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 15 | 机械设备 | 机械设备 | - | 75.91 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 16 | 锂电池概念 | 锂 | - | 75.26 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 17 | 充电桩 | 充电桩 | - | 75.0 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 18 | 化工 | 化工 | - | 74.5 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 19 | 绿色电力 | 绿色电力 | - | 74.04 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 20 | 腾讯概念 | 腾讯概念 | - | 73.92 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 21 | 新零售 | 零售 | - | 73.71 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 22 | 工业互联 | 工业互联网 | - | 73.31 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 23 | 物联网 | 物联网 | - | 73.25 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 24 | 高端装备 | 高端装备 | - | 73.02 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 25 | 抖音概念 | 抖音概念 | - | 70.23 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 26 | 阿里概念 | 阿里概念 | - | 69.65 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | 风电 | 风电 | 电力设备 | 69.23 | new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 28 | 特斯拉概念 | 特斯拉概念 | - | 68.48 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 29 | 国防军工 | 国防军工 | - | 68.39 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 30 | 无人机 | 无人机 | - | 68.35 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 智能电网 | 智能电网 | - | 68.15 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 32 | 氢能源 | 氢能源 | 电力设备 | 67.89 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 33 | 核电核能 | 核电 | - | 67.8 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 34 | 粤港澳 | 粤港澳 | - | 67.73 | new_high_direction、new_high_cluster | 0 | 10 | 0 | missing_concept、missing_evidence |
| 35 | 商业航天 | 商业航天 | 国防军工 | 67.57 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 36 | 小米概念 | 小米概念 | - | 67.52 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 汽车热管理 | 汽车热管理 | - | 67.43 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 38 | 区块链 | 区块链 | - | 67.39 | new_high_direction、new_high_cluster | 1 | 6 | 1 | - |
| 39 | 无人驾驶 | 无人驾驶 | 汽车 | 67.38 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 40 | 通信设备 | 通信设备 | 通信 | 67.19 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 41 | 冷链物流 | 冷链物流 | - | 67.16 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 42 | 虚拟现实 | 虚拟现实 | - | 67.06 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 43 | 医药 | 医药 | 医药生物 | 65.1 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 苹果概念 | 苹果概念 | - | 63.58 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 有色 | 有色冶炼装备 | - | 63.03 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 46 | CPO概念 | CPO | - | 61.88 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 47 | 中特估 | 中特估 | - | 60.76 | new_high_direction、new_high_cluster | 1 | 0 | 1 | missing_entity_exposures |
| 48 | 黄金概念 | 黄金 | - | 59.78 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 49 | 百度概念 | 百度概念 | - | 57.82 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | 高压快充 | 高压快充 | 电力设备 | 57.71 | new_high_direction、new_high_cluster | 0 | 6 | 0 | missing_concept、missing_evidence |

## 五、核心候选明细

## 候选 1：碳中和

- **标准概念**：碳中和
- **申万一级**：-
- **评分**：158.04
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.62%，边际量 11.55%，成交额 748.7 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.62%，边际量11.55%，成交748.7亿 |
| new_high_direction | 42.04 | 新高股38只，新高成交162.9199999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 碳中和 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华测检测 | 300012 | 碳中和 | 检测认证服务 | related | L1_L3_candidate | 20 |
| 岳阳林纸 | 600963 | 碳中和 | 浆纸主业、碳汇开发、生物基新材料 | related | L1_L3_candidate | 20 |
| 汉钟精机 | 002158 | 碳中和 | AIDC液冷压缩机、半导体真空泵、光伏真空泵 | related | L1_L3_candidate | 20 |
| 上海建科 | 603153 | 碳中和 | 环境低碳技术服务 | related | L2 | 20 |
| 凯赛生物 | 688065 | 碳中和 | 生物制造化学品（长链二元酸系列）、生物高分子材料（生物基聚酰胺系列） | related | L1_L3_candidate | 20 |
| 启迪设计 | 300500 | 碳中和 | 聚焦绿色低碳建筑与双碳目标解决方案，布局光伏发电项目设计、智慧园区、AI... | related | L2 | 20 |
| 联检科技 | 301115 | 碳中和 | 国家级绿色制造体系第三方评价机构、零碳工厂评价认证服务机构，提供CBAM... | related | L2 | 20 |
| 海螺水泥 | 600585 | 供给侧改革 | 水泥熟料自产销售、骨料、商品混凝土 | related | L1_L3_candidate | 1 |

## 候选 2：特高压

- **标准概念**：特高压
- **申万一级**：电力设备
- **评分**：153.45
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.46%，边际量 10.17%，成交额 913.9 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.46%，边际量10.17%，成交913.9亿 |
| new_high_direction | 37.45 | 新高股12只，新高成交212.35999999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 特高压 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 许继电气 | 000400 | 特高压 | 中国电力装备行业领先企业，直流输电系统核心供应商，聚焦特高压等五大核心业... | core | L2 | 20 |
| 国缆检测 | 301289 | 特高压 | 电线电缆及光纤光缆检验检测、电化学储能检测、超高压、特高压检测 | core | L1_L3_candidate | 20 |
| 太阳电缆 | 002300 | 特高压 | 海底电缆、高压电力电缆、特种电缆 | core | L2 | 20 |
| 新能泰山 | 000720 | 特高压 | 电线电缆生产（高压、超高压电缆、电力电缆、特种电缆 | core | L1 | 20 |
| 杭电股份 | 603618 | 特高压 | 光通信（光纤光缆）、电力电缆、铜箔 | core | L1_L3_candidate | 20 |
| 汇源通信 | 000586 | 特高压 | 电力光缆（OPGW、ADSS）、输电线路在线监测、车载LED封装 | core | L2 | 20 |
| 球冠电缆 | 920682 | 特高压 | 电力电缆、电气装备线缆、裸电线、高压特种电缆 | core | L1_L3_candidate | 20 |
| 胜业电气 | 920128 | 特高压 | 薄膜电容器、电能质量治理配套产品 | core | L2 | 20 |

## 候选 3：光纤光缆

- **标准概念**：光纤光缆
- **申万一级**：-
- **评分**：115.57
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 25.17 | 新高股4只，新高成交125.74000000000001亿，容量前三=False |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅5.74% |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅4.89% |
| multi_period_rank | 23.2 | day10排名第2，区间涨幅12.39% |
| new_high_cluster | 20.0 | 题材内新高股4只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光纤光缆 | 20 |
| 光纤 | 10 |
| 光缆 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 大族激光 | 002008 | 光纤 | 激光加工设备龙头，子公司投建年产6000万芯公里光纤及预制棒产能 | related | L3 | 20 |
| 长芯博创 | 300548 | 光纤 | 受益标的 | related | L2 | 20 |
| 特发信息 | 000070 | 光纤光缆 | 光纤光缆老牌厂商（华南规模领先基地，深圳/东莞/重庆/常州/赣州/枣庄/... | core | L2 | 20 |
| 杭电股份 | 603618 | 光纤光缆 | 光通信（光纤光缆）、电力电缆、铜箔 | core | L1_L3_candidate | 20 |
| 泰和新材 | 002254 | 光纤光缆 | 对位芳纶（光纤光缆用）、氨纶 | core | L2 | 20 |
| 通光线缆 | 300265 | 光纤光缆 | 光纤光缆（含OPGW、ADSS电力光缆、G.654.E高端光纤）、输电线... | core | L1_L3_candidate | 20 |
| 三孚股份 | 603938 | 光纤光缆 | 硅系列产品（三氯氢硅、四氯化硅、高纯四氯化硅、电子特气等） | related | L2 | 20 |
| 中天科技 | 600522 | 光纤光缆 | 光缆供应商 | related | L3 | 20 |

## 候选 4：股权

- **标准概念**：私募股权投资
- **申万一级**：机械设备
- **评分**：115.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股3只，最高2板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 私募股权投资 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 四川双马 | 000935 | 私募股权投资 | 私募股权投资基金管理业务 | related | L2 | 20 |
| 万丰奥威 | 002085 | 低空经济 | 通用飞机制造业务（收购钻石飞机55%股权起步），形成汽车轻量化+通航飞机... | core | L2 | 1 |
| 海伦哲 | 300201 | 储能消防 | 储能消防（气溶胶灭火）、高空作业车、电力应急保障车、军品及消防车 | core | L1_L3_candidate | 1 |
| 巍华新材 | 603310 | 农药中间体 | 含氟农药/医药中间体供应商（部分为专利期内关键中间体），并沿产业链向原药... | core | L2 | 1 |
| 旭杰科技 | 920149 | 分布式光伏 | 分布式光伏电站系统集成商（转售+投资运营+EPC），2025年该业务收入... | core | L2 | 1 |
| 中晶科技 | 003026 | 功率半导体 | 半导体功率芯片及器件制造商（广泛应用于微波炉、激光打印机、X光机、高压电... | core | L2 | 1 |
| 小崧股份 | 002723 | 小家电 | 可充电照明/风扇等智能生活家电制造商 | core | L2 | 1 |
| 洲际油气 | 600759 | 油气 | 中亚在产+中东开发中的境外油气资产上市平台（哈萨克斯坦马腾/克山+伊拉克... | core | L2 | 1 |

## 候选 5：贵金属

- **标准概念**：贵金属
- **申万一级**：-
- **评分**：80.8
- **触发类型**：limit_advance_cluster、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 30.0 | 连板股1只，最高4板，容量前三=False |
| multi_period_rank | 19.0 | day5排名第1，区间涨幅8.42% |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| multi_period_rank | 15.8 | day10排名第5，区间涨幅10.23% |

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

## 候选 6：新能源车

- **标准概念**：新能源车
- **申万一级**：-
- **评分**：80.32
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 46.82 | 新高股84只，新高成交545.3000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比15.38，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新能源车 | 20 |
| 新能源 | 10 |
| 新能源车出海 | 5 |
| 新能源车热管理 | 5 |
| 新能源车齿轮 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云铝股份 | 000807 | 新能源 | 电解铝冶炼、铝加工、氧化铝 | related | L1_L3_candidate | 20 |
| 北京双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 浙江新能 | 600032 | 新能源 | 风光水综合型可再生能源发电企业（控股装机690.76万千瓦） | core | L2 | 20 |
| 润建股份 | 002929 | 新能源 | 新能源电站（光伏/风力/储能）开发建设运维全生命周期服务商 | core | L2 | 20 |
| 珠海港 | 000507 | 新能源 | 新能源板块收入24.7亿元占比56.34%（风电珠海港昇+管道燃气） | core | L2 | 20 |
| 越秀资本 | 000987 | 新能源 | 户用分布式光伏与风电电站持有运营方（期末管理装机15.52GW、其中控股... | core | L2 | 20 |
| 万润新能 | 688275 | 新能源 | 动力电池及储能电池核心化学品原料配套商 | core | L1 | 20 |
| 中天科技 | 600522 | 新能源 | 新能源业务平台 | core | L1 | 20 |

## 候选 7：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：79.16
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.31 | 新高股39只，新高成交425.09000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比16.92，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 20 |
| AI数据中心 | 5 |
| AI数据中心储能 | 5 |
| AI数据中心电源 | 5 |
| IDC数据中心 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亨通光电 | 600487 | AI数据中心 | 特别是AI数据中心需求驱动的光纤业务 | core | L1_L3_candidate | 20 |
| 中国西电 | 601179 | AI数据中心 | 特高压设备、主网一次设备、海外电力设备 | related | L1_L3_candidate | 20 |
| 京泉华 | 002885 | AI数据中心 | MFT高频变压器（AI数据中心） | related | L1_L3_candidate | 20 |
| 天齐锂业 | 002466 | AI数据中心 | 锂矿采选、锂化工产品（碳酸锂、氢氧化锂 | related | L1_L3_candidate | 20 |
| 宗申动力 | 001696 | AI数据中心 | 通用机械、摩托车发动机、航空动力 | related | L1_L3_candidate | 20 |
| 应流股份 | 603308 | AI数据中心 | 燃气轮机叶片、航空发动机部件、核能装备 | related | L1_L3_candidate | 20 |
| 思源电气 | 002028 | AI数据中心 | 高压开关、变压器、超级电容（AIDC） | related | L1_L3_candidate | 20 |
| 振华股份 | 603067 | AI数据中心 | 铬盐系列产品（金属铬、重铬酸钠、铬酸酐 | related | L1_L3_candidate | 20 |

## 候选 8：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：78.74
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.74 | 新高股26只，新高成交219.6亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人形机器人 | 20 |
| 机器人 | 12 |
| 人形机器人丝杠 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三瑞智能 | 301696 | 人形机器人 | CubeMars品牌深耕机器人关节：机器人电机、驱动板、高度集成动力模组 | core | L2 | 20 |
| 东阳光 | 600673 | 人形机器人 | 具身智能（人形机器人） | core | L1_L3_candidate | 20 |
| 中控技术 | 688777 | 人形机器人 | TPT工业大模型、DCS、SIS控制系统、UCS通用控制系统 | core | L1_L3_candidate | 20 |
| 五洲新春 | 603667 | 人形机器人 | 机器人执行器核心零部件丝杠供应商 | core | L2 | 20 |
| 兆威机电 | 003021 | 人形机器人 | 机器人灵巧手业务（具身智能业务） | core | L1_L3_candidate | 20 |
| 博众精工 | 688097 | 人形机器人 | 人形机器人组装线 | core | L1_L3_candidate | 20 |
| 唯科科技 | 301196 | 人形机器人 | MPO光通信零部件、机器人轻量化部件、新能源汽车零部件、精密注塑模具 | core | L1_L3_candidate | 20 |
| 科德数控 | 688305 | 人形机器人 | 五轴联动数控机床、高档数控系统、关键功能部件 | core | L1_L3_candidate | 20 |

## 候选 9：一带一路

- **标准概念**：一带一路
- **申万一级**：-
- **评分**：78.0
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 44.15 | 新高股85只，新高成交331.91000000000014亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比16.92，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 一带一路 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中色股份 | 000758 | 一带一路 | 有色金属国际工程承包先行者 | core | L2 | 20 |
| 中工国际 | 002051 | 一带一路 | 深度参与国家重大区域建设与一带一路的工程央企 | related | L2 | 20 |
| 陕建股份 | 600248 | 一带一路 | 海外工程承包商，出海企业增至17家，海外新签合同额创历史新高 | related | L2 | 20 |
| 天津港 | 600717 | 一带一路 | 海陆交汇点、新亚欧大陆桥经济走廊重要节点 | related | L2 | 20 |
| 四川路桥 | 600039 | 一带一路 | 延链补链的海外/跨区域工程拓展 | related | L2 | 20 |
| 中铁工业 | 600528 | 一带一路 | 轨道及桥梁建设装备海外出口商 | peripheral | graph_only | 20 |
| 铁建重工 | 688425 | 一带一路 | 图谱弱关联 | peripheral | graph_only | 20 |
| 炬华科技 | 300360 | 仪器仪表 | 国内能源计量仪表行业头部制造商，具备国产自主CPU高端智慧计量电能表 | core | L2 | 1 |

## 候选 10：通用设备

- **标准概念**：通用设备
- **申万一级**：机械设备
- **评分**：77.16
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（7），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.16 | 新高股31只，新高成交92.61000000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光格科技 | 688450 | AIoT | 分布式光纤传感、AIoT资产运维、四足巡检机器人 | core | L2 | 1 |
| 东方中科 | 002819 | AI安全 | 测试技术与服务（占比~81%）、数字安全与数智应用（占比~19%） | related | L2 | 1 |
| 必创科技 | 300667 | CPO | 精密光机（六轴并联平台/耦合台）、光电仪器（光谱仪/光源/检测系统）、智... | related | L1_L3_candidate | 1 |
| 云涌科技 | 688060 | 信创 | 国产化平台通用设备（信创业务） | related | L2 | 1 |
| 瑜欣电子 | 301107 | 工业电机 | 1) 通用机械行业景气度、2) 新能源产品增长、3) 机器人关节电机合作... | related | L1_L3_candidate | 1 |
| 中核科技 | 000777 | 工业阀门 | 核工程阀门、核聚变阀门、石油石化阀门 | related | L1_L3_candidate | 1 |
| 绿的谐波 | 688017 | 机器人零部件 | 谐波减速器、机电一体化执行器、行星滚柱丝杠 | related | L1_L3_candidate | 1 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-bd07829a99be449b67e9 artifact_sha=6daad40b328b1dd327bc41c63ef3e5457cb009fea8d4b93fe7bffe6433837e00 manifest_sha=fe03f1c9d3802f7a3135869b479b283495ea1a8807457e035dd9f34795dd1209 -->
