# 2026-09-16 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：18386.22
- **上涨家数**：4164
- **涨停 / 跌停**：89 / 4
- **容量前三行业**：1.电子(29.1%, super_capacity)、2.通信(9.3%, normal)、3.电力设备(8.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 芯片 | 芯片 | 电子 | 244.7 | double_red、capacity_industry、limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | 电子 | EDA（电子设计自动化） | 电子 | 235.14 | double_red、capacity_industry、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 半导体 | 半导体 | 电子 | 210.27 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | CPO概念 | CPO | - | 200.69 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 5 | 先进封装 | 先进封装 | 电子 | 183.11 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 5 | - |
| 6 | 存储芯片 | 存储芯片 | 电子 | 179.43 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 7 | 电力设备 | 电力设备 | 电力设备 | 178.15 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 8 | 智能穿戴 | 智能穿戴 | 电子 | 178.12 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 9 | 汽车芯片 | 汽车芯片 | 电子 | 177.6 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 10 | 集成电路设计 | 集成电路 | 电子 | 175.14 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 数据中心 | 数据中心 | 计算机 | 175.05 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | AI眼镜 | AI眼镜 | 电子 | 174.84 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 13 | 通信设备 | 通信设备 | 通信 | 172.79 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 14 | 通信 | 通信 | 通信 | 171.41 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 15 | OLED概念 | LED | 电子 | 171.35 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 16 | 光通信 | 光通信 | - | 171.02 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 17 | 锂电池概念 | 锂 | - | 168.52 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 18 | 小米概念 | 小米概念 | - | 166.45 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 19 | 第三代半导体 | 第三代半导体 | - | 159.22 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 20 | 海峡西岸 | 海峡西岸 | 公用事业 | 159.15 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 21 | 无人驾驶 | 无人驾驶 | 汽车 | 158.57 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 22 | 苹果概念 | 苹果概念 | - | 158.16 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 23 | 特斯拉概念 | 特斯拉概念 | - | 154.4 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | 6G概念 | 6G | - | 152.8 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 25 | 抖音概念 | 抖音概念 | - | 151.93 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 26 | 虚拟现实 | 虚拟现实 | - | 151.9 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | PCB | PCB | 电子 | 151.23 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 28 | 元器件 | 电子元器件 | 电子 | 148.62 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 29 | 智能家居 | 智能家居 | 环保 | 147.15 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 2 | 12 | 1 | - |
| 30 | 边缘计算 | 边缘计算 | - | 135.77 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 固态电池 | 固态电池 | 电力设备 | 133.5 | double_red、capacity_industry、limit_heat、new_high_cluster | 3 | 12 | 5 | - |
| 32 | MLCC | MLCC | 电子 | 127.51 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 33 | MicroLED | Micro LED | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 34 | 光刻机 | 光刻机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 4 | 12 | 2 | - |
| 35 | 液冷服务器 | 液冷服务器 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 3 | 12 | 2 | - |
| 36 | 物联网 | 物联网 | - | 123.85 | double_red、limit_heat、new_high_cluster | 4 | 12 | 1 | - |
| 37 | 机械设备 | 机械设备 | 机械设备 | 122.8 | double_red、limit_heat、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 38 | 消费电子 | 消费电子 | 电子 | 122.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 39 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 122.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 40 | 高压快充 | 高压快充 | 电力设备 | 122.0 | double_red、capacity_industry、new_high_cluster | 0 | 6 | 0 | missing_concept、missing_evidence |
| 41 | AI手机PC | AI手机 | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | MCU芯片 | MCU芯片 | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 3 | 12 | 2 | - |
| 43 | 玻璃基板 | 玻璃基板 | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 5 | - |
| 44 | 电池 | 4680大圆柱电池 | 电力设备 | 120.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 45 | 钠电池 | 钠电池 | 电力设备 | 120.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 3 | - |
| 46 | 铜缆高速连接 | 铜 | 电力设备 | 120.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 47 | 半导体封测 | 半导体封测 | - | 116.4 | multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 48 | 3D打印 | 3D打印 | 机械设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 49 | 机器视觉 | 机器视觉 | 机械设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 50 | 新能源车 | 新能源车 | 电力设备 | 115.22 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：芯片

- **标准概念**：芯片
- **申万一级**：电子
- **评分**：244.7
- **触发类型**：double_red、capacity_industry、limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 2.9846%，边际量 25.0826%，成交额 7739.4148 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |
| double_red | 90.0 | 涨幅2.9846%，边际量25.0826%，成交7739.4148亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.7 | 涨停22只，市场占比24.72，排名1 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 芯片 | 20 |
| AI推理芯片 | 5 |
| AI算力核心赛道：ASIC芯片产业链 | 5 |
| AI算力芯片 | 5 |
| AI芯片 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 旋极信息 | 300324 | AI推理芯片 | core_chip_product | related | L1 | 20 |
| 中芯国际 | 688981 | AI算力核心赛道：ASIC芯片产业链 | 中游制造 | peripheral | graph_only | 20 |
| 寒武纪 | 688256 | AI算力核心赛道：ASIC芯片产业链 | 6.1 重点推荐标的 | peripheral | graph_only | 20 |
| 海光信息 | 688041 | AI算力核心赛道：ASIC芯片产业链 | 4.1 设计领域龙头企业 | peripheral | graph_only | 20 |
| 芯原股份 | 688521 | AI算力核心赛道：ASIC芯片产业链 | 885431.TI | peripheral | graph_only | 20 |
| 长电科技 | 600584 | AI算力核心赛道：ASIC芯片产业链 | 中游封装测试 | peripheral | graph_only | 20 |
| 华天科技 | 002185 | AI算力核心赛道：ASIC芯片产业链 | - | - | graph_only | 20 |
| 通富微电 | 002156 | AI算力核心赛道：ASIC芯片产业链 | - | - | graph_only | 20 |

## 候选 2：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：235.14
- **触发类型**：double_red、capacity_industry、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.7446%，边际量 20.2136%，成交额 5389.2295 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.7446%，边际量20.2136%，成交5389.2295亿 |
| new_high_direction | 62.49 | 新高股62只，新高成交999.2530000000002亿，容量前三=True |
| limit_advance_cluster | 36.0 | 连板股1只，最高4板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 10.65 | 涨停19只，市场占比21.35，排名2 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 3：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：210.27
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.6754%，边际量 34.2009%，成交额 2602.2623 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.6754%，边际量34.2009%，成交2602.2623亿 |
| new_high_direction | 54.27 | 新高股19只，新高成交341.7708亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.8 | daily排名第5，区间涨幅4.68% |
| multi_period_rank | 14.2 | day3排名第7，区间涨幅6.37% |
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
| 华润微 | 688396 | 功率半导体 | 中国本土最大功率半导体企业之一，IDM模式全产业链经营 | core | L2 | 20 |
| 协昌科技 | 301418 | 功率半导体 | 功率芯片（晶圆/封装成品）设计销售并向封测领域延伸 | core | L2 | 20 |
| 士兰微 | 600460 | 功率半导体 | 分立器件产品营收63.79亿元/毛利率12.22%/同比+17.32% | core | L2 | 20 |
| 富乐德 | 301297 | 功率半导体 | 富乐德年报披露的功率半导体相关主营业务 | core | L2 | 20 |
| 康强电子 | 002119 | 功率半导体 | 康强电子年报披露的功率半导体相关主营业务 | core | L2 | 20 |
| 新洁能 | 605111 | 功率半导体 | 受益标的 | core | L2 | 20 |
| 有研硅 | 688432 | 功率半导体 | 有研硅年报披露的功率半导体相关主营业务 | core | L2 | 20 |

## 候选 4：CPO概念

- **标准概念**：CPO
- **申万一级**：-
- **评分**：200.69
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.0634%，边际量 25.9324%，成交额 3949.4521 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.0634%，边际量25.9324%，成交3949.4521亿 |
| new_high_direction | 50.14 | 新高股31只，新高成交810.9558000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 13.4 | day10排名第8，区间涨幅7.53% |
| multi_period_rank | 12.6 | daily排名第9，区间涨幅4.06% |
| limit_heat | 8.55 | 涨停13只，市场占比14.61，排名6 |

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

## 候选 5：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：183.11
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.7492%，边际量 27.8417%，成交额 2597.6928 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.7492%，边际量27.8417%，成交2597.6928亿 |
| new_high_direction | 57.11 | 新高股25只，新高成交569.0851亿，容量前三=True |
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
| 华天科技 | 002185 | 先进封装 | WLP、TSV、FO、PLP及2.5D/3D等先进封装产能提供商 | core | L2 | 20 |
| 华峰测控 | 688200 | 先进封装 | ATE测试设备 | core | L1_L3_candidate | 20 |
| 天马新材 | 920971 | 先进封装 | 电子陶瓷用粉体（MLCC上游）、高压电器用粉体、高导热球形氧化铝 | core | L1_L3_candidate | 20 |
| 康强电子 | 002119 | 先进封装 | 引线框架（冲压+蚀刻）、键合丝、电极丝 | core | L1_L3_candidate | 20 |
| 拓荆科技 | 688072 | 先进封装 | 薄膜沉积(CVD/ALD)设备龙头，拟收购尚积补PVD/刻蚀 | core | L3 | 20 |
| 新恒汇 | 301678 | 先进封装 | 芯片封装材料+封测服务一体化，物联网eSIM芯片封测提供DFN/QFN/... | core | L2 | 20 |
| 沃格光电 | 603773 | 先进封装 | 玻璃基TGV与GCP多层玻璃互联键合技术，面向算力芯片先进封装 | core | L2 | 20 |

## 候选 6：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：179.43
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.8876%，边际量 25.5724%，成交额 2840.4916 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.8876%，边际量25.5724%，成交2840.4916亿 |
| new_high_direction | 53.43 | 新高股22只，新高成交274.25939999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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
| 佰维存储 | 688525 | 存储芯片 | 独立半导体存储解决方案提供商，覆盖NAND/DRAM模组与主控 | core | L2 | 20 |
| 兆易创新 | 603986 | 存储芯片 | NOR Flash/SLC NAND/利基型DRAM设计公司，存储为第一... | core | L2 | 20 |
| 北京君正 | 300223 | 存储芯片 | 车规/工规SRAM、DRAM、Nor Flash设计商，全球车规存储重要... | core | L2 | 20 |
| 复旦微电 | 688385 | 存储芯片 | 高可靠性非挥发存储器供应商，产品含EEPROM、NOR Flash及SL... | core | L2 | 20 |
| 大为股份 | 002213 | 存储芯片 | 半导体存储芯片模组与方案商，覆盖DRAM与NAND Flash产品 | core | L2 | 20 |
| 江波龙 | 301308 | 存储芯片 | 江波龙年报披露的存储芯片相关主营业务 | core | L2 | 20 |

## 候选 7：电力设备

- **标准概念**：电力设备
- **申万一级**：电力设备
- **评分**：178.15
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.3793%，边际量 18.8463%，成交额 1484.5238 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.3793%，边际量18.8463%，成交1484.5238亿 |
| new_high_direction | 52.15 | 新高股17只，新高成交171.94479999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电力设备 | 20 |
| 电力 | 10 |
| 数据中心电力设备 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 伊戈尔 | 002922 | 数据中心电力设备 | 数据中心移相/油浸/干式变压器及供电系统供应商 | related | L2 | 20 |
| 雅达股份 | 920556 | 数据中心电力设备 | 数据中心配电监测用电力测控仪表/装置/传感器供应商，为PUE指标计算提供... | related | L2 | 20 |
| 明阳电气 | 301291 | 数据中心电力设备 | 数据中心供电与算力供电方向输配电设备布局方 | peripheral | L2 | 20 |
| 中恒电气 | 002364 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 四方股份 | 601126 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 科士达 | 002518 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 金盘科技 | 688676 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 天富能源 | 600509 | 电力 | 电力相关产品/材料供应商 | related | L2 | 20 |

## 候选 8：智能穿戴

- **标准概念**：智能穿戴
- **申万一级**：电子
- **评分**：178.12
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.4805%，边际量 18.5943%，成交额 1586.5361 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4805%，边际量18.5943%，成交1586.5361亿 |
| new_high_direction | 52.12 | 新高股16只，新高成交169.45270000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能穿戴 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 佰维存储 | 688525 | 智能穿戴 | AI/AR眼镜、智能手表等端侧ePOP存储供应商 | related | L2 | 20 |
| 佳禾智能 | 300793 | 智能穿戴 | 智能手表、智能眼镜等可穿戴产品制造商 | related | L2 | 20 |
| 则成电子 | 920821 | 智能穿戴 | 声学/汽车/医疗电子装联与定制化模组模块（AI智能穿戴高多层AIR-GA... | related | L2 | 20 |
| 天键股份 | 301383 | 智能穿戴 | 声学技术向智能穿戴/智能家居/车载电子等领域延伸 | related | L2 | 20 |
| 萤石网络 | 688475 | 智能穿戴 | 萤石网络年报披露的智能穿戴相关主营业务 | related | L2 | 20 |
| 金太阳 | 300606 | 智能穿戴 | 金太阳年报披露的智能穿戴相关主营业务 | related | L2 | 20 |
| 中科蓝讯 | 688332 | 智能穿戴 | 智能穿戴和智能手表等SoC芯片供应商 | peripheral | graph_only | 20 |
| 唯捷创芯 | 688153 | 射频芯片 | 国内射频前端行业先行者（Fabless模式，产品应用于智能手机、车载通信... | core | L2 | 1 |

## 候选 9：汽车芯片

- **标准概念**：汽车芯片
- **申万一级**：电子
- **评分**：177.6
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.6805%，边际量 35.6362%，成交额 1215.3277 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.6805%，边际量35.6362%，成交1215.3277亿 |
| new_high_direction | 51.6 | 新高股14只，新高成交320.0003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 汽车芯片 | 20 |
| 芯片 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 四维图新 | 002405 | 汽车芯片 | 车规级芯片自研，舱驾融合芯片AC8025AE | core | L2 | 20 |
| 聚辰股份 | 688123 | 汽车芯片 | DDR5 SPD芯片、VPD芯片、EEPROM（车规&工业） | related | L1_L3_candidate | 20 |
| 银河微电 | 688689 | 汽车芯片 | 车规级半导体分立器件、SiC、GaN第三代半导体 | related | L1_L3_candidate | 20 |
| 国芯科技 | 688262 | 汽车芯片 | 汽车电子芯片(域控MCU)国产替代厂商，RISC-V车规MCU与量子安全... | related | L1_L3_candidate | 20 |
| 气派科技 | 688216 | 汽车芯片 | 集成电路封装测试、功率器件封装测试、晶圆测试 | related | L1_L3_candidate | 20 |
| 利尔达 | 920249 | 芯片 | IC增值分销商，为客户提供芯片及一站式配套服务 | core | L2 | 20 |
| 复旦微电 | 688385 | 芯片 | 超大规模集成电路设计企业，产品线覆盖FPGA、安全与识别、非挥发存储器和... | core | L2 | 20 |
| 探路者 | 300005 | 芯片 | 集成电路业务覆盖触控IC、指纹识别芯片、图像及视频处理IP | related | L2 | 20 |

## 候选 10：集成电路设计

- **标准概念**：集成电路
- **申万一级**：电子
- **评分**：175.14
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.3728%，边际量 28.266%，成交额 1157.5867 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.3728%，边际量28.266%，成交1157.5867亿 |
| new_high_direction | 40.74 | 新高股7只，新高成交234.91829999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 8.4 | daily排名第8，区间涨幅4.37% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 集成电路 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 全志科技 | 300458 | 集成电路 | 集成电路设计企业，SoC+模拟+无线互联芯片组合供应商 | core | L2 | 20 |
| 北京君正 | 300223 | 集成电路 | 集成电路芯片研发销售商，坚持存储+计算+模拟产品战略 | core | L2 | 20 |
| 华大九天 | 301269 | 集成电路 | 贯穿集成电路设计、制造、封装的EDA战略基础工具供应商 | core | L2 | 20 |
| 三安光电 | 600703 | 集成电路 | 射频/电力电子/光技术等化合物半导体集成电路 | core | L2 | 20 |
| 东软载波 | 300183 | 集成电路 | 软件及集成电路相关产品/服务商 | core | L2 | 20 |
| 中颖电子 | 300327 | 集成电路 | 集成电路产品相关产品/服务商 | core | L2 | 20 |
| 兴福电子 | 688545 | 集成电路 | 集成电路湿法蚀刻/清洗关键耗材供应商 | core | L2 | 20 |
| 创耀科技 | 688259 | 集成电路 | 软件及集成电路、芯片版图设计服务相关产品/服务商 | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-85af5153c5b21858dd70 artifact_sha=36654cfbb82069a1e96186e7f172922e8322771fcc4264866678d8d32df68456 manifest_sha=a256a79b55200d9ef12724b4743a0a28ccfae48090a010851b8b47e1abd2fc7f -->
