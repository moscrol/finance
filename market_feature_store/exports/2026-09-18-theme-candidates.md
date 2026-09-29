# 2026-09-18 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：20764.84
- **上涨家数**：4234
- **涨停 / 跌停**：79 / 0
- **容量前三行业**：1.电子(31.2%, super_capacity)、2.通信(9.5%, normal)、3.机械设备(7.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 半导体 | 半导体 | 电子 | 251.49 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 集成电路设计 | 集成电路 | 电子 | 247.28 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 3 | 半导体设备 | 半导体设备 | 电子 | 233.6 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 4 | 12 | 5 | - |
| 4 | 汽车芯片 | 汽车芯片 | 电子 | 212.67 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 5 | 电子 | EDA（电子设计自动化） | 电子 | 200.8 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 先进封装 | 先进封装 | 电子 | 200.17 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 5 | - |
| 7 | 存储芯片 | 存储芯片 | 电子 | 192.38 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 8 | MCU芯片 | MCU芯片 | 电子 | 186.32 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 9 | 数据中心 | 数据中心 | 计算机 | 181.5 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 智能穿戴 | 智能穿戴 | 电子 | 180.05 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | AI眼镜 | AI眼镜 | 电子 | 179.43 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 12 | 玻璃基板 | 玻璃基板 | 电子 | 178.25 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 13 | 物联网 | 物联网 | - | 168.63 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 14 | 无人驾驶 | 无人驾驶 | 汽车 | 168.06 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 15 | 阿里概念 | 阿里概念 | - | 163.14 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 16 | 第三代半导体 | 第三代半导体 | - | 161.99 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 17 | 小米概念 | 小米概念 | - | 161.08 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 18 | 云计算 | 云计算 | 计算机 | 160.74 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 19 | 毫米波雷达 | 毫米波雷达 | 汽车 | 160.01 | double_red、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 20 | 算力租赁 | 算力租赁 | 计算机 | 159.99 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 21 | 芯片 | 芯片 | 电子 | 159.6 | double_red、capacity_industry、limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 22 | 英伟达概念 | 英伟达 | - | 156.94 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 23 | 机器人概念 | 机器人 | 电子 | 154.2 | double_red、limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 24 | 粤港澳 | 粤港澳 | 房地产 | 149.45 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 25 | 人工智能 | 人工智能 | 计算机 | 149.25 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 3 | 12 | 1 | - |
| 26 | 新零售 | 零售 | 纺织服饰 | 143.2 | limit_heat、limit_advance_cluster、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 27 | 半导体封测 | 半导体封测 | - | 126.4 | multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 28 | AI手机PC | AI手机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 29 | 无线耳机 | 无线耳机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 30 | 机器视觉 | 机器视觉 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 消费电子 | 消费电子 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 32 | 信创 | 信创 | 计算机 | 122.1 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 33 | AI智能体 | AI智能体 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 34 | ChatGPT概念 | ChatGPT概念 | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 互联金融 | 互联金融 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 36 | 元宇宙概念 | 元宇宙 | - | 116.0 | double_red、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 37 | 创新药 | 创新药 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 5 | - |
| 38 | 区块链 | 区块链 | - | 116.0 | double_red、new_high_cluster | 1 | 9 | 1 | - |
| 39 | 医药 | 医药 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 医药医疗 | 医疗 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 41 | 华为海思 | 华为海思 | - | 116.0 | double_red、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 42 | 华为鸿蒙 | 华为鸿蒙 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 43 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 44 | 国产软件 | 软件 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 45 | 多模态AI | 多模态AI | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 3 | 1 | - |
| 46 | 智能家居 | 智能家居 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 47 | 苹果概念 | 苹果概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 虚拟现实 | 虚拟现实 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 计算机 | 计算机外设 | 计算机 | 116.0 | double_red、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 50 | 车联网 | 车联网 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：251.49
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.9664%，边际量 43.8703%，成交额 3385.168 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.9664%，边际量43.8703%，成交3385.168亿 |
| new_high_direction | 62.29 | 新高股53只，新高成交982.8143000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 21.6 | day3排名第4，区间涨幅8.59% |
| multi_period_rank | 21.6 | day5排名第4，区间涨幅10.35% |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅3.97% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 2：集成电路设计

- **标准概念**：集成电路
- **申万一级**：电子
- **评分**：247.28
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.5677%，边际量 49.9559%，成交额 1626.3593 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.5677%，边际量49.9559%，成交1626.3593亿 |
| new_high_direction | 56.48 | 新高股27只，新高成交518.6473000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅4.57% |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅8.81% |
| multi_period_rank | 19.2 | day5排名第7，区间涨幅9.68% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 集成电路 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 全志科技 | 300458 | 集成电路 | 集成电路设计企业，SoC+模拟+无线互联芯片组合供应商 | core | L2 | 20 |
| 北京君正 | 300223 | 集成电路 | 集成电路芯片研发销售商，坚持存储+计算+模拟产品战略 | core | L2 | 20 |
| 华大九天 | 301269 | 集成电路 | 贯穿集成电路设计、制造、封装的EDA战略基础工具供应商 | core | L2 | 20 |
| 三安光电 | 600703 | 集成电路 | 射频/电力电子/光技术等化合物半导体集成电路 | core | L2 | 20 |
| 东软载波 | 300183 | 集成电路 | 软件及集成电路相关产品/服务商 | core | L2 | 20 |
| 中颖电子 | 300327 | 集成电路 | 集成电路产品相关产品/服务商 | core | L2 | 20 |
| 兴福电子 | 688545 | 集成电路 | 集成电路湿法蚀刻/清洗关键耗材供应商 | core | L2 | 20 |
| 创耀科技 | 688259 | 集成电路 | 软件及集成电路、芯片版图设计服务相关产品/服务商 | core | L2 | 20 |

## 候选 3：半导体设备

- **标准概念**：半导体设备
- **申万一级**：电子
- **评分**：233.6
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 4.398%，边际量 45.1252%，成交额 548.7215 亿，容量前三=是
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.398%，边际量45.1252%，成交548.7215亿 |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅14.12% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅9.97% |
| multi_period_rank | 27.4 | daily排名第3，区间涨幅4.4% |
| multi_period_rank | 25.0 | day10排名第6，区间涨幅13.42% |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体设备 | 20 |
| 半导体 | 10 |
| 半导体设备材料 | 5 |
| 半导体设备零部件 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亚翔集成 | 603929 | 半导体 | IC半导体洁净室工程服务商（建厂工程核心配套） | core | L2 | 20 |
| 利尔达 | 920249 | 半导体 | 半导体IC分销与物联网模组厂商，覆盖芯片到模组的交付 | core | L2 | 20 |
| 力源信息 | 300184 | 半导体 | 国内外半导体原厂产品授权分销商，并开展自研MCU芯片 | core | L2 | 20 |
| 华大九天 | 301269 | 半导体 | 国产半导体设计与制造环节EDA工具龙头 | core | L2 | 20 |
| 华天科技 | 002185 | 半导体 | 半导体封测代工，受益全球半导体销售额增长与国内集成电路产量扩张 | core | L2 | 20 |
| 大为股份 | 002213 | 半导体 | 半导体存储为主业，2025年该业务营收突破10亿元 | core | L2 | 20 |
| 大普微 | 301666 | 半导体 | 半导体存储产品提供商，自研主控芯片委托晶圆制造与封测 | core | L2 | 20 |
| 英唐智控 | 300131 | 半导体 | 全资子公司英唐微技术采用IDM模式研发生产光电转换和图像处理IC，提供光... | core | L2 | 20 |

## 候选 4：汽车芯片

- **标准概念**：汽车芯片
- **申万一级**：电子
- **评分**：212.67
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.9045%，边际量 45.9044%，成交额 1575.5567 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.9045%，边际量45.9044%，成交1575.5567亿 |
| new_high_direction | 59.07 | 新高股33只，新高成交725.6747亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 14.2 | daily排名第7，区间涨幅3.9% |
| multi_period_rank | 13.4 | day3排名第8，区间涨幅7.07% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 汽车芯片 | 20 |
| 芯片 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 四维图新 | 002405 | 汽车芯片 | 车规级芯片自研，舱驾融合芯片AC8025AE | core | L2 | 20 |
| 聚辰股份 | 688123 | 汽车芯片 | DDR5 SPD芯片、VPD芯片、EEPROM（车规&工业） | related | L1_L3_candidate | 20 |
| 银河微电 | 688689 | 汽车芯片 | 车规级半导体分立器件、SiC、GaN第三代半导体 | related | L1_L3_candidate | 20 |
| 国芯科技 | 688262 | 汽车芯片 | 汽车电子芯片(域控MCU)国产替代厂商，RISC-V车规MCU与量子安全... | related | L1_L3_candidate | 20 |
| 气派科技 | 688216 | 汽车芯片 | 集成电路封装测试、功率器件封装测试、晶圆测试 | related | L1_L3_candidate | 20 |
| 利尔达 | 920249 | 芯片 | IC增值分销商，为客户提供芯片及一站式配套服务 | core | L2 | 20 |
| 复旦微电 | 688385 | 芯片 | 超大规模集成电路设计企业，产品线覆盖FPGA、安全与识别、非挥发存储器和... | core | L2 | 20 |
| 探路者 | 300005 | 芯片 | 集成电路业务覆盖触控IC、指纹识别芯片、图像及视频处理IP | related | L2 | 20 |

## 候选 5：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：200.8
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.7489%，边际量 25.8813%，成交额 6499.1619 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.7489%，边际量25.8813%，成交6499.1619亿 |
| new_high_direction | 68.0 | 新高股106只，新高成交1491.7006999999994亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比10.13，排名17 |

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

## 候选 6：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：200.17
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.9504%，边际量 22.3399%，成交额 3080.0643 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.9504%，边际量22.3399%，成交3080.0643亿 |
| new_high_direction | 60.47 | 新高股36只，新高成交837.8094亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 7.6 | day5排名第9，区间涨幅8.34% |
| limit_heat | 6.1 | 涨停6只，市场占比7.59，排名25 |

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

## 候选 7：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：192.38
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.3476%，边际量 35.135%，成交额 3416.7743 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.3476%，边际量35.135%，成交3416.7743亿 |
| new_high_direction | 58.78 | 新高股41只，新高成交702.7253999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 7.6 | daily排名第9，区间涨幅3.35% |

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

## 候选 8：MCU芯片

- **标准概念**：MCU芯片
- **申万一级**：电子
- **评分**：186.32
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.3061%，边际量 51.3805%，成交额 910.8082 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.3061%，边际量51.3805%，成交910.8082亿 |
| new_high_direction | 53.52 | 新高股18只，新高成交281.61019999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 6.8 | daily排名第10，区间涨幅3.31% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MCU芯片 | 20 |
| MCU | 12 |
| 芯片 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中微半导 | 688380 | MCU | 国内8位MCU出货量龙头、以MCU为核心的平台型芯片设计企业 | core | L2 | 20 |
| 兆易创新 | 603986 | MCU | 国内领先的32位MCU设计商，车规GD32A系列进入规模量产 | core | L2 | 20 |
| 国民技术 | 300077 | MCU | 受益标的 | core | L2 | 20 |
| 华虹宏力 | 688347 | MCU | 嵌入式闪存工艺平台上的车规及消费类MCU晶圆代工厂 | related | L2 | 20 |
| 普冉股份 | 688766 | MCU | MCU | related | L1_L3_candidate | 20 |
| 康达新材 | 002669 | MCU | 康达新材年报披露的MCU相关主营业务 | related | L2 | 20 |
| 华大电子 | - | MCU | 受益标的 | related | L2 | 20 |
| 北京君正 | 300223 | MCU | AI MCU与嵌入式MPU设计，首款AI MCU样品回片测试中 | peripheral | L2 | 20 |

## 候选 9：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：181.5
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.9736%，边际量 17.4852%，成交额 5740.2892 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.9736%，边际量17.4852%，成交5740.2892亿 |
| new_high_direction | 58.0 | 新高股74只，新高成交1618.664亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比12.66，排名5 |

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

## 候选 10：智能穿戴

- **标准概念**：智能穿戴
- **申万一级**：电子
- **评分**：180.05
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.3718%，边际量 24.0363%，成交额 2017.7363 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.3718%，边际量24.0363%，成交2017.7363亿 |
| new_high_direction | 54.05 | 新高股32只，新高成交323.78309999999993亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能穿戴 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 佰维存储 | 688525 | 智能穿戴 | AI/AR眼镜、智能手表等端侧ePOP存储供应商 | related | L2 | 20 |
| 佳禾智能 | 300793 | 智能穿戴 | 智能手表、智能眼镜等可穿戴产品制造商 | related | L2 | 20 |
| 则成电子 | 920821 | 智能穿戴 | 声学/汽车/医疗电子装联与定制化模组模块（AI智能穿戴高多层AIR-GA... | related | L2 | 20 |
| 天键股份 | 301383 | 智能穿戴 | 声学技术向智能穿戴/智能家居/车载电子等领域延伸 | related | L2 | 20 |
| 萤石网络 | 688475 | 智能穿戴 | 萤石网络年报披露的智能穿戴相关主营业务 | related | L2 | 20 |
| 金太阳 | 300606 | 智能穿戴 | 金太阳年报披露的智能穿戴相关主营业务 | related | L2 | 20 |
| 中科蓝讯 | 688332 | 智能穿戴 | 智能穿戴和智能手表等SoC芯片供应商 | peripheral | graph_only | 20 |
| 唯捷创芯 | 688153 | 射频芯片 | 国内射频前端行业先行者（Fabless模式，产品应用于智能手机、车载通信... | core | L2 | 1 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-bbda377c624e7642f74f artifact_sha=45db209e1c4e3492018f8ea4b94db7b60d1a517baa6920bc8d8fa0c5aeac8a92 manifest_sha=c07c3e164ad4dd21f37c33f43e441494515bcf813676ee666ab322f3fd8d4fb7 -->
