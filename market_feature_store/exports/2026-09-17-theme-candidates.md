# 2026-09-17 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：18227.57
- **上涨家数**：2576
- **涨停 / 跌停**：47 / 1
- **容量前三行业**：1.电子(28.3%, super_capacity)、2.通信(10.1%, normal)、3.机械设备(7.6%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 新能源车 | 新能源车 | 电子 | 204.18 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 2 | 光纤光缆 | 光纤光缆 | 通信 | 197.48 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 3 | 新零售 | 零售 | 传媒 | 146.45 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 4 | 建材 | 建材 | 建筑材料 | 144.36 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 光学光电 | 光学 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 6 | 通用设备 | 通用设备 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 7 | 汽车 | 新能源汽车 | 汽车 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 8 | 医药医疗 | 医疗 | 医药生物 | 121.05 | double_red、limit_heat、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 9 | 创新药 | 创新药 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 5 | - |
| 10 | 医药 | 医药 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 智能医疗 | 医疗 | - | 112.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 12 | 风电 | 风电 | 电力设备 | 107.22 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 13 | 一带一路 | 一带一路 | 建筑装饰 | 106.83 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 14 | 跨境电商 | 跨境电商 | 电力设备 | 101.39 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 15 | PCB概念 | PCB概念 | - | 90.83 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 16 | 电子 | EDA（电子设计自动化） | 电子 | 89.67 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 17 | CPO概念 | CPO | - | 88.57 | limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 18 | 人形机器人 | 人形机器人 | 机械设备 | 85.17 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 19 | 半导体材料 | 半导体材料 | - | 83.6 | multi_period_rank、new_high_cluster | 3 | 12 | 5 | - |
| 20 | 通信设备 | 通信设备 | 通信 | 80.5 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 21 | 风电零部件 | 风电零部件 | - | 79.6 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 22 | OLED概念 | LED | 电子 | 79.37 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 23 | 先进封装 | 先进封装 | 电子 | 79.19 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 24 | 存储芯片 | 存储芯片 | 电子 | 78.99 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 25 | 机械设备 | 机械设备 | 机械设备 | 78.71 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 26 | 数据中心 | 数据中心 | 计算机 | 78.01 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 通信 | 通信 | 通信 | 77.49 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 28 | 锂电池概念 | 锂 | - | 76.4 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 29 | 东数西算 | 东数西算 | - | 75.24 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 30 | 商业航天 | 商业航天 | 国防军工 | 75.02 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 绿色电力 | 绿色电力 | - | 74.74 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 32 | 光通信 | 光通信 | - | 74.61 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 33 | 化工 | 化工 | 基础化工 | 74.38 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 34 | 国防军工 | 国防军工 | 国防军工 | 72.6 | new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 35 | 核电核能 | 核电 | - | 71.36 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 36 | 液冷服务器 | 液冷服务器 | 电力设备 | 71.06 | new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 37 | 阿里概念 | 阿里概念 | - | 71.03 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 工业互联 | 工业互联网 | - | 70.95 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 39 | 无人机 | 无人机 | - | 70.0 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 40 | 抖音概念 | 抖音概念 | - | 69.86 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 氢能源 | 氢能源 | 电力设备 | 69.58 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 42 | 物联网 | 物联网 | - | 69.55 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 43 | 数据要素 | 数据要素 | 计算机 | 69.39 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 44 | 化工原料 | 化工 | 基础化工 | 69.18 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 45 | 小米概念 | 小米概念 | - | 69.12 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 粤港澳 | 粤港澳 | - | 69.05 | new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 47 | 百度概念 | 百度概念 | - | 68.77 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 卫星导航 | 卫星导航 | - | 68.75 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 49 | 云计算 | 云计算 | 计算机 | 68.28 | new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 50 | 信息安全 | 信息安全 | 计算机 | 67.39 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：新能源车

- **标准概念**：新能源车
- **申万一级**：电子
- **评分**：204.18
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 119.0 | 连板股2只，最高5板，容量前三=True |
| new_high_direction | 50.63 | 新高股74只，新高成交850.2177999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比27.66，排名1 |

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

## 候选 2：光纤光缆

- **标准概念**：光纤光缆
- **申万一级**：通信
- **评分**：197.48
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.5318%，边际量 27.7275%，成交额 572.8206 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.5318%，边际量27.7275%，成交572.8206亿 |
| new_high_direction | 39.08 | 新高股5只，新高成交326.6859亿，容量前三=True |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| multi_period_rank | 19.0 | day5排名第1，区间涨幅9.26% |
| multi_period_rank | 17.4 | day10排名第3，区间涨幅12.96% |
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

## 候选 3：新零售

- **标准概念**：零售
- **申万一级**：传媒
- **评分**：146.45
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 0.8284%，边际量 20.2823%，成交额 684.7324 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.8284%，边际量20.2823%，成交684.7324亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 6.45 | 涨停7只，市场占比14.89，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 零售 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国中免 | 601888 | 零售 | 免税+有税全渠道旅游零售运营商（线下门店+自营电商及第三方平台） | core | L2 | 20 |
| 博士眼镜 | 300622 | 零售 | 眼镜零售连锁运营商，直营+加盟+联营覆盖全国，截至2025年末门店589... | core | L2 | 20 |
| 天虹股份 | 002419 | 零售 | 全渠道多业态零售商（百货/购物中心/超市） | core | L2 | 20 |
| 居然智家 | 000785 | 零售 | 全国连锁家居卖场龙头运营商（居然之家），372家卖场覆盖国内30省区市及... | core | L2 | 20 |
| 明牌珠宝 | 002574 | 零售 | 珠宝首饰全渠道连锁零售商（直营/专营/经销/加盟+电商直播） | core | L2 | 20 |
| 曼卡龙 | 300945 | 零售 | 珠宝首饰零售连锁企业（直营+专柜+加盟+电商全渠道，电商收入占比过半） | core | L2 | 20 |
| 来伊份 | 603777 | 零售 | 休闲食品连锁零售商（直营+加盟+特通+电商全渠道） | core | L2 | 20 |
| 深粮控股 | 000019 | 零售 | 粮油产品批发贸易商+"互联网+粮食"零售/团餐供应运营商 | core | L2 | 20 |

## 候选 4：建材

- **标准概念**：建材
- **申万一级**：建筑材料
- **评分**：144.36
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.2644%，边际量 28.7864%，成交额 512.5138 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.2644%，边际量28.7864%，成交512.5138亿 |
| new_high_direction | 30.36 | 新高股6只，新高成交316.53360000000004亿，容量前三=False |
| new_high_cluster | 24.0 | 题材内新高股6只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 建材 | 20 |
| 中国建材 | 5 |
| 地产链建材 | 5 |
| 家居建材 | 5 |
| 绿色建材 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 鲁北化工 | 600727 | 中国建材 | 鲁北化工年报披露的中国建材相关主营业务 | core | L2 | 20 |
| 联瑞新材 | 688300 | 中国建材 | 联瑞新材年报披露的中国建材相关主营业务 | related | L2 | 20 |
| 汇成真空 | 301392 | 中国建材 | 汇成真空年报披露的中国建材相关主营业务 | related | L2 | 20 |
| 马可波罗 | 001386 | 地产链建材 | 建筑陶瓷行业与房地产市场关系密切，客户为建材经销服务商、房地产开发商、工... | core | L2 | 20 |
| 南玻A | 000012 | 地产链建材 | 浮法玻璃与工程玻璃（建筑节能玻璃）为传统主业，受地产竣工周期影响 | related | L2 | 20 |
| 联翔股份 | 603272 | 家居建材 | 墙布窗帘品牌商，旗下“领绣（LEADSHOW）”“领绣墙布\|菁华”品牌，... | core | L2 | 20 |
| 齐峰新材 | 002521 | 家居建材 | 装饰原纸下游为人造板饰面/地板/家具板材，受家居装修与地产链需求影响 | related | L2 | 20 |
| 华新水泥 | 600801 | 建材 | 水泥、混凝土、骨料及新型建材全产业链一体化建材集团 | core | L2 | 20 |

## 候选 5：光学光电

- **标准概念**：光学
- **申万一级**：电子
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.7187%，边际量 28.2251%，成交额 525.7964 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.7187%，边际量28.2251%，成交525.7964亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光学 | 12 |
| 光电 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中光学 | 002189 | 光学 | 光学相关产品/服务商 | related | L2 | 20 |
| 中润光学 | 688307 | 光学 | 光学相关产品/服务商 | related | L2 | 20 |
| 欧菲光 | 002456 | 光学 | 光学相关产品/材料供应商 | related | L2 | 20 |
| 海泰新光 | 688677 | 光学 | 光学相关产品/服务商 | related | L2 | 20 |
| 新光光电 | 688011 | 光电 | 光学目标与场景仿真系统为第一大产品，2025年收入8,465.24万元（... | core | L2 | 20 |
| 内蒙一机 | 600967 | 光电 | - | related | L1 | 20 |
| 长城军工 | 601606 | 光电 | - | related | L1 | 20 |
| 德科立 | 688205 | OCS光电路交换机 | DCI数据中心互联、相干、非相干光模块、OCS光电路交换机 | core | L1_L3_candidate | 5 |

## 候选 6：通用设备

- **标准概念**：通用设备
- **申万一级**：机械设备
- **评分**：126.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 0.2742%，边际量 11.8406%，成交额 566.0181 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.2742%，边际量11.8406%，成交566.0181亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光格科技 | 688450 | AIoT | 分布式光纤传感、AIoT资产运维、四足巡检机器人 | core | L2 | 1 |
| 东方中科 | 002819 | AI安全 | 测试技术与服务（占比~81%）、数字安全与数智应用（占比~19%） | related | L2 | 1 |
| 必创科技 | 300667 | CPO | 精密光机（六轴并联平台/耦合台）、光电仪器（光谱仪/光源/检测系统）、智... | related | L1_L3_candidate | 1 |
| 南方泵业 | 300145 | 专用设备 | 通用设备制造业-水泵相关产品/服务商 | core | L2 | 1 |
| 云涌科技 | 688060 | 信创 | 国产化平台通用设备（信创业务） | related | L2 | 1 |
| 亚威股份 | 002559 | 工业母机 | 通用设备制造业金属成形机床整机制造商，覆盖钣金机床与冲压机床两大门类 | core | L2 | 1 |
| 创世纪 | 300083 | 工业母机 | 金属切削机床制造商，所属行业为通用设备制造业金属切削机床制造 | core | L2 | 1 |
| 中核科技 | 000777 | 工业阀门 | 核工程阀门、核聚变阀门、石油石化阀门 | related | L1_L3_candidate | 1 |

## 候选 7：汽车

- **标准概念**：新能源汽车
- **申万一级**：汽车
- **评分**：123.5
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 1.3971%，边际量 20.6617%，成交额 560.1152 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.3971%，边际量20.6617%，成交560.1152亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比21.28，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新能源汽车 | 5 |
| 新能源汽车产业链 | 5 |
| 新能源汽车热管理 | 5 |
| 新能源汽车电驱 | 5 |
| 新能源汽车轻量化 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中熔电气 | 301031 | 新能源汽车 | 电力熔断器/激励熔断器龙头（宁德时代、比亚迪等供应链） | core | L2 | 20 |
| 信质集团 | 002704 | 新能源汽车 | 新能源汽车驱动电机定转子及总成供应商，驱动电机业务为增长引擎 | core | L2 | 20 |
| 先惠技术 | 688155 | 新能源汽车 | 新能源汽车智能装备标杆供应商，海外订单已成增长引擎 | core | L2 | 20 |
| 光洋股份 | 002708 | 新能源汽车 | 新能源车线控底盘/电驱动/电机减速机精密轴承与同步器供应商 | core | L2 | 20 |
| 凌云股份 | 600480 | 新能源汽车 | 新能源汽车电池壳体/电池系统配套产品供应商，聚焦电池壳体轻量化 | core | L2 | 20 |
| 千里科技 | 601777 | 新能源汽车 | 燃油与新能源并举的乘用车制造商，覆盖SUV、MPV、精品电动小车及换电营... | core | L2 | 20 |
| 华域汽车 | 600741 | 新能源汽车 | 新能源车型零部件配套商，新获取订单中新能源相关车型配套金额占比达80% | core | L2 | 20 |
| 华锋股份 | 002806 | 新能源汽车 | 新能源商用车电控及驱动系统核心零部件供应商 | core | L2 | 20 |

## 候选 8：医药医疗

- **标准概念**：医疗
- **申万一级**：医药生物
- **评分**：121.05
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.9121%，边际量 13.1623%，成交额 880.8013 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.9121%，边际量13.1623%，成交880.8013亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比6.38，排名29 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗 | 10 |
| 医药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 创新医疗 | 002173 | 医疗 | 医疗服务提供商，营收和利润主要来源于医疗服务 | core | L2 | 20 |
| 嘉事堂 | 002462 | 医疗 | 嘉事堂年报披露的医疗相关主营业务 | core | L2 | 20 |
| 常铝股份 | 002160 | 医疗 | 常铝股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 昊海生科 | 688366 | 医疗 | 昊海生科年报披露的医疗相关主营业务 | related | L2 | 20 |
| 朗姿股份 | 002612 | 医疗 | 朗姿股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 欧林生物 | 688319 | 医疗 | 欧林生物年报披露的医疗相关主营业务 | related | L2 | 20 |
| 航亚科技 | 688510 | 医疗 | 航亚科技年报披露的医疗相关主营业务 | related | L2 | 20 |
| 丽珠集团 | 000513 | 医药 | 大型综合性医药集团，中国医药工业百强榜第27位 | core | L2 | 20 |

## 候选 9：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 0.9011%，边际量 11.3173%，成交额 621.327 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.9011%，边际量11.3173%，成交621.327亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 20 |
| 创新药RWA | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一品红 | 300723 | 创新药 | 核心创新药AR882为高效选择性URAT1抑制剂，覆盖降尿酸治疗痛风、溶... | core | L2 | 20 |
| 三生国健 | 688336 | 创新药 | 医药制造业、医药制造相关产品/服务商 | core | L2 | 20 |
| 上海谊众 | 688091 | 创新药 | 抗肿瘤创新药企业：紫杉醇胶束等纳米制剂，研产销一体化 | core | L2 | 20 |
| 亿帆医药 | 002019 | 创新药 | 医药+维生素B5双主业，创新生物药亿立舒全球销售 | core | L2 | 20 |
| 众生药业 | 002317 | 创新药 | 抗流感一类创新药昂拉地韦片（全球首个靶向PB2亚基口服抗流感药） | core | L2 | 20 |
| 凯因科技 | 688687 | 创新药 | 化学药品、生物药品相关产品/服务商 | core | L2 | 20 |
| 华东医药 | 000963 | 创新药 | 内分泌、自身免疫和肿瘤三大核心治疗领域创新药研发与商业化公司 | core | L2 | 20 |
| 南新制药 | 688189 | 创新药 | 抗流感创新药领军企业：帕拉米韦氯化钠注射液为国内首个上市的抗流感1.1类... | core | L2 | 20 |

## 候选 10：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 1.121%，边际量 14.6567%，成交额 643.3476 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.121%，边际量14.6567%，成交643.3476亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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
| 丽珠集团 | 000513 | 医药 | 大型综合性医药集团，中国医药工业百强榜第27位 | core | L2 | 20 |
| 华润江中 | 600750 | 医药 | 非处方药、处方药与健康消费品并举的医药制造企业 | core | L2 | 20 |
| 复星医药 | 600196 | 医药 | 以创新药为发展重点的综合医药健康集团，业务覆盖制药、医疗器械与医学诊断、... | core | L2 | 20 |
| 寿仙谷 | 603896 | 医药 | 灵芝、铁皮石斛等名贵中药材育种-栽培-饮片炮制-深加工全产业链中药企业 | core | L2 | 20 |
| 小方制药 | 603207 | 医药 | 外用药专业制药企业（消化类/皮肤类/五官类） | core | L2 | 20 |
| 康芝药业 | 300086 | 医药 | 国内领先的儿童药生产销售企业（儿童大健康） | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-d68704b1cca1a867ecb1 artifact_sha=b8d64e5895889cac881a818da7935c7437140412257ebbed2db8901d421c9991 manifest_sha=b2c99dffc459e64d58832e91c177983a4cdcab2f1ef3e09e72519703fc01d7cd -->
