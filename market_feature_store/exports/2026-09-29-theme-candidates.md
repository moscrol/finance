# 2026-09-29 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：14090.71
- **上涨家数**：3471
- **涨停 / 跌停**：57 / 11
- **容量前三行业**：1.电子(25.3%, super_capacity)、2.电力设备(8.2%, normal)、3.机械设备(7.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 新能源车 | 新能源车 | 汽车 | 172.93 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 房地产 | 房地产 | - | 132.1 | limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 3 | 风电零部件 | 风电零部件 | 电力设备 | 131.84 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 4 | 风电设备 | 风电设备 | 电力设备 | 129.29 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 5 | 锂电池概念 | 锂 | 电力设备 | 105.5 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 6 | 出版业 | 出版 | - | 100.0 | multi_period_rank | 1 | 12 | 0 | missing_evidence |
| 7 | 数据中心 | 数据中心 | 计算机 | 99.88 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 电力设备 | 电力设备 | 电力设备 | 78.23 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 1 | - |
| 9 | 风电 | 风电 | 电力设备 | 77.77 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 10 | 高端装备 | 高端装备 | 机械设备 | 77.67 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 一带一路 | 一带一路 | - | 73.45 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 12 | 医药医疗 | 医疗 | 医药生物 | 67.53 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 13 | 绿色电力 | 绿色电力 | - | 67.39 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 14 | 医药 | 医药 | 医药生物 | 67.11 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 工业互联 | 工业互联网 | - | 65.43 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 16 | 无人驾驶 | 无人驾驶 | 汽车 | 63.57 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 17 | 传媒 | 传媒 | 传媒 | 62.1 | limit_heat、limit_advance_cluster、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 18 | 汽车 | 新能源汽车 | 汽车 | 60.41 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 19 | 机器人概念 | 机器人 | 家用电器 | 57.15 | limit_heat、limit_advance_cluster、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 20 | 粤港澳 | 粤港澳 | 房地产 | 57.15 | limit_heat、limit_advance_cluster、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 21 | 储能 | 储能 | 公用事业 | 56.8 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 5 | - |
| 22 | 车联网 | 车联网 | - | 56.29 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 23 | 飞行汽车 | 飞行汽车 | 汽车 | 56.27 | new_high_direction、new_high_cluster | 1 | 8 | 1 | - |
| 24 | 冷链物流 | 冷链物流 | - | 56.25 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 25 | 虚拟现实 | 虚拟现实 | - | 56.24 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 26 | 无线耳机 | 无线耳机 | 电子 | 54.61 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | 住宅开发 | 住宅开发 | - | 52.95 | limit_heat、multi_period_rank、new_high_cluster | 0 | 3 | 0 | missing_concept、missing_evidence |
| 28 | 小家电 | 小家电 | - | 50.8 | multi_period_rank、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 29 | 创新药 | 创新药 | 医药生物 | 50.0 | limit_advance_cluster、new_high_cluster | 2 | 12 | 5 | - |
| 30 | 化工 | 化工 | 基础化工 | 50.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 2 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 汽车整车 | 汽车整车 | - | 49.2 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 32 | 锂电设备 | 锂电设备 | - | 48.4 | multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 33 | 换电概念 | 换电 | - | 44.87 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 34 | 诊断试剂 | 诊断试剂 | - | 44.4 | multi_period_rank、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 35 | 医疗服务 | 医疗服务 | - | 39.2 | multi_period_rank、new_high_cluster | 2 | 12 | 2 | - |
| 36 | CXO概念 | CXO | - | 36.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 37 | 电池 | 4680大圆柱电池 | - | 36.0 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 38 | 固态电池 | 固态电池 | - | 33.5 | limit_heat、new_high_cluster | 3 | 12 | 5 | - |
| 39 | 疫苗 | 疫苗 | - | 33.2 | multi_period_rank | 5 | 12 | 1 | - |
| 40 | 人工智能 | 人工智能 | - | 33.15 | limit_heat、new_high_cluster | 3 | 12 | 1 | - |
| 41 | DeepSeek概念 | DeepSeek | - | 32.8 | limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | 东数西算 | 东数西算 | - | 32.8 | limit_heat、new_high_cluster | 1 | 12 | 2 | - |
| 43 | 电子 | EDA（电子设计自动化） | - | 32.8 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 44 | 低空经济 | 低空经济 | - | 32.45 | limit_heat、new_high_cluster | 2 | 12 | 3 | - |
| 45 | 抖音概念 | 抖音概念 | - | 32.45 | limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 数据要素 | 数据要素 | - | 32.45 | limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 47 | 无人机 | 无人机 | - | 32.45 | limit_heat、new_high_cluster | 3 | 12 | 1 | - |
| 48 | 乡村振兴 | 乡村振兴 | - | 32.1 | limit_heat、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 49 | AIGC概念 | AIGC | - | 31.75 | limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 50 | 区块链 | 区块链 | - | 31.75 | limit_heat、new_high_cluster | 1 | 9 | 1 | - |

## 五、核心候选明细

## 候选 1：新能源车

- **标准概念**：新能源车
- **申万一级**：汽车
- **评分**：172.93
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股2只，最高4板，容量前三=False |
| new_high_direction | 42.43 | 新高股28只，新高成交194.5662亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比17.54，排名4 |

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

## 候选 2：房地产

- **标准概念**：房地产
- **申万一级**：-
- **评分**：132.1
- **触发类型**：limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 25.8 | daily排名第5，区间涨幅3.66% |
| multi_period_rank | 25.0 | day10排名第6，区间涨幅6.82% |
| multi_period_rank | 25.0 | day5排名第6，区间涨幅1.09% |
| multi_period_rank | 24.2 | day3排名第7，区间涨幅0.61% |
| limit_heat | 6.1 | 涨停6只，市场占比10.53，排名24 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 房地产 | 20 |
| 房地产服务 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万科A | 000002 | 房地产 | 全国性住宅开发龙头房企，聚焦"好房子"产品体系（拾系、庐系），连续10年... | core | L2 | 20 |
| 三湘印象 | 000863 | 房地产 | 地产开发与经营业务 | core | L2 | 20 |
| 中国武夷 | 000797 | 房地产 | 福建国资背景房地产开发商 | core | L2 | 20 |
| 中洲控股 | 000042 | 房地产 | 区域城市综合运营商（聚焦粤港澳大湾区、成渝、上海） | core | L2 | 20 |
| 华丽家族 | 600503 | 房地产 | 专注高端改善型住宅的精品房地产开发商，代表项目包括上海檀宫、苏州太湖檀宫 | core | L2 | 20 |
| 天地源 | 600665 | 房地产 | 房地产开发商（控股股东西安高科集团） | core | L2 | 20 |
| 天宸股份 | 600620 | 房地产 | 天宸健康城项目开发与物业租赁 | core | L2 | 20 |
| 招商蛇口 | 001979 | 房地产 | 全国头部住宅开发商（2025年签约销售额1960.09亿元、行业排名第四... | core | L2 | 20 |

## 候选 3：风电零部件

- **标准概念**：风电零部件
- **申万一级**：电力设备
- **评分**：131.84
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 40.24 | 新高股8只，新高成交83.5694亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 24.0 | day10排名第1，区间涨幅8.41% |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅3.2% |
| multi_period_rank | 17.6 | day5排名第9，区间涨幅0.76% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电零部件 | 20 |
| 风电 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三一重能 | 688349 | 风电 | 风电整机厂商：风机全产业链（核心部件自主研发、整机一体化集成）+风电场设... | core | L2 | 20 |
| 中环海陆 | 301040 | 风电 | 风电轴承/法兰/齿圈锻件供应商（国家级专精特新小巨人） | core | L2 | 20 |
| 中船科技 | 600072 | 风电 | 中船系风电整机制造商（风电收入75.63亿元，装机高峰放量） | core | L2 | 20 |
| 光威复材 | 300699 | 风电 | 风电碳梁等拉挤碳纤维复合材料标准型材制造商 | core | L2 | 20 |
| 国投电力 | 600886 | 风电 | 雅砻江流域水电梯级开发、水风光一体化清洁能源基地、火电（煤电+燃气）、风... | core | L1_L3_candidate | 20 |
| 大唐发电 | 601991 | 风电 | 风电装机约1,120万千瓦，布局全国资源富集区域 | core | L2 | 20 |
| 天晟新材 | 300169 | 风电 | 风电叶片夹芯结构泡沫材料供应 | core | L2 | 20 |
| 威力传动 | 300904 | 风电 | 风电齿轮箱国内市场前列供应商 | core | L2 | 20 |

## 候选 4：风电设备

- **标准概念**：风电设备
- **申万一级**：电力设备
- **评分**：129.29
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.69 | 新高股9只，新高成交86.8049亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅2.73% |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅7.05% |
| multi_period_rank | 16.8 | day5排名第10，区间涨幅0.5% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电设备 | 20 |
| 风电 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三一重能 | 688349 | 风电 | 风电整机厂商：风机全产业链（核心部件自主研发、整机一体化集成）+风电场设... | core | L2 | 20 |
| 中环海陆 | 301040 | 风电 | 风电轴承/法兰/齿圈锻件供应商（国家级专精特新小巨人） | core | L2 | 20 |
| 中船科技 | 600072 | 风电 | 中船系风电整机制造商（风电收入75.63亿元，装机高峰放量） | core | L2 | 20 |
| 光威复材 | 300699 | 风电 | 风电碳梁等拉挤碳纤维复合材料标准型材制造商 | core | L2 | 20 |
| 国投电力 | 600886 | 风电 | 雅砻江流域水电梯级开发、水风光一体化清洁能源基地、火电（煤电+燃气）、风... | core | L1_L3_candidate | 20 |
| 大唐发电 | 601991 | 风电 | 风电装机约1,120万千瓦，布局全国资源富集区域 | core | L2 | 20 |
| 天晟新材 | 300169 | 风电 | 风电叶片夹芯结构泡沫材料供应 | core | L2 | 20 |
| 威力传动 | 300904 | 风电 | 风电齿轮箱国内市场前列供应商 | core | L2 | 20 |

## 候选 5：锂电池概念

- **标准概念**：锂
- **申万一级**：电力设备
- **评分**：105.5
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.3 | 新高股24只，新高成交103.85419999999999亿，容量前三=False |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比21.05，排名2 |

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

## 候选 6：出版业

- **标准概念**：出版
- **申万一级**：-
- **评分**：100.0
- **触发类型**：multi_period_rank
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅2.28% |
| multi_period_rank | 25.0 | day3排名第6，区间涨幅0.89% |
| multi_period_rank | 23.4 | day10排名第8，区间涨幅6.6% |
| multi_period_rank | 22.6 | daily排名第9，区间涨幅3.16% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 出版 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国出版 | 601949 | 出版 | 央企出版龙头（商务印书馆、人民文学出版社、中华书局等），图书零售市场占有... | core | L2 | 20 |
| 果麦文化 | 301052 | 出版 | 新闻和出版业、图书策划与发行相关产品/服务商 | core | L2 | 20 |
| 读客文化 | 301025 | 出版 | 新闻和出版业、纸质图书相关产品/服务商 | core | L2 | 20 |
| 读者传媒 | 603999 | 出版 | 新闻出版业务、教材教辅相关产品/服务商 | core | L2 | 20 |
| 新华文轩 | 601811 | 出版 | 出版相关产品/服务商 | related | L2 | 20 |
| 中国科传 | 601858 | 出版 | 科技出版国家队（科学出版社），SCIE收录期刊130种 | core | L2 | 20 |
| 世纪天鸿 | 300654 | 出版 | 教辅图书的策划相关产品供应商 | related | L2 | 20 |
| 凤凰传媒 | 601928 | 出版 | 出版相关产品/服务商 | related | L2 | 20 |

## 候选 7：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：99.88
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.68 | 新高股18只，新高成交134.5488亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 8.2 | 涨停12只，市场占比21.05，排名1 |

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

## 候选 8：电力设备

- **标准概念**：电力设备
- **申万一级**：电力设备
- **评分**：78.23
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.23 | 新高股26只，新高成交178.235亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电力设备 | 20 |
| 电力 | 10 |
| 数据中心电力设备 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 伊戈尔 | 002922 | 数据中心电力设备 | 数据中心移相/油浸/干式变压器及供电系统供应商 | related | L2 | 20 |
| 雅达股份 | 920556 | 数据中心电力设备 | 数据中心配电监测用电力测控仪表/装置/传感器供应商，为PUE指标计算提供... | related | L2 | 20 |
| 明阳电气 | 301291 | 数据中心电力设备 | 数据中心供电与算力供电方向输配电设备布局方 | peripheral | L2 | 20 |
| 中恒电气 | 002364 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 四方股份 | 601126 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 科士达 | 002518 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 金盘科技 | 688676 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 天富能源 | 600509 | 电力 | 电力相关产品/材料供应商 | related | L2 | 20 |

## 候选 9：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：77.77
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.77 | 新高股19只，新高成交141.5514亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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
| 振华重工 | 600320 | 海上风电 | 港口机械、海工装备、钢结构 | core | L1_L3_candidate | 20 |
| 新天绿能 | 600956 | 海上风电 | 风力发电、天然气全产业链、海上风电、燃气热电联产 | core | L1_L3_candidate | 20 |
| 东方电气 | 600875 | 海上风电 | 中游制造 | core | L1_L3_candidate | 20 |
| 东方电缆 | 603606 | 海上风电 | 5.2.3 海缆系统企业 | core | L1_L3_candidate | 20 |
| 太阳电缆 | 002300 | 海上风电 | 海底电缆、高压电力电缆、特种电缆 | core | L2 | 20 |
| 明阳智能 | 601615 | 海上风电 | 中游制造 | core | L1_L3_candidate | 20 |
| 江苏国信 | 002608 | 海上风电 | 火力发电、热力生产、信托金融、海上风电（参股） | core | L1_L3_candidate | 20 |

## 候选 10：高端装备

- **标准概念**：高端装备
- **申万一级**：机械设备
- **评分**：77.67
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.67 | 新高股19只，新高成交133.4255亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 高端装备 | 20 |
| 高端装备与自主可控制造 | 5 |
| 高端装备制造 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 通裕重工 | 300185 | 高端装备 | 能源电力/石化/船舶/海工/核电等大型装备核心部件平台 | related | L2 | 20 |
| 三花智控 | 002050 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 光威复材 | 300699 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 德赛西威 | 002920 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 拓普集团 | 601689 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 汇川技术 | 300124 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 航天电子 | 600879 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 莱斯信息 | 688631 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-2c23617cd1f65d9474ec artifact_sha=b63f68ed976e0fb186479a7ce53a969dc1e0f261cce11ba7c20684add5deec55 manifest_sha=32f36531d95fe1a59de27c39d63df116afbfd0645739db4d8923a8039765f1dd -->
