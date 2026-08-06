# 2026-07-28 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：探底阶段
- **成交额**：20256.14
- **上涨家数**：2603
- **涨停 / 跌停**：61 / 49
- **容量前三行业**：1.电子(29.7%, super_capacity)、2.通信(9.2%, normal)、3.电力设备(7.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 电力 | 电力 | 电力设备 | 174.63 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 2 | 银行 | 银行 | 银行 | 166.81 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 人脑工程 | 人脑工程 | - | 164.66 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 4 | 数据要素 | 数据要素 | 计算机 | 157.11 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | AI智能体 | AI智能体 | 计算机 | 123.85 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 6 | ChatGPT概念 | ChatGPT概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | 新零售 | 零售 | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 8 | 脑机接口 | 脑机接口 | 医药生物 | 105.0 | limit_advance_cluster | 5 | 12 | 2 | - |
| 9 | 机器人 | 机器人 | 汽车 | 89.0 | limit_advance_cluster | 5 | 12 | 2 | - |
| 10 | 连板未映射 | - | 传媒 | 89.0 | limit_advance_cluster | 0 | 0 | 0 | placeholder_market_theme |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 电信服务 | 电信服务 | - | 85.6 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 12 | 化妆品 | 化妆品 | - | 79.2 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 风电 | 风电 | 电力设备 | 77.38 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 14 | 阿里概念 | 阿里概念 | - | 76.03 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 15 | 新能源车 | 新能源车 | - | 75.71 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | 区块链 | 区块链 | - | 75.61 | limit_heat、new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 17 | 数据中心 | 数据中心 | 计算机 | 75.54 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 跨境支付CIPS | IP | - | 75.04 | multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 19 | 大数据 | 大数据 | - | 74.98 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 一带一路 | 一带一路 | - | 74.5 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | 云计算 | 云计算 | 计算机 | 74.06 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 22 | 腾讯概念 | 腾讯概念 | - | 74.04 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 23 | 东数西算 | 东数西算 | - | 72.94 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 24 | 百度概念 | 百度概念 | - | 70.86 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 25 | 氢能源 | 氢能源 | 电力设备 | 70.49 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 26 | 中特估 | 中特估 | - | 69.14 | new_high_direction、new_high_cluster | 3 | 0 | 1 | missing_entity_exposures |
| 27 | 绿色电力 | 绿色电力 | - | 68.04 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 28 | 物联网 | 物联网 | - | 67.6 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 29 | 工业互联 | 工业互联网 | - | 67.49 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 30 | 医药医疗 | 医疗 | - | 67.34 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 化工 | 化工 | - | 67.06 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 32 | 婴童概念 | 婴童概念 | - | 67.05 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 碳中和 | 碳中和 | - | 64.75 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 34 | 公用事业 | 公用事业 | - | 62.57 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 35 | 国防军工 | 国防军工 | - | 60.69 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 地面兵装 | 地面兵装 | - | 60.0 | multi_period_rank | 3 | 4 | 1 | - |
| 37 | 智能电网 | 智能电网 | - | 59.28 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 充电桩 | 充电桩 | - | 59.09 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 电力设备 | 电力设备 | - | 59.03 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 日用化工 | 化工 | - | 58.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 41 | 食品饮料 | 食品饮料 | - | 57.6 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 农用化工 | 化工 | - | 56.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 43 | 白酒 | 白酒 | - | 56.8 | multi_period_rank、new_high_cluster | 2 | 12 | 2 | - |
| 44 | 光伏 | 光伏 | 电力设备 | 56.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 45 | 纺织制造 | 纺织制造 | - | 49.2 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 超临界发电 | 超临界发电 | - | 44.74 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 47 | 家庭医生 | 家庭医生 | - | 41.6 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 人工智能 | 人工智能 | - | 37.0 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 49 | 股权 | 私募股权投资 | - | 36.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 50 | DeepSeek概念 | DeepSeek | - | 35.6 | limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：电力

- **标准概念**：电力
- **申万一级**：电力设备
- **评分**：174.63
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股2只，最高4板，容量前三=True |
| new_high_direction | 33.63 | 新高股10只，新高成交130.65000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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
| 中恒电气 | 002364 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 四方股份 | 601126 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 科士达 | 002518 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 金盘科技 | 688676 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 中国西电 | 601179 | 新型电力系统 | 全产业链 | core | - | 20 |
| 中国能建 | 601868 | 新型电力系统 | 算电协同/三电协同 | core | - | 20 |
| 卧龙电驱 | 600580 | 新型电力系统 | 机器人组件及系统应用、数据中心HVAC电机、电动航空电推进系统 | related | L1_L3_candidate | 20 |
| 国电南瑞 | 600406 | 新型电力系统 | 算电协同/三电协同 | core | - | 20 |

## 候选 2：银行

- **标准概念**：银行
- **申万一级**：银行
- **评分**：166.81
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.21 | 新高股16只，新高成交256.51亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.0 | day3排名第6，区间涨幅2.89% |
| multi_period_rank | 24.2 | daily排名第7，区间涨幅2.16% |
| multi_period_rank | 24.2 | day10排名第7，区间涨幅5.73% |
| multi_period_rank | 24.2 | day5排名第7，区间涨幅4.7% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 银行 | 20 |
| 银行IT | 5 |
| AI应用 | 2 |
| 供应链金融 | 2 |
| 信创 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兴业银行 | 601166 | 银行 | 全国性股份制商业银行，以银行为主体的现代综合金融服务集团（2007年上交... | core | L2 | 20 |
| 北京银行 | 601169 | 银行 | 银行相关产品/材料供应商 | related | L2 | 20 |
| 南京银行 | 601009 | 银行 | 城商行——公司金融、零售金融、金融市场三大板块 | core | L2 | 20 |
| 宁波银行 | 002142 | 银行 | 优质城商行 | core | L2 | 20 |
| 紫金银行 | 601860 | 银行 | 总部位于江苏南京的地方法人农村商业银行，主营存贷款、票据贴现等传统银行业... | core | L2 | 20 |
| 西安银行 | 600928 | 银行 | 深耕陕西本土的城商行，业务含公司金融、零售金融、普惠金融，推进“数智西银... | core | L2 | 20 |
| 齐鲁银行 | 601665 | 银行 | 银行相关产品/材料供应商 | related | L2 | 20 |
| 天阳科技 | 300872 | 银行IT | 银行信贷/信用卡等核心系统IT服务商 | core | L2 | 20 |

## 候选 3：人脑工程

- **标准概念**：人脑工程
- **申万一级**：-
- **评分**：164.66
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.55%，边际量 13.66%，成交额 516.71 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.55%，边际量13.66%，成交516.71亿 |
| new_high_direction | 33.01 | 新高股10只，新高成交81.16999999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 9.2 | day3排名第7，区间涨幅2.77% |
| limit_heat | 6.45 | 涨停7只，市场占比11.48，排名29 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人脑工程 | 20 |
| 工程 | 10 |
| 神经调控 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三博脑科 | 301293 | 人脑工程 | 神经专科临床医疗服务端 | related | L1 | 20 |
| 伟思医疗 | 688580 | 人脑工程 | 脑电、神经电信号采集精密植入式微电极阵列及侵入脑机电极研发商 | related | L1 | 20 |
| 佳禾智能 | 300793 | 人脑工程 | 非侵入式脑电采集传感耳机及低功耗脑波耳机ODM制造商 | related | L1 | 20 |
| 冠昊生物 | 300238 | 人脑工程 | 脑膜修复与脑皮层保护生物材料厂商 | related | L1 | 20 |
| 创新医疗 | 002173 | 人脑工程 | 参股前沿脑机接口及脑电控制学术转化项目的科研投资平台 | related | L1 | 20 |
| 士兰微 | 600460 | 人脑工程 | 上游材料/设备 | peripheral | graph_only | 20 |
| 复旦微电 | 688385 | 人脑工程 | 图谱弱关联 | peripheral | graph_only | 20 |
| 汉威科技 | 300007 | 人脑工程 | 上游材料/设备 | peripheral | graph_only | 20 |

## 候选 4：数据要素

- **标准概念**：数据要素
- **申万一级**：计算机
- **评分**：157.11
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.86%，边际量 13.71%，成交额 1147.81 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.86%，边际量13.71%，成交1147.81亿 |
| new_high_direction | 41.11 | 新高股26只，新高成交88.58亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据要素 | 20 |
| AI智能体 | 2 |
| 数字孪生 | 2 |
| 数字政府 | 2 |
| 新型城镇化 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三维天地 | 301159 | 数据要素 | 全栈数据要素生态软件服务商：数据资产管理平台 | core | L2 | 20 |
| 上海钢联 | 300226 | 数据要素 | 大宗商品数据服务龙头（Mysteel）：全球领先的大宗商品及相关产业数据... | core | L2 | 20 |
| 东方国信 | 300166 | 数据要素 | 数据要素 | related | L1_L3_candidate | 20 |
| 东软集团 | 600718 | 数据要素 | 智能汽车互联、医疗健康信息化、数据价值化 | related | L1_L3_candidate | 20 |
| 中创股份 | 688695 | 数据要素 | 中间件软件销售、中间件定制化开发、中间件运维服务 | related | L1_L3_candidate | 20 |
| 中科曙光 | 603019 | 数据要素 | 芯片/核心器件 | related | L1_L3_candidate | 20 |
| 久远银海 | 002777 | 数据要素 | 数据要素 | related | L1_L3_candidate | 20 |
| 云赛智联 | 600602 | 数据要素 | 云计算及大数据、行业解决方案、智能产品 | related | L1_L3_candidate | 20 |

## 候选 5：AI智能体

- **标准概念**：AI智能体
- **申万一级**：计算机
- **评分**：123.85
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.38%，边际量 12.7%，成交额 1651.18 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.38%，边际量12.7%，成交1651.18亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比18.03，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI智能体 | 20 |
| AI智能体产业链 | 5 |
| AIoT | 2 |
| AI大模型 | 2 |
| AI平台 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万兴科技 | 300624 | AI智能体 | AI原生应用、万兴剧厂（AI漫剧）、AI Agent（ReelClaw） | related | L1_L3_candidate | 20 |
| 三维天地 | 301159 | AI智能体 | AI+实验室（SunwayLink/S-tab/SW-Foundry/S... | related | L1_L3_candidate | 20 |
| 世纪恒通 | 301428 | AI智能体 | 数据标注、AI智能体、OpenClaw部署、自动驾驶数据服务 | core | L1_L3_candidate | 20 |
| 东华软件 | 002065 | AI智能体 | 智能算力基建、行业智能化解决方案、金融科技 | related | L1_L3_candidate | 20 |
| 东软集团 | 600718 | AI智能体 | 智能汽车互联、医疗健康信息化、数据价值化 | related | L1_L3_candidate | 20 |
| 东阳光 | 600673 | AI智能体 | OpenClaw算力链与国产算力/华为系/字节系受益名单 | peripheral | graph_only | 20 |
| 中创股份 | 688695 | AI智能体 | AI智能体平台 | related | L1_L3_candidate | 20 |
| 中国电信 | 601728 | AI智能体 | 云服务、AI算力、量子通信 | related | L1_L3_candidate | 20 |

## 候选 6：ChatGPT概念

- **标准概念**：ChatGPT概念
- **申万一级**：-
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.58%，边际量 11.75%，成交额 532.22 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.58%，边际量11.75%，成交532.22亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：新零售

- **标准概念**：零售
- **申万一级**：-
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 1.12%，边际量 10.28%，成交额 632.27 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.12%，边际量10.28%，成交632.27亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 零售 | 10 |
| AI+视讯 | 2 |
| LED显示 | 2 |
| 轮胎出海 | 2 |
| 饮料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天虹股份 | 002419 | 零售 | 全渠道多业态零售商（百货/购物中心/超市） | core | L2 | 20 |
| 家家悦 | 603708 | 零售 | 超市连锁经营相关产品供应商 | related | L2 | 20 |
| 永辉超市 | 601933 | 零售 | 超市的连锁经营相关产品供应商 | related | L2 | 20 |
| 王府井 | 600859 | 零售 | 零售相关产品/材料供应商 | related | L2 | 20 |
| 致欧科技 | 301376 | 零售 | 跨境电商零售（亚马逊VC | related | L1_L3_candidate | 20 |
| 一心堂 | 002727 | 医药零售 | 西南地区医药零售连锁龙头：直营为主、加盟为辅，医药批发支撑，延伸互联网医... | core | L2 | 5 |
| 上海医药 | 601607 | 医药零售 | 医药零售渠道参与方 | peripheral | graph_only | 5 |
| 中百集团 | 000759 | 即时零售 | 线上超市前置仓与全渠道即时配送布局 | related | L2 | 5 |

## 候选 8：脑机接口

- **标准概念**：脑机接口
- **申万一级**：医药生物
- **评分**：105.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股4只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 脑机接口 | 20 |
| 侵入式脑机接口 | 5 |
| 非侵入式脑机接口 | 5 |
| BCI | 2 |
| 外骨骼 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 复旦微电 | 688385 | 侵入式脑机接口 | 图谱弱关联 | peripheral | graph_only | 20 |
| 三博脑科 | 301293 | 脑机接口 | 侵入式/介入式临床服务潜在相关 | peripheral | L1 | 20 |
| 乐普医疗 | 300003 | 脑机接口 | 脑机接口 | related | L1_L3_candidate | 20 |
| 伟思医疗 | 688580 | 脑机接口 | 脑电采集与神经调控设备材料平台 | related | L1 | 20 |
| 佳禾智能 | 300793 | 脑机接口 | 消费级主动降噪+非侵入脑信号采集可穿戴耳机代工厂商 | related | L1 | 20 |
| 冠昊生物 | 300238 | 脑机接口 | 高生物相容性脑机植入芯片包裹及改性生物绝缘保护硬膜供应商 | related | L1 | 20 |
| 创新医疗 | 002173 | 脑机接口 | 脑机接口业务（通过子公司博灵脑机） | related | L2 | 20 |
| 力合科创 | 002243 | 脑机接口 | 科技创新服务（科技创投+园区运营+成果转化）、新材料（日化包装材料） | related | L1_L3_candidate | 20 |

## 候选 9：机器人

- **标准概念**：机器人
- **申万一级**：汽车
- **评分**：89.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 机器人 | 20 |
| AI机器人 | 5 |
| 人形机器人 | 5 |
| 人形机器人丝杠 | 5 |
| 割草机器人 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 宜通世纪 | 300310 | AI机器人 | 通信网络工程服务、通信网络维护服务、通信网络优化服务 | related | L2 | 20 |
| 富奥股份 | 000030 | AI机器人 | - | related | L1 | 20 |
| 德赛西威 | 002920 | AI机器人 | 智能座舱、智能驾驶、网联服务 | core | L1_L3_candidate | 20 |
| 泽宇智能 | 301179 | AI机器人 | AI机器人 | core | L1_L3_candidate | 20 |
| 移远通信 | 603236 | AI机器人 | 蜂窝模组、车载模组、AI模组 | related | L1_L3_candidate | 20 |
| 万凯新材 | 301216 | 人形机器人 | 聚酯瓶片(PET)、天然气制乙二醇(MEG)、rPET生物酶法再生 | related | L1_L3_candidate | 20 |
| 万向钱潮 | 000559 | 人形机器人 | 研发布局人形机器人精密零部件（依托精密轴承技术平台） | peripheral | L2 | 20 |
| 万通液压 | 920839 | 人形机器人 | 研发人形机器人关节用高精度行星滚柱丝杠副、超大负载工业机器人油气分离平衡... | peripheral | L2 | 20 |

## 候选 10：连板未映射

- **标准概念**：-
- **申万一级**：传媒
- **评分**：89.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-4d1a222d32910c685caa artifact_sha=829b64c383e5dd3034036a85b1a3d27f4ad77156d51074cd33d218b956f60c27 manifest_sha=2e3344c713c2c72dcbe38fde2ff2d70d09fb2ca8524b725612d7e78c4f04fac0 -->
