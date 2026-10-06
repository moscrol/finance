# 2026-09-30 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：14377.22
- **上涨家数**：2568
- **涨停 / 跌停**：52 / 10
- **容量前三行业**：1.电子(24.9%, capacity)、2.医药生物(9.7%, normal)、3.电力设备(8.2%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 新能源车 | 新能源车 | 电力设备 | 193.91 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 2 | 医药 | 医药 | 医药生物 | 192.98 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 3 | 医药医疗 | 医疗 | 医药生物 | 187.96 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 4 | 锂电池概念 | 锂 | 电力设备 | 185.74 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 5 | 创新药 | 创新药 | 医药生物 | 185.22 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 6 | 合成生物 | 合成生物 | 医药生物 | 183.52 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 7 | AI医疗概念 | AI医疗 | 医药生物 | 178.42 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 8 | 化学制药 | 化学制药 | 医药生物 | 178.29 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 9 | 生物制药 | 生物制药 | 医药生物 | 145.34 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |
| 10 | 免疫治疗 | 免疫治疗 | 医药生物 | 140.78 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 5 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 疫苗 | 疫苗 | - | 138.4 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 分散染料 | 染料 | - | 133.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 13 | 房地产 | 房地产 | 房地产 | 126.32 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 14 | 化工 | 化工 | 基础化工 | 124.75 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 2 | - |
| 15 | CXO概念 | CXO | 医药生物 | 115.0 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 16 | 绿色电力 | 绿色电力 | 家用电器 | 101.8 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 17 | 一带一路 | 一带一路 | 房地产 | 101.51 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 18 | 住宅开发 | 住宅开发 | 房地产 | 86.23 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 3 | 0 | missing_concept、missing_evidence |
| 19 | 生物疫苗 | 疫苗 | 医药生物 | 84.93 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 20 | 风电 | 风电 | 电力设备 | 84.68 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 21 | 电力设备 | 电力设备 | 电力设备 | 84.39 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 1 | - |
| 22 | 减肥药 | 减肥药 | 医药生物 | 83.06 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 7 | 3 | - |
| 23 | 钠电池 | 钠电池 | 电力设备 | 82.16 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 3 | - |
| 24 | 氢能源 | 氢能源 | 电力设备 | 77.73 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 25 | 辅助生殖 | 辅助生殖 | 医药生物 | 75.18 | new_high_direction、new_high_cluster、capacity_industry | 2 | 9 | 1 | - |
| 26 | 数据中心 | 数据中心 | 计算机 | 73.92 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 化学制剂 | 化学制剂 | 医药生物 | 73.8 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 28 | 汽车 | 新能源汽车 | 汽车 | 73.67 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 29 | 汽车整车 | 汽车整车 | 汽车 | 73.06 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 30 | 机械设备 | 机械设备 | 机械设备 | 72.61 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 充电桩 | 充电桩 | - | 72.27 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 32 | 养老概念 | 养老概念 | - | 71.4 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 电池 | 4680大圆柱电池 | 电力设备 | 70.85 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 34 | 仿制药 | 仿制药 | 医药生物 | 69.11 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 35 | 粤港澳 | 粤港澳 | - | 68.34 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 36 | 高端装备 | 高端装备 | 机械设备 | 67.95 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 37 | 智能医疗 | 医疗 | - | 67.76 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 38 | 人形机器人 | 人形机器人 | 机械设备 | 67.75 | new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 39 | 华为汽车 | 华为汽车 | 汽车 | 67.66 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 40 | 无人机 | 无人机 | - | 67.18 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 41 | 储能 | 储能 | 电力设备 | 63.15 | limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 42 | 乡村振兴 | 乡村振兴 | 电子 | 62.45 | limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 0 | 4 | 0 | missing_concept、missing_evidence |
| 43 | 无人驾驶 | 无人驾驶 | 汽车 | 61.35 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 44 | 核电核能 | 核电 | - | 60.45 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 45 | 飞行汽车 | 飞行汽车 | 汽车 | 59.76 | new_high_direction、new_high_cluster | 1 | 8 | 1 | - |
| 46 | 冷链物流 | 冷链物流 | - | 59.3 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 47 | 工业互联 | 工业互联网 | - | 59.23 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 48 | 医疗服务 | 医疗服务 | - | 58.4 | multi_period_rank、new_high_cluster | 2 | 12 | 2 | - |
| 49 | 婴童概念 | 婴童概念 | 食品饮料 | 55.75 | limit_heat、limit_advance_cluster、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | 换电概念 | 换电 | - | 55.11 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：新能源车

- **标准概念**：新能源车
- **申万一级**：电力设备
- **评分**：193.91
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股2只，最高4板，容量前三=True |
| new_high_direction | 44.71 | 新高股55只，新高成交376.87300000000005亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比23.08，排名1 |

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
| 北京双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 华鲁恒升 | 600426 | 新能源 | 煤化工平台向新能源新材料延伸，新能源新材料已成第一大产品 | core | L2 | 20 |
| 双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 固德威 | 688390 | 新能源 | 固德威年报披露的新能源相关主营业务 | core | L2 | 20 |
| 浙江新能 | 600032 | 新能源 | 风光水综合型可再生能源发电企业（控股装机690.76万千瓦） | core | L2 | 20 |
| 润建股份 | 002929 | 新能源 | 新能源电站（光伏/风力/储能）开发建设运维全生命周期服务商 | core | L2 | 20 |
| 涪陵电力 | 600452 | 新能源 | 涪陵电力年报披露的新能源相关主营业务 | core | L2 | 20 |
| 珠海港 | 000507 | 新能源 | 新能源板块收入24.7亿元占比56.34%（风电珠海港昇+管道燃气） | core | L2 | 20 |

## 候选 2：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：192.98
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.4961%，边际量 42.3573%，成交额 1027.8783 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4961%，边际量42.3573%，成交1027.8783亿 |
| new_high_direction | 54.43 | 新高股47只，新高成交354.5067000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| multi_period_rank | 6.8 | daily排名第10，区间涨幅2.5% |
| limit_heat | 5.75 | 涨停5只，市场占比9.62，排名14 |

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
| 丽珠集团 | 000513 | 医药 | 大型综合性医药集团，中国医药工业百强榜第27位 | core | L2 | 20 |
| 华润江中 | 600750 | 医药 | 非处方药、处方药与健康消费品并举的医药制造企业 | core | L2 | 20 |
| 复星医药 | 600196 | 医药 | 以创新药为发展重点的综合医药健康集团，业务覆盖制药、医疗器械与医学诊断、... | core | L2 | 20 |
| 寿仙谷 | 603896 | 医药 | 灵芝、铁皮石斛等名贵中药材育种-栽培-饮片炮制-深加工全产业链中药企业 | core | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 康芝药业 | 300086 | 医药 | 国内领先的儿童药生产销售企业（儿童大健康） | core | L2 | 20 |

## 候选 3：医药医疗

- **标准概念**：医疗
- **申万一级**：医药生物
- **评分**：187.96
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.0898%，边际量 35.7543%，成交额 1376.43 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.0898%，边际量35.7543%，成交1376.43亿 |
| new_high_direction | 55.16 | 新高股74只，新高成交412.87900000000013亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比15.38，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗 | 10 |
| 医药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 创新医疗 | 002173 | 医疗 | 医疗服务提供商，营收和利润主要来源于医疗服务 | core | L2 | 20 |
| 嘉事堂 | 002462 | 医疗 | 嘉事堂年报披露的医疗相关主营业务 | core | L2 | 20 |
| 常铝股份 | 002160 | 医疗 | 常铝股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 昊海生科 | 688366 | 医疗 | 昊海生科年报披露的医疗相关主营业务 | related | L2 | 20 |
| 朗姿股份 | 002612 | 医疗 | 朗姿股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 欧林生物 | 688319 | 医疗 | 欧林生物年报披露的医疗相关主营业务 | related | L2 | 20 |
| 航亚科技 | 688510 | 医疗 | 航亚科技年报披露的医疗相关主营业务 | related | L2 | 20 |
| 丽珠集团 | 000513 | 医药 | 大型综合性医药集团，中国医药工业百强榜第27位 | core | L2 | 20 |

## 候选 4：锂电池概念

- **标准概念**：锂
- **申万一级**：电力设备
- **评分**：185.74
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 111.0 | 连板股2只，最高3板，容量前三=True |
| new_high_direction | 42.29 | 新高股32只，新高成交182.87579999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比13.46，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 锂 | 10 |
| 锂电池 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亿纬锂能 | 300014 | 锂电池 | 消费/动力/储能全场景锂电池平台公司，覆盖锂原、小型锂电、圆柱、方形铁锂... | core | L2 | 20 |
| 先导智能 | 300450 | 锂电池 | 锂电池智能制造装备供应商，服务动力/储能方壳与圆柱产线 | core | L2 | 20 |
| 利元亨 | 688499 | 锂电池 | 锂电池产线智能制造装备供应商，收入高度绑定下游锂电客户资本开支 | core | L2 | 20 |
| 华盛锂电 | 688353 | 锂电池 | VC、FEC相关产品/服务商 | core | L2 | 20 |
| 国轩高科 | 002074 | 锂电池 | 新能源锂电池制造商与绿色能源综合解决方案服务商，聚焦动力电池与储能电池 | core | L2 | 20 |
| 多氟多 | 002407 | 锂电池 | "氟芯"大圆柱电池制造商，2025年底新能源电池产能达20GWh，产品覆... | core | L2 | 20 |
| 天力锂能 | 301152 | 锂电池 | 动力/储能锂电池正极材料及碳酸锂供应 | core | L2 | 20 |
| 天华新能 | 300390 | 锂电池 | 锂离子电池正极材料原材料供应商，服务动力电池与储能电池 | core | L2 | 20 |

## 候选 5：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：185.22
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.4181%，边际量 42.891%，成交额 1016.0485 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4181%，边际量42.891%，成交1016.0485亿 |
| new_high_direction | 53.82 | 新高股39只，新高成交305.5641亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 5.4 | 涨停4只，市场占比7.69，排名19 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 20 |
| 创新药RWA | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一品红 | 300723 | 创新药 | 核心创新药AR882为高效选择性URAT1抑制剂，覆盖降尿酸治疗痛风、溶... | core | L2 | 20 |
| 三生国健 | 688336 | 创新药 | 医药制造业、医药制造相关产品/服务商 | core | L2 | 20 |
| 上海谊众 | 688091 | 创新药 | 抗肿瘤创新药企业：紫杉醇胶束等纳米制剂，研产销一体化 | core | L2 | 20 |
| 亿帆医药 | 002019 | 创新药 | 医药+维生素B5双主业，创新生物药亿立舒全球销售 | core | L2 | 20 |
| 众生药业 | 002317 | 创新药 | 抗流感一类创新药昂拉地韦片（全球首个靶向PB2亚基口服抗流感药） | core | L2 | 20 |
| 凯因科技 | 688687 | 创新药 | 化学药品、生物药品相关产品/服务商 | core | L2 | 20 |
| 华东医药 | 000963 | 创新药 | 内分泌、自身免疫和肿瘤三大核心治疗领域创新药研发与商业化公司 | core | L2 | 20 |
| 南新制药 | 688189 | 创新药 | 抗流感创新药领军企业：帕拉米韦氯化钠注射液为国内首个上市的抗流感1.1类... | core | L2 | 20 |

## 候选 6：合成生物

- **标准概念**：合成生物
- **申万一级**：医药生物
- **评分**：183.52
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.8224%，边际量 24.9406%，成交额 509.6609 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.8224%，边际量24.9406%，成交509.6609亿 |
| new_high_direction | 52.12 | 新高股25只，新高成交169.48340000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 5.4 | 涨停4只，市场占比7.69，排名20 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 合成生物 | 20 |
| 合成生物学 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凯赛生物 | 688065 | 合成生物 | 合成生物材料研发生产商，规模化生产生物基新材料 | core | L2 | 20 |
| 华恒生物 | 688639 | 合成生物 | 以合成生物技术为核心的生物基产品制造商 | core | L2 | 20 |
| 华熙生物 | 688363 | 合成生物 | 合成生物驱动的生物活性物制造商，透明质酸生物制造全球领先 | core | L2 | 20 |
| 楚天科技 | 300358 | 合成生物 | 制药装备及整体技术解决方案 | core | L1_L3_candidate | 20 |
| 蔚蓝生物 | 603739 | 合成生物 | 以酶制剂、微生态制剂、动物保健品为核心的生物科技企业，为生物制造提供核心... | core | L2 | 20 |
| 锦波生物 | 832982 | 合成生物 | 山西省重点产业链合成生物产业链“链主”企业，通过AI驱动合成生物学生产重... | core | L2 | 20 |
| 中油工程 | 600339 | 合成生物 | 合成生物学等） | related | L1_L3_candidate | 20 |
| 共同药业 | 300966 | 合成生物 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 20 |

## 候选 7：AI医疗概念

- **标准概念**：AI医疗
- **申万一级**：医药生物
- **评分**：178.42
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.3511%，边际量 28.2094%，成交额 503.6504 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.3511%，边际量28.2094%，成交503.6504亿 |
| new_high_direction | 52.42 | 新高股21只，新高成交193.96909999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI医疗 | 10 |
| 医疗 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 创新医疗 | 002173 | AI医疗 | AI医疗布局 | core | L2 | 20 |
| 麦迪科技 | 603990 | AI医疗 | 医疗信息化（急危重症CIS）、康养陪伴机器人、低空医疗救援、辅助生殖医疗... | core | L1_L3_candidate | 20 |
| 东华软件 | 002065 | AI医疗 | 医疗AI应用落地方（智能病历生成、临床决策支持、医疗垂类模型矩阵） | related | L2 | 20 |
| 久远银海 | 002777 | AI医疗 | 医疗医保AI智能体与自研大模型应用开发商（“久问”医疗智能体、“闻语”大... | related | L2 | 20 |
| 华大智造 | 688114 | AI医疗 | 全读长测序业务、多组学业务、智能自动化业务 | related | L1_L3_candidate | 20 |
| 卫宁健康 | 300253 | AI医疗 | 医疗垂直大模型与医护智能助手提供商，将AI能力植入诊疗流程、公共卫生与数... | related | L2 | 20 |
| 朗玛信息 | 300288 | AI医疗 | 医学大模型产品商（39AI医生，国内首个通过国家备案的医学大模型） | related | L2 | 20 |
| 翔宇医疗 | 688626 | AI医疗 | 脑机接口康复设备 | related | L2 | 20 |

## 候选 8：化学制药

- **标准概念**：化学制药
- **申万一级**：医药生物
- **评分**：178.29
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.1155%，边际量 40.9748%，成交额 566.4955 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.1155%，边际量40.9748%，成交566.4955亿 |
| new_high_direction | 52.29 | 新高股24只，新高成交182.94749999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 化学制药 | 20 |
| 制药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 九洲药业 | 603456 | 制药 | 小分子CDMO、TIDES（多肽、小核酸 | related | L1_L3_candidate | 20 |
| 亚虹医药 | 688176 | 制药 | 抗肿瘤仿制药（欧优比 | related | L1_L3_candidate | 20 |
| 共同药业 | 300966 | 制药 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 20 |
| 圣诺生物 | 688117 | 制药 | 多肽原料药、CDMO、制剂 | related | L1_L3_candidate | 20 |
| 复星医药 | 600196 | 制药 | 创新药（PD-1、PD-L1 ADC、HER2单抗） | related | L1_L3_candidate | 20 |
| 上海医药 | 601607 | 制药 | 覆盖化学生物药、现代中药与医疗器械的大型医药工业企业（约800个药品品规... | core | L2 | 20 |
| 振东制药 | 300158 | 制药 | 中成药+化药双线制药企业（核心品种复方苦参注射液、米诺地尔搽剂、西黄丸、... | core | L2 | 20 |
| 灵康药业 | 603669 | 制药 | 化学药品制剂制造企业，55个品种入国家医保目录 | core | L2 | 20 |

## 候选 9：生物制药

- **标准概念**：生物制药
- **申万一级**：医药生物
- **评分**：145.34
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.14 | 新高股23只，新高成交171.5592亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅4.27% |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅3.56% |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅12.3% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 生物制药 | 20 |
| 制药 | 10 |
| 生物制药上游 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亚虹医药 | 688176 | 制药 | 抗肿瘤仿制药（欧优比 | related | L1_L3_candidate | 20 |
| 圣诺生物 | 688117 | 制药 | 多肽原料药、CDMO、制剂 | related | L1_L3_candidate | 20 |
| 川宁生物 | 301301 | 制药 | 抗生素中间体（硫氰酸红霉素、6-APA、7-ACA）+ 合成生物学（麦角... | related | L1_L3_candidate | 20 |
| 上海医药 | 601607 | 制药 | 覆盖化学生物药、现代中药与医疗器械的大型医药工业企业（约800个药品品规... | core | L2 | 20 |
| 振东制药 | 300158 | 制药 | 中成药+化药双线制药企业（核心品种复方苦参注射液、米诺地尔搽剂、西黄丸、... | core | L2 | 20 |
| 灵康药业 | 603669 | 制药 | 化学药品制剂制造企业，55个品种入国家医保目录 | core | L2 | 20 |
| 药明康德 | 603259 | 制药 | 药明康德年报披露的制药相关主营业务 | core | L2 | 20 |
| 三力制药 | 603439 | 制药 | 中成药的研发、生产和销售、核心产品为开喉剑喷雾剂系列 | related | L2 | 20 |

## 候选 10：免疫治疗

- **标准概念**：免疫治疗
- **申万一级**：医药生物
- **评分**：140.78
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（5），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.38 | 新高股17只，新高成交190.2509亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 22.4 | day10排名第3，区间涨幅12.5% |
| multi_period_rank | 21.6 | daily排名第4，区间涨幅3.52% |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅2.79% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 免疫治疗 | 20 |
| 细胞免疫治疗 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 百济神州 | 688235 | 免疫治疗 | 图谱弱关联 | peripheral | graph_only | 20 |
| 东富龙 | 300171 | 细胞免疫治疗 | 上游材料/设备 | related | L1_L3_candidate | 20 |
| 和元生物 | 688238 | 细胞免疫治疗 | 4.2.1 CDMO 服务提供商 | related | L1_L3_candidate | 20 |
| 复星医药 | 600196 | 细胞免疫治疗 | 7.2.2 复星医药：CAR-T 商业化的先行者 | related | L1_L3_candidate | 20 |
| 冠昊生物 | 300238 | CAR-T | 再生医学材料（硬脑膜补片）、药业（本维莫德）、细胞技术服务 | related | L1_L3_candidate | 1 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-36ed343a78163a219e3e artifact_sha=ca037c5c7457f95f29f54153459fabb2ba3993254c1b39504b6948f2246fc0c5 manifest_sha=a5cc636419762609821a559eb2b67e1136a83e96c595ac2bc15f2dd5fd26cf86 -->
