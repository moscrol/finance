# 2026-08-17 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：23857.9
- **上涨家数**：4248
- **涨停 / 跌停**：106 / 1
- **容量前三行业**：1.电子(30.5%, super_capacity)、2.通信(10.0%, normal)、3.机械设备(7.1%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光通信 | 光通信 | 电力设备 | 292.95 | double_red、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 2 | CPO概念 | CPO | - | 236.95 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 3 | 半导体封测 | 半导体封测 | - | 222.4 | double_red、multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 4 | 通信设备 | 通信设备 | 通信 | 218.37 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 5 | 通信 | 通信 | - | 205.59 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 先进封装 | 先进封装 | 电子 | 196.69 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 5 | - |
| 7 | 半导体 | 半导体 | 电子 | 194.52 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 存储芯片 | 存储芯片 | 电子 | 193.59 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 9 | 电子 | EDA（电子设计自动化） | - | 183.95 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 10 | 光刻机 | 光刻机 | 电子 | 183.66 | double_red、capacity_industry、new_high_direction、new_high_cluster | 4 | 12 | 2 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 商业航天 | 商业航天 | 国防军工 | 183.44 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 12 | AI眼镜 | AI眼镜 | 电子 | 181.06 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 13 | PCB概念 | PCB概念 | - | 181.02 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 14 | 电子化学品 | 电子化学品 | 基础化工 | 179.2 | double_red、multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 15 | 无人驾驶 | 无人驾驶 | 汽车 | 174.43 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 16 | 第三代半导体 | 第三代半导体 | - | 173.54 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 17 | 机械设备 | 机械设备 | - | 172.79 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 18 | 卫星导航 | 卫星导航 | - | 172.78 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 19 | PCB | PCB | 电子 | 166.8 | double_red、capacity_industry、limit_advance_cluster、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 20 | OLED概念 | LED | - | 165.14 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 21 | 小米概念 | 小米概念 | - | 162.76 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 22 | 智能穿戴 | 智能穿戴 | - | 161.74 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 23 | 虚拟现实 | 虚拟现实 | - | 161.4 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | 芯片 | 芯片 | 电子 | 138.05 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 25 | 半导体设备 | 半导体设备 | 电子 | 133.2 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 4 | 12 | 5 | - |
| 26 | 医药 | 医药 | 医药生物 | 131.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 集成电路设计 | 集成电路 | - | 127.6 | double_red、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 28 | 化工 | 化工 | - | 126.65 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 29 | 3D打印 | 3D打印 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 30 | MCU芯片 | MCU芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 3 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 工业母机 | 工业母机 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 2 | - |
| 32 | 消费电子 | 消费电子 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 33 | 通用设备 | 通用设备 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 7 | 0 | missing_concept、missing_evidence |
| 34 | 元器件 | 电子元器件 | - | 125.2 | double_red、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 35 | 玻璃基板 | 玻璃基板 | - | 123.6 | double_red、multi_period_rank、new_high_cluster | 2 | 12 | 5 | - |
| 36 | 化工原料 | 化工 | - | 123.5 | double_red、limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 37 | AI手机PC | AI手机 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 38 | MicroLED | Micro LED | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 39 | MiniLED | Mini LED | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 光学光电 | 光学 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 41 | 华为海思 | 华为海思 | - | 116.0 | double_red、new_high_cluster | 0 | 10 | 0 | missing_concept、missing_evidence |
| 42 | 工业金属 | 工业金属 | 有色金属 | 116.0 | double_red、new_high_cluster | 0 | 9 | 0 | missing_concept、missing_evidence |
| 43 | 折叠屏 | 折叠屏 | - | 116.0 | double_red、new_high_cluster | 4 | 12 | 1 | - |
| 44 | 无线耳机 | 无线耳机 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 毫米波雷达 | 毫米波雷达 | 汽车 | 116.0 | double_red、new_high_cluster | 4 | 12 | 1 | - |
| 46 | 氟概念 | 氟概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 汽车芯片 | 汽车芯片 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 48 | 苹果概念 | 苹果概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 50 | 高压快充 | 高压快充 | 电力设备 | 116.0 | double_red、new_high_cluster | 0 | 6 | 0 | missing_concept、missing_evidence |

## 五、核心候选明细

## 候选 1：光通信

- **标准概念**：光通信
- **申万一级**：电力设备
- **评分**：292.95
- **触发类型**：double_red、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.51%，边际量 25.67%，成交额 3638.32 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股3只，最高4板，容量前三=False |
| double_red | 90.0 | 涨幅3.51%，边际量25.67%，成交3638.32亿 |
| new_high_direction | 58.0 | 新高股66只，新高成交1571.1000000000006亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比8.49，排名22 |
| multi_period_rank | 6.8 | day5排名第10，区间涨幅8.08% |

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

## 候选 2：CPO概念

- **标准概念**：CPO
- **申万一级**：-
- **评分**：236.95
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.17%，边际量 25.41%，成交额 5096.88 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.17%，边际量25.41%，成交5096.88亿 |
| new_high_direction | 58.0 | 新高股105只，新高成交1781.739999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 19.2 | day3排名第7，区间涨幅6.24% |
| multi_period_rank | 18.4 | day5排名第8，区间涨幅9.13% |
| multi_period_rank | 16.8 | day10排名第10，区间涨幅27.92% |
| limit_heat | 8.55 | 涨停13只，市场占比12.26，排名12 |

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

## 候选 3：半导体封测

- **标准概念**：半导体封测
- **申万一级**：-
- **评分**：222.4
- **触发类型**：double_red、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 7.53%，边际量 55.8%，成交额 509.56 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅7.53%，边际量55.8%，成交509.56亿 |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅7.53% |
| multi_period_rank | 28.2 | day10排名第2，区间涨幅36.56% |
| multi_period_rank | 27.4 | day3排名第3，区间涨幅7.6% |
| multi_period_rank | 25.8 | day5排名第5，区间涨幅9.4% |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体封测 | 20 |
| 半导体 | 10 |
| 封测 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亚翔集成 | 603929 | 半导体 | IC半导体洁净室工程服务商（建厂工程核心配套） | core | L2 | 20 |
| 英唐智控 | 300131 | 半导体 | 全资子公司英唐微技术采用IDM模式研发生产光电转换和图像处理IC，提供光... | core | L2 | 20 |
| 英集芯 | 688209 | 半导体 | 专注高性能、高品质数模混合芯片设计，受益半导体国产替代与新兴应用领域拓展 | core | L2 | 20 |
| 裕太微 | 688515 | 半导体 | 以太网物理层/交换机/网卡芯片国产供应商，覆盖网通、车载、工业以太网场景... | core | L2 | 20 |
| 东芯股份 | 688110 | 半导体 | 半导体集成电路设计企业 | core | L1 | 20 |
| 中芯国际 | 688981 | 半导体 | 半导体制造和晶圆代工核心龙头 | core | L1 | 20 |
| 乐鑫科技 | 688018 | 半导体 | 数模混合物联网芯片设计商 | core | L1 | 20 |
| 线上线下 | 300959 | 半导体 | 移动信息服务（企业短信）、数字营销、深蕾科技（控股股东）— 半导体元器件... | core | L1 | 20 |

## 候选 4：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：218.37
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.1%，边际量 21.46%，成交额 2438.71 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.1%，边际量21.46%，成交2438.71亿 |
| new_high_direction | 62.37 | 新高股39只，新高成交989.8699999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.8 | day3排名第5，区间涨幅7.25% |
| multi_period_rank | 14.2 | day5排名第7，区间涨幅9.15% |
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
- **申万一级**：-
- **评分**：205.59
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.94%，边际量 20.23%，成交额 2269.04 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.94%，边际量20.23%，成交2269.04亿 |
| new_high_direction | 52.39 | 新高股37只，新高成交991.31亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 19.0 | day5排名第1，区间涨幅12.41% |
| multi_period_rank | 18.2 | day3排名第2，区间涨幅8.09% |

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

## 候选 6：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：196.69
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.48%，边际量 34.54%，成交额 3292.52 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.48%，边际量34.54%，成交3292.52亿 |
| new_high_direction | 63.19 | 新高股97只，新高成交1055.4799999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.5 | 涨停10只，市场占比9.43，排名17 |

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

## 候选 7：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：194.52
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.22%，边际量 38.34%，成交额 4096.5 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.22%，边际量38.34%，成交4096.5亿 |
| new_high_direction | 57.72 | 新高股76只，新高成交617.93亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 10.8 | daily排名第5，区间涨幅5.22% |
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
| 协昌科技 | 301418 | 功率半导体 | 功率芯片（晶圆/封装成品）设计销售并向封测领域延伸 | core | L2 | 20 |
| 士兰微 | 600460 | 功率半导体 | 分立器件产品营收63.79亿元/毛利率12.22%/同比+17.32% | core | L2 | 20 |
| 扬杰科技 | 300373 | 功率半导体 | 受益标的 | core | L2 | 20 |
| 新洁能 | 605111 | 功率半导体 | 受益标的 | core | L2 | 20 |
| 民德电子 | 300656 | 功率半导体 | 功率半导体smartIDM生态圈构建者（晶圆原材料+晶圆代工+特种工艺代... | core | L2 | 20 |
| 派瑞股份 | 300831 | 功率半导体 | 大功率半导体器件（晶闸管/IGCT/FRD）研发制造商 | core | L2 | 20 |
| 紫光国微 | 002049 | 功率半导体 | 特种集成电路、智能安全芯片、石英晶体频率器件、功率半导体（拟收购） | core | L1_L3_candidate | 20 |

## 候选 8：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：193.59
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.58%，边际量 32.26%，成交额 4336.31 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.58%，边际量32.26%，成交4336.31亿 |
| new_high_direction | 60.79 | 新高股76只，新高成交862.9099999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 6.8 | daily排名第10，区间涨幅4.58% |

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
| 中船特气 | 688146 | 存储芯片 | 电子特种气体（六氟化钨、三氟化氮等） | core | L1_L3_candidate | 20 |
| 深科技 | 000021 | 存储芯片 | DRAM/NAND Flash/嵌入式存储芯片封测服务商 | core | L2 | 20 |
| 香农芯创 | 300475 | 存储芯片 | SK海力士授权代理的高端存储芯片分销商+自研存储模组厂商 | core | L2 | 20 |
| 兆易创新 | 603986 | 存储芯片 | 中游利基存储/MCU | core | L1 | 20 |
| 北京君正 | 300223 | 存储芯片 | 利基DRAM | core | L1_L3_candidate | 20 |
| 北方华创 | 002371 | 存储芯片 | 上游设备 | core | L1_L3_candidate | 20 |

## 候选 9：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：-
- **评分**：183.95
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.33%，边际量 29.76%，成交额 7438.45 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.33%，边际量29.76%，成交7438.45亿 |
| new_high_direction | 58.0 | 新高股206只，新高成交1674.4899999999989亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.95 | 涨停17只，市场占比16.04，排名6 |

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

## 候选 10：光刻机

- **标准概念**：光刻机
- **申万一级**：电子
- **评分**：183.66
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.07%，边际量 28.23%，成交额 1027.78 亿，容量前三=是
- **知识库状态**：concept=是（4），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.07%，边际量28.23%，成交1027.78亿 |
| new_high_direction | 57.66 | 新高股65只，新高成交612.9299999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光刻机 | 20 |
| 光刻 | 10 |
| 电子束光刻机 | 5 |
| 电子束光刻机产业 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 芯源微 | 688037 | 光刻 | 图谱弱关联 | peripheral | graph_only | 20 |
| 奥普光电 | 002338 | 光刻机 | 光源系统/科益虹源股东与整机布局 | core | L2 | 20 |
| 福晶科技 | 002222 | 光刻机 | 光源系统/LBO-BBO非线性光学晶体 | core | L2 | 20 |
| 聚和材料 | 688503 | 光刻机 | 掩膜板材料/空白掩膜板基板 | core | L2 | 20 |
| 芯碁微装 | 688630 | 光刻机 | 直写光刻/无掩膜光刻设备 | core | L2 | 20 |
| 茂莱光学 | 688502 | 光刻机 | 光学系统/投影物镜与匀光系统 | core | L2 | 20 |
| 中旗新材 | 001212 | 光刻机 | 半导体设备资产注入预期（星空科技光刻机 | related | L2 | 20 |
| 凤凰光学 | 600071 | 光刻机 | 半导体制造级、精密超高解像度光刻镜头精密抛光及在研平台 | related | L1 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-3c332212ee2d4fec22e3 artifact_sha=64e83f336b9b205f860b3f00f204898d2a7922a63f0813aa1d3a6946c0ecde23 manifest_sha=246e162c82769c04ca462633050fa98f394fa7b4449e0ca100f27601288a71fa -->
