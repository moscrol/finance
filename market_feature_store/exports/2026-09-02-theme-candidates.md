# 2026-09-02 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：17908.79
- **上涨家数**：1541
- **涨停 / 跌停**：52 / 8
- **容量前三行业**：1.电子(21.4%, capacity)、2.机械设备(7.8%, normal)、3.通信(7.6%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 国防军工 | 国防军工 | 国防军工 | 175.11 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 2 | 军民融合 | 军民融合 | - | 171.15 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 7 | 1 | - |
| 3 | 地面兵装 | 地面兵装 | - | 142.0 | multi_period_rank、new_high_cluster | 1 | 5 | 1 | - |
| 4 | 军贸概念 | 军贸 | - | 134.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 5 | 大消费 | 消费 | 商贸零售 | 105.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 6 | AI长剧 | AI长剧 | 传媒 | 101.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | AIGC概念 | AIGC | - | 93.59 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 8 | 大金融 | 大金融 | 计算机 | 89.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 9 | 短剧游戏 | 游戏 | - | 86.0 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 10 | 高端装备 | 高端装备 | 机械设备 | 84.49 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 影视音像 | 影视 | - | 82.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 12 | 新能源车 | 新能源车 | - | 80.79 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 机械设备 | 机械设备 | 机械设备 | 79.81 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 14 | 一带一路 | 一带一路 | - | 79.64 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 15 | 通用设备 | 通用设备 | 机械设备 | 78.27 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 16 | 数字货币 | 数字货币 | 计算机 | 78.18 | multi_period_rank、new_high_direction、new_high_cluster | 1 | 4 | 1 | - |
| 17 | 电子 | EDA（电子设计自动化） | 电子 | 78.14 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 18 | 通信设备 | 通信设备 | 通信 | 78.01 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 19 | 银行 | 银行 | 银行 | 77.39 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 20 | 数据中心 | 数据中心 | 计算机 | 77.28 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | 无人机 | 无人机 | - | 77.09 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 22 | 风电 | 风电 | 电力设备 | 76.05 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 23 | 物联网 | 物联网 | - | 75.94 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 24 | 氢能源 | 氢能源 | 电力设备 | 75.9 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 25 | 液冷服务器 | 液冷服务器 | 电力设备 | 75.6 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 26 | 新零售 | 零售 | - | 75.46 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 27 | 商业航天 | 商业航天 | 国防军工 | 75.38 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 28 | 核电核能 | 核电 | - | 75.02 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 29 | 化工 | 化工 | 基础化工 | 74.98 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 30 | 锂电池概念 | 锂 | - | 74.86 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 无人驾驶 | 无人驾驶 | 汽车 | 74.1 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 32 | 充电桩 | 充电桩 | - | 74.0 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 33 | 中特估 | 中特估 | - | 70.31 | new_high_direction、new_high_cluster | 1 | 0 | 1 | missing_entity_exposures |
| 34 | 抖音概念 | 抖音概念 | - | 69.75 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 东数西算 | 东数西算 | - | 69.67 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 36 | 绿色电力 | 绿色电力 | - | 69.39 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 37 | 乡村振兴 | 乡村振兴 | - | 68.95 | new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 38 | 华为鸿蒙 | 华为鸿蒙 | 计算机 | 68.88 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 39 | 腾讯概念 | 腾讯概念 | - | 68.88 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 40 | 跨境电商 | 跨境电商 | - | 68.82 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 41 | 水利建设 | 水利 | - | 68.73 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | 工业互联 | 工业互联网 | - | 68.71 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 43 | 区块链 | 区块链 | - | 68.7 | new_high_direction、new_high_cluster | 1 | 9 | 1 | - |
| 44 | 车联网 | 车联网 | - | 68.63 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 45 | 阿里概念 | 阿里概念 | - | 68.63 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 信创 | 信创 | 计算机 | 68.56 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 互联金融 | 互联金融 | - | 68.47 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 天然气 | 天然气 | - | 68.37 | new_high_direction、new_high_cluster | 1 | 12 | 3 | - |
| 49 | IP经济 | IP经济 | 传媒 | 68.29 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 50 | 碳中和 | 碳中和 | - | 68.14 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |

## 五、核心候选明细

## 候选 1：国防军工

- **标准概念**：国防军工
- **申万一级**：国防军工
- **评分**：175.11
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.52%，边际量 27.1%，成交额 543.38 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.52%，边际量27.1%，成交543.38亿 |
| new_high_direction | 46.21 | 新高股77只，新高成交496.64999999999975亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比17.31，排名7 |
| limit_heat | 5.75 | 涨停5只，市场占比9.62，排名25 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 国防军工 | 20 |
| 军工 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三角防务 | 300775 | 军工 | 军用航空飞行器关键锻件供应商，具备军工产品资质 | core | L2 | 20 |
| 上大股份 | 301522 | 军工 | 向军用领域客户销售特种合金产品 | core | L2 | 20 |
| 中航光电 | 002179 | 军工 | 防务领域光、电、流体互连解决方案首选供应商 | core | L2 | 20 |
| 中航成飞 | 302132 | 军工 | 航空装备研制生产国家队（歼-10/歼-20等主战装备整机） | core | L2 | 20 |
| 中航机载 | 600372 | 军工 | 航空防务装备机载系统（航电、飞控、机电）核心配套商，歼-10CE/枭龙/... | core | L2 | 20 |
| 中航沈飞 | 600760 | 军工 | 我国航空防务装备主要研制基地、整机供应商（歼击机主机厂） | core | L2 | 20 |
| 中航西飞 | 000768 | 军工 | 我国主要的军用大中型运输机、轰炸机、特种飞机制造商（运-20、运-9系列... | core | L2 | 20 |
| 中航重机 | 600765 | 军工 | 航空锻铸龙头（飞机/发动机锻件核心供应商） | core | L2 | 20 |

## 候选 2：军民融合

- **标准概念**：军民融合
- **申万一级**：-
- **评分**：171.15
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.69%，边际量 17.84%，成交额 685.27 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.69%，边际量17.84%，成交685.27亿 |
| new_high_direction | 42.15 | 新高股40只，新高成交172.16000000000005亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 7.6 | daily排名第9，区间涨幅0.69% |
| limit_heat | 5.4 | 涨停4只，市场占比7.69，排名30 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 军民融合 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华如科技 | 301302 | 军民融合 | 在军事智能主业之外培育数字文创、线上游戏与线下数字空间等民用业务 | related | L2 | 20 |
| 北方长龙 | 301357 | 军民融合 | 军用车辆非金属复合材料配套装备、拟并购军用智能检测装备（顺义科技） | related | L1_L3_candidate | 20 |
| 泰豪科技 | 600590 | 军民融合 | 泰豪科技年报披露的军民融合相关主营业务 | related | L2 | 20 |
| 海伦哲 | 300201 | 军民融合 | 海伦哲年报披露的军民融合相关主营业务 | related | L2 | 20 |
| 科思科技 | 688788 | 军民融合 | 科思科技年报披露的军民融合相关主营业务 | related | L2 | 20 |
| 航发控制 | 000738 | 军民融合 | 航发控制年报披露的军民融合相关主营业务 | related | L2 | 20 |
| 雷科防务 | 002413 | 军民融合 | 雷达系统、卫星应用、安全存储 | related | L1_L3_candidate | 20 |

## 候选 3：地面兵装

- **标准概念**：地面兵装
- **申万一级**：-
- **评分**：142.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（5），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅7.2% |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅14.54% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅11.59% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅14.35% |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 地面兵装 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 内蒙一机 | 600967 | 地面兵装 | 我国唯一集主战坦克、轮式战车、中口径火炮为一体的高新武器装备研发制造集团... | core | L2 | 20 |
| 北方导航 | 600435 | 地面兵装 | 导航控制与弹药信息化 | related | L1_L3_candidate | 20 |
| 北方长龙 | 301357 | 地面兵装 | 轮式及履带装甲车辆人机环内饰与配套装备供应商 | related | L2 | 20 |
| 银河电子 | 002519 | 地面兵装 | 智能机电（军用电源、机电系统）、新能源（精密结构件 | related | L2 | 20 |
| 中兵红箭 | 000519 | 地面兵装 | 地面兵装环节企业 | peripheral | graph_only | 20 |

## 候选 4：军贸概念

- **标准概念**：军贸
- **申万一级**：-
- **评分**：134.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 28.2 | daily排名第2，区间涨幅2.49% |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅8.75% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅10.24% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | day3排名第5，区间涨幅5.98% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 军贸 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 内蒙一机 | 600967 | 军贸 | 国外收入体量可观且毛利率显著高于国内 | related | L2 | 20 |
| 中无人机 | 688297 | 军贸出口 | 我国军贸无人机出口主力型号供应商（翼龙系列出口十余个国家，覆盖一带一路） | core | L2 | 5 |
| 航发控制 | 000738 | AIDC发电设备 | 航空发动机控制系统、燃气轮机控制系统、国际合作转包 | related | L1_L3_candidate | 1 |
| 六九一二 | 301592 | 低空经济 | 高功率微波反无人机（九源高能）、军用存储控制芯片（四川惟芯）、军事训练装... | related | L1_L3_candidate | 1 |
| 中航机载 | 600372 | 军工 | 航空防务装备机载系统（航电、飞控、机电）核心配套商，歼-10CE/枭龙/... | core | L2 | 1 |
| 国睿科技 | 600562 | 军工 | 防务雷达装备供应商，军贸项目交付带动雷达板块收入增长 | core | L2 | 1 |
| 航天电子 | 600879 | 军工信息化 | 卫星互联网配套（相控阵天线、激光通信终端）、无人系统装备（军贸+国内） | related | L1_L3_candidate | 1 |
| 航天南湖 | 688552 | 军工电子 | 防空预警雷达整机制造、军贸出口、低空探测与反无系统 | related | L1_L3_candidate | 1 |

## 候选 5：大消费

- **标准概念**：消费
- **申万一级**：商贸零售
- **评分**：105.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股3只，最高4板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 张小泉 | 301055 | 消费 | 刀剪具/厨房五金/家居五金生活五金消费品制造与全渠道零售商 | core | L2 | 20 |
| 百润股份 | 002568 | 消费 | 百润股份年报披露的消费相关主营业务 | core | L2 | 20 |
| 盈趣科技 | 002925 | 消费 | 电子烟（创新消费电子）、健康环境产品、汽车电子、智能控制部件 | core | L1_L3_candidate | 20 |
| 酒鬼酒 | 000799 | 消费 | 深度联动胖东来联合开发「酒鬼酒・自由爱」新品成为核心增长引擎，启动光瓶湘... | related | L2 | 20 |
| 华夏航空 | 002928 | 消费 | 支线航空运营商，地方政府采购+中央支线补贴商业模式，覆盖下沉市场 | related | L1_L3_candidate | 20 |
| 哈尔斯 | 002615 | 消费 | 真空器皿相关产品供应商 | related | L2 | 20 |
| 宁波中百 | 600857 | 消费 | 宁波中百年报披露的消费相关主营业务 | related | L2 | 20 |
| 宝立食品 | 603170 | 消费 | 宝立食品年报披露的消费相关主营业务 | related | L2 | 20 |

## 候选 6：AI长剧

- **标准概念**：AI长剧
- **申万一级**：传媒
- **评分**：101.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 101.0 | 连板股3只，最高3板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：AIGC概念

- **标准概念**：AIGC
- **申万一级**：-
- **评分**：93.59
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.99 | 新高股37只，新高成交319.1099999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 11.8 | day3排名第10，区间涨幅3.93% |
| multi_period_rank | 11.8 | day5排名第10，区间涨幅5.48% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AIGC | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中文在线 | 300364 | AIGC | AI内容生产平台（逍遥大模型支持14种语言创作，自研全栈创作引擎Flar... | core | L2 | 20 |
| 峨眉山A | 000888 | AIGC | 峨眉山A年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 捷成股份 | 300182 | AIGC | 捷成股份年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 数码视讯 | 300079 | AIGC | AI+超高清视频、AIGC、AI Agent、数据安全 | core | L2 | 20 |
| 昆仑万维 | 300418 | AIGC | 昆仑万维年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 芒果超媒 | 300413 | AIGC | 芒果超媒年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 万事利 | 301066 | AIGC | 丝绸行业首个垂类图形AIGC大模型应用方 | related | L2 | 20 |
| 元隆雅图 | 002878 | AIGC | IP文创业务、特许商品业务、体育IP开发 | related | L1_L3_candidate | 20 |

## 候选 8：大金融

- **标准概念**：大金融
- **申万一级**：计算机
- **评分**：89.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

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

## 候选 9：短剧游戏

- **标准概念**：游戏
- **申万一级**：-
- **评分**：86.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 21.6 | day3排名第4，区间涨幅6.0% |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅6.59% |
| multi_period_rank | 17.6 | day10排名第9，区间涨幅8.56% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 游戏 | 10 |
| 短剧 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 世纪华通 | 002602 | 游戏 | 游戏出海龙头：点点互动《Whiteout Survival》《Kings... | core | L2 | 20 |
| 冰川网络 | 300533 | 游戏 | 网络游戏充值收、移动游戏充值收相关产品/服务商 | core | L2 | 20 |
| 凯撒文化 | 002425 | 游戏 | 移动端网络游戏研发与运营商（子公司酷牛互动、天上友嘉），以联合运营模式为... | core | L2 | 20 |
| 华立科技 | 301011 | 游戏 | 商用游戏游艺设备设计、研发、生产、销售及运营商 | core | L2 | 20 |
| 吉比特 | 603444 | 游戏 | 游戏收入相关产品/服务商 | core | L2 | 20 |
| 名臣健康 | 002919 | 游戏 | 游戏研发+发行商（海南星炫/星际奥游/杭州雷焰，SLG/MMORPG/二... | core | L2 | 20 |
| 姚记科技 | 002605 | 游戏 | 休闲益智类精品手游研运一体（捕鱼系列等） | core | L2 | 20 |
| 完美世界 | 002624 | 游戏 | 自研引擎端手游全平台研发发行（诛仙/幻塔/异环等） | core | L2 | 20 |

## 候选 10：高端装备

- **标准概念**：高端装备
- **申万一级**：机械设备
- **评分**：84.49
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.74 | 新高股53只，新高成交219.39000000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比9.62，排名22 |

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


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-c78e66b1951eb94cb0ed artifact_sha=3e1ce0436b3c112fb392eca39c65d3ad4eb40d5f73fcafde8e1134ba6c34ae79 manifest_sha=27bebbca60cc79dc157fa48aab22e6412c0884a26826f1dca7871b9fd46ccf28 -->
