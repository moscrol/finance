# 2026-07-24 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：19352.8
- **上涨家数**：534
- **涨停 / 跌停**：40 / 24
- **容量前三行业**：1.电子(29.6%, super_capacity)、2.电力设备(8.0%, normal)、3.通信(6.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 连板未映射 | - | 电力设备 | 195.0 | limit_advance_cluster、capacity_industry | 0 | 0 | 0 | placeholder_market_theme |
| 2 | 油气开采及服务 | 油气 | 石油石化 | 132.51 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 3 | 电力 | 电力 | 电力设备 | 127.48 | limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 4 | 房地产 | 房地产 | 房地产 | 110.05 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 银行 | 银行 | - | 87.6 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 风电 | 风电 | 电力设备 | 84.98 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 7 | 氢能源 | 氢能源 | 电力设备 | 78.55 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 8 | 数据中心 | 数据中心 | 计算机 | 72.87 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 无人驾驶 | 无人驾驶 | 汽车 | 71.64 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 商业航天 | 商业航天 | 国防军工 | 71.12 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 可控核聚变 | 可控核聚变 | 电力设备 | 60.7 | limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 12 | 军工装备 | 军工装备 | - | 58.65 | limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 煤炭开采加工 | 煤炭 | - | 58.4 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 14 | 军工 | 军工 | 国防军工 | 57.15 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 港口航运 | 港口航运 | - | 54.4 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 16 | 金属铅 | 金属铅 | - | 50.4 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 金属锌 | 有色金属 | - | 48.4 | multi_period_rank、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 18 | 电网设备 | 电网设备 | - | 43.35 | limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 2 | - |
| 19 | 毫米波雷达 | 毫米波雷达 | 汽车 | 41.38 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 半导体设备 | 半导体设备 | - | 37.9 | limit_heat、multi_period_rank | 5 | 12 | 5 | - |
| 21 | 保险 | 低空经济 | - | 33.2 | multi_period_rank | 5 | 7 | 0 | missing_evidence |
| 22 | 贵金属 | 贵金属 | - | 33.2 | multi_period_rank | 5 | 12 | 1 | - |
| 23 | 钢铁 | 钢铁 | - | 32.8 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 24 | 人工智能 | 人工智能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 储能 | 储能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 26 | 海峡两岸 | 海峡两岸 | - | 32.1 | limit_heat、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 27 | AI应用 | AI应用 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 28 | 先进封装 | 先进封装 | - | 31.4 | limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 29 | 数据要素 | 数据要素 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 30 | 医疗器械 | 医疗器械 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 特高压 | 特高压 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 传感器 | 传感器 | - | 29.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 信创 | 信创 | - | 29.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 公路铁路运输 | 铁路运输 | - | 26.4 | multi_period_rank、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 35 | 机器视觉 | 机器视觉 | - | 25.05 | limit_heat、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 36 | 金属钴 | 金属钴 | - | 24.4 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 高压氧舱 | 高压氧舱 | - | 23.6 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 军工信息化 | 军工信息化 | - | 23.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 液冷服务器 | 液冷服务器 | - | 23.05 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 40 | 半导体 | 半导体 | - | 18.25 | limit_heat、multi_period_rank | 5 | 12 | 1 | - |
| 41 | 存储芯片 | 存储芯片 | - | 16.2 | limit_heat、multi_period_rank | 5 | 12 | 5 | - |
| 42 | 锂 | 锂 | - | 14.0 | multi_period_rank | 1 | 2 | 1 | - |
| 43 | 能源金属 | 盐湖提锂 | - | 12.4 | multi_period_rank | 2 | 6 | 0 | missing_evidence |
| 44 | 光刻机 | 光刻机 | - | 11.6 | multi_period_rank | 5 | 12 | 2 | - |
| 45 | 白酒 | 白酒 | - | 9.2 | multi_period_rank | 2 | 12 | 2 | - |
| 46 | 汽车服务及其他 | 汽车服务及其他 | - | 8.4 | multi_period_rank | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 电子化学品 | 电子化学品 | - | 7.6 | multi_period_rank | 5 | 12 | 1 | - |
| 48 | 金属镍 | 金属镍 | - | 7.6 | multi_period_rank | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 氟化工 | 氟化工 | - | 6.8 | multi_period_rank | 5 | 12 | 2 | - |
| 50 | 芯片概念 | 芯片 | - | 6.45 | limit_heat | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：连板未映射

- **标准概念**：-
- **申万一级**：电力设备
- **评分**：195.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 195.0 | 连板股12只，最高4板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 2：油气开采及服务

- **标准概念**：油气
- **申万一级**：石油石化
- **评分**：132.51
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 36.11 | 新高股12只，新高成交104.74000000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | day10排名第1，区间涨幅8.61% |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅4.84% |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅8.02% |

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

## 候选 3：电力

- **标准概念**：电力
- **申万一级**：电力设备
- **评分**：127.48
- **触发类型**：limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.68 | 新高股17只，新高成交134.29999999999998亿，容量前三=False |
| limit_advance_cluster | 33.0 | 连板股1只，最高3板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.0 | day10排名第6，区间涨幅2.59% |
| multi_period_rank | 11.8 | day5排名第10，区间涨幅2.36% |

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

## 候选 4：房地产

- **标准概念**：房地产
- **申万一级**：房地产
- **评分**：110.05
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| limit_heat | 5.05 | 涨停3只，市场占比7.5，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 房地产 | 20 |
| 房地产服务 | 5 |
| 免税 | 2 |
| 冰雪旅游 | 2 |
| 减水剂 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万科A | 000002 | 房地产 | 住宅开发企业 | peripheral | graph_only | 20 |
| 三湘印象 | 000863 | 房地产 | 地产开发与经营业务 | core | L2 | 20 |
| 世联行 | 002285 | 房地产 | 房地产相关产品/材料供应商 | related | L2 | 20 |
| 中国建筑 | 601668 | 房地产 | 旗下中海地产等房地产开发平台 | related | L2 | 20 |
| 中国武夷 | 000797 | 房地产 | 福建国资背景房地产开发商 | core | L2 | 20 |
| 中洲控股 | 000042 | 房地产 | 区域城市综合运营商（聚焦粤港澳大湾区、成渝、上海） | core | L2 | 20 |
| 华丽家族 | 600503 | 房地产 | 房地产主业、创新药投资（海和药物）、机器人业务（南江机器人）、石墨烯业务 | core | L1_L3_candidate | 20 |
| 南山控股 | 002314 | 房地产 | 房地产开发与产业园区业务定位为优化提升业务，以保障现金流安全、提升运营效... | related | L2 | 20 |

## 候选 5：银行

- **标准概念**：银行
- **申万一级**：-
- **评分**：87.6
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| multi_period_rank | 22.4 | daily排名第3，区间涨幅-0.24% |
| multi_period_rank | 22.4 | day10排名第3，区间涨幅4.96% |
| multi_period_rank | 16.8 | day3排名第10，区间涨幅1.05% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 银行 | 20 |
| 银行IT | 5 |
| AI应用 | 2 |
| 供应链金融 | 2 |
| 信创 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兴业银行 | 601166 | 银行 | 全国性股份制商业银行，以银行为主体的现代综合金融服务集团（2007年上交... | core | L2 | 20 |
| 北京银行 | 601169 | 银行 | 银行相关产品/材料供应商 | related | L2 | 20 |
| 南京银行 | 601009 | 银行 | 城商行——公司金融、零售金融、金融市场三大板块 | core | L2 | 20 |
| 宁波银行 | 002142 | 银行 | 优质城商行 | core | L2 | 20 |
| 紫金银行 | 601860 | 银行 | 总部位于江苏南京的地方法人农村商业银行，主营存贷款、票据贴现等传统银行业... | core | L2 | 20 |
| 西安银行 | 600928 | 银行 | 深耕陕西本土的城商行，业务含公司金融、零售金融、普惠金融，推进“数智西银... | core | L2 | 20 |
| 齐鲁银行 | 601665 | 银行 | 银行相关产品/材料供应商 | related | L2 | 20 |
| 天阳科技 | 300872 | 银行IT | 银行信贷/信用卡等核心系统IT服务商 | core | L2 | 20 |

## 候选 6：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：84.98
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.88 | 新高股34只，新高成交230.04999999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比15.0，排名3 |

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

## 候选 7：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：78.55
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.55 | 新高股38只，新高成交204.16000000000008亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 氢能源 | 20 |
| 氢能 | 10 |
| SOFC燃料电池 | 2 |
| 压缩机 | 2 |
| 天然气 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 氢能 | 重型燃气轮机与综合电力装备供应商，布局自主G50燃机、引进型燃机、电站服... | related | L1_L3_candidate | 20 |
| 中国中车 | 601766 | 氢能 | 氢能 | related | L1_L3_candidate | 20 |
| 中国能建 | 601868 | 氢能 | 氢能 | related | L1_L3_candidate | 20 |
| 中复神鹰 | 688295 | 氢能 | 高性能碳纤维生产销售（T700-T1200、M系列全覆盖） | related | L1_L3_candidate | 20 |
| 中材科技 | 002080 | 氢能 | 特种玻纤布、风电叶片、锂电池隔膜 | related | L1_L3_candidate | 20 |
| 佛燃能源 | 002911 | 氢能 | 氢能装备（隔膜压缩机） | related | L1_L3_candidate | 20 |
| 冰轮环境 | 000811 | 氢能 | AIDC冷水机组（一次侧）、冷链装备、能源化工装备 | related | L1_L3_candidate | 20 |
| 卧龙新能 | 600173 | 氢能 | AEM制氢技术实现兆瓦级产品交付 | related | L2 | 20 |

## 候选 8：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：72.87
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.47 | 新高股18只，新高成交117.96000000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比10.0，排名10 |

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
| 中仑新材 | 301565 | AI数据中心 | BOPP新能源膜材（薄膜电容器基膜）、功能性BOPA膜材、生物降解BOP... | related | L1_L3_candidate | 20 |
| 中国西电 | 601179 | AI数据中心 | 特高压设备、主网一次设备、海外电力设备 | related | L1_L3_candidate | 20 |
| 亨通光电 | 600487 | AI数据中心 | 特别是AI数据中心需求驱动的光纤业务 | core | L1_L3_candidate | 20 |
| 京泉华 | 002885 | AI数据中心 | MFT高频变压器（AI数据中心） | related | L1_L3_candidate | 20 |
| 佛燃能源 | 002911 | AI数据中心 | 城市燃气（天然气销售与输配）、能源化工服务及延伸（油品/化工品贸易）、绿... | related | L1_L3_candidate | 20 |
| 天齐锂业 | 002466 | AI数据中心 | 锂矿采选、锂化工产品（碳酸锂、氢氧化锂 | related | L1_L3_candidate | 20 |
| 宏微科技 | 688711 | AI数据中心 | AI数据中心电源 | related | L1_L3_candidate | 20 |
| 宗申动力 | 001696 | AI数据中心 | 通用机械、摩托车发动机、航空动力 | related | L1_L3_candidate | 20 |

## 候选 9：无人驾驶

- **标准概念**：无人驾驶
- **申万一级**：汽车
- **评分**：71.64
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 40.59 | 新高股15只，新高成交127.09999999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比7.5，排名26 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 无人驾驶 | 20 |
| Robotaxi | 2 |
| 低空经济 | 2 |
| 农机 | 2 |
| 智能交通与低空空天基础设施 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万集科技 | 300552 | 无人驾驶 | 激光雷达/MEMS固态雷达供应商，适配城市NOA与L4客车场景 | related | L1_L3_candidate | 20 |
| 万马科技 | 300698 | 无人驾驶 | 率先推出L4级无人驾驶高阶网联解决方案，与无人驾驶头部企业合作落地，并开... | core | L2 | 20 |
| 保隆科技 | 603197 | 无人驾驶 | 毫米波雷达与汽车传感器供应商 | related | L2_candidate | 20 |
| 千里科技 | 601777 | 无人驾驶 | Robotaxi闭环平台服务商 | related | L1_L3_candidate | 20 |
| 四维图新 | 002405 | 无人驾驶 | 高精地图与智能驾驶数据服务商 | related | L1_L3_candidate | 20 |
| 富临运业 | 002357 | 无人驾驶 | 公路客运运营商，与新石器合营切入L4无人驾驶物流，布局四川文旅低空物流 | related | L1_L3_candidate | 20 |
| 德赛西威 | 002920 | 无人驾驶 | 智能驾驶域控制器供应商 | related | L1_L3_candidate | 20 |
| 拓普集团 | 601689 | 无人驾驶 | 智能底盘供应商 | peripheral | L1 | 20 |

## 候选 10：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：71.12
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 40.07 | 新高股15只，新高成交85.68亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比7.5，排名22 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 20 |
| 商业航天光学载荷 | 5 |
| AI算力基础设施 | 2 |
| SOFC燃料电池 | 2 |
| 东数西算 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 受益标的 | core | L3 | 20 |
| 三角防务 | 300775 | 商业航天 | 航空、航天、船舶等行业锻件产品的研制 | related | L1_L3_candidate | 20 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 20 |
| 上海瀚讯 | 300762 | 商业航天 | 卫星通信载荷、地面信关站、用户终端 | core | L1_L3_candidate | 20 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 20 |
| 东方钽业 | 000962 | 商业航天 | 钽铌铍金属及合金制品 | core | L1_L3_candidate | 20 |
| 中国卫通 | 601698 | 商业航天 | 应用端 | core | L2 | 20 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-cc650b69aec750a159c2 artifact_sha=c6bc16b12e2ba2bf3df651457bcc98bdb588ba3de5d24d20252161f428de37ab manifest_sha=6d5c4c76e674451b90bc638018f3bdc3c90a4735bdc2092d16ed4b56a7a117e5 -->
