# 2026-08-27 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：21256.25
- **上涨家数**：3394
- **涨停 / 跌停**：77 / 3
- **容量前三行业**：1.电子(27.4%, super_capacity)、2.通信(9.0%, normal)、3.机械设备(8.0%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 电子 | EDA（电子设计自动化） | 电子 | 188.59 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | PCB | PCB | 电子 | 188.0 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 3 | 光纤光缆 | 光纤光缆 | 通信 | 184.57 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 4 | 通信设备 | 通信设备 | 通信 | 184.31 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 5 | 通信 | 通信 | 通信 | 184.26 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 元器件 | 电子元器件 | 电子 | 182.0 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 7 | 数据中心 | 数据中心 | 计算机 | 178.82 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 光通信 | 光通信 | - | 173.4 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 9 | CPO概念 | CPO | - | 172.88 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 10 | 先进封装 | 先进封装 | 电子 | 171.9 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 液冷服务器 | 液冷服务器 | 电力设备 | 171.26 | double_red、limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 12 | 商业航天 | 商业航天 | 国防军工 | 169.35 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 13 | 物联网 | 物联网 | - | 167.85 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 14 | 东数西算 | 东数西算 | - | 167.44 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 15 | PCB概念 | PCB概念 | - | 166.27 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 16 | 智慧城市 | 智慧城市 | - | 160.91 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 17 | 信息安全 | 信息安全 | 计算机 | 160.58 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 18 | 第三代半导体 | 第三代半导体 | - | 160.54 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 19 | 抖音概念 | 抖音概念 | - | 159.53 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 20 | 阿里概念 | 阿里概念 | - | 158.83 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 21 | 腾讯概念 | 腾讯概念 | - | 158.69 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 22 | 卫星导航 | 卫星导航 | - | 158.67 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 23 | 6G概念 | 6G | - | 153.96 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 24 | 云计算 | 云计算 | 计算机 | 153.46 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 25 | 集成电路设计 | 集成电路 | 电子 | 152.8 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 26 | 量子科技 | 量子科技 | 计算机 | 150.65 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 27 | 铜缆高速连接 | 铜 | 电力设备 | 147.66 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 28 | 芯片 | 芯片 | 电子 | 135.6 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 29 | 贵金属 | 贵金属 | 电子 | 135.4 | limit_advance_cluster、multi_period_rank、capacity_industry | 4 | 12 | 1 | - |
| 30 | 存储芯片 | 存储芯片 | 电子 | 132.45 | double_red、capacity_industry、limit_heat、new_high_cluster | 2 | 12 | 5 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 3D打印 | 3D打印 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 32 | AI手机PC | AI手机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 33 | AI眼镜 | AI眼镜 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 2 | - |
| 34 | MCU芯片 | MCU芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 3 | 12 | 1 | - |
| 35 | 光刻机 | 光刻机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 4 | 12 | 2 | - |
| 36 | 半导体 | 半导体 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 37 | 汽车芯片 | 汽车芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 1 | - |
| 38 | MicroLED | Micro LED | 电子 | 124.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 39 | 折叠屏 | 折叠屏 | 电子 | 124.0 | double_red、capacity_industry、new_high_cluster | 4 | 12 | 1 | - |
| 40 | 光伏 | 光伏 | 电力设备 | 123.15 | double_red、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 41 | OLED概念 | LED | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 42 | 医药 | 医药 | 医药生物 | 119.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 信创 | 信创 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 小米概念 | 小米概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 毫米波雷达 | 毫米波雷达 | 汽车 | 116.0 | double_red、new_high_cluster | 4 | 12 | 1 | - |
| 46 | 玻璃基板 | 玻璃基板 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 5 | - |
| 47 | 百度概念 | 百度概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 石墨烯 | 石墨烯 | - | 116.0 | double_red、new_high_cluster | 2 | 10 | 2 | - |
| 49 | 算力租赁 | 算力租赁 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 5 | - |
| 50 | 车联网 | 车联网 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：188.59
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.33%，边际量 36.39%，成交额 5884.61 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.33%，边际量36.39%，成交5884.61亿 |
| new_high_direction | 54.04 | 新高股44只，新高成交322.95亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.55 | 涨停13只，市场占比16.88，排名6 |

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

## 候选 2：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：188.0
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 5.52%，边际量 42.88%，成交额 973.58 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.52%，边际量42.88%，成交973.58亿 |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| multi_period_rank | 22.4 | day5排名第3，区间涨幅5.8% |
| multi_period_rank | 21.6 | daily排名第4，区间涨幅5.52% |
| multi_period_rank | 20.0 | day3排名第6，区间涨幅6.97% |
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
| 沪电股份 | 002463 | PCB | 受益标的 | core | L2 | 21 |
| 胜宏科技 | 300476 | PCB | 高密度印制线路板制造商 | core | L2 | 21 |
| 超颖电子 | 603175 | PCB | 汽车电子PCB供应商，布局高多层服务器板、汽车板、存储板等高阶PCB产能 | related | L1_L3_candidate | 21 |
| 国际复材 | 301526 | PCB | 电子布供应商，再度提价+AI算力材料 | peripheral | L1 | 21 |
| 容大感光 | 300576 | AIPCB专用油墨 | PCB光刻胶/高端油墨核心验证标的 | core | L1_L3_candidate | 20 |
| 广信材料 | 300537 | AIPCB专用油墨 | PCB光刻胶/高频低Dk油墨验证标的 | core_related | L1_L3_candidate | 20 |

## 候选 3：光纤光缆

- **标准概念**：光纤光缆
- **申万一级**：通信
- **评分**：184.57
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.57 | 新高股7只，新高成交381.87亿，容量前三=True |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅8.19% |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅18.66% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅13.17% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅14.09% |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光纤光缆 | 20 |
| 光纤 | 10 |
| 光缆 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 大族激光 | 002008 | 光纤 | 激光加工设备龙头，子公司投建年产6000万芯公里光纤及预制棒产能 | related | L3 | 20 |
| 长芯博创 | 300548 | 光纤 | 受益标的 | related | L2 | 20 |
| 特发信息 | 000070 | 光纤光缆 | 光纤光缆老牌厂商（华南规模领先基地，深圳/东莞/重庆/常州/赣州/枣庄/... | core | L2 | 20 |
| 杭电股份 | 603618 | 光纤光缆 | 光通信（光纤光缆）、电力电缆、铜箔 | core | L1_L3_candidate | 20 |
| 泰和新材 | 002254 | 光纤光缆 | 对位芳纶（光纤光缆用）、氨纶 | core | L2 | 20 |
| 通光线缆 | 300265 | 光纤光缆 | 光纤光缆（含OPGW、ADSS电力光缆、G.654.E高端光纤）、输电线... | core | L1_L3_candidate | 20 |
| 三孚股份 | 603938 | 光纤光缆 | 硅系列产品（三氯氢硅、四氯化硅、高纯四氯化硅、电子特气等） | related | L2 | 20 |
| 中天科技 | 600522 | 光纤光缆 | 光缆供应商 | related | L3 | 20 |

## 候选 4：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：184.31
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.26%，边际量 33.38%，成交额 2003.86 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.26%，边际量33.38%，成交2003.86亿 |
| new_high_direction | 58.31 | 新高股21只，新高成交664.5500000000001亿，容量前三=True |
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

## 候选 5：通信

- **标准概念**：通信
- **申万一级**：通信
- **评分**：184.26
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.27%，边际量 30.95%，成交额 1866.9 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.27%，边际量30.95%，成交1866.9亿 |
| new_high_direction | 58.26 | 新高股20只，新高成交660.8800000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

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

## 候选 6：元器件

- **标准概念**：电子元器件
- **申万一级**：电子
- **评分**：182.0
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 5.26%，边际量 47.79%，成交额 1213.89 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.26%，边际量47.79%，成交1213.89亿 |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅5.26% |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅6.39% |
| multi_period_rank | 17.6 | day5排名第9，区间涨幅5.01% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元器件 | 5 |
| 电子元器件分销 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 利和兴 | 301013 | 电子元器件 | 向新型电子元器件领域拓展（孙公司利和兴电子），客户含摩尔线程、蓝思科技、... | related | L2 | 20 |
| 中电港 | 001287 | 电子元器件分销 | 本土元器件分销商龙头（连续6年首位，近140条授权产品线） | core | L2 | 20 |
| 新亚制程 | 002388 | 电子元器件分销 | 电子信息产品销售服务为第一大业务，2025年收入13.45亿元（占比69... | core | L2 | 20 |
| 英唐智控 | 300131 | 电子元器件分销 | 电子元器件分销商，产品类型含被动元件、存储类、触控显示类、半导体类、模块... | core | L2 | 20 |
| 云汉芯城 | 301563 | 3D NAND | B2B电子元器件线上分销、PCBA智造、国产替代 | related | L1_L3_candidate | 1 |
| 商络电子 | 300975 | 3D NAND | MLCC分销、存储芯片分销、被动元器件分销、机器人元器件供应 | related | L1_L3_candidate | 1 |
| 香农芯创 | 300475 | AI存储 | 电子元器件分销（SK海力士代理）、自研企业级存储品牌"海普存储" | related | L1_L3_candidate | 1 |
| 力源信息 | 300184 | AI服务器 | AI服务器MLCC分销、华为海思芯片代理、存储芯片分销、碳化硅（SiC）... | core | L1_L3_candidate | 1 |

## 候选 7：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：178.82
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.02%，边际量 34.06%，成交额 5848.87 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.02%，边际量34.06%，成交5848.87亿 |
| new_high_direction | 53.22 | 新高股63只，新高成交1057.8500000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比20.78，排名3 |

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

## 候选 8：光通信

- **标准概念**：光通信
- **申万一级**：-
- **评分**：173.4
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.84%，边际量 33.84%，成交额 3063.01 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.84%，边际量33.84%，成交3063.01亿 |
| new_high_direction | 49.9 | 新高股25只，新高成交792.0700000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比12.99，排名9 |

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

## 候选 9：CPO概念

- **标准概念**：CPO
- **申万一级**：-
- **评分**：172.88
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.49%，边际量 43.31%，成交额 4222.31 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.49%，边际量43.31%，成交4222.31亿 |
| new_high_direction | 50.08 | 新高股25只，新高成交806.2700000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比10.39，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 泰晶科技 | 603738 | CPO | 超高频差分晶振（光模块/AI算力） | core | L1_L3_candidate | 20 |
| 金信诺 | 300252 | CPO | 通信设备（信号互联产品） | core | L1_L3_candidate | 20 |
| 仕佳光子 | 688313 | CPO | MPO核心玩家/CW光源/CPO FAU，平台型光器件公司 | core | L1_L3_candidate | 20 |
| 天孚通信 | 300394 | CPO | 光模块无源器件/光引擎核心供应商 | core | L1_L3_candidate | 20 |
| 天通股份 | 600330 | CPO | 薄膜铌酸锂（TFLN）晶圆、压电晶体材料（铌酸锂/钽酸锂）、磁性材料（软... | core | L1_L3_candidate | 20 |
| 富信科技 | 688662 | CPO | 光模块温控 | core | L1_L3_candidate | 20 |
| 工业富联 | 601138 | CPO | CPO组装+AI服务器OEM | core | L3 | 20 |
| 环旭电子 | 601231 | CPO | SiP封装+光通信 | core | L3 | 20 |

## 候选 10：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：171.9
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.19%，边际量 31.1%，成交额 2714.86 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.19%，边际量31.1%，成交2714.86亿 |
| new_high_direction | 45.9 | 新高股11只，新高成交200.15亿，容量前三=True |
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
| 华峰测控 | 688200 | 先进封装 | ATE测试设备 | core | L1_L3_candidate | 20 |
| 天马新材 | 920971 | 先进封装 | 电子陶瓷用粉体（MLCC上游）、高压电器用粉体、高导热球形氧化铝 | core | L1_L3_candidate | 20 |
| 康强电子 | 002119 | 先进封装 | 引线框架（冲压+蚀刻）、键合丝、电极丝 | core | L1_L3_candidate | 20 |
| 拓荆科技 | 688072 | 先进封装 | 薄膜沉积(CVD/ALD)设备龙头，拟收购尚积补PVD/刻蚀 | core | L3 | 20 |
| 新恒汇 | 301678 | 先进封装 | 芯片封装材料+封测服务一体化，物联网eSIM芯片封测提供DFN/QFN/... | core | L2 | 20 |
| 沃格光电 | 603773 | 先进封装 | 玻璃基TGV与GCP多层玻璃互联键合技术，面向算力芯片先进封装 | core | L2 | 20 |
| 甬矽电子 | 688362 | 先进封装 | 中游高端封测 | core | L1_L3_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-9a410c50615ccb73b25e artifact_sha=c2cfe635ace9cb25e4fc2071534e19a921dd04775441aff799d655f8e403432b manifest_sha=47b330666697e5423bfd3116f3e56b4b9496a02dbc5a57a7412d51ad9956d932 -->
