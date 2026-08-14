# 2026-07-20 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：27019.21
- **上涨家数**：1740
- **涨停 / 跌停**：53 / 212
- **容量前三行业**：1.电子(29.1%, super_capacity)、2.通信(8.4%, normal)、3.机械设备(7.1%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 电力 | 电力 | 公用事业 | 400.85 | double_red、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | 银行 | 银行 | 银行 | 173.81 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 油气开采及服务 | 油气 | 石油石化 | 173.4 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 4 | 白酒 | 白酒 | 食品饮料 | 167.25 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 5 | 保险 | 低空经济 | 非银金融 | 149.9 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 7 | 0 | missing_evidence |
| 6 | 煤炭开采加工 | 煤炭 | - | 135.65 | limit_heat、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 7 | 公路铁路运输 | 铁路运输 | - | 82.8 | multi_period_rank、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 8 | 风电 | 风电 | 电力设备 | 79.34 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 9 | 数据中心 | 数据中心 | 计算机 | 75.35 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 氢能源 | 氢能源 | 电力设备 | 74.88 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 数据要素 | 数据要素 | 计算机 | 71.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 汽车整车 | 汽车整车 | - | 68.8 | multi_period_rank、new_high_cluster | 5 | 9 | 0 | missing_evidence |
| 13 | 信创 | 信创 | 计算机 | 67.53 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 云计算 | 云计算 | 计算机 | 65.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 15 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 64.81 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 16 | 三胎 | 三胎 | 社会服务 | 60.7 | new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 17 | 创新药 | 创新药 | 医药生物 | 59.25 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 18 | 宠物经济 | 宠物经济 | 社会服务 | 57.67 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 19 | 燃料电池 | 燃料电池 | 电力设备 | 57.63 | new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 20 | 医疗器械 | 医疗器械 | 医药生物 | 48.58 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 空气能热泵 | 空气能热泵 | 家用电器 | 48.21 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 22 | 白色家电 | 家电 | 家用电器 | 48.17 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 23 | 量子科技 | 量子科技 | 计算机 | 48.09 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 24 | 液冷服务器 | 液冷服务器 | 电力设备 | 44.93 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 25 | 特高压 | 特高压 | 电力设备 | 44.63 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 储能 | 储能 | - | 34.55 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 27 | 港口航运 | 港口航运 | - | 32.8 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 人工智能 | 人工智能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 29 | AI智能体 | AI智能体 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 30 | 低空经济 | 低空经济 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 算力租赁 | 算力租赁 | - | 30.1 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 32 | 石油加工贸易 | 石油 | - | 29.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 33 | 高压氧舱 | 高压氧舱 | - | 28.4 | multi_period_rank | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 34 | 中药 | 中药 | - | 28.0 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 35 | 医药商业 | 医药商业 | - | 27.6 | multi_period_rank | 5 | 12 | 0 | missing_evidence |
| 36 | 传感器 | 传感器 | - | 24.7 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 37 | 煤化工 | 煤化工 | 基础化工 | 24.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 38 | 固态电池 | 固态电池 | - | 22.7 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 39 | 智能座舱 | 智能座舱 | - | 22.7 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 40 | 通信服务 | 通信服务 | - | 22.7 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 化学原料 | CXO | - | 21.05 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 42 | AI眼镜 | AI眼镜 | - | 20.7 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 43 | 证券 | 证券 | - | 9.2 | multi_period_rank | 5 | 12 | 0 | missing_evidence |
| 44 | 机场航运 | 机场 | - | 7.6 | multi_period_rank | 2 | 12 | 0 | missing_evidence |
| 45 | DRG/DIP | IP | - | 6.8 | multi_period_rank | 2 | 12 | 0 | missing_evidence |
| 46 | DeepSeek概念 | DeepSeek | - | 6.8 | limit_heat | 1 | 12 | 0 | missing_evidence |
| 47 | 机器人概念 | 机器人 | - | 6.8 | limit_heat | 2 | 12 | 0 | missing_evidence |
| 48 | 三胎概念 | 三胎概念 | - | 5.05 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 光伏概念 | 光伏 | - | 5.05 | limit_heat | 1 | 12 | 0 | missing_evidence |
| 50 | 芯片概念 | 芯片 | - | 5.05 | limit_heat | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：电力

- **标准概念**：电力
- **申万一级**：公用事业
- **评分**：400.85
- **触发类型**：double_red、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.8%，边际量 28.12%，成交额 777.83 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 125.0 | 连板股6只，最高3板，容量前三=False |
| double_red | 90.0 | 涨幅4.8%，边际量28.12%，成交777.83亿 |
| new_high_direction | 43.05 | 新高股28只，新高成交243.91亿，容量前三=False |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅5.04% |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅8.03% |
| multi_period_rank | 27.4 | daily排名第3，区间涨幅4.8% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 22.6 | day10排名第9，区间涨幅1.55% |

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

## 候选 2：银行

- **标准概念**：银行
- **申万一级**：银行
- **评分**：173.81
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 44.61 | 新高股31只，新高成交369.01000000000005亿，容量前三=False |
| multi_period_rank | 28.2 | day10排名第2，区间涨幅5.65% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | day3排名第5，区间涨幅1.65% |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅2.02% |
| multi_period_rank | 24.2 | day5排名第7，区间涨幅3.71% |

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

## 候选 3：油气开采及服务

- **标准概念**：油气
- **申万一级**：石油石化
- **评分**：173.4
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 30.35 | 新高股8只，新高成交91.79亿，容量前三=False |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅7.14% |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅10.11% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅3.74% |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 25.8 | day5排名第5，区间涨幅6.97% |
| limit_heat | 5.05 | 涨停3只，市场占比5.66，排名15 |

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

## 候选 4：白酒

- **标准概念**：白酒
- **申万一级**：食品饮料
- **评分**：167.25
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 32.45 | 新高股8只，新高成交260.19亿，容量前三=False |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅8.25% |
| multi_period_rank | 27.4 | day3排名第3，区间涨幅2.23% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅4.74% |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 25.8 | daily排名第5，区间涨幅3.79% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 白酒 | 20 |
| 节能装备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 五粮液 | 000858 | 白酒 | 千元价格带龙头 | core | - | 20 |
| 今世缘 | 603369 | 白酒 | 江苏区域酒 | peripheral | - | 20 |
| 伊力特 | 600197 | 白酒 | 新疆区域白酒龙头（中国白酒工业百强企业） | core | L2 | 20 |
| 口子窖 | 603589 | 白酒 | 安徽区域白酒 | peripheral | - | 20 |
| 古井贡酒 | 000596 | 白酒 | 安徽区域名酒龙头 | related | - | 20 |
| 天佑德酒 | 002646 | 白酒 | 青稞白酒龙头（天佑德/互助/永庆和/八大作坊/世义德品牌） | core | L2 | 20 |
| 山西汾酒 | 600809 | 白酒 | 清香白酒全国化龙头 | core | - | 20 |
| 水井坊 | 600779 | 白酒 | 高端浓香型白酒，高档产品（第一坊/水井坊系列）占酒业收入约94% | core | L2 | 20 |

## 候选 5：保险

- **标准概念**：低空经济
- **申万一级**：非银金融
- **评分**：149.9
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（7），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 27.4 | day10排名第3，区间涨幅5.14% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅7.48% |
| multi_period_rank | 26.6 | daily排名第4，区间涨幅4.51% |
| multi_period_rank | 26.6 | day3排名第4，区间涨幅2.05% |
| new_high_direction | 23.9 | 新高股3只，新高成交135.76亿，容量前三=False |
| new_high_cluster | 18.0 | 题材内新高股3只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 低空经济 | 2 |
| 新能源汽车零部件 | 2 |
| 智能交通与低空空天基础设施 | 2 |
| 汽车后市场 | 2 |
| 金融IT | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科软 | 603927 | AI应用 | 保险等行业AI技术应用方与整合方（记录型软件向约束型软件转型） | related | L2 | 1 |
| 亿航智能 | - | 低空经济 | 运营端 | core | - | 1 |
| 友升股份 | 603418 | 新能源汽车零部件 | 产品主要应用于新能源汽车领域（门槛梁/电池托盘/保险杠/副车架等） | core | L2 | 1 |
| 中信海直 | 000099 | 智能交通与低空空天基础设施 | 运营端 | core | - | 1 |
| 世纪恒通 | 301428 | 汽车后市场 | 综合性车主服务生态：为保险公司、银行、运营商、高速集团提供车主服务解决方... | core | L2 | 1 |
| 凌云股份 | 600480 | 汽车零部件 | 车身结构件（热成型/辊压/门环）、保险杠、管路系统等金属+非金属零部件供... | core | L2 | 1 |
| 新致软件 | 688590 | 金融IT | 面向银行、保险金融机构的软件服务商，布局金融知识语料库等AI技术 | core | L2 | 1 |

## 候选 6：煤炭开采加工

- **标准概念**：煤炭
- **申万一级**：-
- **评分**：135.65
- **触发类型**：limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 28.2 | daily排名第2，区间涨幅5.3% |
| multi_period_rank | 26.6 | day5排名第4，区间涨幅7.08% |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| multi_period_rank | 24.2 | day10排名第7，区间涨幅1.89% |
| multi_period_rank | 24.2 | day3排名第7，区间涨幅0.48% |
| limit_heat | 6.45 | 涨停7只，市场占比13.21，排名6 |

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

## 候选 7：公路铁路运输

- **标准概念**：铁路运输
- **申万一级**：-
- **评分**：82.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（6），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| multi_period_rank | 20.0 | day3排名第6，区间涨幅0.57% |
| multi_period_rank | 18.4 | day10排名第8，区间涨幅1.87% |
| multi_period_rank | 18.4 | day5排名第8，区间涨幅3.48% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 铁路运输 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 西部创业 | 000557 | 铁路运输 | 宁东能源化工基地区域铁路运营商，铁路运营里程315公里、总延展长度642... | core | L2 | 20 |
| 淮河能源 | 600575 | 光伏 | 火力发电、煤炭开采与销售、铁路运输、配煤贸易 | related | L1_L3_candidate | 1 |
| 中国中车 | 601766 | 央企改革 | 国务院国资委控股轨道交通制造核心央企 | peripheral | graph_only | 1 |
| 伊泰B股 | 900948 | 煤炭 | 动力煤生产运输销售一体化大型能源企业（10座煤矿+3条自营铁路） | core | L2 | 1 |
| 大秦铁路 | 601006 | 煤炭 | 铁路货运（以煤炭运输为主） | related | L1_L3_candidate | 1 |
| 昊华能源 | 601101 | 煤炭 | 动力煤生产销售、甲醇（煤化工）、铁路运输、煤炭物流 | core | L1_L3_candidate | 1 |

## 候选 8：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：79.34
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.04 | 新高股29只，新高成交243.49999999999994亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 10.3 | 涨停18只，市场占比33.96，排名1 |

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

## 候选 9：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：75.35
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.6 | 新高股22只，新高成交287.68999999999994亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比9.43，排名9 |

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

## 候选 10：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：74.88
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.13 | 新高股23只，新高成交250.37999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比9.43，排名11 |

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


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-536493128798afa7182a artifact_sha=5e944156b9551c86365f4307f705243331554c9ad78e1d78cc0fef0a67c2e279 manifest_sha=c834bb13140bc2dcb5ad441cdc015adfdfc1554ad5dbf84bad5b1642d71c1b2c -->
