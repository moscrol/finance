# 2026-07-16 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：24033.87
- **上涨家数**：2499
- **涨停 / 跌停**：42 / 34
- **容量前三行业**：1.电子(31.8%, super_capacity)、2.医药生物(9.1%, normal)、3.通信(7.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 医疗服务 | 医疗服务 | 医药生物 | 189.72 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 2 | ChatGPT | ChatGPT | 传媒 | 149.53 | double_red、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 3 | 创新药 | 创新药 | 医药生物 | 147.9 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 4 | CRO | CRO | 医药生物 | 146.43 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 5 | 化学制药 | 化学制药 | 医药生物 | 144.79 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 6 | 中药 | 中药 | 医药生物 | 137.15 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 7 | 医药商业 | 医药商业 | - | 135.6 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 8 | 维生素 | 维生素 | 基础化工 | 128.85 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 9 | 消费电子 | 消费电子 | 电子 | 127.75 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 10 | 医药 | 医药 | 医药生物 | 127.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 云计算 | 云计算 | 计算机 | 121.4 | double_red、limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 12 | 多模态AI | 多模态AI | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 3 | 1 | - |
| 13 | 减肥药 | 创新药 | 医药生物 | 111.34 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 2 | 0 | missing_evidence |
| 14 | IT服务 | IT服务 | 计算机 | 110.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 阿尔茨海默 | 化学发光 | 医药生物 | 101.64 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 2 | 0 | missing_evidence |
| 16 | 白酒 | 白酒 | 食品饮料 | 87.12 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 17 | AI眼镜 | AI眼镜 | 电子 | 80.58 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 18 | 合成生物 | 合成生物 | 医药生物 | 79.76 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 19 | 辅助生殖 | 辅助生殖 | 医药生物 | 78.09 | new_high_direction、new_high_cluster、capacity_industry | 3 | 9 | 1 | - |
| 20 | 医疗器械 | 医疗器械 | 医药生物 | 77.29 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 21 | 银行 | 银行 | 银行 | 74.39 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 22 | 数据中心 | 数据中心 | 计算机 | 74.32 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 海峡两岸 | 海峡两岸 | 综合 | 73.13 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 24 | 无人驾驶 | 无人驾驶 | 汽车 | 70.06 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 25 | AIGC | AIGC | 传媒 | 68.85 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 宠物经济 | 宠物经济 | 社会服务 | 68.52 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 27 | 三胎 | 三胎 | 社会服务 | 67.94 | new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 28 | 养殖业 | 养殖 | 农林牧渔 | 67.04 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 29 | 影视院线 | 影视院线 | - | 63.45 | limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 30 | MCU芯片 | MCU芯片 | 电子 | 62.64 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 人形机器人 | 人形机器人 | 机械设备 | 58.23 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 32 | 英伟达 | 英伟达 | 电子 | 58.23 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 33 | 机器视觉 | 机器视觉 | 机械设备 | 57.11 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 34 | AI应用 | AI应用 | 计算机 | 56.1 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 5 | - |
| 35 | 半导体 | 半导体 | 电子 | 52.12 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 36 | 高压氧舱 | 高压氧舱 | - | 50.8 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 房地产 | 房地产 | 商贸零售 | 50.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 零售 | 零售 | 交通运输 | 50.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 39 | 智能座舱 | 智能座舱 | 汽车 | 48.22 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 40 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 44.76 | new_high_direction、new_high_cluster | 5 | 9 | 2 | - |
| 41 | 短剧游戏 | 游戏 | - | 43.45 | limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 42 | 文化传媒 | 文化传媒 | - | 37.6 | multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 43 | 旅游及酒店 | 旅游 | - | 36.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 人工智能 | 人工智能 | - | 34.55 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 45 | AI智能体 | AI智能体 | - | 32.8 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 储能 | 储能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 47 | IP经济(谷子经济) | 谷子经济 | - | 31.75 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 48 | 低空经济 | 低空经济 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 49 | 军工 | 军工 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 脑机接口 | 脑机接口 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |

## 五、核心候选明细

## 候选 1：医疗服务

- **标准概念**：医疗服务
- **申万一级**：医药生物
- **评分**：189.72
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.32 | 新高股27只，新高成交265.82000000000005亿，容量前三=True |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅10.26% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅14.61% |
| multi_period_rank | 28.2 | day10排名第2，区间涨幅11.55% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.2 | daily排名第7，区间涨幅1.83% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗服务 | 20 |
| 医疗 | 10 |
| BCI | 2 |
| FDA | 2 |
| 互联网医疗 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三博脑科 | 301293 | 医疗服务 | 专科医院/医疗服务提供方 | peripheral | graph_only | 20 |
| 三星电气 | 601567 | 医疗服务 | 医疗服务运营板块 | core | L2 | 20 |
| 创新医疗 | 002173 | 医疗服务 | 脑机接口业务（通过子公司博灵脑机）、AI医疗布局 | related | L2 | 20 |
| 合富中国 | 603122 | 医疗服务 | 体外诊断集约化销售、ACME极致赋能（AI诊疗、远程手术 | related | L2 | 20 |
| 和元生物 | 688238 | 医疗服务 | 细胞和基因治疗CDMO、CRO、再生医学 | related | L1_L3_candidate | 20 |
| 新开源 | 300109 | 医疗服务 | 医疗服务相关产品/材料供应商 | related | L2 | 20 |
| 新里程 | 002219 | 医疗服务 | 民营区域医疗集团（4家三级医院、24家医院），2025年医疗行业收入26... | core | L2 | 20 |
| 泰格医药 | 300347 | 医疗服务 | 临床试验技术服务、临床试验相关服务及实验室服务 | related | L1_L3_candidate | 20 |

## 候选 2：ChatGPT

- **标准概念**：ChatGPT
- **申万一级**：传媒
- **评分**：149.53
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.1%，边际量 16.78%，成交额 876.71 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.1%，边际量16.78%，成交876.71亿 |
| new_high_direction | 33.53 | 新高股10只，新高成交122.09亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科蓝讯 | 688332 | AI端侧 | AI端侧芯片 | related | L1_L3_candidate | 1 |

## 候选 3：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：147.9
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 58.55 | 新高股118只，新高成交684.01亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 20.0 | day10排名第6，区间涨幅7.82% |
| multi_period_rank | 19.2 | day5排名第7，区间涨幅10.32% |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅7.19% |
| limit_heat | 5.75 | 涨停5只，市场占比11.9，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 20 |
| 创新药RWA | 5 |
| AI辅助生殖 | 2 |
| CDMO | 2 |
| CRO | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一品红 | 300723 | 创新药 | 核心创新药AR882为高效选择性URAT1抑制剂，覆盖降尿酸治疗痛风、溶... | core | L2 | 20 |
| 一心堂 | 002727 | 创新药 | 院外零售渠道潜在相关 | peripheral | L1 | 20 |
| 三元基因 | 920344 | 创新药 | 布局重组全人胶原蛋白系列原料与组织工程材料，延伸消费医学、类器官等高增长... | related | L2 | 20 |
| 三生制药 | 01530.HK | 创新药 | 双抗BD出海标杆 | related | - | 20 |
| 上海医药 | 601607 | 创新药 | 医药流通渠道潜在相关 | peripheral | L1 | 20 |
| 上海谊众 | 688091 | 创新药 | 抗肿瘤创新药企业：紫杉醇胶束等纳米制剂，研产销一体化 | core | L2 | 20 |
| 东富龙 | 300171 | 创新药 | 创新药生产装备潜在供应商 | related | L1 | 20 |
| 丽珠集团 | 000513 | 创新药 | - | related | L1 | 20 |

## 候选 4：CRO

- **标准概念**：CRO
- **申万一级**：医药生物
- **评分**：146.43
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.03 | 新高股29只，新高成交322.1999999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅12.42% |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅9.21% |
| multi_period_rank | 21.6 | day3排名第4，区间涨幅8.52% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CRO | 20 |
| Micro LED | 5 |
| Micro LED光互连 | 5 |
| Micro OLED | 5 |
| Micro-OLED | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兆驰股份 | 002429 | LED | LED外延片、芯片、封装器件、Mini/Micro LED显示模组、LE... | core | L2 | 21 |
| 美迪凯 | 688079 | LED | TGV玻璃基板（先进封装）、半导体声光学、半导体封测、MicroLED（... | core | L1_L3_candidate | 21 |
| 深天马A | 000050 | OLED | AMOLED、车载/IT显示与Micro-LED显示面板供应商 | related | L1_L3_candidate | 21 |
| 激智科技—— | 300566 | OLED | 高端显示光学膜（量子点膜、复合膜DOP/POP、COP膜）、传统显示光学... | related | L1 | 21 |
| 万邦医药 | 301520 | CRO | CRO相关产品/材料供应商 | related | L2 | 20 |
| 南模生物 | 688265 | CRO | 国家级高新技术企业，以基因编辑技术为核心、以小鼠大鼠等模式生物为载体构建... | core | L2 | 20 |
| 和元生物 | 688238 | CRO | CRO | related | L1_L3_candidate | 20 |
| 泰格医药 | 300347 | CRO | 图谱弱关联 | peripheral | graph_only | 20 |

## 候选 5：化学制药

- **标准概念**：化学制药
- **申万一级**：医药生物
- **评分**：144.79
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.74 | 新高股58只，新高成交299.59亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 20.8 | day3排名第5，区间涨幅7.68% |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅10.66% |
| multi_period_rank | 18.4 | day10排名第8，区间涨幅6.9% |
| limit_heat | 5.05 | 涨停3只，市场占比7.14，排名23 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 化学制药 | 20 |
| 制药 | 10 |
| CXO | 2 |
| 原料药 | 2 |
| 多肽药物 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 丽珠集团 | 000513 | 制药 | - | related | L1 | 20 |
| 九洲药业 | 603456 | 制药 | 小分子CDMO、TIDES（多肽、小核酸 | related | L1_L3_candidate | 20 |
| 亚虹医药 | 688176 | 制药 | 抗肿瘤仿制药（欧优比 | related | L1_L3_candidate | 20 |
| 共同药业 | 300966 | 制药 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 20 |
| 圣诺生物 | 688117 | 制药 | 多肽原料药、CDMO、制剂 | related | L1_L3_candidate | 20 |
| 三力制药 | 603439 | 制药 | 中成药的研发、生产和销售、核心产品为开喉剑喷雾剂系列 | related | L2 | 20 |
| 上海医药 | 601607 | 制药 | 医药研发与制造企业 | peripheral | graph_only | 20 |
| 东富龙 | 300171 | 制药 | 制药装备整体解决方案、生物制药装备 | related | L1_L3_candidate | 20 |

## 候选 6：中药

- **标准概念**：中药
- **申万一级**：医药生物
- **评分**：137.15
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.95 | 新高股44只，新高成交156.02000000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 22.4 | day10排名第3，区间涨幅9.69% |
| multi_period_rank | 20.0 | day5排名第6，区间涨幅10.54% |
| multi_period_rank | 16.8 | daily排名第10，区间涨幅1.47% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中药 | 20 |
| 中药材 | 5 |
| 创新中药 | 5 |
| 中成药 | 2 |
| 兽药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | 中药 | 延伸中药全产业链相关业务 | related | L2 | 20 |
| 万邦德 | 002082 | 中药 | 现代中药+化学原料药/制剂完整产业链，覆盖心脑血管、神经、呼吸、消化、精... | core | L2 | 20 |
| 三力制药 | 603439 | 中药 | 苗药/中成药制造商：开喉剑喷雾剂（儿童型）为核心大单品，另有芪胶升白胶囊... | core | L2 | 20 |
| 上海凯宝 | 300039 | 中药 | 现代中药企业：痰热清注射液为独家品种，92个药品纳入国家医保目录 | core | L2 | 20 |
| 千金药业 | 600479 | 中药 | 口服妇科炎症中成药领域领先品牌，'千金'为国家驰名商标，妇科千金片（胶囊... | core | L2 | 20 |
| 太极集团 | 600129 | 中药 | 西成药相关产品供应商 | related | L2 | 20 |
| 康芝药业 | 300086 | 中药 | 儿童药研发生产销售、中成药、母婴健康用品 | related | L1_L3_candidate | 20 |
| 新里程 | 002219 | 中药 | 以中国驰名商标"独一味"为核心的中成药制造，2025年医药行业收入4.0... | related | L2 | 20 |

## 候选 7：医药商业

- **标准概念**：医药商业
- **申万一级**：-
- **评分**：135.6
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅11.63% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅9.04% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅11.97% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅1.89% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医药商业 | 20 |
| 医药 | 12 |
| 医药商业化 | 5 |
| 中药 | 2 |
| 医药流通 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 神奇制药 | 600613 | 医药 | 医药制造+医药商业双板块，医药制造收入11.23亿元毛利率71.72%，... | core | L2 | 20 |
| 丽珠集团 | 000513 | 医药 | 医药相关产品/材料供应商 | related | L2 | 20 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 20 |
| 仙琚制药 | 002332 | 医药 | 甾体类原料药相关产品供应商 | related | L2 | 20 |
| 千红制药 | 002550 | 医药 | 片剂相关产品供应商 | related | L2 | 20 |
| 奇正藏药 | 002287 | 医药 | 藏药相关产品供应商 | related | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 山东药玻 | 600529 | 医药 | 各种药用玻璃瓶产品相关产品供应商 | related | L2 | 20 |

## 候选 8：维生素

- **标准概念**：维生素
- **申万一级**：基础化工
- **评分**：128.85
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（10），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.0 | 新高股34只，新高成交80.13亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 19.2 | day10排名第7，区间涨幅7.39% |
| multi_period_rank | 19.2 | day3排名第7，区间涨幅7.3% |
| multi_period_rank | 18.4 | day5排名第8，区间涨幅10.01% |
| limit_heat | 5.05 | 涨停3只，市场占比7.14，排名24 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 维生素 | 20 |
| 动物疫苗 | 2 |
| 化学制药 | 2 |
| 原料药 | 2 |
| 精细化工 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亿帆医药 | 002019 | 维生素 | 维生素B5（泛酸钙）及原B5全球主要供应商 | core | L2 | 20 |
| 兄弟科技 | 002562 | 维生素 | 全球知名维生素生产商（维生素K3/B1/B3/B5产业平台） | core | L2 | 20 |
| 圣达生物 | 603079 | 维生素 | 全球生物素、叶酸主要供应商 | core | L2 | 20 |
| 天新药业 | 603235 | 维生素 | 维生素相关产品/材料供应商 | related | L2 | 20 |
| 中牧股份 | 600195 | 动物疫苗 | 重大动物疫病疫苗国家队（口蹄疫、高致病性禽流感定点生产企业） | core | L2 | 1 |
| 卫信康 | 603676 | 化学制药 | 化学药品制剂及原料药企业（复合维生素类、微量元素类、电解质类领域竞争力较... | core | L2 | 1 |
| 誉衡药业 | 002437 | 化学制药 | 哈尔滨药企，产品覆盖心脑血管、骨骼肌肉、维生素、电解质、抗肿瘤等领域，代... | core | L2 | 1 |
| 振华股份 | 603067 | 化工 | 铬化学品相关产品供应商 | related | L2 | 1 |

## 候选 9：消费电子

- **标准概念**：消费电子
- **申万一级**：电子
- **评分**：127.75
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.13%，边际量 14.14%，成交额 690.81 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.13%，边际量14.14%，成交690.81亿 |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比11.9，排名12 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费电子 | 20 |
| 消费 | 10 |
| 消费电子材料 | 5 |
| 消费电子渠道 | 5 |
| 消费电子设备 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中体产业 | 600158 | 消费 | 体育赛事运营与场馆经营受益名单 | peripheral | graph_only | 20 |
| 华夏航空 | 002928 | 消费 | 支线航空运营商，地方政府采购+中央支线补贴商业模式，覆盖下沉市场 | related | L1_L3_candidate | 20 |
| 盈趣科技 | 002925 | 消费 | 电子烟（创新消费电子）、健康环境产品、汽车电子、智能控制部件 | core | L1_L3_candidate | 20 |
| 立华股份 | 300761 | 消费 | 图谱弱关联 | peripheral | graph_only | 20 |
| 酒鬼酒 | 000799 | 消费 | 深度联动胖东来联合开发「酒鬼酒・自由爱」新品成为核心增长引擎，启动光瓶湘... | related | L2 | 20 |
| 锦江酒店 | 600754 | 消费 | 连锁酒店集团，受益休闲需求与RevPAR修复 | peripheral | graph_only | 20 |
| 首旅酒店 | 600258 | 消费 | 连锁酒店集团，受益休闲需求与RevPAR修复 | peripheral | graph_only | 20 |
| 万祥科技 | 301180 | 消费电子 | 消费电子精密零组件市场份额稳定，围绕锂电池行业发展 | core | L2 | 20 |

## 候选 10：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：127.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 127.0 | 连板股3只，最高5板，容量前三=True |

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
| 丽珠集团 | 000513 | 医药 | 医药相关产品/材料供应商 | related | L2 | 20 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 20 |
| 仙琚制药 | 002332 | 医药 | 甾体类原料药相关产品供应商 | related | L2 | 20 |
| 千红制药 | 002550 | 医药 | 片剂相关产品供应商 | related | L2 | 20 |
| 奇正藏药 | 002287 | 医药 | 藏药相关产品供应商 | related | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-50ee382f4cc4207446da artifact_sha=b2af7fc45e276f8b518b34041b5516e2cdbbe67cb6ffe70e651b777fa8e10b49 manifest_sha=b9437aad223dbce5d417da7a5738b968341556bf0a3524f4cc3f66fd5e102c49 -->
