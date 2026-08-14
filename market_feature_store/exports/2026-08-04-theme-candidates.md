# 2026-08-04 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：22133.71
- **上涨家数**：3642
- **涨停 / 跌停**：138 / 0
- **容量前三行业**：1.电子(27.5%, super_capacity)、2.通信(9.5%, normal)、3.电力设备(7.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 算力租赁 | 算力租赁 | 计算机 | 196.12 | double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 2 | 液冷服务器 | 液冷服务器 | 电力设备 | 189.14 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 3 | 数据中心 | 数据中心 | 计算机 | 178.81 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 新能源车 | 新能源车 | - | 175.35 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 东数西算 | 东数西算 | - | 174.45 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 6 | 短剧游戏 | 游戏 | 传媒 | 167.02 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 7 | 跨境电商 | 跨境电商 | - | 161.98 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 8 | 云计算 | 云计算 | 计算机 | 158.86 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 9 | 智能电网 | 智能电网 | - | 158.73 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 10 | 医药医疗 | 医疗 | - | 158.48 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 智慧城市 | 智慧城市 | - | 158.48 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 12 | 通信设备 | 通信设备 | 通信 | 156.8 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 13 | 光通信 | 光通信 | 电力设备 | 155.25 | double_red、limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 14 | 商业航天 | 商业航天 | 国防军工 | 151.35 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 2 | 12 | 5 | - |
| 15 | 电力 | 电力 | 电力设备 | 145.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 16 | AI营销 | AI营销 | - | 137.65 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 3 | 0 | missing_concept、missing_evidence |
| 17 | 广告营销 | 广告营销 | - | 137.07 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 18 | 互联网广告 | 互联网广告 | - | 136.56 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 3 | 0 | missing_evidence |
| 19 | PCB | PCB | 电子 | 134.0 | double_red、capacity_industry、multi_period_rank | 5 | 12 | 5 | - |
| 20 | AI应用 | AI应用 | 计算机 | 133.0 | limit_advance_cluster | 1 | 12 | 5 | - |
| 21 | CPO概念 | CPO | - | 132.1 | double_red、limit_heat、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 22 | 元器件 | 电子元器件 | - | 128.9 | double_red、limit_heat、multi_period_rank | 2 | 12 | 0 | missing_evidence |
| 23 | PCB概念 | PCB概念 | - | 127.7 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 24 | 通信 | 通信 | - | 126.8 | double_red、multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 25 | 可控核聚变 | 可控核聚变 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 3 | 12 | 1 | - |
| 26 | 特高压 | 特高压 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 1 | - |
| 27 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 28 | 高压快充 | 高压快充 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 6 | 0 | missing_concept、missing_evidence |
| 29 | 智谱AI | 智谱AI | 计算机 | 123.13 | multi_period_rank、new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 30 | 3D打印 | 3D打印 | 机械设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 6G概念 | 6G | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 32 | AI医疗概念 | AI医疗 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 33 | 人脑工程 | 人脑工程 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 34 | 创新药 | 创新药 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 5 | - |
| 35 | 动力电池回收 | 动力电池回收 | - | 116.0 | double_red、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 36 | 化学制药 | 化学制药 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 37 | 医药 | 医药 | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 华为汽车 | 华为汽车 | - | 116.0 | double_red、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 39 | 华为算力 | 华为算力 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 40 | 口罩防护 | 口罩防护 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 工业母机 | 工业母机 | 机械设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 2 | - |
| 42 | 操作系统 | 操作系统 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 43 | 无人驾驶 | 无人驾驶 | 汽车 | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 44 | 粤港澳 | 粤港澳 | - | 116.0 | double_red、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 45 | 英伟达概念 | 英伟达 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 46 | 苹果概念 | 苹果概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 虚拟现实 | 虚拟现实 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 通用设备 | 通用设备 | 机械设备 | 116.0 | double_red、new_high_cluster | 0 | 7 | 0 | missing_concept、missing_evidence |
| 49 | 量子科技 | 量子科技 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 50 | 铜缆高速连接 | 铜 | 电力设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：196.12
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.42%，边际量 19.28%，成交额 1670.03 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.42%，边际量19.28%，成交1670.03亿 |
| new_high_direction | 43.17 | 新高股63只，新高成交253.50999999999996亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.95 | 涨停17只，市场占比12.32，排名19 |

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

## 候选 2：液冷服务器

- **标准概念**：液冷服务器
- **申万一级**：电力设备
- **评分**：189.14
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.45%，边际量 24.2%，成交额 2681.81 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.45%，边际量24.2%，成交2681.81亿 |
| new_high_direction | 52.49 | 新高股19只，新高成交199.30000000000007亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 10.65 | 涨停19只，市场占比13.77，排名14 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 液冷服务器 | 20 |
| 服务器 | 12 |
| 液冷 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中兴通讯 | 000063 | 服务器 | 服务器等算力产品突破头部互联网及行业客户 | related | L2 | 20 |
| 中国长城 | 000066 | 服务器 | 自主可控服务器和计算设备供应商 | related | L1 | 20 |
| 紫光股份 | 000938 | 服务器 | 服务器相关产品/材料供应商 | related | L2 | 20 |
| 申菱环境 | 301018 | 液冷 | 数据中心液冷CDU/Manifold/冷板等，海外业务和液冷取得较好进展 | core | L2 | 20 |
| 科创新源 | 300731 | 液冷 | 热管理系统业务（瑞泰克/创源智热）：新能源汽车动力电池液冷板、数据中心服... | core | L2 | 20 |
| 纳百川 | 301667 | 液冷 | 电池液冷板核心制造商，产品覆盖乘用车/储能/eVTOL/工程机械/船舶等... | core | L2 | 20 |
| 软通动力 | 301236 | 液冷 | Token工厂运营+液冷服务器一体化，签头部大模型推理协议 | core | L3 | 20 |
| 比亚迪电子 | - | 液冷 | 受益标的 | core | supply_chain | 20 |

## 候选 3：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：178.81
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.63%，边际量 23.1%，成交额 6576.85 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.63%，边际量23.1%，成交6576.85亿 |
| new_high_direction | 46.91 | 新高股137只，新高成交553.13亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 15.9 | 涨停34只，市场占比24.64，排名2 |

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

## 候选 4：新能源车

- **标准概念**：新能源车
- **申万一级**：-
- **评分**：175.35
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.43%，边际量 15.23%，成交额 4929.84 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.43%，边际量15.23%，成交4929.84亿 |
| new_high_direction | 44.15 | 新高股141只，新高成交332.1899999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 15.2 | 涨停32只，市场占比23.19，排名5 |

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
| 云铝股份 | 000807 | 新能源 | 电解铝冶炼、铝加工、氧化铝 | related | L1_L3_candidate | 20 |
| 北京双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 珠海港 | 000507 | 新能源 | 新能源板块收入24.7亿元占比56.34%（风电珠海港昇+管道燃气） | core | L2 | 20 |
| 万润新能 | 688275 | 新能源 | 动力电池及储能电池核心化学品原料配套商 | core | L1 | 20 |
| 中天科技 | 600522 | 新能源 | 新能源业务平台 | core | L1 | 20 |
| 中材科技 | 002080 | 新能源 | 风电和锂电材料平台 | core | L1 | 20 |
| 金房能源 | 001210 | 新能源 | 供热运营（核心基本盘）、新能源供热（高增速板块）、蓄冷储能（新兴业务）、... | core | L1_L3_candidate | 20 |
| 上海洗霸 | 603200 | 新能源 | 固态电池核心材料（硫化锂、硅碳负极、固态电解质） | related | L1_L3_candidate | 20 |

## 候选 5：东数西算

- **标准概念**：东数西算
- **申万一级**：-
- **评分**：174.45
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.17%，边际量 17.01%，成交额 3383.76 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.17%，边际量17.01%，成交3383.76亿 |
| new_high_direction | 43.95 | 新高股88只，新高成交316.28亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 14.5 | 涨停30只，市场占比21.74，排名6 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 东数西算 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亚康股份 | 301017 | 东数西算 | 算力租赁运营、算力基础设施综合服务(IT运维)、IT设备销售(系统集成) | related | L1_L3_candidate | 20 |
| 优刻得 | 688158 | 东数西算 | AI算力服务（智算中心、算力租赁）、公有云IaaS、PaaS | related | L1_L3_candidate | 20 |
| 光环新网 | 300383 | 东数西算 | AIDC智算中心、IDC数据中心、云计算(AWS中国) | related | L1_L3_candidate | 20 |
| 华胜天成 | 600410 | 东数西算 | AI算力基建服务、华为昇腾生态总包、信创业务 | related | L1_L3_candidate | 20 |
| 奥飞数据 | 300738 | 东数西算 | IDC数据中心服务、算力租赁、云计算服务 | related | L1_L3_candidate | 20 |
| 浙大网新 | 600797 | 东数西算 | 智算云服务、产业数智化（金融科技、能源数字化） | related | L1_L3_candidate | 20 |
| 甘肃能化 | 000552 | 东数西算 | 煤炭采掘、火电、煤化工（尿素、复合肥 | related | L1_L3_candidate | 20 |
| 盘江股份 | 600395 | 东数西算 | 焦煤开采销售、燃煤发电、新能源发电（光伏为主） | related | L1_L3_candidate | 20 |

## 候选 6：短剧游戏

- **标准概念**：游戏
- **申万一级**：传媒
- **评分**：167.02
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.49%，边际量 21.2%，成交额 614.05 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.49%，边际量21.2%，成交614.05亿 |
| new_high_direction | 44.22 | 新高股43只，新高成交337.94亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 6.8 | day5排名第10，区间涨幅11.79% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 游戏 | 10 |
| 短剧 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 世纪华通 | 002602 | 游戏 | 游戏出海龙头：点点互动《Whiteout Survival》《Kings... | core | L2 | 20 |
| 凯撒文化 | 002425 | 游戏 | 移动端网络游戏研发与运营商（子公司酷牛互动、天上友嘉），以联合运营模式为... | core | L2 | 20 |
| 名臣健康 | 002919 | 游戏 | 游戏研发+发行商（海南星炫/星际奥游/杭州雷焰，SLG/MMORPG/二... | core | L2 | 20 |
| 姚记科技 | 002605 | 游戏 | 休闲益智类精品手游研运一体（捕鱼系列等） | core | L2 | 20 |
| 完美世界 | 002624 | 游戏 | 自研引擎端手游全平台研发发行（诛仙/幻塔/异环等） | core | L2 | 20 |
| 实丰文化 | 002862 | 游戏 | 游戏营收1.38亿元/占比33.01%/同比+10.66% | core | L2 | 20 |
| 顺网科技 | 300113 | 游戏 | 电竞与游戏服务平台商 | core | L2 | 20 |
| 中青宝 | 300052 | 游戏 | 游戏研运商（传统业务） | related | L2 | 20 |

## 候选 7：跨境电商

- **标准概念**：跨境电商
- **申万一级**：-
- **评分**：161.98
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.47%，边际量 19.7%，成交额 1081.52 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.47%，边际量19.7%，成交1081.52亿 |
| new_high_direction | 45.98 | 新高股101只，新高成交478.6400000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 跨境电商 | 20 |
| 电商 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凯淳股份 | 301001 | 电商 | 品牌电商综合服务商（覆盖天猫/京东/抖音/小红书等全渠道，含AI客服数据... | core | L2 | 20 |
| 申通快递 | 002468 | 电商 | 经济快递产品面向电商商家/电商平台，收入494.97亿元占比89.05% | core | L2 | 20 |
| 丽人丽妆 | 605136 | 电商 | 电商相关产品/材料供应商 | related | L2 | 20 |
| 天音控股 | 000829 | 电商 | 电商业务板块 | related | L2 | 20 |
| 若羽臣 | 003010 | 电商 | 线上代运营相关产品供应商 | related | L2 | 20 |
| 三态股份 | 301558 | 跨境电商 | 出口跨境电商零售+第三方出口跨境电商物流综合企业：泛SKU零售，物流产品... | core | L2 | 20 |
| 中源家居 | 603709 | 跨境电商 | 功能沙发跨境品牌零售商（亚马逊等平台自有品牌出海） | core | L2 | 20 |
| 乐歌股份 | 300729 | 跨境电商 | 美国多节点自营公共海外仓网络运营商，为中大件跨境卖家提供一体化物流履约 | core | L2 | 20 |

## 候选 8：云计算

- **标准概念**：云计算
- **申万一级**：计算机
- **评分**：158.86
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.42%，边际量 15.43%，成交额 1724.33 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.42%，边际量15.43%，成交1724.33亿 |
| new_high_direction | 42.86 | 新高股70只，新高成交228.65999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 云计算 | 20 |
| 云计算数据中心 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 工业富联 | 601138 | 云计算 | AI服务器（GPU+ASIC）、高速交换机（800G/CPO）、云计算、... | core | L1_L3_candidate | 20 |
| 青云科技 | 688316 | 云计算 | 云计算产品与服务商 | core | L2 | 20 |
| 首都在线 | 300846 | 云计算 | 云主机及相关服务营收6.81亿元/占比55.07%/同比+18.57% | core | L2 | 20 |
| 光环新网 | 300383 | 云计算 | 云计算(AWS中国) | related | L1_L3_candidate | 20 |
| 利通电子 | 603629 | 云计算 | AI算力租赁、液晶电视精密金属结构件 | related | L1_L3_candidate | 20 |
| 太极股份 | 002368 | 云计算 | 太极云服务与数据智能全链路服务 | related | L2 | 20 |
| 奥飞数据 | 300738 | 云计算 | 云计算服务 | related | L1_L3_candidate | 20 |
| 杰创智能 | 301248 | 云计算 | AI+云计算（智算云服务/算力租赁） | related | L1_L3_candidate | 20 |

## 候选 9：智能电网

- **标准概念**：智能电网
- **申万一级**：-
- **评分**：158.73
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.41%，边际量 17.86%，成交额 1473.9 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.41%，边际量17.86%，成交1473.9亿 |
| new_high_direction | 42.73 | 新高股66只，新高成交218.34000000000006亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能电网 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万胜智能 | 300882 | 智能电网 | 电能仪表计量领域领先企业：通过招投标向国家电网、南方电网、蒙电集团销售智... | core | L2 | 20 |
| 三星电气 | 601567 | 智能电网 | 智能配用电板块聚焦海外战略，海外配电业务重点布局欧洲等市场（宁波三星医疗... | core | L2 | 20 |
| 三晖电气 | 002857 | 智能电网 | 电能表标准检测设备与自动化检定系统厂商 | core | L2 | 20 |
| 中电鑫龙 | 002298 | 智能电网 | 智能输配电设备与元器件制造商（列入全国电网建设与改造推荐名录） | core | L2 | 20 |
| 中能电气 | 300062 | 智能电网 | 输配电开关控制设备制造商（电网智能化产品占收入86.34%） | core | L2 | 20 |
| 未来电器 | 301386 | 智能电网 | 智能终端电器（智能模块）用于智能电网/智能楼宇/通信基站等无人值守场合，... | core | L2 | 20 |
| 西力科技 | 688616 | 智能电网 | 电能计量产品供应商，主营智能电表（单相/三相）、用电信息采集终端、电能计... | core | L2 | 20 |
| 许昌智能 | 920496 | 智能电网 | 国家级专精特新“小巨人”智能配用电设备商，主营配电终端、一二次融合成套环... | core | L2 | 20 |

## 候选 10：医药医疗

- **标准概念**：医疗
- **申万一级**：-
- **评分**：158.48
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.76%，边际量 26.69%，成交额 1184.95 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.76%，边际量26.69%，成交1184.95亿 |
| new_high_direction | 42.48 | 新高股43只，新高成交198.76999999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗 | 10 |
| 医药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 泰恩康 | 301263 | 医药 | 两性健康/肠胃/眼科三大板块，核心品种爱廷玖、和胃整肠丸、沃丽汀 | core | L2 | 20 |
| 神奇制药 | 600613 | 医药 | 医药制造+医药商业双板块，医药制造收入11.23亿元毛利率71.72%，... | core | L2 | 20 |
| 丽珠集团 | 000513 | 医药 | 医药相关产品/材料供应商 | related | L2 | 20 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 20 |
| 仙琚制药 | 002332 | 医药 | 甾体类原料药相关产品供应商 | related | L2 | 20 |
| 千红制药 | 002550 | 医药 | 片剂相关产品供应商 | related | L2 | 20 |
| 奇正藏药 | 002287 | 医药 | 藏药相关产品供应商 | related | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-0fef52661da7a8ab96de artifact_sha=1070e6e0e5c521d61a5ac0606a89116920ddbed6711744bb7ad585cabcf21d0b manifest_sha=dc23d01916f55d7d155910b2e4999250879009efb3771525b45f6ce674e80a7d -->
