# 2026-06-22 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：37368.79
- **上涨家数**：2916
- **涨停 / 跌停**：134 / 4
- **容量前三行业**：1.电子(30.5%, super_capacity)、2.电力设备(9.5%, normal)、3.机械设备(8.1%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PCB | PCB | 电力设备 | 201.0 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 2 | 氢能源 | 氢能源 | 电力设备 | 197.86 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 4 | 1 | - |
| 3 | 3D打印 | 3D打印 | 机械设备 | 185.01 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 钠离子电池 | 储能 | 电力设备 | 184.68 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 5 | 燃料电池 | 燃料电池 | 电力设备 | 184.01 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 数据中心 | 数据中心 | 计算机 | 183.95 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 光刻胶 | 光刻胶 | 电子 | 182.88 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 小金属 | 小金属 | 有色金属 | 181.15 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 9 | 通信设备 | 通信设备 | 通信 | 174.0 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 金属铜 | 金属铜 | 有色金属 | 173.64 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 超级电容 | 超级电容 | 电力设备 | 173.31 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 6G | 6G | 通信 | 172.78 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 磷化工 | 磷化工 | 基础化工 | 168.57 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 14 | 氟化工 | 氟化工 | 基础化工 | 165.6 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 证券 | 证券IT | 非银金融 | 164.64 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 16 | 数据要素 | 数据要素 | 计算机 | 164.49 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | 电子化学品 | 电子化学品 | 基础化工 | 164.39 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 量子科技 | 量子科技 | 计算机 | 159.0 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 19 | 储能 | 储能 | 电力设备 | 137.35 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 20 | 固态电池 | 固态电池 | 电力设备 | 137.35 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 4 | - |
| 21 | 机器人 | 机器人 | 机械设备 | 133.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 22 | BC电池 | BC电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 5 | 1 | - |
| 23 | MLCC | MLCC | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 24 | 电池 | 4C电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 25 | 电池化学品 | 电池化学品 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 26 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 6 | 1 | - |
| 27 | 高压快充 | 超充 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 5 | 0 | missing_evidence |
| 28 | 光伏设备 | 光伏设备 | 电力设备 | 124.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 29 | AI应用 | AI应用 | 计算机 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 30 | 金属铅 | 金属铅 | 有色金属 | 123.15 | double_red、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 金属锌 | 金属锌 | 有色金属 | 123.15 | double_red、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 32 | 工业金属 | 工业金属 | 有色金属 | 122.8 | double_red、limit_heat、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 33 | 电网设备 | 电网设备 | 电力设备 | 122.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 雅下水电 | 雅下水电 | 电力设备 | 120.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 35 | 氮化铝 | 氮化铝 | 电子 | 119.0 | limit_advance_cluster、capacity_industry | 0 | 2 | 0 | missing_concept、missing_evidence |
| 36 | 商业航天 | 商业航天 | 国防军工 | 116.2 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 37 | AIGC | AIGC | 传媒 | 116.0 | double_red、new_high_cluster | 5 | 10 | 1 | - |
| 38 | AI智能体 | AI智能体 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 39 | ChatGPT | ChatGPT | 传媒 | 116.0 | double_red、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 40 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 41 | 化学制品 | 化工周期 | 基础化工 | 116.0 | double_red、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 42 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 计算机设备 | 计算机设备 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 9 | 1 | - |
| 44 | 超导 | 超导 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 9 | 1 | - |
| 45 | 软件开发 | AIGC | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 46 | 金属钴 | 金属钴 | 有色金属 | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 金属镍 | 金属镍 | 有色金属 | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 锂电池 | 锂电池 | 电力设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 3 | - |
| 49 | 黄金 | 黄金 | 有色金属 | 116.0 | double_red、new_high_cluster | 5 | 12 | 2 | - |
| 50 | 电容器 | MLCC材料 | 电力设备 | 115.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：PCB

- **标准概念**：PCB
- **申万一级**：电力设备
- **评分**：201.0
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |
| new_high_direction | 68.0 | 新高股72只，新高成交2412.4200000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 10 |
| AI PCB | 5 |
| AIPCB专用油墨 | 5 |
| PCB印制电路板 | 5 |
| PCB微钻 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东威科技 | 688700 | AI PCB | PCB精密电镀设备（核心） | related | L1_L3_candidate | 20 |
| 东山精密 | 002384 | AI PCB | 光模块（含光芯片，索尔思光电）、AI PCB（高多层硬板/RPCB）、F... | core | L1_L3_candidate | 20 |
| 中京电子 | 002579 | AI PCB | - | - | - | 20 |
| 中富电路 | 300814 | AI PCB | AI服务器三次电源PCB、二次电源PCB（HVDC）、埋感埋容嵌入式PC... | related | L1_L3_candidate | 20 |
| 中钨高新 | 000657 | AI PCB | PCB微钻、铣刀（金洲公司，AI+光模块耗材） | related | L1_L3_candidate | 20 |
| 南亚新材 | 688519 | AI PCB | 高频高速CCL国产替代和涨价弹性标的 | related | - | 20 |
| 嘉元科技 | 688388 | AI PCB | 高端电子电路铜箔（PCB铜箔/HVLP/RTF） | related | L1_L3_candidate | 20 |
| 大族数控 | 301200 | AI PCB | PCB钻孔设备核心受益标的 | core | - | 20 |

## 候选 2：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：197.86
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.09%，边际量 18.73%，成交额 3278.21 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（4），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.09%，边际量18.73%，成交3278.21亿 |
| new_high_direction | 65.06 | 新高股41只，新高成交1204.73亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比5.97，排名26 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 氢能源 | 10 |
| SOFC燃料电池 | 2 |
| 压缩机 | 2 |
| 天然气 | 2 |
| 氢能储运 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东岳硅材 | 300821 | 氢能源 | 参股材料平台潜在相关 | peripheral | L1 | 10 |
| 阳光电源 | 300274 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 隆基绿能 | 601012 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 雪人股份 | 002639 | 氢能源 | 上游设备 | peripheral | L1 | 10 |

## 候选 3：3D打印

- **标准概念**：3D打印
- **申万一级**：机械设备
- **评分**：185.01
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 11.34%，成交额 1829.5 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量11.34%，成交1829.5亿 |
| new_high_direction | 59.01 | 新高股23只，新高成交720.5299999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 3D打印 | 10 |
| 3D打印钛合金 | 5 |
| 开源3D打印 | 5 |
| 微通道冷板（绿激光3D打印） | 5 |
| 消费级3D打印 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华曙高科 | 688433 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 南风股份 | 300004 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 大族激光 | 002008 | 微通道冷板（绿激光3D打印） | - | - | - | 20 |
| XD艾为电 | 688798 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中兴通讯 | 000063 | 微通道冷板（绿激光3D打印） | - | - | - | 20 |
| 中恒电气 | 002364 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中石科技 | 300684 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中科曙光 | 603019 | 微通道冷板（绿激光3D打印） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 4：钠离子电池

- **标准概念**：储能
- **申万一级**：电力设备
- **评分**：184.68
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.79%，边际量 24.72%，成交额 1897.59 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（10），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.79%，边际量24.72%，成交1897.59亿 |
| new_high_direction | 58.68 | 新高股23只，新高成交694.4999999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 储能 | 2 |
| 储能电池 | 2 |
| 动力电池 | 2 |
| 固态电池 | 2 |
| 电解液 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科电气 | 300035 | 钠离子电池 | 钠电硬碳负极及电极活性材料潜在研发布局商 | related | L1 | 10 |
| 亿纬锂能 | 300014 | 钠离子电池 | 中游制造/电池 | related | L3_candidate | 10 |
| 传艺科技 | 002866 | 钠离子电池 | 钠离子电池电芯、正负极材料及储能/动力电池系统集成全流程生产商 | related | L1 | 10 |
| 华阳股份 | 600348 | 钠离子电池 | 钠离子电池一体化（正极/负极/电芯及PACK）国内最先量产释放的战略布局... | related | L1 | 10 |
| 振华新材 | 688707 | 钠离子电池 | 钠离子电池相关产品/材料供应商 | related | L2 | 10 |
| 宁德时代 | 300750 | 储能电池 | 储能电池 | related | L1_L3_candidate | 1 |
| 普利特 | 002324 | 化工 | 通用材料类相关产品供应商 | related | L2 | 1 |
| 同兴科技 | 300490 | 环保 | 环保相关产品/材料供应商 | related | L2 | 1 |

## 候选 5：燃料电池

- **标准概念**：燃料电池
- **申万一级**：电力设备
- **评分**：184.01
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.72%，边际量 14.87%，成交额 1783.88 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.72%，边际量14.87%，成交1783.88亿 |
| new_high_direction | 58.01 | 新高股26只，新高成交640.9700000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 燃料电池 | 10 |
| SOFC燃料电池 | 5 |
| SOFC（固体氧化物燃料电池） | 5 |
| 固体氧化物燃料电池(SOFC) | 5 |
| 储能电池 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 壹石通 | 688733 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 三环集团 | 300408 | SOFC（固体氧化物燃料电池） | 陶瓷材料与零部件潜在相关 | peripheral | L1 | 20 |
| 三花智控 | 002050 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国巨石 | 600176 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国船舶 | 600150 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中材科技 | 002080 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中航光电 | 002179 | SOFC（固体氧化物燃料电池） | - | - | - | 20 |
| 京东方A | 000725 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 6：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：183.95
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.85%，边际量 12.11%，成交额 10289.92 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.85%，边际量12.11%，成交10289.92亿 |
| new_high_direction | 58.0 | 新高股87只，新高成交4250.259999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.95 | 涨停17只，市场占比12.69，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 10 |
| AI数据中心 | 5 |
| AI数据中心储能 | 5 |
| 数据中心交换机 | 5 |
| 数据中心供电 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国西电 | 601179 | AI数据中心 | 特高压设备、主网一次设备、海外电力设备 | related | L1_L3_candidate | 10 |
| 亨通光电 | 600487 | AI数据中心 | 特别是AI数据中心需求驱动的光纤业务 | core | L1_L3_candidate | 10 |
| 京泉华 | 002885 | AI数据中心 | MFT高频变压器（AI数据中心） | related | L1_L3_candidate | 10 |
| 天齐锂业 | 002466 | AI数据中心 | 锂矿采选、锂化工产品（碳酸锂、氢氧化锂 | related | L1_L3_candidate | 10 |
| 应流股份 | 603308 | AI数据中心 | 燃气轮机叶片、航空发动机部件、核能装备 | related | L1_L3_candidate | 10 |
| 英维克 | 002837 | AI数据中心 | 数据中心液冷全链条解决方案（冷板/快接头/Manifold/CDU）、机... | related | L1_L3_candidate | 10 |
| 金盘科技 | 688676 | AI数据中心 | 干式变压器（风电/数据中心/储能）、液浸式变压器（海外高压）、固态变压器... | related | L1_L3_candidate | 10 |
| 锴威特 | 688693 | AI数据中心 | 功率器件（MOSFET/SiC MOSFET）、功率IC（电源管理IC/... | related | L1_L3_candidate | 10 |

## 候选 7：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：182.88
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.64%，边际量 23.8%，成交额 989.87 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.64%，边际量23.8%，成交989.87亿 |
| new_high_direction | 56.88 | 新高股23只，新高成交550.1800000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光刻胶 | 10 |
| EUV光刻胶 | 5 |
| g线光刻胶 | 5 |
| i线光刻胶 | 5 |
| 光刻胶树脂 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 晶瑞电材 | 300655 | g线光刻胶 | 图谱弱关联 | peripheral | graph_only | 10 |
| 万润股份 | 002643 | 光刻胶 | - | - | - | 10 |
| 上海新阳 | 300236 | 光刻胶 | 光刻胶） | related | L1_L3_candidate | 10 |
| 中芯国际 | 688981 | 光刻胶 | 2025 年国内 12 英寸晶圆产能同比增长 25%，带动成熟制程光刻胶... | peripheral | L1_L3_candidate | 10 |
| 八亿时空 | 688181 | 光刻胶 | 百吨级KrF高端光刻胶配方树脂国产化自主突破及生产平台 | related | L1 | 10 |
| 兴福电子 | 688545 | 光刻胶 | 湿电子化学品（电子级磷酸、硫酸、双氧水 | related | L1_L3_candidate | 10 |
| 华特气体 | 688268 | 光刻胶 | - | - | - | 10 |
| 华虹宏力 | 688347 | 光刻胶 | 特色工艺晶圆代工、12英寸成熟制程扩产、华力微收购并表 | related | L1_L3_candidate | 10 |

## 候选 8：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：181.15
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.49%，边际量 18.5%，成交额 3051.0 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.49%，边际量18.5%，成交3051.0亿 |
| new_high_direction | 58.0 | 新高股51只，新高成交2425.6899999999982亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比6.72，排名19 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小金属 | 10 |
| 二氧化锆 | 2 |
| 半导体设备材料 | 2 |
| 周期资源 | 2 |
| 战略金属 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方钽业 | 000962 | 小金属 | 钽铌材料/钽电容材料 | core | - | 10 |
| 东方锆业 | 002167 | 小金属 | 锆材料/其他小金属 | related | graph_only | 10 |
| 中国稀土 | 000831 | 小金属 | 中重稀土整合平台 | related | - | 10 |
| 中钨高新 | 000657 | 小金属 | 钨产业链/硬质合金刀具 | core | - | 10 |
| 凤形股份 | 002760 | 小金属 | 铟/锌/银回收深加工线索 | related | - | 10 |
| 北方稀土 | 600111 | 小金属 | 稀土/战略资源交叉 | related | - | 10 |
| 华钰矿业 | 601020 | 小金属 | 锑资源 | core | - | 10 |
| 华锡有色 | 600301 | 小金属 | 锑/锡资源端 | core | - | 10 |

## 候选 9：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：174.0
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.59%，边际量 13.72%，成交额 2753.64 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.59%，边际量13.72%，成交2753.64亿 |
| new_high_direction | 58.0 | 新高股22只，新高成交1804.8800000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 通信设备 | 10 |
| 5G | 2 |
| 5G-A | 2 |
| 5G_6G通信 | 2 |
| 5G基站 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | 通信设备 | 通信设备组件和光模块供应商 | related | L1 | 10 |
| 佳讯飞鸿 | 300213 | 通信设备 | AI+铁路大模型、民航空管国产化、低空经济空管设备 | related | L1_L3_candidate | 10 |
| 信科移动 | 688387 | 通信设备 | 无线网络5G-A宏基站及核心网网络整机制造商 | core | L1 | 10 |
| 天邑股份 | 300504 | 通信设备 | 宽带网络终端设备、通信网络物理连接与保护设备、移动通信网络优化系统设备 | related | L1_L3_candidate | 10 |
| 意华股份 | 002897 | 通信设备 | 通讯连接器产品相关产品供应商 | related | L2 | 10 |
| 锐捷网络 | 301165 | 通信设备 | 市场信号弱关联 | related | L2_candidate | 10 |
| 阿莱德 | 301419 | 通信设备 | 电子导热散热器件、光模块散热材料、AI服务器液冷散热、人形机器人热管理 | related | L1_L3_candidate | 10 |
| 万马科技 | 300698 | Robotaxi | 车联网连接服务（优咔科技）、L4无人驾驶高阶网联（RoboX）、AIDC... | related | L1_L3_candidate | 1 |

## 候选 10：金属铜

- **标准概念**：金属铜
- **申万一级**：有色金属
- **评分**：173.64
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.14%，边际量 23.11%，成交额 1532.8 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.14%，边际量23.11%，成交1532.8亿 |
| new_high_direction | 49.44 | 新高股22只，新高成交755.2800000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比8.96，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
