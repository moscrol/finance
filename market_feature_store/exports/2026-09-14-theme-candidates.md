# 2026-09-14 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：16283.51
- **上涨家数**：3126
- **涨停 / 跌停**：55 / 16
- **容量前三行业**：1.电子(26.3%, super_capacity)、2.通信(8.6%, normal)、3.机械设备(7.3%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PCB | PCB | 电子 | 200.72 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 2 | 元器件 | 电子元器件 | 电子 | 196.25 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 3 | 新能源车 | 新能源车 | 电力设备 | 187.45 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 数据中心 | 数据中心 | 计算机 | 173.33 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 电力 | 电力 | 公用事业 | 92.58 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 电子 | EDA（电子设计自动化） | 电子 | 90.15 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 7 | PCB概念 | PCB概念 | - | 89.51 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 8 | 培育钻石 | 培育钻石 | - | 87.6 | multi_period_rank、new_high_cluster | 1 | 9 | 1 | - |
| 9 | 水力发电 | 水力发电 | - | 87.6 | multi_period_rank、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 10 | 先进封装 | 先进封装 | 电子 | 84.96 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 人形机器人 | 人形机器人 | 机械设备 | 79.45 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 12 | 商业航天 | 商业航天 | 国防军工 | 78.35 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 13 | MiniLED | Mini LED | 电子 | 78.26 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 14 | 机械设备 | 机械设备 | 机械设备 | 77.56 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 15 | CPO概念 | CPO | - | 77.11 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 16 | 国防军工 | 国防军工 | 国防军工 | 77.08 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 17 | 光纤光缆 | 光纤光缆 | - | 76.4 | multi_period_rank、new_high_cluster | 3 | 12 | 5 | - |
| 18 | 无人驾驶 | 无人驾驶 | 汽车 | 76.32 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 19 | 无人机 | 无人机 | - | 76.3 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 20 | 存储芯片 | 存储芯片 | 电子 | 76.11 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 21 | 东数西算 | 东数西算 | - | 75.83 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 22 | 锂电池概念 | 锂 | - | 75.66 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 23 | 充电桩 | 充电桩 | - | 75.61 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 24 | 工业互联 | 工业互联网 | - | 75.61 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 25 | 毫米波雷达 | 毫米波雷达 | 汽车 | 75.32 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 26 | 卫星导航 | 卫星导航 | - | 74.38 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 27 | 数据要素 | 数据要素 | 计算机 | 74.18 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 28 | 信息安全 | 信息安全 | 计算机 | 73.74 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 29 | 智能穿戴 | 智能穿戴 | 电子 | 70.95 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 30 | 一带一路 | 一带一路 | - | 68.71 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 风电 | 风电 | 电力设备 | 68.37 | new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 32 | 物联网 | 物联网 | - | 68.32 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 33 | 粤港澳 | 粤港澳 | - | 68.13 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 34 | AI眼镜 | AI眼镜 | 电子 | 68.12 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 35 | 特斯拉概念 | 特斯拉概念 | - | 67.95 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 36 | 阿里概念 | 阿里概念 | - | 67.93 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 小米概念 | 小米概念 | - | 67.88 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 腾讯概念 | 腾讯概念 | - | 67.86 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 39 | 绿色电力 | 绿色电力 | - | 67.81 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 40 | 国产软件 | 软件 | 计算机 | 67.75 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 41 | 信创 | 信创 | 计算机 | 67.5 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 车联网 | 车联网 | - | 67.5 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 43 | 云计算 | 云计算 | 计算机 | 67.49 | new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 44 | 公用事业 | 公用事业 | 公用事业 | 67.47 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 45 | 计算机 | 计算机外设 | 计算机 | 67.45 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 46 | 区块链 | 区块链 | - | 67.36 | new_high_direction、new_high_cluster | 1 | 9 | 1 | - |
| 47 | 软件服务 | 软件 | 计算机 | 67.35 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 48 | 折叠屏 | 折叠屏 | 电子 | 66.63 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 1 | - |
| 49 | 抖音概念 | 抖音概念 | - | 66.62 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | AI手机PC | AI手机 | 电子 | 65.31 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：200.72
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 55.82 | 新高股25只，新高成交465.7038000000002亿，容量前三=True |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅11.35% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅8.4% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅11.99% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | daily排名第5，区间涨幅3.09% |
| limit_heat | 6.1 | 涨停6只，市场占比10.91，排名25 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 20 |
| 1.6T交换机PCB | 5 |
| AI PCB | 5 |
| AIPCB专用油墨 | 5 |
| AI服务器PCB | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | PCB | 全球电子电路（软板+硬板+软硬结合板）平台型制造商，高多层PCB/高阶H... | core | L2 | 21 |
| 沪电股份 | 002463 | PCB | 受益标的 | core | L2 | 21 |
| 天承科技 | 688603 | PCB | 受益于AI算力驱动的高多层板/HDI/封装基板需求 | core | L2 | 21 |
| 本川智能 | 300964 | PCB | 中高端PCB定制化制造商，以通信设备为核心，布局汽车电子、新能源、AI服... | core | L2 | 21 |
| 胜宏科技 | 300476 | PCB | 高密度印制线路板制造商 | core | L2 | 21 |
| 三孚新科 | 688359 | PCB | 高端PCB电镀专用化学品与电镀设备供应商 | related | L2 | 21 |
| 超颖电子 | 603175 | PCB | 汽车电子PCB供应商，布局高多层服务器板、汽车板、存储板等高阶PCB产能 | related | L1_L3_candidate | 21 |
| 容大感光 | 300576 | AIPCB专用油墨 | PCB光刻胶/高端油墨核心验证标的 | core | L1_L3_candidate | 20 |

## 候选 2：元器件

- **标准概念**：电子元器件
- **申万一级**：电子
- **评分**：196.25
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 56.15 | 新高股27只，新高成交492.23670000000016亿，容量前三=True |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅7.21% |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅9.53% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅7.74% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅2.84% |
| limit_heat | 6.1 | 涨停6只，市场占比10.91，排名27 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元器件 | 5 |
| 电子元器件分销 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华安鑫创 | 300928 | 电子元器件 | 通用器件分销相关产品/服务商 | core | L2 | 20 |
| 国力电子 | 688103 | 电子元器件 | 电子真空器件、直流接触器相关产品/服务商 | core | L2 | 20 |
| 利和兴 | 301013 | 电子元器件 | 向新型电子元器件领域拓展（孙公司利和兴电子），客户含摩尔线程、蓝思科技、... | related | L2 | 20 |
| 三友联众 | 300932 | 电子元器件 | 继电器相关产品供应商 | related | L2 | 20 |
| 灿勤科技 | 688182 | 电子元器件 | 高端先进电子陶瓷元器件相关产品供应商 | related | L2 | 20 |
| 中电港 | 001287 | 电子元器件分销 | 本土元器件分销商龙头（连续6年首位，近140条授权产品线） | core | L2 | 20 |
| 新亚制程 | 002388 | 电子元器件分销 | 电子信息产品销售服务为第一大业务，2025年收入13.45亿元（占比69... | core | L2 | 20 |
| 英唐智控 | 300131 | 电子元器件分销 | 电子元器件分销商，产品类型含被动元件、存储类、触控显示类、半导体类、模块... | core | L2 | 20 |

## 候选 3：新能源车

- **标准概念**：新能源车
- **申万一级**：电力设备
- **评分**：187.45
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股4只，最高2板，容量前三=False |
| new_high_direction | 46.5 | 新高股67只，新高成交520.1294亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.95 | 涨停17只，市场占比30.91，排名1 |

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

## 候选 4：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：173.33
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 93.0 | 连板股2只，最高3板，容量前三=False |
| new_high_direction | 45.43 | 新高股42只，新高成交434.76000000000016亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.9 | 涨停14只，市场占比25.45，排名2 |

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

## 候选 5：电力

- **标准概念**：电力
- **申万一级**：公用事业
- **评分**：92.58
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.38 | 新高股27只，新高成交110.2393亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 12.6 | day10排名第9，区间涨幅4.17% |
| multi_period_rank | 12.6 | day5排名第9，区间涨幅3.12% |

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
| 伊戈尔 | 002922 | 数据中心电力设备 | 数据中心移相/油浸/干式变压器及供电系统供应商 | related | L2 | 20 |
| 雅达股份 | 920556 | 数据中心电力设备 | 数据中心配电监测用电力测控仪表/装置/传感器供应商，为PUE指标计算提供... | related | L2 | 20 |
| 明阳电气 | 301291 | 数据中心电力设备 | 数据中心供电与算力供电方向输配电设备布局方 | peripheral | L2 | 20 |
| 中恒电气 | 002364 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 四方股份 | 601126 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 科士达 | 002518 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 金盘科技 | 688676 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 国电南瑞 | 600406 | 新型电力系统 | 新型电力系统核心装备与控制技术供应商，布局构网型储能、源网荷储与大电网运... | core | L2 | 20 |

## 候选 6：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：90.15
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 57.35 | 新高股40只，新高成交587.7109亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比14.55，排名20 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| EDA（电子设计自动化） | 5 |
| LED电子器件 | 5 |
| 军工电子 | 5 |
| 柔性电子 | 5 |
| 水声电子防务 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士 | 000660 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 上海新阳 | 300236 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中科蓝讯 | 688332 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中芯国际 | 688981 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中际旭创 | 300308 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 乐鑫科技 | 688018 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 兆易创新 | 603986 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 全志科技 | 300458 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 7：PCB概念

- **标准概念**：PCB概念
- **申万一级**：-
- **评分**：89.51
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 47.51 | 新高股37只，新高成交600.8684000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 9.2 | day3排名第7，区间涨幅1.24% |
| limit_heat | 6.8 | 涨停8只，市场占比14.55，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB概念 | 20 |
| PCB | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一博科技 | 301366 | PCB | PCB研发设计服务细分行业引领者，一站式硬件创新平台（设计+制板+PCB... | core | L2 | 20 |
| 万源通 | 920060 | PCB | 内资PCB企业第39位（CPCA 2024榜单），单/双/多层板+HDI... | core | L2 | 20 |
| 世运电路 | 603920 | PCB | 硬板营收49.19亿元/毛利率16.67%/同比+9.93% | core | L2 | 20 |
| 东山精密 | 002384 | PCB | 全球电子电路（软板+硬板+软硬结合板）平台型制造商，高多层PCB/高阶H... | core | L2 | 20 |
| 中京电子 | 002579 | PCB | PCB厂商：刚性板+柔性板，LED封装印制电路板具备省级研发平台 | core | L2 | 20 |
| 中富电路 | 300814 | PCB | 高可靠性定制化PCB制造商（通信及数据中心、工业控制、汽车电子等领域） | core | L2 | 20 |
| 依顿电子 | 603328 | PCB | 汽车电子、计算与通信、工控医疗、新能源及电源、多媒体与显示用PCB供应商 | core | L2 | 20 |
| 则成电子 | 920821 | PCB | 高精密线路板制造商（自研FIPIS细间距减除法，具备线宽/线距15μm/... | core | L2 | 20 |

## 候选 8：培育钻石

- **标准概念**：培育钻石
- **申万一级**：-
- **评分**：87.6
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅3.69% |
| multi_period_rank | 22.4 | day10排名第3，区间涨幅9.28% |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| multi_period_rank | 20.0 | day5排名第6，区间涨幅5.01% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 培育钻石 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中兵红箭 | 000519 | 培育钻石 | 培育钻石上游超硬材料平台 | related | L1_L3_candidate | 20 |
| 力量钻石 | 301071 | 培育钻石 | 上游材料 | related | L2_candidate | 20 |
| 博云新材 | 002297 | 培育钻石 | 硬质合金（碳化钨）、C919刹车系统、碳 | related | L1_L3_candidate | 20 |
| 四方达 | 300179 | 培育钻石 | 上游材料 | related | L1_L3_candidate | 20 |
| 国机精工 | 002046 | 培育钻石 | 上游设备 | related | L1_L3_candidate | 20 |
| 惠丰钻石 | 839725 | 培育钻石 | 下游应用/客户 | related | L1_L3_candidate | 20 |
| 黄河旋风 | 600172 | 培育钻石 | 黄河旋风年报披露的培育钻石相关主营业务 | related | L2 | 20 |
| 沃尔德 | 688028 | 培育钻石 | 上游设备 | peripheral | L1 | 20 |

## 候选 9：水力发电

- **标准概念**：水力发电
- **申万一级**：-
- **评分**：87.6
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 20.8 | day10排名第5，区间涨幅6.99% |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅5.21% |
| multi_period_rank | 20.0 | day3排名第6，区间涨幅2.47% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 湖北能源 | 000883 | 光伏 | 水力发电、火力发电、新能源发电 | related | L1_L3_candidate | 1 |
| 兴发集团 | 600141 | 化工 | 化工相关产品/材料供应商 | related | L2 | 1 |
| 大唐发电 | 601991 | 容量电价 | 火力发电（煤电+燃机）、水力发电、风力发电、光伏发电 | related | L1_L3_candidate | 1 |
| 长江电力 | 600900 | 抽水蓄能 | 大型水力发电、配售电、国际水电运营、抽水蓄能 | core | L1_L3_candidate | 1 |
| 华能水电 | 600025 | 水电 | 澜沧江流域梯级水电开发运营龙头，西电东送核心电源 | core | L2 | 1 |
| 国电电力 | 600795 | 水电 | 流域梯级水电开发运营商，大渡河、开都河及伊犁河水电为调峰调频主力 | core | L2 | 1 |
| 华电国际 | 600027 | 水电 | 兼营水力发电项目，四川水电贡献增量电量 | related | L2 | 1 |
| 罗平锌电 | 002114 | 水电 | 水力发电相关产品供应商 | related | L2 | 1 |

## 候选 10：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：84.96
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.86 | 新高股17只，新高成交228.9766亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比10.91，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 先进封装 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中芯国际 | 688981 | 先进封装 | 晶圆代工、先进制程、成熟制程、先进封装 | core | L1_L3_candidate | 20 |
| 华天科技 | 002185 | 先进封装 | WLP、TSV、FO、PLP及2.5D/3D等先进封装产能提供商 | core | L2 | 20 |
| 华峰测控 | 688200 | 先进封装 | ATE测试设备 | core | L1_L3_candidate | 20 |
| 天马新材 | 920971 | 先进封装 | 电子陶瓷用粉体（MLCC上游）、高压电器用粉体、高导热球形氧化铝 | core | L1_L3_candidate | 20 |
| 康强电子 | 002119 | 先进封装 | 引线框架（冲压+蚀刻）、键合丝、电极丝 | core | L1_L3_candidate | 20 |
| 拓荆科技 | 688072 | 先进封装 | 薄膜沉积(CVD/ALD)设备龙头，拟收购尚积补PVD/刻蚀 | core | L3 | 20 |
| 新恒汇 | 301678 | 先进封装 | 芯片封装材料+封测服务一体化，物联网eSIM芯片封测提供DFN/QFN/... | core | L2 | 20 |
| 沃格光电 | 603773 | 先进封装 | 玻璃基TGV与GCP多层玻璃互联键合技术，面向算力芯片先进封装 | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-989ef667ef9c7c418da7 artifact_sha=cd1e0e6bead0d2426613ea463ee518c8206edf5a7b42bd159fe5428b37afcd66 manifest_sha=d310f107e30dabce9dbc817f4f1a1b59bc9dea4c7e480ecb873263773c7d2807 -->
