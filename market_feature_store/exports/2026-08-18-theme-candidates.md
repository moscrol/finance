# 2026-08-18 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：24006.36
- **上涨家数**：2121
- **涨停 / 跌停**：79 / 7
- **容量前三行业**：1.电子(31.2%, super_capacity)、2.通信(8.1%, normal)、3.机械设备(7.9%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 半导体材料 | 半导体材料 | - | 222.4 | double_red、multi_period_rank、new_high_cluster | 3 | 12 | 5 | - |
| 2 | 新型工业化 | 新型工业化 | 机械设备 | 183.55 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 3 | 机械设备 | 机械设备 | - | 175.1 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 4 | 光学光电 | 光学 | - | 171.59 | double_red、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 5 | 化工 | 化工 | - | 169.62 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 6 | 高端装备 | 高端装备 | - | 166.16 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 7 | MiniLED | Mini LED | - | 164.44 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 玻璃基板 | 玻璃基板 | - | 163.58 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 9 | MicroLED | Micro LED | - | 163.09 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 10 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 162.71 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 机器人 | 机器人 | 基础化工 | 158.6 | limit_advance_cluster、multi_period_rank、new_high_cluster | 5 | 12 | 2 | - |
| 12 | 电子化学品 | 电子化学品 | 基础化工 | 147.6 | double_red、multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 13 | 光学元件 | 光学元件 | - | 133.2 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 14 | 乡村振兴 | 乡村振兴 | - | 128.4 | double_red、limit_heat、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 15 | 减速器 | 减速器 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 4 | 12 | 1 | - |
| 16 | 通用设备 | 通用设备 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 7 | 0 | missing_concept、missing_evidence |
| 17 | AI手机PC | AI手机 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 18 | TOPCon电池 | TOPCon电池 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 19 | 光伏 | 光伏 | 电力设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 5 | - |
| 20 | 华为汽车 | 华为汽车 | - | 116.0 | double_red、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 21 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 22 | 操作系统 | 操作系统 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 23 | 汽车热管理 | 汽车热管理 | - | 116.0 | double_red、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 24 | 养殖业 | 养殖 | 农林牧渔 | 115.0 | limit_advance_cluster、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 25 | 种植业 | 种植业 | - | 105.75 | limit_heat、multi_period_rank、new_high_cluster | 1 | 5 | 1 | - |
| 26 | 农业 | 农业 | - | 105.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 27 | AI硬件 | AI硬件 | 电力设备 | 101.0 | limit_advance_cluster | 1 | 12 | 1 | - |
| 28 | 粮食概念 | 粮食概念 | - | 99.95 | limit_heat、multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 29 | 存储芯片 | 存储芯片 | 电子 | 99.26 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 30 | CPO概念 | CPO | - | 98.15 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 先进封装 | 先进封装 | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 32 | 新能源车 | 新能源车 | - | 93.25 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 光纤光缆 | 光纤光缆 | - | 93.2 | multi_period_rank、new_high_cluster | 3 | 12 | 5 | - |
| 34 | 人形机器人 | 人形机器人 | 机械设备 | 93.09 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 35 | 大消费 | 消费 | - | 93.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 36 | 数据中心 | 数据中心 | 计算机 | 90.8 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 37 | 电子 | EDA（电子设计自动化） | - | 90.8 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 38 | 商业航天 | 商业航天 | 国防军工 | 90.45 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 39 | 一带一路 | 一带一路 | - | 90.34 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 40 | 半导体 | 半导体 | 电子 | 89.98 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 41 | 股权 | 私募股权投资 | - | 89.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | 通信设备 | 通信设备 | 通信 | 87.8 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 43 | AI眼镜 | AI眼镜 | 电子 | 87.32 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 44 | 通信 | 通信 | - | 86.46 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 45 | 物联网 | 物联网 | - | 85.28 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 46 | 光刻机 | 光刻机 | 电子 | 85.24 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 2 | - |
| 47 | 充电桩 | 充电桩 | - | 84.68 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 48 | 光通信 | 光通信 | - | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 49 | PCB概念 | PCB概念 | - | 83.91 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 50 | 国防军工 | 国防军工 | - | 82.85 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：半导体材料

- **标准概念**：半导体材料
- **申万一级**：-
- **评分**：222.4
- **触发类型**：double_red、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 3.44%，边际量 41.68%，成交额 532.4 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.44%，边际量41.68%，成交532.4亿 |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅33.6% |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅11.18% |
| multi_period_rank | 26.6 | day5排名第4，区间涨幅11.27% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 22.6 | daily排名第9，区间涨幅3.44% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体材料 | 20 |
| 半导体 | 10 |
| 半导体材料去日化 | 5 |

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

## 候选 2：新型工业化

- **标准概念**：新型工业化
- **申万一级**：机械设备
- **评分**：183.55
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 15.98%，成交额 1332.58 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量15.98%，成交1332.58亿 |
| new_high_direction | 57.55 | 新高股86只，新高成交604.23亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新型工业化 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东土科技 | 300353 | 新型工业化 | 工业操作系统 / 工业软件-操作系统 / 半导体设备映射标的 | core | L2 | 20 |
| 中控技术 | 688777 | 新型工业化 | DCS（集散控制系统） / 工业AI大模型 / 工业软件-DCS/AI ... | core | L2 | 20 |
| 信捷电气 | 603416 | 新型工业化 | 运动控制/PLC / 工控-小型PLC / PLC（大中型）映射标的 | core | L2 | 20 |
| 华中数控 | 300161 | 新型工业化 | 数控系统 / 工业母机-数控系统映射标的 | core | L2 | 20 |
| 埃斯顿 | 002747 | 新型工业化 | 工业机器人整机 / 机器人-整机 / 新能源汽车映射标的 | core | L2 | 20 |
| 宝信软件 | 600845 | 新型工业化 | 钢铁信息化/PLC / 工业软件-钢铁信息化 / 钢铁行业AI赋能映射标... | core | L2 | 20 |
| 汇川技术 | 300124 | 新型工业化 | 通用自动化/伺服 / 工控-通用自动化 / 新能源汽车 / 人形机器人映... | core | L2 | 20 |
| 海天精工 | 601882 | 新型工业化 | 机床整机（主机厂） / 出口竞争力 / 工业母机-整机 / AI液冷精密... | core | L2 | 20 |

## 候选 3：机械设备

- **标准概念**：机械设备
- **申万一级**：-
- **评分**：175.1
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.56%，边际量 12.39%，成交额 1995.06 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.56%，边际量12.39%，成交1995.06亿 |
| new_high_direction | 52.65 | 新高股219只，新高成交1012.1599999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比8.86，排名21 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光格科技 | 688450 | AIoT | 分布式光纤传感、AIoT资产运维、四足巡检机器人 | core | L2 | 1 |
| 卓兆点胶 | 920026 | AI眼镜 | 消费电子点胶设备/阀体（果链核心供应商）、Meta AI眼镜点胶阀、点胶... | core | L1_L3_candidate | 1 |
| 武进不锈 | 603878 | 不锈钢管 | 工业用不锈钢管（无缝管/焊管/管件），下游为石化、电力设备、机械设备制造 | core | L2 | 1 |
| 双元科技 | 688623 | 人形机器人 | 人形机器人自动化检测装配设备、在线自动化测控系统、机器视觉智能检测系统 | core | L2 | 1 |
| 锐科激光 | 300747 | 低空经济 | 连续光纤激光器、超快激光器、脉冲光纤激光器、特种光纤 | core | L1_L3_candidate | 1 |
| 海伦哲 | 300201 | 储能消防 | 储能消防（气溶胶灭火）、高空作业车、电力应急保障车、军品及消防车 | core | L1_L3_candidate | 1 |
| 联赢激光 | 688518 | 固态电池 | 锂电激光焊接、消费电子焊接、固态电池设备、TGV玻璃基板激光加工 | core | L1_L3_candidate | 1 |
| 正弦电气 | 688395 | 工控（工业自动化） | 工业自动化电机驱动与控制系统产品供应商（变频器/一体化专机/伺服系统，深... | core | L2 | 1 |

## 候选 4：光学光电

- **标准概念**：光学
- **申万一级**：-
- **评分**：171.59
- **触发类型**：double_red、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.04%，边际量 47.47%，成交额 810.15 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.04%，边际量47.47%，成交810.15亿 |
| new_high_direction | 47.19 | 新高股56只，新高成交575.17亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 8.4 | day3排名第8，区间涨幅7.78% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光学 | 12 |
| 光电 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 欧菲光 | 002456 | 光学 | 光学相关产品/材料供应商 | related | L2 | 20 |
| 新光光电 | 688011 | 光电 | 光学目标与场景仿真系统为第一大产品，2025年收入8,465.24万元（... | core | L2 | 20 |
| 德科立 | 688205 | OCS光电路交换机 | DCI数据中心互联、相干、非相干光模块、OCS光电路交换机 | core | L1_L3_candidate | 5 |
| 瑞斯康达 | 603803 | OCS光电路交换机 | AI算力网络设备（RoCE交换机、OCS光交换机）、高速光模块（400G... | related | L1_L3_candidate | 5 |
| 光库科技 | 300620 | OCS光电路交换机 | 图谱弱关联 | peripheral | graph_only | 5 |
| 永鼎股份 | 600105 | OCS光电路交换机 | 图谱弱关联 | peripheral | graph_only | 5 |
| 罗博特科 | 300757 | OCS光电路交换机 | 图谱弱关联 | peripheral | graph_only | 5 |
| 赛微电子 | 300456 | OCS光电路交换机 | 图谱弱关联 | peripheral | graph_only | 5 |

## 候选 5：化工

- **标准概念**：化工
- **申万一级**：-
- **评分**：169.62
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.64%，边际量 12.88%，成交额 1326.57 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.64%，边际量12.88%，成交1326.57亿 |
| new_high_direction | 46.82 | 新高股156只，新高成交545.4400000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比10.13，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 化工 | 20 |
| C4化工 | 5 |
| 中国化工全球份额提升 | 5 |
| 化工出海 | 5 |
| 化工周期 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万华化学 | 600309 | 中国化工全球份额提升 | 化工龙头与全球份额提升受益企业 | peripheral | graph_only | 20 |
| 鲁西化工 | 000830 | 中国化工全球份额提升 | 化工龙头与全球份额提升受益企业 | peripheral | graph_only | 20 |
| 宇新股份 | 002986 | 化工 | 以LPG为原料的深加工有机化工产品生产商（化工行业收入占比99.99%） | core | L2 | 20 |
| 正丹股份 | 300641 | 化工 | 石油化工行业酸酐及酯类产品生产商（酸酐及酯类设计产能18.5万吨/年、在... | core | L2 | 20 |
| 皖维高新 | 600063 | 化工 | 聚乙烯醇（PVA）行业龙头 | core | L2 | 20 |
| 长华化学 | 301518 | 化工 | 国内聚醚多元醇行业头部企业（POP/软泡用PPG/CASE用聚醚及特种聚... | core | L2 | 20 |
| 东岳硅材 | 300821 | 化工 | 基础化工材料企业 | core | L1 | 20 |
| 中欣氟材 | 002915 | 化工 | 基础化工企业 | core | L1 | 20 |

## 候选 6：高端装备

- **标准概念**：高端装备
- **申万一级**：-
- **评分**：166.16
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 11.93%，成交额 1800.11 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量11.93%，成交1800.11亿 |
| new_high_direction | 50.16 | 新高股101只，新高成交812.8899999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 高端装备 | 20 |
| 高端装备与自主可控制造 | 5 |
| 高端装备制造 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 通裕重工 | 300185 | 高端装备 | 能源电力/石化/船舶/海工/核电等大型装备核心部件平台 | related | L2 | 20 |
| 三花智控 | 002050 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 光威复材 | 300699 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 德赛西威 | 002920 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 拓普集团 | 601689 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 汇川技术 | 300124 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 航天电子 | 600879 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 莱斯信息 | 688631 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |

## 候选 7：MiniLED

- **标准概念**：Mini LED
- **申万一级**：-
- **评分**：164.44
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.2%，边际量 10.58%，成交额 1357.7 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.2%，边际量10.58%，成交1357.7亿 |
| new_high_direction | 48.44 | 新高股51只，新高成交675.4499999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| Mini LED | 20 |
| MiniLED | 20 |
| LED | 12 |
| MiniLED产业 | 5 |
| MiniLED电视 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兆驰股份 | 002429 | LED | LED外延片、芯片、封装器件、Mini/Micro LED显示模组、LE... | core | L2 | 21 |
| 万润科技 | 002654 | LED | LED产业中游封装、下游应用业务，集研发设计生产销售一体 | core | L2 | 20 |
| 三安光电 | 600703 | LED | LED外延芯片+应用品为第一大收入来源 | core | L2 | 20 |
| 聚飞光电 | 300303 | LED | LED封装龙头企业 | core | L2 | 20 |
| 英飞特 | 300582 | LED | LED照明配套产品供应商，主营LED驱动电源、传感器、控制系统和LED模... | core | L2 | 20 |
| 蔚蓝锂芯 | 002245 | LED | LED业务具备从蓝宝石衬底切磨抛、PSS、外延片、LED芯片、CSP特种... | core | L2 | 20 |
| 美迪凯 | 688079 | LED | TGV玻璃基板（先进封装）、半导体声光学、半导体封测、MicroLED（... | core | L1_L3_candidate | 20 |
| 三雄极光 | 300625 | LED | LED光源应用环节 | related | L2 | 20 |

## 候选 8：玻璃基板

- **标准概念**：玻璃基板
- **申万一级**：-
- **评分**：163.58
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.11%，边际量 20.75%，成交额 1164.86 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.11%，边际量20.75%，成交1164.86亿 |
| new_high_direction | 47.58 | 新高股34只，新高成交606.0500000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 玻璃基板 | 20 |
| 玻璃 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三峡新材 | 600293 | 玻璃 | 平板玻璃生产商（湖北当阳），围绕玻璃主业深耕 | core | L2 | 20 |
| 北玻股份 | 002613 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 南玻A | 000012 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 福耀玻璃 | 600660 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 蓝思科技 | 300433 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 金晶科技 | 600586 | 玻璃 | 玻璃相关产品/材料供应商 | related | L2 | 20 |
| 沃格光电 | 603773 | 玻璃基板 | 牵头发起中国玻璃线路板产业联盟（GCPA），参与玻璃基板先进封装行业标准... | core | L2 | 20 |
| 长川科技 | 300604 | 玻璃基板 | 待补充 | core | L1_L3_candidate | 20 |

## 候选 9：MicroLED

- **标准概念**：Micro LED
- **申万一级**：-
- **评分**：163.09
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.09%，边际量 24.76%，成交额 902.66 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.09%，边际量24.76%，成交902.66亿 |
| new_high_direction | 47.09 | 新高股39只，新高成交567.5300000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| Micro LED | 20 |
| LED | 12 |
| CRO | 10 |
| OLED | 10 |
| Micro LED光互连 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兆驰股份 | 002429 | LED | LED外延片、芯片、封装器件、Mini/Micro LED显示模组、LE... | core | L2 | 21 |
| 美迪凯 | 688079 | LED | TGV玻璃基板（先进封装）、半导体声光学、半导体封测、MicroLED（... | core | L1_L3_candidate | 21 |
| 南模生物 | 688265 | CRO | 国家级高新技术企业，以基因编辑技术为核心、以小鼠大鼠等模式生物为载体构建... | core | L2 | 20 |
| 益诺思 | 688710 | CRO | 非临床CRO收入7.81亿元占主营96%以上，2025年新签合同11.3... | core | L2 | 20 |
| 睿智医药 | 300149 | CRO | 药效药动业务收入6.03亿元占53.18%同比+10.28%，化学业务收... | core | L2 | 20 |
| 阳光诺和 | 688621 | CRO | 国内较早对外提供药物研发服务的全国性综合CRO企业，“临床前+临床”一体... | core | L2 | 20 |
| 万邦医药 | 301520 | CRO | CRO相关产品/材料供应商 | related | L2 | 20 |
| 和元生物 | 688238 | CRO | CRO | related | L1_L3_candidate | 20 |

## 候选 10：钙钛矿电池

- **标准概念**：钙钛矿
- **申万一级**：电力设备
- **评分**：162.71
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.15%，边际量 13.78%，成交额 775.76 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.15%，边际量13.78%，成交775.76亿 |
| new_high_direction | 46.71 | 新高股40只，新高成交536.4800000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 钙钛矿 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中矿资源 | 002738 | 钙钛矿 | 全球铷矿端资源及铷盐精细化工领域龙头 | related | L1_L3_candidate | 20 |
| 天合光能 | 688599 | 钙钛矿 | 光伏组件、储能系统、系统解决方案 | related | L1_L3_candidate | 20 |
| 恒星科技 | 002132 | 钙钛矿 | 有机硅化工（核心增长极）、金属制品（压舱石业务） | core | L1_L3_candidate | 20 |
| 隆华科技 | 300263 | 钙钛矿 | 电子新材料（靶材：ITO/IZO/AZO/钼靶/银合金靶）、高分子复合材... | core | L1_L3_candidate | 20 |
| 信宇人 | 688573 | 钙钛矿 | 锂电干燥/涂布/辊压分切设备、固态电池（卤化物电解质材料+干法电极设备）... | core | L1_L3_candidate | 20 |
| 晶科能源 | 688223 | 钙钛矿 | 钙钛矿叠层 | related | L1_L3_candidate | 20 |
| 三超新材 | 300554 | 钙钛矿 | 钙钛矿晶硅叠层 | related | L2 | 20 |
| 中来股份 | 300393 | 钙钛矿 | 光伏设备与辅材供应商 | related | L1_L3_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-c628edcdb2db59119d1b artifact_sha=9aac0f4c2c6f98b29edcd8999ef5d2c658e9bc7c55b4e07b19a6128b51a7baca manifest_sha=91f2251a26a8289acb32ce8d10a6ab070801121811eb440b9bb7385114f2e824 -->
