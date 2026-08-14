# 2026-07-15 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：25709.31
- **上涨家数**：3351
- **涨停 / 跌停**：72 / 32
- **容量前三行业**：1.电子(31.9%, super_capacity)、2.医药生物(8.7%, normal)、3.通信(7.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 创新药 | 创新药 | 医药生物 | 329.12 | double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 2 | 医疗服务 | 医疗服务 | 医药生物 | 299.04 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 3 | 减肥药 | 创新药 | 医药生物 | 294.21 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 2 | 0 | missing_evidence |
| 4 | CRO | CRO | 医药生物 | 293.12 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 化学制药 | 化学制药 | 医药生物 | 289.39 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 合成生物 | 合成生物 | 医药生物 | 186.51 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 中药 | 中药 | 医药生物 | 144.01 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 8 | 维生素 | 维生素 | 基础化工 | 126.05 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 9 | 其他医药 | 医药 | 医药生物 | 115.0 | limit_advance_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 10 | 业绩 | AI PC | 基础化工 | 113.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | AI硬件 | AI硬件 | 电子 | 111.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 1 | - |
| 12 | 阿尔茨海默 | 化学发光 | 医药生物 | 103.04 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 2 | 0 | missing_evidence |
| 13 | 医药商业 | 医药商业 | - | 94.0 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 14 | 股权 | 私募股权投资 | 公用事业 | 89.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 15 | 生物制品 | 生物制品 | 医药生物 | 84.38 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 0 | missing_evidence |
| 16 | 医疗器械 | 医疗器械 | 医药生物 | 82.61 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 17 | 辅助生殖 | 辅助生殖 | 医药生物 | 79.86 | new_high_direction、new_high_cluster、capacity_industry | 3 | 9 | 1 | - |
| 18 | 银行 | 银行 | 银行 | 77.62 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 19 | 海峡两岸 | 海峡两岸 | 综合 | 75.52 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 20 | 宠物经济 | 宠物经济 | 社会服务 | 75.13 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 风电 | 风电 | 电力设备 | 72.49 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 22 | 数据中心 | 数据中心 | 计算机 | 72.35 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 三胎 | 三胎 | 社会服务 | 67.99 | new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 24 | 氢能源 | 氢能源 | 电力设备 | 67.23 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 白酒 | 白酒 | 食品饮料 | 65.24 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 26 | AIGC | AIGC | 传媒 | 60.46 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 燃料电池 | 燃料电池 | 电力设备 | 57.84 | new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 28 | 传感器 | 传感器 | 机械设备 | 57.78 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 29 | 无人驾驶 | 无人驾驶 | 汽车 | 56.92 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 30 | PCB | PCB | 电子 | 54.91 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | AI眼镜 | AI眼镜 | 电子 | 54.74 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 32 | 共封装光学(CPO) | CPO | 电子 | 54.39 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 33 | 机器人 | 机器人 | 机械设备 | 53.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 2 | - |
| 34 | 高压快充 | 超充 | 电力设备 | 52.35 | new_high_direction、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 35 | 人形机器人 | 人形机器人 | 机械设备 | 52.05 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 36 | MCU芯片 | MCU芯片 | 电子 | 51.73 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 37 | 光纤 | 光纤 | 通信 | 51.56 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 38 | 半导体 | 半导体 | 电子 | 50.64 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 39 | 工业金属 | 锻件 | 有色金属 | 48.65 | new_high_direction、new_high_cluster | 2 | 9 | 0 | missing_evidence |
| 40 | 液冷服务器 | 液冷服务器 | 电力设备 | 48.35 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 41 | 煤炭开采加工 | 煤炭 | - | 33.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | 人工智能 | 人工智能 | - | 32.8 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 储能 | 储能 | - | 32.8 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 44 | AI应用 | AI应用 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 45 | AI智能体 | AI智能体 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 46 | IP经济(谷子经济) | 谷子经济 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 47 | 算力租赁 | 算力租赁 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 48 | 统一大市场 | 统一大市场 | - | 31.05 | limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 美容护理 | 美容护理 | - | 27.6 | multi_period_rank、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 50 | 退市整理 | 退市整理 | 计算机 | 27.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 五、核心候选明细

## 候选 1：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：329.12
- **触发类型**：double_red、capacity_industry、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.65%，边际量 47.05%，成交额 1824.89 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.65%，边际量47.05%，成交1824.89亿 |
| new_high_direction | 65.37 | 新高股157只，新高成交1229.39亿，容量前三=True |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| multi_period_rank | 26.6 | day5排名第4，区间涨幅9.25% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.0 | day3排名第6，区间涨幅6.17% |
| multi_period_rank | 24.2 | day10排名第7，区间涨幅7.38% |
| multi_period_rank | 23.4 | daily排名第8，区间涨幅3.65% |

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

## 候选 2：医疗服务

- **标准概念**：医疗服务
- **申万一级**：医药生物
- **评分**：299.04
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.51%，边际量 52.52%，成交额 557.27 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.51%，边际量52.52%，成交557.27亿 |
| new_high_direction | 56.19 | 新高股36只，新高成交495.29999999999995亿，容量前三=True |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅5.51% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅13.13% |
| multi_period_rank | 26.6 | day3排名第4，区间涨幅6.6% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | day10排名第5，区间涨幅7.65% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

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

## 候选 3：减肥药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：294.21
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.37%，边际量 55.21%，成交额 636.62 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.37%，边际量55.21%，成交636.62亿 |
| new_high_direction | 56.51 | 新高股42只，新高成交520.74亿，容量前三=True |
| multi_period_rank | 27.4 | day10排名第3，区间涨幅8.87% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅10.7% |
| multi_period_rank | 26.6 | daily排名第4，区间涨幅4.37% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.2 | day3排名第7，区间涨幅5.89% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 2 |
| 多肽药物 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 信达生物 | 01801.HK | 创新药 | BD与减肥药/双抗管线平台 | core | - | 1 |
| 凯莱英 | 002821 | 创新药 | CDMO与减肥药供应链 | related | graph_only | 1 |

## 候选 4：CRO

- **标准概念**：CRO
- **申万一级**：医药生物
- **评分**：293.12
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.74%，边际量 51.49%，成交额 696.36 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.74%，边际量51.49%，成交696.36亿 |
| new_high_direction | 57.52 | 新高股45只，新高成交601.7900000000003亿，容量前三=True |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅12.2% |
| multi_period_rank | 27.4 | daily排名第3，区间涨幅4.74% |
| multi_period_rank | 27.4 | day3排名第3，区间涨幅6.97% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅8.09% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

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
- **评分**：289.39
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.85%，边际量 54.53%，成交额 912.09 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.85%，边际量54.53%，成交912.09亿 |
| new_high_direction | 56.24 | 新高股79只，新高成交498.82000000000016亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | day3排名第5，区间涨幅6.2% |
| multi_period_rank | 25.8 | day5排名第5，区间涨幅9.13% |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅3.85% |
| multi_period_rank | 23.4 | day10排名第8，区间涨幅7.04% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

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

## 候选 6：合成生物

- **标准概念**：合成生物
- **申万一级**：医药生物
- **评分**：186.51
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.37%，边际量 37.23%，成交额 662.41 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.37%，边际量37.23%，成交662.41亿 |
| new_high_direction | 54.76 | 新高股59只，新高成交380.62亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比6.94，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 合成生物 | 20 |
| 合成生物学 | 5 |
| 3D生物打印 | 2 |
| CDMO | 2 |
| 保健品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | - | 合成生物 | 受益标的 | related | - | 20 |
| 三元生物 | 301206 | 合成生物 | 发酵法生产糖醇类/稀有糖类配料（阿洛酮糖甜度约为蔗糖70%、热量仅十分之... | related | L2 | 20 |
| 中油工程 | 600339 | 合成生物 | 合成生物学等） | related | L1_L3_candidate | 20 |
| 共同药业 | 300966 | 合成生物 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 20 |
| 凯赛生物 | 688065 | 合成生物 | 受益标的 | related | - | 20 |
| 利民股份 | 002734 | 合成生物 | 受益标的 | related | - | 20 |
| 华恒生物 | 688639 | 合成生物 | 受益标的 | related | - | 20 |
| 华熙生物 | 688363 | 合成生物 | 透明质酸原料、医疗终端（医美、骨科 | related | L1_L3_candidate | 20 |

## 候选 7：中药

- **标准概念**：中药
- **申万一级**：医药生物
- **评分**：144.01
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.41 | 新高股46只，新高成交192.94999999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | day10排名第2，区间涨幅9.52% |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅7.46% |
| multi_period_rank | 19.2 | day5排名第7，区间涨幅8.66% |

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

## 候选 8：维生素

- **标准概念**：维生素
- **申万一级**：基础化工
- **评分**：126.05
- **触发类型**：limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（10），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.5 | 新高股33只，新高成交120.00000000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅5.81% |
| multi_period_rank | 17.6 | day5排名第9，区间涨幅7.9% |
| multi_period_rank | 16.8 | day10排名第10，区间涨幅6.98% |
| limit_heat | 5.75 | 涨停5只，市场占比6.94，排名15 |

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

## 候选 9：其他医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：115.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股2只，最高4板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 丽珠集团 | 000513 | 医药 | 医药相关产品/材料供应商 | related | L2 | 20 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 20 |
| 仙琚制药 | 002332 | 医药 | 甾体类原料药相关产品供应商 | related | L2 | 20 |
| 千红制药 | 002550 | 医药 | 片剂相关产品供应商 | related | L2 | 20 |
| 奇正藏药 | 002287 | 医药 | 藏药相关产品供应商 | related | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 山东药玻 | 600529 | 医药 | 各种药用玻璃瓶产品相关产品供应商 | related | L2 | 20 |
| 山河药辅 | 300452 | 医药 | 药用辅料相关产品供应商 | related | L2 | 20 |

## 候选 10：业绩

- **标准概念**：AI PC
- **申万一级**：基础化工
- **评分**：113.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 113.0 | 连板股5只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI PC | 2 |
| AI PCB | 2 |
| AI基础设施与国产算力 | 2 |
| AI处理器 | 2 |
| AI算力 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万润新能 | 688275 | AIDC发电设备 | 磷酸铁锂正极材料（含高压实密度新品）、钠离子电池正极材料、固态电池材料（... | related | L1_L3_candidate | 1 |
| 三环集团 | 300408 | AI算力 | MLCC（片式多层陶瓷电容器）、光通信陶瓷组件（光纤插芯、MT插芯、陶瓷... | core | L1_L3_candidate | 1 |
| 三友化工 | 600409 | PVC | 氯碱（烧碱53万吨、PVC 52.5万吨） | related | L1_L3_candidate | 1 |
| 万凯新材 | 301216 | 人形机器人 | 聚酯瓶片(PET)、天然气制乙二醇(MEG)、rPET生物酶法再生 | related | L1_L3_candidate | 1 |
| 万通发展 | 600246 | 低轨卫星 | PCIe高速交换芯片、毫米波射频芯片、AI算力运营 | related | L1_L3_candidate | 1 |
| 三力制药 | 603439 | 制药 | 中成药的研发、生产和销售、核心产品为开喉剑喷雾剂系列 | related | L2 | 1 |
| 万隆光电 | 300710 | 并购重组 | 广电网络设备、数据通信系统、拟收购中控信息（基础设施数智化） | core | L1_L3_candidate | 1 |
| 万集科技 | 300552 | 机器人与具身智能装备 | 激光雷达、智能网联（V2X、车路云一体化） | related | L1_L3_candidate | 1 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-427752dc0baf796c5ead artifact_sha=955d382eef29d0882be3649a2bfdac1c0681e71a337a5674cef8b712197d8b8a manifest_sha=4e901791ac7f9c1ed9d035c8a188c4ef695201cfc009ef34afb52df8139bda06 -->
