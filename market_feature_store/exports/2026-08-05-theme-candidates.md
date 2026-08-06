# 2026-08-05 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：26594.32
- **上涨家数**：3725
- **涨停 / 跌停**：103 / 1
- **容量前三行业**：1.电子(29.3%, super_capacity)、2.通信(10.2%, normal)、3.计算机(7.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 算力租赁 | 算力租赁 | 计算机 | 296.19 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 2 | PCB | PCB | 电子 | 243.0 | double_red、capacity_industry、limit_advance_cluster、multi_period_rank | 5 | 12 | 5 | - |
| 3 | 光通信 | 光通信 | 电力设备 | 228.15 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 5 | - |
| 4 | 云计算 | 云计算 | 计算机 | 182.09 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 5 | 有色 | 有色冶炼装备 | - | 173.33 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 6 | 物联网 | 物联网 | - | 171.3 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 7 | 东数西算 | 东数西算 | - | 169.77 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 8 | 计算机 | 计算机外设 | - | 165.35 | double_red、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 9 | 黄金概念 | 黄金 | - | 164.29 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 10 | 工业金属 | 工业金属 | 有色金属 | 160.95 | double_red、new_high_direction、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 智能医疗 | 医疗 | - | 160.61 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 12 | 信息安全 | 信息安全 | - | 159.94 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 13 | 智慧城市 | 智慧城市 | - | 159.85 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 14 | 液冷服务器 | 液冷服务器 | 电力设备 | 159.26 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 15 | 特斯拉概念 | 特斯拉概念 | - | 159.26 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 16 | 基因概念 | 基因概念 | - | 151.12 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 玻璃基板 | 玻璃基板 | 电子 | 138.0 | double_red、limit_advance_cluster、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 18 | CPO概念 | CPO | - | 127.05 | double_red、limit_heat、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 19 | 消费电子 | 消费电子 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 20 | 通信设备 | 通信设备 | 通信 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 1 | - |
| 21 | 量子科技 | 量子科技 | 计算机 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 1 | - |
| 22 | 智能穿戴 | 智能穿戴 | - | 123.5 | double_red、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 23 | 小金属 | 小金属 | 有色金属 | 123.15 | double_red、limit_heat、new_high_cluster | 3 | 12 | 2 | - |
| 24 | AI应用 | AI应用 | 传媒 | 121.0 | limit_advance_cluster | 1 | 12 | 5 | - |
| 25 | PCB概念 | PCB概念 | - | 120.55 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 26 | 3D打印 | 3D打印 | 机械设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 6G概念 | 6G | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 28 | IT设备 | IT设备 | - | 116.0 | double_red、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 29 | 国资云 | 国资云 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 30 | 操作系统 | 操作系统 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 智能交通 | 智能交通 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 32 | 毫米波雷达 | 毫米波雷达 | 汽车 | 116.0 | double_red、new_high_cluster | 4 | 12 | 1 | - |
| 33 | 石墨烯 | 石墨烯 | - | 116.0 | double_red、new_high_cluster | 2 | 10 | 2 | - |
| 34 | 稀土永磁 | 稀土永磁 | 有色金属 | 116.0 | double_red、new_high_cluster | 3 | 12 | 2 | - |
| 35 | 稀有金属 | 稀有金属 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 36 | 英伟达概念 | 英伟达 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 37 | 苹果概念 | 苹果概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 39 | 钴金属 | 钴金属 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 40 | 镍金属 | 镍金属 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 磷化铟反制 | 磷化铟 | 电子 | 115.0 | limit_advance_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 42 | AI手机PC | AI手机 | - | 114.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 43 | OLED概念 | LED | - | 114.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 44 | 光学光电 | 光学 | - | 114.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 45 | 折叠屏 | 折叠屏 | - | 114.0 | double_red、new_high_cluster | 4 | 12 | 1 | - |
| 46 | MicroLED | Micro LED | - | 112.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 47 | 无线耳机 | 无线耳机 | - | 112.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 混合现实 | 混合现实 | - | 110.0 | double_red、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 49 | 铜缆高速连接 | 铜 | 电力设备 | 108.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 50 | MiniLED | Mini LED | - | 106.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：296.19
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.22%，边际量 30.04%，成交额 2171.76 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股3只，最高2板，容量前三=True |
| double_red | 90.0 | 涨幅2.22%，边际量30.04%，成交2171.76亿 |
| new_high_direction | 55.19 | 新高股54只，新高成交415.1200000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 计算机 位于容量前三 |

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

## 候选 2：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：243.0
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、multi_period_rank
- **盘面信号**：涨幅 6.34%，边际量 36.5%，成交额 1136.03 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 113.0 | 连板股5只，最高2板，容量前三=False |
| double_red | 90.0 | 涨幅6.34%，边际量36.5%，成交1136.03亿 |
| multi_period_rank | 18.2 | day3排名第2，区间涨幅13.83% |
| multi_period_rank | 11.8 | daily排名第10，区间涨幅6.34% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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
| 天承科技 | 688603 | PCB | 受益于AI算力驱动的高多层板/HDI/封装基板需求 | core | L2 | 21 |
| 本川智能 | 300964 | PCB | 中高端PCB定制化制造商，以通信设备为核心，布局汽车电子、新能源、AI服... | core | L2 | 21 |
| 沪电股份 | 002463 | PCB | 受益标的 | core | supply_chain | 21 |
| 胜宏科技 | 300476 | PCB | 高密度印制线路板制造商 | core | L2 | 21 |
| 超颖电子 | 603175 | PCB | 汽车电子PCB供应商，布局高多层服务器板、汽车板、存储板等高阶PCB产能 | related | L1_L3_candidate | 21 |
| 国际复材 | 301526 | PCB | 电子布供应商，再度提价+AI算力材料 | peripheral | L1 | 21 |
| 容大感光 | 300576 | AIPCB专用油墨 | PCB光刻胶/高端油墨核心验证标的 | core | L2_L3_candidate | 20 |
| 广信材料 | 300537 | AIPCB专用油墨 | PCB光刻胶/高频低Dk油墨验证标的 | core_related | L2_L3_candidate | 20 |

## 候选 3：光通信

- **标准概念**：光通信
- **申万一级**：电力设备
- **评分**：228.15
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 3.6%，边际量 29.16%，成交额 4141.45 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股4只，最高2板，容量前三=False |
| double_red | 90.0 | 涨幅3.6%，边际量29.16%，成交4141.45亿 |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| limit_heat | 7.15 | 涨停9只，市场占比8.74，排名26 |

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

## 候选 4：云计算

- **标准概念**：云计算
- **申万一级**：计算机
- **评分**：182.09
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.96%，边际量 35.77%，成交额 2341.17 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.96%，边际量35.77%，成交2341.17亿 |
| new_high_direction | 56.09 | 新高股75只，新高成交486.8599999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 计算机 位于容量前三 |

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

## 候选 5：有色

- **标准概念**：有色冶炼装备
- **申万一级**：-
- **评分**：173.33
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.39%，边际量 48.62%，成交额 1677.87 亿，容量前三=否
- **知识库状态**：concept=是（4），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.39%，边际量48.62%，成交1677.87亿 |
| new_high_direction | 48.78 | 新高股50只，新高成交702.6899999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比12.62，排名10 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 有色冶炼装备 | 5 |
| 有色加工 | 5 |
| 有色工程 | 5 |
| 有色金属 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三友科技 | 920475 | 有色冶炼装备 | 有色金属电化学精炼专用新型电极材料及成套智能装备供应商（北交所） | core | L2 | 20 |
| 中金岭南 | 000060 | 有色加工 | 有色材料精深加工商 | peripheral | graph_only | 20 |
| 中铝国际 | 601068 | 有色工程 | 有色金属工程设计与EPC龙头（中铝系） | core | L2 | 20 |
| 上海物贸 | 600822 | 有色金属 | 有色/黑色金属现货交易市场及仓储物流平台 | core | L2 | 20 |
| 厦门信达 | 000701 | 有色金属 | 有色及黑色大宗商品贸易供应链 | core | L2 | 20 |
| 厦门国贸 | 600755 | 有色金属 | 冶金/有色等大宗商品供应链运营 | core | L2 | 20 |
| 厦门象屿 | 600057 | 有色金属 | 金属矿产大宗供应链(铜铝镍/不锈钢/黑色) | core | L2 | 20 |
| 盛达资源 | 000603 | 有色金属 | 有色金属采选收入20.69亿元占84.04%，毛利率71.26% | core | L2 | 20 |

## 候选 6：物联网

- **标准概念**：物联网
- **申万一级**：-
- **评分**：171.3
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.18%，边际量 30.66%，成交额 4040.77 亿，容量前三=否
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.18%，边际量30.66%，成交4040.77亿 |
| new_high_direction | 45.7 | 新高股113只，新高成交456.23999999999984亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比15.53，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 物联网 | 20 |
| 工业物联网 | 5 |
| 物联网IoT | 5 |
| 物联网模组 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 纬德信息 | 688171 | 工业物联网 | 提供工业物联网加密网关、加密终端、防篡改认证装置等安全传输系列设备，主要... | core | L2 | 20 |
| 柯力传感 | 603662 | 工业物联网 | 工业物联网 | related | L1_L3_candidate | 20 |
| 智微智能 | 001339 | 工业物联网 | 市场信号弱关联 | related | L2_candidate | 20 |
| 云里物里 | 920374 | 物联网 | 蓝牙传感器/物联网模组/网关厂商 | core | L2 | 20 |
| 思创智联 | 300078 | 物联网 | 聚焦物联网商业智能业务 | core | L2 | 20 |
| 移为通信 | 300590 | 物联网 | 业界领先的物联网设备和解决方案提供商，产品覆盖NB-IoT/卫星通信/4... | core | L2 | 20 |
| 移远通信 | 603236 | 物联网 | 全球领先的物联网整体解决方案供应商，构建'1+N'业务矩阵（模组为基石，... | core | L2 | 20 |
| 翱捷科技 | 688220 | 物联网 | 蜂窝基带芯片、手机SoC、ASIC定制服务 | core | L1_L3_candidate | 20 |

## 候选 7：东数西算

- **标准概念**：东数西算
- **申万一级**：-
- **评分**：169.77
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.53%，边际量 30.53%，成交额 4416.76 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.53%，边际量30.53%，成交4416.76亿 |
| new_high_direction | 46.27 | 新高股82只，新高成交501.49999999999983亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比9.71，排名22 |

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

## 候选 8：计算机

- **标准概念**：计算机外设
- **申万一级**：-
- **评分**：165.35
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.33%，边际量 31.92%，成交额 1975.71 亿，容量前三=否
- **知识库状态**：concept=是（4），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.33%，边际量31.92%，成交1975.71亿 |
| new_high_direction | 49.35 | 新高股140只，新高成交747.8699999999994亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 计算机外设 | 5 |
| 计算机视觉 | 5 |
| 计算机设备 | 5 |
| 高端计算机 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 雷柏科技 | 002577 | 计算机外设 | 以计算机外设为核心业务，游戏电竞外设覆盖游戏鼠标、键盘、耳机、手柄，商务... | core | L2 | 20 |
| 海天瑞声 | 688787 | 计算机视觉 | 计算机视觉 | related | L1_L3_candidate | 20 |
| 格灵深瞳 | 688207 | 计算机视觉 | 计算机视觉相关产品/材料供应商 | related | L2 | 20 |
| 云从科技 | 688327 | 计算机视觉 | 计算机视觉及多模态人机交互技术平台 | peripheral | graph_only | 20 |
| 中国长城 | 000066 | 计算机设备 | 计算机设备制造商 | peripheral | graph_only | 20 |
| 中孚信息 | 300659 | 计算机设备 | 安全计算终端与保密硬件厂商 | peripheral | graph_only | 20 |
| 中科曙光 | 603019 | 高端计算机 | 高端计算机相关产品/材料供应商 | related | L2 | 20 |
| 协创数据 | 300857 | 800G_1.6T光模块 | 算力租赁、存储、光模块、服务器再制造 | related | L1_L3_candidate | 1 |

## 候选 9：黄金概念

- **标准概念**：黄金
- **申万一级**：-
- **评分**：164.29
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.37%，边际量 70.58%，成交额 892.41 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.37%，边际量70.58%，成交892.41亿 |
| new_high_direction | 48.29 | 新高股43只，新高成交663.0799999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 黄金 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中金黄金 | 600489 | 黄金 | 央企黄金龙头（保有金资源量917.35吨） | core | L2 | 20 |
| 宝鼎科技 | 002552 | 黄金 | AI铜箔（HVLP、HTE铜箔）、金矿业务 | core | L1_L3_candidate | 20 |
| 山东黄金 | 600947 | 黄金 | 黄金矿业龙头企业 | core | L2 | 20 |
| 山金国际 | 000975 | 黄金 | 黄金矿采选企业（山东黄金集团旗下，原银泰黄金）：玉龙矿业、黑河银泰等矿山 | core | L2 | 20 |
| 晓程科技 | 300139 | 黄金 | 加纳AKROMA/AKOASE/FGM金矿开采冶炼销售，黄金收入占比82... | core | L2 | 20 |
| 白银有色 | 601212 | 黄金 | 黄金生产商，年产金50吨生产能力 | core | L2 | 20 |
| 紫金矿业 | 601899 | 黄金 | 全球金属矿企黄金龙头（2025年《福布斯》全球黄金企业第1位），保有资源... | core | L2 | 20 |
| 华钰矿业 | 601020 | 黄金 | 黄金业务（泥堡金矿 | related | L1_L3_candidate | 20 |

## 候选 10：工业金属

- **标准概念**：工业金属
- **申万一级**：有色金属
- **评分**：160.95
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.92%，边际量 55.05%，成交额 646.67 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.92%，边际量55.05%，成交646.67亿 |
| new_high_direction | 44.95 | 新高股24只，新高成交395.64亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 株冶集团 | 600961 | 800G_1.6T光模块 | 铟（高纯铟、磷化铟衬底原料）、贵金属（金 | related | L1_L3_candidate | 1 |
| 海亮股份 | 002203 | AI PCB | AI热管理 | related | L1_L3_candidate | 1 |
| 云铝股份 | 000807 | AI算力 | 电解铝冶炼、铝加工、氧化铝 | related | L1_L3_candidate | 1 |
| 华钰矿业 | 601020 | AI算力 | 锑业务（全球龙头）、黄金业务（泥堡金矿、塔铝金业） | related | L1_L3_candidate | 1 |
| 铜陵有色金属 | 000630 | HVLP铜箔 | 铜矿开采、冶炼及铜加工业务 | related | L1_L3_candidate | 1 |
| 鼎胜新材 | 603876 | 储能系统 | 电池铝箔业务（核心）、空调箔业务、包装铝箔业务 | related | L1_L3_candidate | 1 |
| 中金岭南 | 000060 | 有色金属 | 有色金属矿产品及冶炼深加工商 | core | L2_candidate | 1 |
| 南山铝业 | 600219 | 汽车板 | 高端铝加工（汽车板 | related | L1_L3_candidate | 1 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-443f12a72baafd82d81e artifact_sha=c304e9d5ecfe40c2f4b168e028606411a95b445fa401e238248b679cbe46f532 manifest_sha=91460d1ac1b6a0d75b9f2076c4bdefd620ad4ace7784551b0fa605bffe86c512 -->
