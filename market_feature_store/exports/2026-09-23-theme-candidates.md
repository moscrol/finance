# 2026-09-23 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：17629.6
- **上涨家数**：1888
- **涨停 / 跌停**：51 / 14
- **容量前三行业**：1.电子(28.1%, super_capacity)、2.机械设备(7.7%, normal)、3.医药生物(7.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PCB | PCB | 电子 | 143.81 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 2 | DeepSeek概念 | DeepSeek | 计算机 | 137.8 | limit_heat、limit_advance_cluster、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 3 | 电子 | EDA（电子设计自动化） | 电子 | 128.75 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 4 | 元器件 | 电子元器件 | 电子 | 111.42 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 5 | 锂电池概念 | 锂 | 轻工制造 | 107.63 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 6 | 新能源车 | 新能源车 | 汽车 | 106.16 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 智能家居 | 智能家居 | 房地产 | 101.65 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 8 | 玻璃基板 | 玻璃基板 | 电子 | 91.62 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 9 | 医疗服务 | 医疗服务 | - | 90.8 | multi_period_rank、new_high_cluster | 2 | 12 | 2 | - |
| 10 | 疫苗 | 疫苗 | - | 90.4 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 半导体 | 半导体 | 电子 | 88.63 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 12 | CXO概念 | CXO | - | 88.4 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 13 | 机械设备 | 机械设备 | 机械设备 | 87.83 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 14 | 存储芯片 | 存储芯片 | 电子 | 86.14 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 15 | 先进封装 | 先进封装 | 电子 | 83.1 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 16 | OLED概念 | LED | 电子 | 82.29 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 17 | 医药医疗 | 医疗 | 医药生物 | 81.85 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 18 | 智能穿戴 | 智能穿戴 | 电子 | 81.22 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 19 | AI眼镜 | AI眼镜 | 电子 | 80.93 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 20 | MiniLED | Mini LED | 电子 | 80.93 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 21 | 折叠屏 | 折叠屏 | 电子 | 80.84 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 1 | - |
| 22 | PCB概念 | PCB概念 | - | 80.38 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 23 | 人形机器人 | 人形机器人 | 机械设备 | 80.27 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 24 | 医药 | 医药 | 医药生物 | 80.26 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 25 | 创新药 | 创新药 | 医药生物 | 79.99 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 26 | 光学光电 | 光学 | 电子 | 79.61 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 27 | MicroLED | Micro LED | 电子 | 79.43 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 28 | AI医疗概念 | AI医疗 | 医药生物 | 78.58 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 29 | CPO概念 | CPO | - | 78.47 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 30 | 物联网 | 物联网 | - | 77.06 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 数据中心 | 数据中心 | 计算机 | 77.05 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 小米概念 | 小米概念 | - | 76.86 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 无人驾驶 | 无人驾驶 | 汽车 | 76.47 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 34 | 商业航天 | 商业航天 | 国防军工 | 76.25 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 35 | 一带一路 | 一带一路 | - | 75.7 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 36 | 改性塑料 | 改性塑料 | - | 75.2 | multi_period_rank、new_high_cluster | 1 | 12 | 1 | - |
| 37 | 工业互联 | 工业互联网 | - | 74.97 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 38 | 车联网 | 车联网 | - | 74.74 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 39 | AI手机PC | AI手机 | 电子 | 73.49 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 40 | 苹果概念 | 苹果概念 | - | 71.98 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 虚拟现实 | 虚拟现实 | - | 71.62 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 42 | 东数西算 | 东数西算 | - | 70.95 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 43 | 新零售 | 零售 | - | 70.16 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 粤港澳 | 粤港澳 | - | 69.95 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 45 | 无人机 | 无人机 | - | 69.85 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 46 | 第三代半导体 | 第三代半导体 | - | 69.48 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 47 | 充电桩 | 充电桩 | - | 69.39 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 48 | 智能医疗 | 医疗 | - | 69.35 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 49 | 化工 | 化工 | 基础化工 | 69.07 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 50 | 养老概念 | 养老概念 | - | 69.02 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 五、核心候选明细

## 候选 1：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：143.81
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.61 | 新高股22只，新高成交368.7334000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | day10排名第1，区间涨幅18.96% |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅1.94% |
| multi_period_rank | 19.2 | day3排名第7，区间涨幅6.59% |

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
| 东山精密 | 002384 | PCB | 全球电子电路（软板+硬板+软硬结合板）平台型制造商，高多层PCB/高阶H... | core | L2 | 21 |
| 沪电股份 | 002463 | PCB | 受益标的 | core | L2 | 21 |
| 天承科技 | 688603 | PCB | 受益于AI算力驱动的高多层板/HDI/封装基板需求 | core | L2 | 21 |
| 本川智能 | 300964 | PCB | 中高端PCB定制化制造商，以通信设备为核心，布局汽车电子、新能源、AI服... | core | L2 | 21 |
| 胜宏科技 | 300476 | PCB | 高密度印制线路板制造商 | core | L2 | 21 |
| 三孚新科 | 688359 | PCB | 高端PCB电镀专用化学品与电镀设备供应商 | related | L2 | 21 |
| 超颖电子 | 603175 | PCB | 汽车电子PCB供应商，布局高多层服务器板、汽车板、存储板等高阶PCB产能 | related | L1_L3_candidate | 21 |
| 容大感光 | 300576 | AIPCB专用油墨 | PCB光刻胶/高端油墨核心验证标的 | core | L1_L3_candidate | 20 |

## 候选 2：DeepSeek概念

- **标准概念**：DeepSeek
- **申万一级**：计算机
- **评分**：137.8
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股3只，最高4板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比15.69，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| DeepSeek | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天源迪科 | 300047 | DeepSeek | 天源迪科年报披露的DeepSeek相关主营业务 | core | L2 | 20 |
| 寒武纪 | 688256 | DeepSeek | 寒武纪年报披露的DeepSeek相关主营业务 | core | L2 | 20 |
| 电科数字 | 600850 | DeepSeek | 电科数字年报披露的DeepSeek相关主营业务 | core | L2 | 20 |
| 长盈精密 | 300115 | DeepSeek | 长盈精密年报披露的DeepSeek相关主营业务 | core | L2 | 20 |
| 华大智造 | 688114 | AI智能体 | 全读长测序业务、多组学业务、智能自动化业务 | related | L1_L3_candidate | 1 |
| 大普微 | 301666 | AI算力 | 为AI模型训练与推理提供企业级存力，企业级SSD被定位为算力基础设施基石 | related | L2 | 1 |
| 亚康股份 | 301017 | 东数西算 | 算力租赁运营、算力基础设施综合服务(IT运维)、IT设备销售(系统集成) | related | L1_L3_candidate | 1 |
| 先进数通 | 300541 | 华为昇腾 | IT基础设施建设（算力服务器/数据中心）、软件解决方案（Starring... | core | L1_L3_candidate | 1 |

## 候选 3：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：128.75
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 65.25 | 新高股102只，新高成交1220.2645999999997亿，容量前三=True |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比19.61，排名2 |

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

## 候选 4：元器件

- **标准概念**：电子元器件
- **申万一级**：电子
- **评分**：111.42
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.62 | 新高股23只，新高成交369.26220000000006亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 18.2 | day10排名第2，区间涨幅15.9% |
| multi_period_rank | 12.6 | day3排名第9，区间涨幅5.19% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元器件 | 5 |
| 电子元器件分销 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华安鑫创 | 300928 | 电子元器件 | 通用器件分销相关产品/服务商 | core | L2 | 20 |
| 国力电子 | 688103 | 电子元器件 | 电子真空器件、直流接触器相关产品/服务商 | core | L2 | 20 |
| 利和兴 | 301013 | 电子元器件 | 向新型电子元器件领域拓展（孙公司利和兴电子），客户含摩尔线程、蓝思科技、... | related | L2 | 20 |
| 三友联众 | 300932 | 电子元器件 | 继电器相关产品供应商 | related | L2 | 20 |
| 灿勤科技 | 688182 | 电子元器件 | 高端先进电子陶瓷元器件相关产品供应商 | related | L2 | 20 |
| 长城军工 | 601606 | 电子元器件 | - | related | L1 | 20 |
| 中电港 | 001287 | 电子元器件分销 | 本土元器件分销商龙头（连续6年首位，近140条授权产品线） | core | L2 | 20 |
| 新亚制程 | 002388 | 电子元器件分销 | 电子信息产品销售服务为第一大业务，2025年收入13.45亿元（占比69... | core | L2 | 20 |

## 候选 5：锂电池概念

- **标准概念**：锂
- **申万一级**：轻工制造
- **评分**：107.63
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.18 | 新高股59只，新高成交414.1058999999999亿，容量前三=False |
| limit_advance_cluster | 30.0 | 连板股1只，最高4板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比13.73，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 锂 | 10 |
| 锂电池 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亿纬锂能 | 300014 | 锂电池 | 消费/动力/储能全场景锂电池平台公司，覆盖锂原、小型锂电、圆柱、方形铁锂... | core | L2 | 20 |
| 先导智能 | 300450 | 锂电池 | 锂电池智能制造装备供应商，服务动力/储能方壳与圆柱产线 | core | L2 | 20 |
| 利元亨 | 688499 | 锂电池 | 锂电池产线智能制造装备供应商，收入高度绑定下游锂电客户资本开支 | core | L2 | 20 |
| 华盛锂电 | 688353 | 锂电池 | VC、FEC相关产品/服务商 | core | L2 | 20 |
| 国轩高科 | 002074 | 锂电池 | 新能源锂电池制造商与绿色能源综合解决方案服务商，聚焦动力电池与储能电池 | core | L2 | 20 |
| 多氟多 | 002407 | 锂电池 | "氟芯"大圆柱电池制造商，2025年底新能源电池产能达20GWh，产品覆... | core | L2 | 20 |
| 天力锂能 | 301152 | 锂电池 | 动力/储能锂电池正极材料及碳酸锂供应 | core | L2 | 20 |
| 天华新能 | 300390 | 锂电池 | 锂离子电池正极材料原材料供应商，服务动力电池与储能电池 | core | L2 | 20 |

## 候选 6：新能源车

- **标准概念**：新能源车
- **申万一级**：汽车
- **评分**：106.16
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 49.01 | 新高股96只，新高成交721.1197亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 7.15 | 涨停9只，市场占比17.65，排名3 |

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
| 北京双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 华鲁恒升 | 600426 | 新能源 | 煤化工平台向新能源新材料延伸，新能源新材料已成第一大产品 | core | L2 | 20 |
| 双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 固德威 | 688390 | 新能源 | 固德威年报披露的新能源相关主营业务 | core | L2 | 20 |
| 浙江新能 | 600032 | 新能源 | 风光水综合型可再生能源发电企业（控股装机690.76万千瓦） | core | L2 | 20 |
| 润建股份 | 002929 | 新能源 | 新能源电站（光伏/风力/储能）开发建设运维全生命周期服务商 | core | L2 | 20 |
| 涪陵电力 | 600452 | 新能源 | 涪陵电力年报披露的新能源相关主营业务 | core | L2 | 20 |
| 珠海港 | 000507 | 新能源 | 新能源板块收入24.7亿元占比56.34%（风电珠海港昇+管道燃气） | core | L2 | 20 |

## 候选 7：智能家居

- **标准概念**：智能家居
- **申万一级**：房地产
- **评分**：101.65
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.9 | 新高股34只，新高成交232.22770000000003亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比9.8，排名21 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能家居 | 20 |
| 家居 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 嘉益股份 | 301004 | 家居 | 不锈钢器皿相关产品/服务商 | core | L2 | 20 |
| 欧派家居 | 603833 | 家居 | 定制家居龙头（橱柜/衣柜/卫浴/木门） | core | L2 | 20 |
| 皮阿诺 | 002853 | 家居 | 中高端定制家居品牌：整体橱柜、全屋定制及门墙三大核心品类，柔性化规模定制... | core | L2 | 20 |
| 美之高 | 920765 | 家居 | 金属收纳置物架ODM/OEM厂商（家用类为主、工业类为辅），主要客户为日... | core | L2 | 20 |
| 美克家居 | 600337 | 家居 | 多品牌家居零售+国际批发商：直营品牌美克美家（连续十三年入选中国500最... | core | L2 | 20 |
| 顶固集创 | 300749 | 家居 | 定制衣柜及配套家居相关产品/服务商 | core | L2 | 20 |
| 茶花股份 | 603615 | 家居 | 塑料制品、非塑料制品相关产品/服务商 | related | L2 | 20 |
| 创源股份 | 300703 | 家居 | 家居相关产品/服务商 | related | L2 | 20 |

## 候选 8：玻璃基板

- **标准概念**：玻璃基板
- **申万一级**：电子
- **评分**：91.62
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.02 | 新高股24只，新高成交321.344亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 11.6 | daily排名第4，区间涨幅2.13% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 玻璃基板 | 20 |
| 玻璃 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三峡新材 | 600293 | 玻璃 | 平板玻璃生产商（湖北当阳），围绕玻璃主业深耕 | core | L2 | 20 |
| 秀强股份 | 300160 | 玻璃 | 玻璃深加工行业相关产品/服务商 | core | L2 | 20 |
| 北玻股份 | 002613 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 南玻A | 000012 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 德力股份 | 002571 | 玻璃 | 玻璃相关产品/服务商 | related | L2 | 20 |
| 海南发展 | 002163 | 玻璃 | 玻璃相关产品/服务商 | related | L2 | 20 |
| 福耀玻璃 | 600660 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 蓝思科技 | 300433 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |

## 候选 9：医疗服务

- **标准概念**：医疗服务
- **申万一级**：-
- **评分**：90.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅11.24% |
| multi_period_rank | 20.8 | day10排名第5，区间涨幅11.02% |
| multi_period_rank | 20.8 | day3排名第5，区间涨幅7.05% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗服务 | 20 |
| 医疗 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 嘉事堂 | 002462 | 医疗 | 嘉事堂年报披露的医疗相关主营业务 | core | L2 | 20 |
| 常铝股份 | 002160 | 医疗 | 常铝股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 昊海生科 | 688366 | 医疗 | 昊海生科年报披露的医疗相关主营业务 | related | L2 | 20 |
| 朗姿股份 | 002612 | 医疗 | 朗姿股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 欧林生物 | 688319 | 医疗 | 欧林生物年报披露的医疗相关主营业务 | related | L2 | 20 |
| 航亚科技 | 688510 | 医疗 | 航亚科技年报披露的医疗相关主营业务 | related | L2 | 20 |
| 三星电气 | 601567 | 医疗服务 | 医疗服务运营板块 | core | L2 | 20 |
| 创新医疗 | 002173 | 医疗服务 | 民营医院医疗服务运营商，下属建华、康华、福恬、明珠四家医院 | core | L2 | 20 |

## 候选 10：疫苗

- **标准概念**：疫苗
- **申万一级**：-
- **评分**：90.4
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅9.06% |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅13.0% |
| multi_period_rank | 22.4 | daily排名第3，区间涨幅2.31% |
| new_high_cluster | 20.0 | 题材内新高股4只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 疫苗 | 20 |
| DC疫苗 | 5 |
| HIV疫苗 | 5 |
| HPV疫苗 | 5 |
| mRNA疫苗 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 智飞生物 | 300122 | mRNA疫苗 | mRNA技术平台布局者（带状疱疹/新冠mRNA疫苗获临床批件） | peripheral | L2 | 20 |
| 沃森生物 | 300142 | mRNA疫苗 | 与合作方共建mRNA疫苗技术平台 | related | L2 | 20 |
| 科前生物 | 688526 | mRNA疫苗 | 科前生物年报披露的mRNA疫苗相关主营业务 | core | L2 | 20 |
| 生物股份 | 600201 | mRNA疫苗 | 兽用生物制品（猪、牛、禽 | related | L1_L3_candidate | 20 |
| 康泰生物 | 300601 | mRNA疫苗 | mRNA核酸疫苗研发平台（储备） | related | L2 | 20 |
| 石药创新 | 300765 | mRNA疫苗 | mRNA疫苗平台储备 | related | L2 | 20 |
| 瑞普生物 | 300119 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |
| 金河生物 | 002688 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-a84e81e3da069b020028 artifact_sha=d41a5fd6a6f5818d93730a54ac38568cdbef1d8970b53fb451569b52d0f93e31 manifest_sha=105b5b0ebf46d03d27182953da7d94ad9a34c55155f90d0c592bc6dd305c5fb0 -->
