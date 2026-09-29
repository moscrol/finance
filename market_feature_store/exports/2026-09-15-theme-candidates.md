# 2026-09-15 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：16122.28
- **上涨家数**：1120
- **涨停 / 跌停**：32 / 28
- **容量前三行业**：1.电子(27.5%, super_capacity)、2.电力设备(8.1%, normal)、3.通信(7.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 锂电池概念 | 锂 | 电力设备 | 186.97 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 2 | PCB概念 | PCB概念 | - | 182.81 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 3 | 先进封装 | 先进封装 | 电子 | 180.25 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 5 | - |
| 4 | 存储芯片 | 存储芯片 | 电子 | 179.5 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 5 | OLED概念 | LED | 电子 | 173.12 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 6 | PCB | PCB | 电子 | 155.57 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 7 | 元器件 | 电子元器件 | 电子 | 153.83 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 8 | 半导体 | 半导体 | 电子 | 126.8 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 光刻机 | 光刻机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 4 | 12 | 2 | - |
| 10 | 玻璃基板 | 玻璃基板 | 电子 | 124.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 复合铜箔 | 复合铜箔 | - | 121.4 | limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 汽车芯片 | 汽车芯片 | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 1 | - |
| 13 | 数据中心 | 数据中心 | 计算机 | 109.05 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 绿色电力 | 绿色电力 | 公用事业 | 107.72 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 15 | 玻璃玻纤 | 玻璃 | 建筑材料 | 106.43 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 16 | 新能源车 | 新能源车 | 计算机 | 105.16 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | 信创 | 信创 | 计算机 | 97.42 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 风电零部件 | 风电零部件 | - | 91.8 | limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 19 | 电子 | EDA（电子设计自动化） | 电子 | 91.48 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 20 | 风电设备 | 风电设备 | - | 88.6 | limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 21 | 风电 | 风电 | 电力设备 | 86.0 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 22 | MLCC | MLCC | - | 79.6 | multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 23 | 折叠屏 | 折叠屏 | 电子 | 77.35 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 1 | - |
| 24 | 智能穿戴 | 智能穿戴 | 电子 | 77.33 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 25 | 电力设备 | 电力设备 | 电力设备 | 77.04 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 1 | - |
| 26 | 无人机 | 无人机 | - | 76.54 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 27 | MiniLED | Mini LED | 电子 | 75.95 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 28 | 粤港澳 | 粤港澳 | - | 75.12 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 29 | 数据要素 | 数据要素 | 计算机 | 73.35 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 30 | 信息安全 | 信息安全 | 计算机 | 73.25 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | CPO概念 | CPO | - | 73.03 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 32 | 计算机 | 计算机外设 | 计算机 | 71.96 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 33 | 工业互联 | 工业互联网 | - | 71.39 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 34 | 东数西算 | 东数西算 | - | 71.25 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 35 | 商业航天 | 商业航天 | 国防军工 | 71.25 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 36 | AI眼镜 | AI眼镜 | 电子 | 70.61 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 37 | 无人驾驶 | 无人驾驶 | 汽车 | 70.45 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 38 | 一带一路 | 一带一路 | - | 69.66 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 39 | 国防军工 | 国防军工 | 国防军工 | 69.65 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 40 | 云计算 | 云计算 | 计算机 | 69.61 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 41 | 毫米波雷达 | 毫米波雷达 | 汽车 | 69.5 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 42 | 充电桩 | 充电桩 | - | 69.37 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 43 | 卫星导航 | 卫星导航 | - | 69.36 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 44 | 阿里概念 | 阿里概念 | - | 68.71 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 小米概念 | 小米概念 | - | 68.69 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 物联网 | 物联网 | - | 68.12 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 47 | 车联网 | 车联网 | - | 67.81 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 48 | 智慧城市 | 智慧城市 | - | 67.66 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 49 | 储能 | 储能 | 电子 | 66.15 | limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 50 | 6G概念 | 6G | - | 65.76 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：锂电池概念

- **标准概念**：锂
- **申万一级**：电力设备
- **评分**：186.97
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 111.0 | 连板股2只，最高3板，容量前三=True |
| new_high_direction | 42.47 | 新高股16只，新高成交197.5223亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比31.25，排名1 |

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

## 候选 2：PCB概念

- **标准概念**：PCB概念
- **申万一级**：-
- **评分**：182.81
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.575%，边际量 11.9183%，成交额 2577.0197 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.575%，边际量11.9183%，成交2577.0197亿 |
| new_high_direction | 51.51 | 新高股41只，新高成交920.7496亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 9.2 | day10排名第7，区间涨幅3.75% |
| limit_heat | 6.1 | 涨停6只，市场占比18.75，排名8 |

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

## 候选 3：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：180.25
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.6775%，边际量 16.2638%，成交额 2031.9598 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.6775%，边际量16.2638%，成交2031.9598亿 |
| new_high_direction | 54.25 | 新高股18只，新高成交340.0646亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 4：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：179.5
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.9679%，边际量 13.8855%，成交额 2262.0357 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.9679%，边际量13.8855%，成交2262.0357亿 |
| new_high_direction | 53.5 | 新高股15只，新高成交360.1267亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 存储芯片 | 20 |
| 芯片 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万润科技 | 002654 | 存储芯片 | 以半导体存储电子产业为核心的新一代信息技术主产业（一主一副格局），提供存... | core | L2 | 20 |
| 中电港 | 001287 | 存储芯片 | 存储器分销核心渠道（存储器占营收38.38%） | core | L2 | 20 |
| 佰维存储 | 688525 | 存储芯片 | 独立半导体存储解决方案提供商，覆盖NAND/DRAM模组与主控 | core | L2 | 20 |
| 兆易创新 | 603986 | 存储芯片 | NOR Flash/SLC NAND/利基型DRAM设计公司，存储为第一... | core | L2 | 20 |
| 北京君正 | 300223 | 存储芯片 | 车规/工规SRAM、DRAM、Nor Flash设计商，全球车规存储重要... | core | L2 | 20 |
| 复旦微电 | 688385 | 存储芯片 | 高可靠性非挥发存储器供应商，产品含EEPROM、NOR Flash及SL... | core | L2 | 20 |
| 大为股份 | 002213 | 存储芯片 | 半导体存储芯片模组与方案商，覆盖DRAM与NAND Flash产品 | core | L2 | 20 |
| 江波龙 | 301308 | 存储芯片 | 江波龙年报披露的存储芯片相关主营业务 | core | L2 | 20 |

## 候选 5：OLED概念

- **标准概念**：LED
- **申万一级**：电子
- **评分**：173.12
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.3694%，边际量 14.5863%，成交额 1224.2719 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.3694%，边际量14.5863%，成交1224.2719亿 |
| new_high_direction | 47.12 | 新高股12只，新高成交185.72959999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| LED | 10 |
| OLED | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万润科技 | 002654 | LED | LED产业中游封装、下游应用业务，集研发设计生产销售一体 | core | L2 | 20 |
| 三安光电 | 600703 | LED | LED外延芯片+应用品为第一大收入来源 | core | L2 | 20 |
| 兆驰股份 | 002429 | LED | LED外延片、芯片、封装器件、Mini/Micro LED显示模组、LE... | core | L2 | 20 |
| 光莆股份 | 300632 | LED | LED照明灯具及半导体光应用产品制造商，覆盖全球50多个国家和地区 | core | L2 | 20 |
| 利亚德 | 300296 | LED | LED显示产业链企业，产品应用于指挥控制、会议显示、广电演播、商业零售及... | core | L2 | 20 |
| 华灿光电 | 300323 | LED | LED衬底-PSS-外延-芯片垂直整合制造商 | core | L2 | 20 |
| 聚灿光电 | 300708 | LED | LED芯片及外延片相关产品/服务商 | core | L2 | 20 |
| 聚飞光电 | 300303 | LED | LED封装龙头企业 | core | L2 | 20 |

## 候选 6：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：155.57
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 57.57 | 新高股26只，新高成交605.8395000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | day10排名第1，区间涨幅17.6% |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅7.03% |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅11.93% |

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

## 候选 7：元器件

- **标准概念**：电子元器件
- **申万一级**：电子
- **评分**：153.83
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 58.23 | 新高股28只，新高成交658.4512000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | day10排名第2，区间涨幅13.72% |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅6.49% |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅9.7% |

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

## 候选 8：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：126.8
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 1.2105%，边际量 18.1718%，成交额 1939.0799 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.2105%，边际量18.1718%，成交1939.0799亿 |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 6.8 | daily排名第10，区间涨幅1.21% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体 | 20 |
| 功率半导体 | 5 |
| 化合物半导体 | 5 |
| 半导体IP | 5 |
| 半导体产业链 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中晶科技 | 003026 | 功率半导体 | 半导体功率芯片及器件制造商（广泛应用于微波炉、激光打印机、X光机、高压电... | core | L2 | 20 |
| 华润微 | 688396 | 功率半导体 | 中国本土最大功率半导体企业之一，IDM模式全产业链经营 | core | L2 | 20 |
| 协昌科技 | 301418 | 功率半导体 | 功率芯片（晶圆/封装成品）设计销售并向封测领域延伸 | core | L2 | 20 |
| 士兰微 | 600460 | 功率半导体 | 分立器件产品营收63.79亿元/毛利率12.22%/同比+17.32% | core | L2 | 20 |
| 富乐德 | 301297 | 功率半导体 | 富乐德年报披露的功率半导体相关主营业务 | core | L2 | 20 |
| 康强电子 | 002119 | 功率半导体 | 康强电子年报披露的功率半导体相关主营业务 | core | L2 | 20 |
| 新洁能 | 605111 | 功率半导体 | 受益标的 | core | L2 | 20 |
| 有研硅 | 688432 | 功率半导体 | 有研硅年报披露的功率半导体相关主营业务 | core | L2 | 20 |

## 候选 9：光刻机

- **标准概念**：光刻机
- **申万一级**：电子
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.6526%，边际量 21.8518%，成交额 661.2299 亿，容量前三=是
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.6526%，边际量21.8518%，成交661.2299亿 |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光刻机 | 20 |
| 光刻 | 10 |
| 电子束光刻机 | 5 |
| 电子束光刻机产业 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凯美特气 | 002549 | 光刻 | 光刻气供应商，产品获Cymer、GIGAPHOTON认证 | peripheral | L2 | 20 |
| 芯源微 | 688037 | 光刻 | 图谱弱关联 | peripheral | graph_only | 20 |
| 奥普光电 | 002338 | 光刻机 | 光源系统/科益虹源股东与整机布局 | core | L2 | 20 |
| 福晶科技 | 002222 | 光刻机 | 光源系统/LBO-BBO非线性光学晶体 | core | L2 | 20 |
| 聚和材料 | 688503 | 光刻机 | 掩膜板材料/空白掩膜板基板 | core | L2 | 20 |
| 芯碁微装 | 688630 | 光刻机 | 直写光刻/无掩膜光刻设备 | core | L2 | 20 |
| 茂莱光学 | 688502 | 光刻机 | 光学系统/投影物镜与匀光系统 | core | L2 | 20 |
| 中旗新材 | 001212 | 光刻机 | 半导体设备资产注入预期（星空科技光刻机 | related | L2 | 20 |

## 候选 10：玻璃基板

- **标准概念**：玻璃基板
- **申万一级**：电子
- **评分**：124.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.1844%，边际量 11.4803%，成交额 532.7724 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.1844%，边际量11.4803%，成交532.7724亿 |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 玻璃基板 | 20 |
| 玻璃 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三峡新材 | 600293 | 玻璃 | 平板玻璃生产商（湖北当阳），围绕玻璃主业深耕 | core | L2 | 20 |
| 秀强股份 | 300160 | 玻璃 | 玻璃深加工行业相关产品/服务商 | core | L2 | 20 |
| 北玻股份 | 002613 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 南玻A | 000012 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 德力股份 | 002571 | 玻璃 | 玻璃相关产品/服务商 | related | L2 | 20 |
| 海南发展 | 002163 | 玻璃 | 玻璃相关产品/服务商 | related | L2 | 20 |
| 福耀玻璃 | 600660 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 蓝思科技 | 300433 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-0b86f6ff9cc3e13ccb7b artifact_sha=ff9afcfa315402728a1121419a7886f7413afadd40cb1ee8b190b7532c141da4 manifest_sha=7805a2e723531219bf348d1c7fb9a42a0ef47d51e75671e3edb0c5a5bed23c85 -->
