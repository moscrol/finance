# 2026-09-09 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：18543.31
- **上涨家数**：1793
- **涨停 / 跌停**：48 / 8
- **容量前三行业**：1.电子(22.6%, capacity)、2.通信(8.9%, normal)、3.机械设备(7.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 农林牧渔 | 农林牧渔 | 农林牧渔 | 221.5 | double_red、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 2 | PCB | PCB | 电子 | 185.48 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 3 | 光纤光缆 | 光纤光缆 | 通信 | 183.6 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 3 | 12 | 5 | - |
| 4 | 国防军工 | 国防军工 | 国防军工 | 176.51 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 5 | 一带一路 | 一带一路 | 农林牧渔 | 171.33 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 6 | 风电 | 风电 | 电力设备 | 169.76 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 7 | 智能电网 | 智能电网 | - | 165.51 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 8 | 核电核能 | 核电 | - | 165.51 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 9 | 军民融合 | 军民融合 | - | 160.96 | double_red、new_high_direction、new_high_cluster | 1 | 7 | 1 | - |
| 10 | 大飞机 | 大飞机 | 国防军工 | 159.11 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 绿色电力 | 绿色电力 | - | 158.89 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 12 | 有色 | 有色冶炼装备 | 有色金属 | 158.8 | double_red、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 13 | 石墨烯 | 石墨烯 | - | 157.93 | double_red、new_high_direction、new_high_cluster | 2 | 10 | 2 | - |
| 14 | 6G概念 | 6G | - | 157.24 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 15 | 特高压 | 特高压 | 电力设备 | 157.09 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 16 | 铜缆高速连接 | 铜 | 电力设备 | 154.04 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 17 | 芯片 | 芯片 | 电子 | 139.45 | limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 18 | 可控核聚变 | 可控核聚变 | 电力设备 | 116.0 | double_red、new_high_cluster | 3 | 12 | 1 | - |
| 19 | 工业金属 | 工业金属 | 有色金属 | 116.0 | double_red、new_high_cluster | 1 | 12 | 3 | - |
| 20 | 氢能源 | 氢能源 | 电力设备 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 21 | 黄金概念 | 黄金 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 22 | 钙钛矿电池 | 钙钛矿 | 电力设备 | 110.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 23 | 新零售 | 零售 | 商贸零售 | 105.6 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 24 | 乡村振兴 | 乡村振兴 | 基础化工 | 104.64 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 25 | 水产品 | 水产 | - | 91.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 26 | 元器件 | 电子元器件 | 电子 | 90.85 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 27 | 培育钻石 | 培育钻石 | - | 88.4 | multi_period_rank、new_high_cluster | 1 | 9 | 1 | - |
| 28 | 高端装备 | 高端装备 | 机械设备 | 87.29 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |
| 29 | 粮食概念 | 粮食概念 | 农林牧渔 | 86.78 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 30 | 电子 | EDA（电子设计自动化） | 电子 | 85.53 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 新能源车 | 新能源车 | - | 83.95 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 人形机器人 | 人形机器人 | 机械设备 | 82.18 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 33 | 养殖业 | 养殖 | - | 82.0 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 34 | 激光设备 | 激光设备 | - | 81.6 | multi_period_rank、new_high_cluster | 2 | 12 | 1 | - |
| 35 | 商业航天 | 商业航天 | 国防军工 | 81.57 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 36 | 锂电池概念 | 锂 | - | 80.65 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 37 | 通信设备 | 通信设备 | 通信 | 80.08 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 38 | 通信 | 通信 | 通信 | 79.98 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 39 | 机械设备 | 机械设备 | 机械设备 | 79.77 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 40 | 先进封装 | 先进封装 | 电子 | 79.74 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 41 | 存储芯片 | 存储芯片 | 电子 | 79.34 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 42 | 无人机 | 无人机 | - | 78.94 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 43 | 数据中心 | 数据中心 | 计算机 | 77.48 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 化工 | 化工 | 基础化工 | 75.81 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 45 | CPO概念 | CPO | - | 75.79 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 46 | 光通信 | 光通信 | - | 75.48 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 47 | 充电桩 | 充电桩 | - | 75.36 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 48 | PCB概念 | PCB概念 | - | 74.97 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 49 | 东数西算 | 东数西算 | - | 72.75 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 50 | 工业互联 | 工业互联网 | - | 71.3 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：农林牧渔

- **标准概念**：农林牧渔
- **申万一级**：农林牧渔
- **评分**：221.5
- **触发类型**：double_red、limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.2074%，边际量 24.7253%，成交额 514.7434 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.2074%，边际量24.7253%，成交514.7434亿 |
| new_high_direction | 44.8 | 新高股54只，新高成交383.86680000000007亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.0 | day3排名第6，区间涨幅7.36% |
| multi_period_rank | 12.6 | day10排名第9，区间涨幅9.87% |
| limit_heat | 6.1 | 涨停6只，市场占比12.5，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 农林牧渔 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中宠股份 | 002891 | 农林牧渔 | 宠物食品及用品（自主品牌WANPY顽皮、TOPTREES领先、ZEAL真... | related | L1_L3_candidate | 20 |
| 中牧股份 | 600195 | 农林牧渔 | 兽用生物制品（口蹄疫疫苗、禽流感疫苗等）、化药原料药及制剂、饲料及饲料添... | related | L1_L3_candidate | 20 |
| 乖宝宠物 | 301498 | 农林牧渔 | 自有品牌宠物食品（麦富迪、弗列加特、霸弗等） | related | L1_L3_candidate | 20 |
| 众兴菌业 | 002772 | 农林牧渔 | 金针菇、双孢菇、人工培育冬虫夏草 | related | L1_L3_candidate | 20 |
| 回盛生物 | 300871 | 农林牧渔 | 兽用原料药及制剂（泰乐菌素、泰万菌素等大环内酯类原料药） | related | L1_L3_candidate | 20 |
| 圣农发展 | 002299 | 农林牧渔 | 白羽肉鸡养殖与屠宰（鸡肉生食）、食品深加工（熟食/调理品/预制菜）、种鸡... | related | L1_L3_candidate | 20 |
| 天康生物 | 002100 | 农林牧渔 | 生猪养殖、饲料、动物疫苗 | related | L1_L3_candidate | 20 |
| 温氏股份 | 300498 | 农林牧渔 | 生猪养殖、肉鸡（黄羽鸡）养殖、配套业务（动保 | related | L1_L3_candidate | 20 |

## 候选 2：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：185.48
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 55.48 | 新高股24只，新高成交438.5995亿，容量前三=True |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅7.14% |
| multi_period_rank | 27.4 | day3排名第3，区间涨幅7.5% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.2 | daily排名第7，区间涨幅2.64% |
| multi_period_rank | 24.2 | day10排名第7，区间涨幅11.23% |

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

## 候选 3：光纤光缆

- **标准概念**：光纤光缆
- **申万一级**：通信
- **评分**：183.6
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 5.9645%，边际量 74.4221%，成交额 504.0332 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.9645%，边际量74.4221%，成交504.0332亿 |
| multi_period_rank | 24.0 | daily排名第1，区间涨幅5.96% |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅5.67% |
| multi_period_rank | 16.8 | day3排名第10，区间涨幅6.82% |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光纤光缆 | 20 |
| 光纤 | 12 |
| 光缆 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 远东股份 | 600869 | 光纤 | 光纤光棒+微通道液冷板供应商 | core | L1_L3_candidate | 20 |
| 大族激光 | 002008 | 光纤 | 激光加工设备龙头，子公司投建年产6000万芯公里光纤及预制棒产能 | related | L3 | 20 |
| 天孚通信 | 300394 | 光纤 | 提供光纤适配器、陶瓷套管等光纤连接无源器件 | related | L2 | 20 |
| 海看股份 | 301262 | 光纤 | 海看股份年报披露的光纤相关主营业务 | related | L2 | 20 |
| 长芯博创 | 300548 | 光纤 | 受益标的 | related | L2 | 20 |
| 长飞光纤 | 601869 | 光纤 | 光纤光缆及新型光纤产品供应商 | related | L1_L3_candidate | 20 |
| 永鼎股份 | 600105 | 光纤 | 卖方晚报点名标的（待细化） | peripheral | L1 | 20 |
| 华脉科技 | 603042 | 光纤光缆 | 光缆类产品制造商，光缆产销量随运营商建设需求扩张 | core | L2 | 20 |

## 候选 4：国防军工

- **标准概念**：国防军工
- **申万一级**：国防军工
- **评分**：176.51
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.1789%，边际量 10.1476%，成交额 2373.01 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.1789%，边际量10.1476%，成交2373.01亿 |
| new_high_direction | 54.76 | 新高股90只，新高成交1180.5969亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比10.42，排名12 |

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

## 候选 5：一带一路

- **标准概念**：一带一路
- **申万一级**：农林牧渔
- **评分**：171.33
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_direction | 49.18 | 新高股128只，新高成交734.1090000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比18.75，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 一带一路 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 上海港湾 | 605598 | 一带一路 | 深耕东南亚/中东等一带一路沿线市场的岩土工程与新能源基建承包商 | core | L2 | 20 |
| 中色股份 | 000758 | 一带一路 | 有色金属国际工程承包先行者 | core | L2 | 20 |
| 宁波港 | 601018 | 一带一路 | 宁波港年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 安泰科技 | 000969 | 一带一路 | 安泰科技年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 敦煌种业 | 600354 | 一带一路 | 敦煌种业年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 重庆港 | 600279 | 一带一路 | 重庆港年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 青岛港 | 601298 | 一带一路 | 青岛港年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 中国能建 | 601868 | 一带一路 | "一带一路"能源基建出海主力（境外收入高增长） | related | L2 | 20 |

## 候选 6：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：169.76
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.5679%，边际量 23.0465%，成交额 2004.2219 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.5679%，边际量23.0465%，成交2004.2219亿 |
| new_high_direction | 46.96 | 新高股59只，新高成交556.8691999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比16.67，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电 | 20 |
| 海上风电 | 5 |
| 深远海风电 | 5 |
| 漂浮式风电 | 5 |
| 陆上风电 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三峡能源 | 600905 | 海上风电 | 三峡集团新能源平台：海上风电引领战略，协同推进沙戈荒风电光伏基地 | core | L2 | 20 |
| 振华重工 | 600320 | 海上风电 | 港口机械、海工装备、钢结构 | core | L1_L3_candidate | 20 |
| 新天绿能 | 600956 | 海上风电 | 风力发电、天然气全产业链、海上风电、燃气热电联产 | core | L1_L3_candidate | 20 |
| 东方电气 | 600875 | 海上风电 | 中游制造 | core | L1_L3_candidate | 20 |
| 东方电缆 | 603606 | 海上风电 | 5.2.3 海缆系统企业 | core | L1_L3_candidate | 20 |
| 太阳电缆 | 002300 | 海上风电 | 海底电缆、高压电力电缆、特种电缆 | core | L2 | 20 |
| 明阳智能 | 601615 | 海上风电 | 中游制造 | core | L1_L3_candidate | 20 |
| 江苏国信 | 002608 | 海上风电 | 火力发电、热力生产、信托金融、海上风电（参股） | core | L1_L3_candidate | 20 |

## 候选 7：智能电网

- **标准概念**：智能电网
- **申万一级**：-
- **评分**：165.51
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.0609%，边际量 15.7467%，成交额 1202.1755 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.0609%，边际量15.7467%，成交1202.1755亿 |
| new_high_direction | 43.76 | 新高股24只，新高成交300.71049999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比10.42，排名13 |

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
| 东软载波 | 300183 | 智能电网 | 电力线载波通信相关产品/服务商 | core | L2 | 20 |
| 中电鑫龙 | 002298 | 智能电网 | 智能输配电设备与元器件制造商（列入全国电网建设与改造推荐名录） | core | L2 | 20 |
| 中能电气 | 300062 | 智能电网 | 输配电开关控制设备制造商（电网智能化产品占收入86.34%） | core | L2 | 20 |
| 亨通光电 | 600487 | 智能电网 | 特高压及电网智能化输电装备与电力电缆制造商 | core | L2 | 20 |
| 力合微 | 688589 | 智能电网 | 智能电网、非智能电网相关产品/服务商 | core | L2 | 20 |

## 候选 8：核电核能

- **标准概念**：核电
- **申万一级**：-
- **评分**：165.51
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.3276%，边际量 14.0791%，成交额 1309.1986 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.3276%，边际量14.0791%，成交1309.1986亿 |
| new_high_direction | 43.76 | 新高股45只，新高成交300.7085000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比10.42，排名15 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 核电 | 10 |
| 核能 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 瑞奇智造 | 920781 | 核电 | 核能装备和试验装置（华龙一号安全系统试验装置、控制棒换料专用套筒等）及核... | core | L2 | 20 |
| 电投产融 | 000958 | 核电 | 核能发电、热电联产、新能源（风电、光伏） | core | L1_L3_candidate | 20 |
| 中国核电 | 601985 | 核电 | 中核集团旗下核电运营平台 | core | L2 | 20 |
| 中国一重 | 601106 | 核电 | 核岛一回路核电设备全覆盖制造，承担国家绝大多数核电锻件和核反应堆压力容器... | core | L2 | 20 |
| 中国广核 | 003816 | 核电 | 中广核集团核能发电唯一平台，国内核电运营双寡头之一（华龙一号自主三代技术... | core | L2 | 20 |
| 中国核建 | 601611 | 核电 | 核电工程建设国家队，全球唯一41年不间断从事核电建造的企业 | core | L2 | 20 |
| 中核科技 | 000777 | 核电 | 核电及核化工关键阀门龙头（中核集团旗下阀门平台） | core | L2 | 20 |
| 景业智能 | 688290 | 核电 | 核工业特种机器人及智能装备、军工智能装备、AI+具身智能 | core | L1_L3_candidate | 20 |

## 候选 9：军民融合

- **标准概念**：军民融合
- **申万一级**：-
- **评分**：160.96
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.2186%，边际量 14.5934%，成交额 738.41 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.2186%，边际量14.5934%，成交738.41亿 |
| new_high_direction | 44.96 | 新高股41只，新高成交396.55899999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 10：大飞机

- **标准概念**：大飞机
- **申万一级**：国防军工
- **评分**：159.11
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.6364%，边际量 33.5834%，成交额 635.6347 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.6364%，边际量33.5834%，成交635.6347亿 |
| new_high_direction | 43.11 | 新高股37只，新高成交248.62639999999996亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 大飞机 | 20 |
| C919大飞机 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中航机载 | 600372 | C919大飞机 | 军机机载系统、C919机载配套、非航空防务、民机国产化 | core | L1_L3_candidate | 20 |
| 金海高科 | 603311 | C919大飞机 | 空气过滤器、航空空滤、新能源汽车空滤 | core | L2 | 20 |
| 中航成飞 | 302132 | 大飞机 | 民机大部件重要制造商（C919/AG600机头） | core | L2 | 20 |
| 中航重机 | 600765 | 大飞机 | C919/C929锻铸件配套供应商（商用航空收入+13%） | core | L2 | 20 |
| 爱乐达 | 300696 | 大飞机 | 国产大飞机及国际转包零部件供应商（C919/C929部组件装配，空客/波... | related | L2 | 20 |
| 中复神鹰 | 688295 | 大飞机 | 上游材料 | related | L2_candidate | 20 |
| 中直股份 | 600038 | 大飞机 | 军用直升机整机、民用直升机（AC系列）、eVTOL | related | L1_L3_candidate | 20 |
| 中航西飞 | 000768 | 大飞机 | 产业链供应商 | related | L2_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-b1d5cf5393907878b9fc artifact_sha=48d142f2927614843609cec7af00089408b09b07945592eaef2f1eb0b0cfa523 manifest_sha=b48ffd3cd72489b6be5e1ef66fdec3fe7f245c968aa4865d9f903a04d024806e -->
