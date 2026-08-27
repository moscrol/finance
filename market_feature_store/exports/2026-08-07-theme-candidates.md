# 2026-08-07 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：26642.51
- **上涨家数**：2856
- **涨停 / 跌停**：74 / 4
- **容量前三行业**：1.电子(29.4%, super_capacity)、2.通信(9.0%, normal)、3.有色金属(7.2%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 医药 | 医药 | 医药生物 | 267.37 | double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 元器件 | 电子元器件 | - | 218.04 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 3 | 通信 | 通信 | 国防军工 | 205.0 | double_red、limit_advance_cluster、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 4 | PCB | PCB | 电子 | 202.25 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |
| 5 | CXO概念 | CXO | - | 179.58 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 11 | 0 | missing_evidence |
| 6 | 复合铜箔 | 复合铜箔 | - | 174.45 | double_red、limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 医药医疗 | 医疗 | - | 173.21 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 8 | 创新药 | 创新药 | 医药生物 | 169.13 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 9 | 化学制药 | 化学制药 | 医药生物 | 166.18 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 10 | CPO概念 | CPO | - | 164.08 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 口罩防护 | 口罩防护 | - | 158.52 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 12 | 基因概念 | 基因概念 | - | 158.14 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 13 | 半导体 | 半导体 | 电子 | 147.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | AI算力 | AI算力 | 电子 | 131.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 5 | - |
| 15 | PCB概念 | PCB概念 | - | 125.95 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 16 | 光伏 | 光伏 | 电力设备 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 17 | 合成生物 | 合成生物 | 医药生物 | 122.45 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 18 | 3D打印 | 3D打印 | 机械设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 19 | AI医疗概念 | AI医疗 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 20 | MCU芯片 | MCU芯片 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 3 | 12 | 1 | - |
| 21 | 人脑工程 | 人脑工程 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 22 | 光通信 | 光通信 | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 5 | - |
| 23 | 建材 | 建材 | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 折叠屏 | 折叠屏 | - | 116.0 | double_red、new_high_cluster | 4 | 12 | 1 | - |
| 25 | 机械设备 | 机械设备 | - | 116.0 | double_red、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 26 | 量子科技 | 量子科技 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 27 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 28 | 飞行汽车 | 飞行汽车 | 汽车 | 116.0 | double_red、new_high_cluster | 1 | 5 | 1 | - |
| 29 | 汽车芯片 | 汽车芯片 | - | 112.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 30 | AI手机PC | AI手机 | - | 110.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | MiniLED | Mini LED | - | 110.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 32 | MicroLED | Micro LED | - | 106.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 33 | 医疗服务 | 医疗服务 | 医药生物 | 105.17 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 34 | 玻璃基板 | 玻璃基板 | - | 90.0 | double_red | 2 | 12 | 5 | - |
| 35 | 集成电路设计 | 集成电路 | - | 90.0 | double_red | 1 | 12 | 0 | missing_evidence |
| 36 | 锂电池概念 | 锂 | - | 82.32 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 37 | 小金属 | 小金属 | 有色金属 | 81.38 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 2 | - |
| 38 | 新能源车 | 新能源车 | - | 81.18 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 商业航天 | 商业航天 | 国防军工 | 80.01 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 40 | 工业金属 | 工业金属 | 有色金属 | 79.78 | new_high_direction、new_high_cluster、capacity_industry | 0 | 9 | 0 | missing_concept、missing_evidence |
| 41 | 电子 | EDA（电子设计自动化） | - | 79.72 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 42 | 一带一路 | 一带一路 | - | 77.73 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 43 | 卫星导航 | 卫星导航 | - | 77.25 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 44 | 东数西算 | 东数西算 | - | 77.04 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 45 | 国防军工 | 国防军工 | - | 76.78 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 46 | 有色 | 有色冶炼装备 | - | 76.51 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 47 | 液冷服务器 | 液冷服务器 | 电力设备 | 76.43 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 48 | 数据中心 | 数据中心 | 计算机 | 76.38 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 49 | 黄金概念 | 黄金 | - | 71.1 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 50 | 化工 | 化工 | - | 70.88 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |

## 五、核心候选明细

## 候选 1：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：267.37
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.1%，边际量 46.22%，成交额 1335.43 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股2只，最高4板，容量前三=False |
| double_red | 90.0 | 涨幅5.1%，边际量46.22%，成交1335.43亿 |
| new_high_direction | 44.77 | 新高股30只，新高成交381.78000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比21.62，排名5 |

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
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 泰恩康 | 301263 | 医药 | 两性健康/肠胃/眼科三大板块，核心品种爱廷玖、和胃整肠丸、沃丽汀 | core | L2 | 20 |
| 神奇制药 | 600613 | 医药 | 医药制造+医药商业双板块，医药制造收入11.23亿元毛利率71.72%，... | core | L2 | 20 |
| 丽珠集团 | 000513 | 医药 | 医药相关产品/材料供应商 | related | L2 | 20 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 20 |
| 仙琚制药 | 002332 | 医药 | 甾体类原料药相关产品供应商 | related | L2 | 20 |

## 候选 2：元器件

- **标准概念**：电子元器件
- **申万一级**：-
- **评分**：218.04
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 7.22%，边际量 19.81%，成交额 1687.39 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅7.22%，边际量19.81%，成交1687.39亿 |
| new_high_direction | 30.19 | 新高股7只，新高成交191.17亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅24.85% |
| multi_period_rank | 20.8 | daily排名第5，区间涨幅7.22% |
| multi_period_rank | 20.0 | day3排名第6，区间涨幅16.74% |
| limit_heat | 7.85 | 涨停11只，市场占比14.86，排名11 |

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

## 候选 3：通信

- **标准概念**：通信
- **申万一级**：国防军工
- **评分**：205.0
- **触发类型**：double_red、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 12.91%，成交额 2316.92 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量12.91%，成交2316.92亿 |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 4：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：202.25
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 8.71%，边际量 23.06%，成交额 1295.16 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅8.71%，边际量23.06%，成交1295.16亿 |
| multi_period_rank | 24.0 | daily排名第1，区间涨幅8.71% |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅27.58% |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅19.19% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.85 | 涨停11只，市场占比14.86，排名10 |

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

## 候选 5：CXO概念

- **标准概念**：CXO
- **申万一级**：-
- **评分**：179.58
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 8.22%，边际量 54.02%，成交额 602.62 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（11），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅8.22%，边际量54.02%，成交602.62亿 |
| new_high_direction | 43.68 | 新高股16只，新高成交294.23亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 12.4 | daily排名第3，区间涨幅8.22% |
| limit_heat | 7.5 | 涨停10只，市场占比13.51，排名13 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CXO | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 睿智医药 | 300149 | CXO | 医药研发服务及生产外包业务收入11.21亿元占98.80%同比+16.6... | core | L2 | 20 |
| 药石科技 | 300725 | CXO | 以分子砌块为核心能力底座的一体化CRDMO创新服务商，覆盖药物发现、临床... | core | L2 | 20 |
| 宣泰医药 | 688247 | CXO | 创新药CRO/CMO一体化服务 | related | L2 | 20 |
| 和元生物 | 688238 | CXO | 细胞和基因治疗CDMO、CRO、再生医学 | related | L1_L3_candidate | 20 |
| 星昊医药 | 920017 | CXO | 利用MAH制度对外提供CMC/CMO一体化服务，2025年该业务收入5,... | related | L2 | 20 |
| 苑东生物 | 688513 | CXO | 化学原料药国内外销售并为客户提供原料药CMO/CDMO服务 | related | L2 | 20 |
| 药明康德 | 603259 | CXO | 市场信号弱关联 | related | L2_candidate | 20 |
| 泰格医药 | 300347 | CXO | 图谱弱关联 | peripheral | graph_only | 20 |

## 候选 6：复合铜箔

- **标准概念**：复合铜箔
- **申万一级**：-
- **评分**：174.45
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 5.69%，边际量 36.87%，成交额 554.14 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.69%，边际量36.87%，成交554.14亿 |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 18.4 | day5排名第8，区间涨幅18.77% |
| multi_period_rank | 16.8 | daily排名第10，区间涨幅5.69% |
| multi_period_rank | 16.8 | day3排名第10，区间涨幅13.83% |
| limit_heat | 6.45 | 涨停7只，市场占比9.46，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 复合铜箔 | 20 |
| 铜 | 10 |
| 铜箔 | 10 |
| PET基复合铜箔 | 5 |
| PI基复合铜箔 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三孚新科 | 688359 | 复合铜箔 | 一步法湿法化学镀铜专用化学品及一体化表面处理设备供应商 | core | L1 | 20 |
| 东威科技 | 688700 | 复合铜箔 | 复合铜箔设备 | related | L1_L3_candidate | 20 |
| 东材科技 | 601208 | 复合铜箔 | 上游材料 | related | L1_L3_candidate | 20 |
| 双星新材 | 002585 | 复合铜箔 | 产业链供应商 | related | L2_candidate | 20 |
| 宝明科技 | 002992 | 复合铜箔 | 产业链供应商 | related | L2_candidate | 20 |
| 汇成真空 | 301392 | 复合铜箔 | 新能源镀膜设备（复合铜箔/光伏） | related | L1_L3_candidate | 20 |
| 英联股份 | 002846 | 复合铜箔 | 产业链供应商 | related | L2_candidate | 20 |
| 诺德股份 | 600110 | 复合铜箔 | 产业链供应商 | related | L1_L3_candidate | 20 |

## 候选 7：医药医疗

- **标准概念**：医疗
- **申万一级**：-
- **评分**：173.21
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.41%，边际量 42.98%，成交额 1837.16 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.41%，边际量42.98%，成交1837.16亿 |
| new_high_direction | 45.86 | 新高股66只，新高成交468.4899999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.35 | 涨停21只，市场占比28.38，排名1 |

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

## 候选 8：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：169.13
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.86%，边际量 46.08%，成交额 1396.3 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.86%，边际量46.08%，成交1396.3亿 |
| new_high_direction | 44.58 | 新高股24只，新高成交366.51亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比17.57，排名8 |

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
| 神州细胞 | 688520 | 创新药 | 生物药企业：重组八因子（血友病）、抗体药物、重组蛋白与创新疫苗管线 | core | L2 | 20 |
| 舒泰神 | 300204 | 创新药 | 创新生物制药企业，上市产品苏肽生（注射用鼠神经生长因子）与舒泰清；在研管... | core | L2 | 20 |
| 苑东生物 | 688513 | 创新药 | 聚焦麻醉镇痛、抗肿瘤、自身免疫领域，搭建六大核心技术平台，形成创新药、改... | core | L2 | 20 |

## 候选 9：化学制药

- **标准概念**：化学制药
- **申万一级**：医药生物
- **评分**：166.18
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.62%，边际量 53.01%，成交额 791.52 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.62%，边际量53.01%，成交791.52亿 |
| new_high_direction | 43.38 | 新高股16只，新高成交270.17000000000013亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比10.81，排名18 |

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
| 三力制药 | 603439 | 制药 | 中成药的研发、生产和销售、核心产品为开喉剑喷雾剂系列 | related | L2 | 20 |
| 仙琚制药 | 002332 | 制药 | 甾体原料药和制剂的研制、生产与销售 | related | L2 | 20 |
| 川宁生物 | 301301 | 制药 | 抗生素中间体（硫氰酸红霉素、6-APA、7-ACA）+ 合成生物学（麦角... | related | L1_L3_candidate | 20 |

## 候选 10：CPO概念

- **标准概念**：CPO
- **申万一级**：-
- **评分**：164.08
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.85%，边际量 10.91%，成交额 5628.43 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.85%，边际量10.91%，成交5628.43亿 |
| new_high_direction | 31.93 | 新高股8只，新高成交218.54亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| limit_heat | 8.55 | 涨停13只，市场占比17.57，排名7 |
| multi_period_rank | 7.6 | day5排名第9，区间涨幅18.16% |

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


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-bb90e215e28c17ca2486 artifact_sha=071de40638593202d6bcf18efd1127cc36a6cecae3021e90f3fa54913f8f18d2 manifest_sha=347c5a9b32ffcdac503c6d7a6b21b3b691dbf2395be2600959e18d01c17aa97f -->
