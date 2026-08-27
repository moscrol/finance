# 2026-08-20 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：20792.47
- **上涨家数**：4096
- **涨停 / 跌停**：79 / 14
- **容量前三行业**：1.电子(26.4%, super_capacity)、2.医药生物(11.3%, normal)、3.通信(7.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 生物制药 | 生物制药 | - | 231.97 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 2 | 医药 | 医药 | 医药生物 | 209.46 | double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 3 | 免疫治疗 | 免疫治疗 | - | 200.83 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 5 | 0 | missing_evidence |
| 4 | CXO概念 | CXO | - | 198.77 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 5 | 基因概念 | 基因概念 | - | 198.76 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 6 | 创新药 | 创新药 | 医药生物 | 196.92 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 7 | 医疗服务 | 医疗服务 | 医药生物 | 195.02 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 8 | 减肥药 | 减肥药 | 医药生物 | 194.51 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 9 | 化学制药 | 化学制药 | 医药生物 | 189.33 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 10 | 合成生物 | 合成生物 | 医药生物 | 186.8 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 医药医疗 | 医疗 | - | 184.15 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 12 | AI医疗概念 | AI医疗 | - | 165.74 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 13 | 养老概念 | 养老概念 | - | 164.16 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 14 | 化学制剂 | 化学制剂 | - | 163.85 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 11 | 0 | missing_evidence |
| 15 | 仿制药 | 仿制药 | - | 158.09 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 16 | 黄金概念 | 黄金 | - | 149.04 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 17 | 疫苗 | 疫苗 | - | 140.45 | limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 18 | 黄金 | 黄金 | 有色金属 | 118.4 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 19 | 贵金属 | 贵金属 | 有色金属 | 116.0 | multi_period_rank、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 20 | 工业金属 | 工业金属 | 有色金属 | 106.0 | double_red、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 21 | 生物疫苗 | 疫苗 | - | 87.93 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 22 | 种植业 | 种植业 | - | 85.2 | multi_period_rank、new_high_cluster | 1 | 5 | 1 | - |
| 23 | 辅助生殖 | 辅助生殖 | 医药生物 | 83.55 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 9 | 1 | - |
| 24 | 维生素 | 维生素 | 基础化工 | 80.47 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 10 | 0 | missing_evidence |
| 25 | 一带一路 | 一带一路 | - | 76.4 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 26 | 数据中心 | 数据中心 | 计算机 | 75.03 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 婴童概念 | 婴童概念 | - | 74.48 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 28 | 新零售 | 零售 | - | 73.91 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 29 | 机械设备 | 机械设备 | - | 73.4 | limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 30 | 大数据 | 大数据 | - | 71.38 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 化工 | 化工 | - | 68.63 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 32 | 电子 | EDA（电子设计自动化） | - | 67.88 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 33 | 新能源车 | 新能源车 | - | 67.68 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 锂电池概念 | 锂 | - | 67.64 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 35 | 智能医疗 | 医疗 | - | 67.54 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 36 | 乡村振兴 | 乡村振兴 | - | 67.35 | new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 37 | 医美概念 | 医美 | - | 67.33 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 38 | 化工原料 | 化工 | - | 67.26 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 39 | 交通运输 | 交通运输 | - | 67.18 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 40 | 氢能源 | 氢能源 | 电力设备 | 67.1 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 41 | 物联网 | 物联网 | - | 67.1 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 42 | 宠物经济 | 宠物经济 | 社会服务 | 67.08 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 43 | 东数西算 | 东数西算 | - | 66.57 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 44 | 航运概念 | 航运 | - | 66.33 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 45 | 口罩防护 | 口罩防护 | - | 64.76 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 民营医院 | 民营医院 | - | 63.5 | limit_heat、new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 47 | 有色 | 有色冶炼装备 | - | 63.43 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 48 | 阿里概念 | 阿里概念 | - | 62.84 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 半导体 | 半导体 | 电子 | 61.63 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 50 | 通信设备 | 通信设备 | 通信 | 58.85 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：生物制药

- **标准概念**：生物制药
- **申万一级**：-
- **评分**：231.97
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 7.82%，边际量 85.53%，成交额 586.07 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅7.82%，边际量85.53%，成交586.07亿 |
| new_high_direction | 42.82 | 新高股39只，新高成交225.64000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅7.82% |
| multi_period_rank | 21.6 | day10排名第4，区间涨幅14.38% |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅3.32% |
| limit_heat | 9.95 | 涨停17只，市场占比21.52，排名4 |

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
| 振东制药 | 300158 | 制药 | 中成药+化药双线制药企业（核心品种复方苦参注射液、米诺地尔搽剂、西黄丸、... | core | L2 | 20 |
| 灵康药业 | 603669 | 制药 | 化学药品制剂制造企业，55个品种入国家医保目录 | core | L2 | 20 |
| 三力制药 | 603439 | 制药 | 中成药的研发、生产和销售、核心产品为开喉剑喷雾剂系列 | related | L2 | 20 |
| 九洲药业 | 603456 | 制药 | 小分子CDMO、TIDES（多肽、小核酸 | related | L1_L3_candidate | 20 |
| 仙琚制药 | 002332 | 制药 | 甾体原料药和制剂的研制、生产与销售 | related | L2 | 20 |

## 候选 2：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：209.46
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 3.37%，边际量 60.42%，成交额 1759.29 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.37%，边际量60.42%，成交1759.29亿 |
| new_high_direction | 48.96 | 新高股105只，新高成交716.9199999999997亿，容量前三=False |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 14.5 | 涨停30只，市场占比37.97，排名2 |

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
| 寿仙谷 | 603896 | 医药 | 灵芝、铁皮石斛等名贵中药材育种-栽培-饮片炮制-深加工全产业链中药企业 | core | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 康芝药业 | 300086 | 医药 | 国内领先的儿童药生产销售企业（儿童大健康） | core | L2 | 20 |
| 振东制药 | 300158 | 医药 | 肿瘤/皮科/消化/泌尿/心脑管线中西药生产销售企业，拥有592个批文、4... | core | L2 | 20 |
| 柳药集团 | 603368 | 医药 | 综合性医药大健康产业集团（医药商业为主业+中药工业：中药饮片、中药配方颗... | core | L2 | 20 |
| 梓橦宫 | 920566 | 医药 | 神经系统/消化系统处方药研发生产企业，胞磷胆碱钠片为拳头品种（占营收约7... | core | L2 | 20 |

## 候选 3：免疫治疗

- **标准概念**：免疫治疗
- **申万一级**：-
- **评分**：200.83
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 7.01%，边际量 90.65%，成交额 582.48 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（5），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅7.01%，边际量90.65%，成交582.48亿 |
| new_high_direction | 42.18 | 新高股21只，新高成交174.69亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 17.4 | daily排名第3，区间涨幅7.01% |
| multi_period_rank | 17.4 | day10排名第3，区间涨幅15.24% |
| limit_heat | 7.85 | 涨停11只，市场占比13.92，排名9 |

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

## 候选 4：CXO概念

- **标准概念**：CXO
- **申万一级**：-
- **评分**：198.77
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.26%，边际量 50.19%，成交额 773.84 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.26%，边际量50.19%，成交773.84亿 |
| new_high_direction | 44.27 | 新高股22只，新高成交341.43亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 19.0 | day10排名第1，区间涨幅17.27% |
| multi_period_rank | 13.4 | daily排名第8，区间涨幅5.26% |
| limit_heat | 6.1 | 涨停6只，市场占比7.59，排名21 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CXO | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 普蕊斯 | 301257 | CXO | 医药研发外包链条上的SMO环节头部企业（临床试验执行外包） | core | L2 | 20 |
| 睿智医药 | 300149 | CXO | 医药研发服务及生产外包业务收入11.21亿元占98.80%同比+16.6... | core | L2 | 20 |
| 药石科技 | 300725 | CXO | 以分子砌块为核心能力底座的一体化CRDMO创新服务商，覆盖药物发现、临床... | core | L2 | 20 |
| 宣泰医药 | 688247 | CXO | 创新药CRO/CMO一体化服务 | related | L2 | 20 |
| 和元生物 | 688238 | CXO | 细胞和基因治疗CDMO、CRO、再生医学 | related | L1_L3_candidate | 20 |
| 星昊医药 | 920017 | CXO | 利用MAH制度对外提供CMC/CMO一体化服务，2025年该业务收入5,... | related | L2 | 20 |
| 苑东生物 | 688513 | CXO | 化学原料药国内外销售并为客户提供原料药CMO/CDMO服务 | related | L2 | 20 |
| 药明康德 | 603259 | CXO | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 5：基因概念

- **标准概念**：基因概念
- **申万一级**：-
- **评分**：198.76
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.65%，边际量 31.46%，成交额 716.11 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.65%，边际量31.46%，成交716.11亿 |
| new_high_direction | 44.66 | 新高股40只，新高成交372.64亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.8 | daily排名第5，区间涨幅5.65% |
| multi_period_rank | 13.4 | day10排名第8，区间涨幅10.44% |
| limit_heat | 8.9 | 涨停14只，市场占比17.72，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 6：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：196.92
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.5%，边际量 65.58%，成交额 1791.55 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.5%，边际量65.58%，成交1791.55亿 |
| new_high_direction | 58.87 | 新高股87只，新高成交709.9799999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 12.05 | 涨停23只，市场占比29.11，排名3 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 20 |
| 创新药RWA | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一品红 | 300723 | 创新药 | 核心创新药AR882为高效选择性URAT1抑制剂，覆盖降尿酸治疗痛风、溶... | core | L2 | 20 |
| 上海谊众 | 688091 | 创新药 | 抗肿瘤创新药企业：紫杉醇胶束等纳米制剂，研产销一体化 | core | L2 | 20 |
| 亿帆医药 | 002019 | 创新药 | 医药+维生素B5双主业，创新生物药亿立舒全球销售 | core | L2 | 20 |
| 众生药业 | 002317 | 创新药 | 抗流感一类创新药昂拉地韦片（全球首个靶向PB2亚基口服抗流感药） | core | L2 | 20 |
| 南新制药 | 688189 | 创新药 | 抗流感创新药领军企业：帕拉米韦氯化钠注射液为国内首个上市的抗流感1.1类... | core | L2 | 20 |
| 智翔金泰 | 688443 | 创新药 | 自免/感染/肿瘤领域创新抗体药企（16个在研产品、GR1803双抗lic... | core | L2 | 20 |
| 神州细胞 | 688520 | 创新药 | 生物药企业：重组八因子（血友病）、抗体药物、重组蛋白与创新疫苗管线 | core | L2 | 20 |
| 舒泰神 | 300204 | 创新药 | 创新生物制药企业，上市产品苏肽生（注射用鼠神经生长因子）与舒泰清；在研管... | core | L2 | 20 |

## 候选 7：医疗服务

- **标准概念**：医疗服务
- **申万一级**：医药生物
- **评分**：195.02
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.45%，边际量 60.09%，成交额 634.2 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.45%，边际量60.09%，成交634.2亿 |
| new_high_direction | 50.07 | 新高股13只，新高成交309.28999999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 13.2 | day10排名第2，区间涨幅16.03% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比6.33，排名30 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗服务 | 20 |
| 医疗 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三星电气 | 601567 | 医疗服务 | 医疗服务运营板块 | core | L2 | 20 |
| 新里程 | 002219 | 医疗服务 | 民营区域医疗集团（4家三级医院、24家医院），2025年医疗行业收入26... | core | L2 | 20 |
| 普瑞眼科 | 301239 | 医疗服务 | 全国性直营连锁眼科专科医院集团（36家医院+4家门诊部，覆盖25城） | core | L2 | 20 |
| 朗玛信息 | 300288 | 医疗服务 | 综合性三级医院运营商（控股子公司贵阳六医，25个临床医技科室） | core | L2 | 20 |
| 尚荣医疗 | 002551 | 医疗服务 | 医院建设EPC总承包与医疗专业工程服务商（国内医院建设整体解决方案先行者... | related | L2 | 20 |
| 山外山 | 688410 | 医疗服务 | 连锁血液透析中心运营商（直销模式，全产业链一体化+全程信息化管理） | related | L2 | 20 |
| 模塑科技 | 000700 | 医疗服务 | 旗下无锡明慈医院为区域性心血管疾病诊疗中心，公司为汽车零部件+医疗健康双... | related | L2 | 20 |
| 皓元医药 | 688131 | 医疗服务 | 生命科学试剂（前端）、原料药、中间体 | related | L1_L3_candidate | 20 |

## 候选 8：减肥药

- **标准概念**：减肥药
- **申万一级**：医药生物
- **评分**：194.51
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.64%，边际量 90.92%，成交额 618.37 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.64%，边际量90.92%，成交618.37亿 |
| new_high_direction | 52.06 | 新高股18只，新高成交164.59000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| multi_period_rank | 10.0 | day10排名第6，区间涨幅12.1% |
| limit_heat | 6.45 | 涨停7只，市场占比8.86，排名18 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 信达生物 | 01801.HK | 创新药 | BD与减肥药/双抗管线平台 | core | L1 | 1 |
| 凯莱英 | 002821 | 创新药 | CDMO与减肥药供应链 | related | graph_only | 1 |

## 候选 9：化学制药

- **标准概念**：化学制药
- **申万一级**：医药生物
- **评分**：189.33
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.76%，边际量 58.23%，成交额 999.64 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.76%，边际量58.23%，成交999.64亿 |
| new_high_direction | 55.83 | 新高股55只，新高成交466.51000000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 7.5 | 涨停10只，市场占比12.66，排名10 |

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
| 振东制药 | 300158 | 制药 | 中成药+化药双线制药企业（核心品种复方苦参注射液、米诺地尔搽剂、西黄丸、... | core | L2 | 20 |
| 灵康药业 | 603669 | 制药 | 化学药品制剂制造企业，55个品种入国家医保目录 | core | L2 | 20 |
| 三力制药 | 603439 | 制药 | 中成药的研发、生产和销售、核心产品为开喉剑喷雾剂系列 | related | L2 | 20 |

## 候选 10：合成生物

- **标准概念**：合成生物
- **申万一级**：医药生物
- **评分**：186.8
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.53%，边际量 30.09%，成交额 763.5 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.53%，边际量30.09%，成交763.5亿 |
| new_high_direction | 52.6 | 新高股40只，新高成交208.13000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比15.19，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 合成生物 | 20 |
| 合成生物学 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 楚天科技 | 300358 | 合成生物 | 制药装备及整体技术解决方案 | core | L1_L3_candidate | 20 |
| 蔚蓝生物 | 603739 | 合成生物 | 以酶制剂、微生态制剂、动物保健品为核心的生物科技企业，为生物制造提供核心... | core | L2 | 20 |
| 锦波生物 | 832982 | 合成生物 | 山西省重点产业链合成生物产业链“链主”企业，通过AI驱动合成生物学生产重... | core | L2 | 20 |
| 中油工程 | 600339 | 合成生物 | 合成生物学等） | related | L1_L3_candidate | 20 |
| 共同药业 | 300966 | 合成生物 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 20 |
| 华熙生物 | 688363 | 合成生物 | 透明质酸原料、医疗终端（医美、骨科 | related | L1_L3_candidate | 20 |
| 无锡晶海 | 920547 | 合成生物 | 以发酵法/合成生物学技术生产氨基酸，建有合成生物学-生物制造研发平台（无... | related | L2 | 20 |
| 星湖科技 | 600866 | 合成生物 | 以赖氨酸为前体合成戊二胺及尼龙56关键技术产业化，获国家技术发明奖提名 | related | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-39fea160f67803c5284a artifact_sha=197d2b4ccf59f2f037892adb2ccc822d8082e72ad578fc1c071b66b627cebff1 manifest_sha=ff94c49e4ab25cd49c4d744cef3eb6d5b22955db8b7f39576e1ef2954bfe226b -->
