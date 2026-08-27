# 2026-08-13 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：25507.6
- **上涨家数**：1143
- **涨停 / 跌停**：59 / 4
- **容量前三行业**：1.电子(27.5%, super_capacity)、2.通信(8.4%, normal)、3.医药生物(8.3%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | CXO概念 | CXO | - | 229.6 | double_red、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 2 | 创新药 | 创新药 | 医药生物 | 217.71 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 3 | 医疗服务 | 医疗服务 | 医药生物 | 198.5 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 4 | 减肥药 | 减肥药 | 医药生物 | 189.2 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 5 | 通信设备 | 通信设备 | 通信 | 183.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 6 | 通信 | 通信 | - | 177.09 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 7 | 医药医疗 | 医疗 | - | 174.23 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 8 | 算力租赁 | 算力租赁 | 计算机 | 173.2 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 9 | 医药 | 医药 | - | 169.72 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 光通信 | 光通信 | 电力设备 | 165.54 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 低价股 | 低价股 | 医药生物 | 147.0 | limit_advance_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 12 | 电力 | 电力 | 公用事业 | 146.0 | double_red、limit_advance_cluster、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 13 | 基因概念 | 基因概念 | - | 144.4 | double_red、multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 14 | 化学制药 | 化学制药 | 医药生物 | 133.6 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 15 | 合成生物 | 合成生物 | 医药生物 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 1 | - |
| 16 | 公用事业 | 公用事业 | - | 121.75 | double_red、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 17 | AI医疗概念 | AI医疗 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 18 | IT设备 | IT设备 | - | 116.0 | double_red、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 19 | 智能医疗 | 医疗 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 20 | 股权 | 私募股权投资 | 计算机 | 113.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 21 | 大消费 | 消费 | 传媒 | 97.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 22 | PCB | PCB | 电子 | 96.59 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 23 | 数据中心 | 数据中心 | 计算机 | 91.15 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 新能源车 | 新能源车 | - | 90.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 25 | CPO概念 | CPO | - | 89.74 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 26 | 东数西算 | 东数西算 | - | 86.83 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 27 | 免疫治疗 | 免疫治疗 | - | 86.8 | multi_period_rank、new_high_cluster | 2 | 5 | 0 | missing_evidence |
| 28 | 先进封装 | 先进封装 | 电子 | 86.64 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 29 | 元器件 | 电子元器件 | - | 86.14 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 30 | 存储芯片 | 存储芯片 | 电子 | 85.17 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 电子 | EDA（电子设计自动化） | - | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 32 | 腾讯概念 | 腾讯概念 | - | 82.37 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 生物制药 | 生物制药 | - | 82.0 | multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 34 | 抖音概念 | 抖音概念 | - | 81.58 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 物联网 | 物联网 | - | 81.08 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 36 | 人形机器人 | 人形机器人 | 机械设备 | 80.81 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 37 | 液冷服务器 | 液冷服务器 | 电力设备 | 80.41 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 38 | 商业航天 | 商业航天 | 国防军工 | 78.08 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 39 | 充电桩 | 充电桩 | - | 78.06 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 40 | 氢能源 | 氢能源 | 电力设备 | 77.96 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 41 | 国防军工 | 国防军工 | - | 76.99 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 42 | OLED概念 | LED | - | 76.83 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 43 | PCB概念 | PCB概念 | - | 76.82 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 44 | 无人驾驶 | 无人驾驶 | 汽车 | 76.57 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 45 | 小米概念 | 小米概念 | - | 76.21 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 英伟达概念 | 英伟达 | - | 75.81 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 47 | 锂电池概念 | 锂 | - | 75.5 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 48 | AIGC概念 | AIGC | - | 75.31 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 49 | 一带一路 | 一带一路 | - | 75.17 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 50 | 粤港澳 | 粤港澳 | - | 74.81 | new_high_direction、new_high_cluster | 0 | 10 | 0 | missing_concept、missing_evidence |

## 五、核心候选明细

## 候选 1：CXO概念

- **标准概念**：CXO
- **申万一级**：-
- **评分**：229.6
- **触发类型**：double_red、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 3.16%，边际量 35.81%，成交额 705.44 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.16%，边际量35.81%，成交705.44亿 |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅3.16% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅16.57% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅4.81% |
| multi_period_rank | 27.4 | day10排名第3，区间涨幅28.42% |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 2：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：217.71
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.81%，边际量 31.39%，成交额 1565.54 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.81%，边际量31.39%，成交1565.54亿 |
| new_high_direction | 57.66 | 新高股99只，新高成交612.4500000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.0 | day5排名第6，区间涨幅9.15% |
| multi_period_rank | 12.6 | daily排名第9，区间涨幅1.81% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 6.45 | 涨停7只，市场占比11.86，排名11 |

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

## 候选 3：医疗服务

- **标准概念**：医疗服务
- **申万一级**：医药生物
- **评分**：198.5
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 2.4%，边际量 24.81%，成交额 593.39 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4%，边际量24.81%，成交593.39亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅2.4% |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅14.93% |
| multi_period_rank | 20.0 | day10排名第6，区间涨幅25.39% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |
| limit_heat | 6.1 | 涨停6只，市场占比10.17，排名18 |

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

## 候选 4：减肥药

- **标准概念**：减肥药
- **申万一级**：医药生物
- **评分**：189.2
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 1.97%，边际量 34.53%，成交额 517.96 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.97%，边际量34.53%，成交517.96亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 22.4 | day5排名第3，区间涨幅11.92% |
| multi_period_rank | 20.8 | day3排名第5，区间涨幅3.65% |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅1.97% |
| capacity_industry | 10.0 | 所属申万一级 医药生物 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 信达生物 | 01801.HK | 创新药 | BD与减肥药/双抗管线平台 | core | L1 | 1 |
| 凯莱英 | 002821 | 创新药 | CDMO与减肥药供应链 | related | graph_only | 1 |

## 候选 5：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：183.24
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.32%，边际量 17.02%，成交额 2180.99 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.32%，边际量17.02%，成交2180.99亿 |
| new_high_direction | 57.24 | 新高股51只，新高成交579.5899999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 通信设备 | 20 |
| 通信 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 普天科技 | 002544 | 通信 | 面向数字时代提供ICT融合相关产品供应商 | related | L2 | 20 |
| 三维通信 | 002115 | 通信设备 | 无线网络优化覆盖设备与服务商 | core | L2 | 20 |
| 世嘉科技 | 002796 | 通信设备 | 波发特滤波器、基站天线等移动通信设备 | core | L2 | 20 |
| 天邑股份 | 300504 | 通信设备 | 面向国内运营商的宽带终端及网优设备供应商 | core | L2 | 20 |
| 宁通信B | 200468 | 通信设备 | 信息通信产品及解决方案提供商 | core | L2 | 20 |
| 平治信息 | 300571 | 通信设备 | 面向三大运营商的通信智能终端设备供应商（智慧家庭系列第一梯队） | core | L2 | 20 |
| 盛洋科技 | 603703 | 通信设备 | 显示器件营收2.93亿元/毛利率30.13%/同比-11.34% | core | L2 | 20 |
| 盛路通信 | 002446 | 通信设备 | 移动通信天线/射频器件/有源一体化设备，频段覆盖1000KHz至80GH... | core | L2 | 20 |

## 候选 6：通信

- **标准概念**：通信
- **申万一级**：-
- **评分**：177.09
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.85%，边际量 17.74%，成交额 2017.94 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.85%，边际量17.74%，成交2017.94亿 |
| new_high_direction | 47.09 | 新高股45只，新高成交566.9199999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 14.0 | day3排名第1，区间涨幅4.87% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 通信 | 20 |
| 5G_6G通信 | 5 |
| 5G通信 | 5 |
| 6G通信 | 5 |
| 专网通信 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中兴通讯 | 000063 | 5G通信 | 全球主要通信设备商，“连接+算力”双轮驱动 | core | L2 | 20 |
| 中国卫通 | 601698 | 5G通信 | 通信网络卫星补充环节 | peripheral | L1 | 20 |
| 信科移动 | 688387 | 5G通信 | 图谱弱关联 | peripheral | graph_only | 20 |
| 信维通信 | 300136 | 5G通信 | 5G-A终端多天线及高精密LCP、射频电磁兼容件供应商 | core | L1 | 20 |
| 中国移动 | 600941 | 5G通信 | 5G通信运营商 | related | L2_candidate | 20 |
| 中英科技 | 300936 | 5G通信 | 高频覆铜板（PTFE）、VC散热片、引线框架 | related | L1 | 20 |
| 瑞玛精密 | 002976 | 5G通信 | 5G通讯滤波器与天线设备，通信设备收入同比+365.66% | related | L2 | 20 |
| 神宇股份 | 300563 | 5G通信 | - | related | L1 | 20 |

## 候选 7：医药医疗

- **标准概念**：医疗
- **申万一级**：-
- **评分**：174.23
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.06%，边际量 30.49%，成交额 2100.29 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.06%，边际量30.49%，成交2100.29亿 |
| new_high_direction | 49.68 | 新高股169只，新高成交774.18亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比22.03，排名3 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗 | 10 |
| 医药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 寿仙谷 | 603896 | 医药 | 灵芝、铁皮石斛等名贵中药材育种-栽培-饮片炮制-深加工全产业链中药企业 | core | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 康芝药业 | 300086 | 医药 | 国内领先的儿童药生产销售企业（儿童大健康） | core | L2 | 20 |
| 振东制药 | 300158 | 医药 | 肿瘤/皮科/消化/泌尿/心脑管线中西药生产销售企业，拥有592个批文、4... | core | L2 | 20 |
| 柳药集团 | 603368 | 医药 | 综合性医药大健康产业集团（医药商业为主业+中药工业：中药饮片、中药配方颗... | core | L2 | 20 |
| 梓橦宫 | 920566 | 医药 | 神经系统/消化系统处方药研发生产企业，胞磷胆碱钠片为拳头品种（占营收约7... | core | L2 | 20 |
| 泰恩康 | 301263 | 医药 | 两性健康/肠胃/眼科三大板块，核心品种爱廷玖、和胃整肠丸、沃丽汀 | core | L2 | 20 |
| 浙江震元 | 000705 | 医药 | 绍兴区域综合性医药企业（流通+工业+中药饮片全产业链） | core | L2 | 20 |

## 候选 8：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：173.2
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 93.0 | 连板股2只，最高3板，容量前三=False |
| new_high_direction | 48.45 | 新高股70只，新高成交676.0500000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比8.47，排名25 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 算力租赁 | 20 |
| 算力 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云天励飞 | 688343 | 算力 | 智算集群与AI训练推理算力服务商 | core | L2 | 20 |
| 曙光数创 | 872808 | 算力 | AI算力中心散热基础设施供应商 | core | L2 | 20 |
| 深南电路 | 002916 | 算力 | AI服务器/交换机高多层PCB核心供应商 | core | L2 | 20 |
| 直真科技 | 003007 | 算力 | 算力服务收入1.14亿元（新增），战略布局智算中心建设与运营服务 | core | L2 | 20 |
| 软通动力 | 301236 | 算力 | 计算产品与智能电子+智算服务，软硬一体 | core | L2 | 20 |
| 云赛智联 | 600602 | 算力 | 上海算力建设及城市大脑运营主力军 | core | L1 | 20 |
| 中电港 | 001287 | 算力 | AI处理器/GPU等算力芯片分销与方案服务商 | related | L2 | 20 |
| 中石科技 | 300684 | 算力 | 热管理材料（导热石墨、VC均热板、TIM | related | L1_L3_candidate | 20 |

## 候选 9：医药

- **标准概念**：医药
- **申万一级**：-
- **评分**：169.72
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.94%，边际量 33.7%，成交额 1538.52 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.94%，边际量33.7%，成交1538.52亿 |
| new_high_direction | 47.27 | 新高股104只，新高成交581.3400000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比11.86，排名13 |

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

## 候选 10：光通信

- **标准概念**：光通信
- **申万一级**：电力设备
- **评分**：165.54
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_direction | 50.54 | 新高股60只，新高成交843.5799999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光通信 | 20 |
| 通信 | 10 |
| 光通信与AI网络基础设施 | 5 |
| 光通信测试仪器 | 5 |
| 光通信滤光片 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | 光通信 | MLCC（片式多层陶瓷电容器）、光通信陶瓷组件（光纤插芯、MT插芯、陶瓷... | core | L1_L3_candidate | 20 |
| 久之洋 | 300516 | 光通信 | 星间激光通信核心部件（光纤放大器EDFA、捕跟相机）、低空经济/反无人机... | core | L1_L3_candidate | 20 |
| 天邑股份 | 300504 | 光通信 | 接入网宽带网络终端与智能组网产品 | core | L2 | 20 |
| 腾景科技 | 688195 | 光通信 | 光模块/光器件上游精密光学元组件供应商，受益数通算力需求 | core | L2 | 20 |
| 中瓷电子 | 003031 | 光通信 | 光通信陶瓷外壳及器件外壳供应商 | core | L1 | 20 |
| 华脉科技 | 603042 | 光通信 | 光通信网络设备制造、无线通信网络设备制造 | core | L2 | 20 |
| 国缆检测 | 301289 | 光通信 | 电线电缆及光纤光缆检验检测、电化学储能检测、超高压、特高压检测 | core | L1_L3_candidate | 20 |
| 兆驰股份 | 002429 | 光通信 | 光通信产业链业务板块 | related | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-0df6fb8c45b3f7de95b7 artifact_sha=08f67f1e0fd41600dce88d702c9a1bda591b49d5d74cd7f82c9f8babc8cf9b23 manifest_sha=de8e7bab78f27085bcf5050eeb2aa3603b5b0c002852bfec116643d1788c9857 -->
