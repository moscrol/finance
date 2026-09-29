# 2026-09-21 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：20310.6
- **上涨家数**：4534
- **涨停 / 跌停**：102 / 2
- **容量前三行业**：1.电子(28.5%, super_capacity)、2.通信(8.2%, normal)、3.机械设备(7.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 粤港澳 | 粤港澳 | 房地产 | 277.28 | double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 2 | 医药医疗 | 医疗 | 医药生物 | 265.45 | double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 3 | CXO概念 | CXO | 医药生物 | 219.2 | double_red、multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 4 | 新零售 | 零售 | 纺织服饰 | 172.25 | limit_heat、limit_advance_cluster、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 5 | 国防军工 | 国防军工 | 国防军工 | 167.08 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 6 | 口罩防护 | 口罩防护 | 基础化工 | 150.5 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | 养老概念 | 养老概念 | 房地产 | 147.5 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 8 | 人工智能 | 人工智能 | 电子 | 142.25 | limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 3 | 12 | 1 | - |
| 9 | 医疗服务 | 医疗服务 | - | 136.4 | multi_period_rank、new_high_cluster | 2 | 12 | 2 | - |
| 10 | MLCC | MLCC | 电子 | 133.6 | double_red、capacity_industry、multi_period_rank、new_high_cluster | 5 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 化学制药 | 化学制药 | 医药生物 | 133.6 | double_red、limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 12 | 医药 | 医药 | 医药生物 | 132.15 | double_red、limit_heat、multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 创新药 | 创新药 | 医药生物 | 131.35 | double_red、limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 5 | - |
| 14 | AI医疗概念 | AI医疗 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 15 | 军民融合 | 军民融合 | - | 116.0 | double_red、new_high_cluster | 1 | 7 | 1 | - |
| 16 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 17 | 一带一路 | 一带一路 | 交通运输 | 107.07 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 18 | 锂电池概念 | 锂 | 轻工制造 | 105.19 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 19 | 电子 | EDA（电子设计自动化） | 电子 | 101.15 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 20 | 半导体 | 半导体 | 电子 | 96.76 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 21 | 元器件 | 电子元器件 | 电子 | 94.51 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 22 | 新能源车 | 新能源车 | - | 90.65 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 汽车芯片 | 汽车芯片 | 电子 | 90.31 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 24 | 通信设备 | 通信设备 | 通信 | 88.57 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 25 | 通信 | 通信 | 通信 | 88.35 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 26 | 机械设备 | 机械设备 | 机械设备 | 87.37 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 27 | 存储芯片 | 存储芯片 | 电子 | 86.56 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 28 | 物联网 | 物联网 | - | 85.59 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 29 | 先进封装 | 先进封装 | 电子 | 85.57 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 30 | CPO概念 | CPO | - | 84.0 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 光通信 | 光通信 | - | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 32 | 数据中心 | 数据中心 | 计算机 | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | PCB概念 | PCB概念 | - | 83.39 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 34 | AI眼镜 | AI眼镜 | 电子 | 83.28 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 35 | 智能穿戴 | 智能穿戴 | 电子 | 83.25 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 36 | 无人驾驶 | 无人驾驶 | 汽车 | 83.11 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 37 | 人形机器人 | 人形机器人 | 机械设备 | 82.23 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 38 | OLED概念 | LED | 电子 | 82.21 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 39 | 玻璃基板 | 玻璃基板 | 电子 | 81.03 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 40 | MiniLED | Mini LED | 电子 | 80.66 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 41 | 折叠屏 | 折叠屏 | 电子 | 80.58 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 1 | - |
| 42 | 商业航天 | 商业航天 | 国防军工 | 80.5 | new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 43 | 无人机 | 无人机 | - | 79.77 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 44 | 智慧城市 | 智慧城市 | - | 79.41 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 45 | 东数西算 | 东数西算 | - | 78.87 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 46 | 液冷服务器 | 液冷服务器 | 电力设备 | 76.08 | new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 47 | 6G概念 | 6G | - | 74.12 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 48 | 小米概念 | 小米概念 | - | 73.81 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 工业互联 | 工业互联网 | - | 73.4 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 50 | 阿里概念 | 阿里概念 | - | 72.96 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 五、核心候选明细

## 候选 1：粤港澳

- **标准概念**：粤港澳
- **申万一级**：房地产
- **评分**：277.28
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.1419%，边际量 10.6073%，成交额 1625.1514 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股3只，最高4板，容量前三=False |
| double_red | 90.0 | 涨幅2.1419%，边际量10.6073%，成交1625.1514亿 |
| new_high_direction | 47.03 | 新高股58只，新高成交562.1720999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.25 | 涨停15只，市场占比14.71，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 奥飞数据 | 300738 | 东数西算 | IDC数据中心服务、算力租赁、云计算服务 | related | L1_L3_candidate | 1 |
| 农产品 | 000061 | 农批市场 | 国内最具规模的农产品批发市场网络（20余城35个实体物流园，海吉星体系）... | core | L2 | 1 |
| 美丽生态 | 000010 | 基建 | 综合性跨区域民营建筑企业（市政总承包壹级、建筑总承包壹级等资质），重点布... | core | L2 | 1 |
| 筑博设计 | 300564 | 建筑设计 | 建筑设计与咨询服务商，涵盖居住建筑、医疗与康养建筑、商业综合体与超高层、... | core | L2 | 1 |
| 中洲控股 | 000042 | 房地产 | 区域城市综合运营商（聚焦粤港澳大湾区、成渝、上海） | core | L2 | 1 |
| 中国移动 | 600941 | 数据中心 | 全国枢纽节点AIDC/IDC资源供给方 | related | L2 | 1 |
| 深水海纳 | 300961 | 水处理 | 工业污水处理+优质供水投建运一体化水务运营商（TEPS园区污染治理模式） | core | L2 | 1 |
| 佛燃能源 | 002911 | 清洁能源 | 天然气气源代购、长输管线分销及低碳清洁电力运营商 | core | L1 | 1 |

## 候选 2：医药医疗

- **标准概念**：医疗
- **申万一级**：医药生物
- **评分**：265.45
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.0936%，边际量 32.5348%，成交额 1473.5689 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 93.0 | 连板股2只，最高3板，容量前三=False |
| double_red | 90.0 | 涨幅4.0936%，边际量32.5348%，成交1473.5689亿 |
| new_high_direction | 44.75 | 新高股69只，新高成交380.1389000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.7 | 涨停22只，市场占比21.57，排名1 |

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

## 候选 3：CXO概念

- **标准概念**：CXO
- **申万一级**：医药生物
- **评分**：219.2
- **触发类型**：double_red、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 4.7864%，边际量 15.0594%，成交额 506.8128 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.7864%，边际量15.0594%，成交506.8128亿 |
| multi_period_rank | 28.2 | day3排名第2，区间涨幅8.64% |
| multi_period_rank | 26.6 | daily排名第4，区间涨幅4.79% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.2 | day10排名第7，区间涨幅9.7% |
| multi_period_rank | 24.2 | day5排名第7，区间涨幅9.41% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CXO | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凯莱英 | 002821 | CXO | 医药CXO/CDMO服务商，覆盖小分子及新兴业务 | core | L2 | 20 |
| 博济医药 | 300404 | CXO | CRO为主、兼有CDMO的医药外包 | core | L2 | 20 |
| 博腾股份 | 300363 | CXO | 医药研发生产外包 | core | L2 | 20 |
| 普蕊斯 | 301257 | CXO | 医药研发外包链条上的SMO环节头部企业（临床试验执行外包） | core | L2 | 20 |
| 百花医药 | 600721 | CXO | 从发现到申报的医药外包 | core | L2 | 20 |
| 睿智医药 | 300149 | CXO | 医药研发服务及生产外包业务收入11.21亿元占98.80%同比+16.6... | core | L2 | 20 |
| 药石科技 | 300725 | CXO | 以分子砌块为核心能力底座的一体化CRDMO创新服务商，覆盖药物发现、临床... | core | L2 | 20 |
| 义翘神州 | 301047 | CXO | 生物试剂+CRO技术服务 | related | L2 | 20 |

## 候选 4：新零售

- **标准概念**：零售
- **申万一级**：纺织服饰
- **评分**：172.25
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 137.0 | 连板股7只，最高4板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.25 | 涨停15只，市场占比14.71，排名3 |

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

## 候选 5：国防军工

- **标准概念**：国防军工
- **申万一级**：国防军工
- **评分**：167.08
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.9093%，边际量 10.6%，成交额 521.9754 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.9093%，边际量10.6%，成交521.9754亿 |
| new_high_direction | 51.08 | 新高股72只，新高成交886.6502999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 6：口罩防护

- **标准概念**：口罩防护
- **申万一级**：基础化工
- **评分**：150.5
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 2.2183%，边际量 11.1334%，成交额 968.3047 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.2183%，边际量11.1334%，成交968.3047亿 |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比9.8，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：养老概念

- **标准概念**：养老概念
- **申万一级**：房地产
- **评分**：147.5
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 3.0982%，边际量 13.3154%，成交额 514.1277 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.0982%，边际量13.3154%，成交514.1277亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 7.5 | 涨停10只，市场占比9.8，排名13 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 8：人工智能

- **标准概念**：人工智能
- **申万一级**：电子
- **评分**：142.25
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.25 | 涨停15只，市场占比14.71，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人工智能 | 20 |
| AI人工智能 | 5 |
| 人工智能AI | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凡拓数创 | 301313 | AI人工智能 | AI 3D标准化产品、虚拟数智人与行业AI小模型服务商 | core | L2 | 20 |
| 云从科技 | 688327 | 人工智能 | AI平台厂商（人机协同操作系统+行业解决方案） | core | L2 | 20 |
| 华如科技 | 301302 | 人工智能 | 军事大模型及AI工具集（智能仿真、数字战场、智能体、数字兵力、数实互联）... | core | L2 | 20 |
| 天娱数科 | 002354 | 人工智能 | 以自研天星大模型为技术底座的AI能力平台，贯通基础模型-行业模型-智能体... | core | L2 | 20 |
| 安博通 | 688168 | 人工智能 | 智能、安全人工智能相关产品/服务商 | core | L2 | 20 |
| 宝兰德 | 688058 | 人工智能 | 宝兰德年报披露的人工智能相关主营业务 | core | L2 | 20 |
| 宝鹰股份 | 002047 | 人工智能 | 宝鹰股份年报披露的人工智能相关主营业务 | core | L2 | 20 |
| 广电运通 | 002152 | 人工智能 | 广电运通年报披露的人工智能相关主营业务 | core | L2 | 20 |

## 候选 9：医疗服务

- **标准概念**：医疗服务
- **申万一级**：-
- **评分**：136.4
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | daily排名第1，区间涨幅5.14% |
| multi_period_rank | 29.0 | day3排名第1，区间涨幅9.26% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅11.66% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | day5排名第5，区间涨幅10.2% |

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

## 候选 10：MLCC

- **标准概念**：MLCC
- **申万一级**：电子
- **评分**：133.6
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 1.5243%，边际量 20.7267%，成交额 540.9601 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.5243%，边际量20.7267%，成交540.9601亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| multi_period_rank | 7.6 | day10排名第9，区间涨幅9.07% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MLCC | 20 |
| MLCC微型化 | 5 |
| MLCC材料 | 5 |
| MLCC粉体 | 5 |
| MLCC镍粉 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | MLCC | 国产MLCC主力厂商（0201至2220全尺寸+车规+高容数据中心产品） | core | L2 | 20 |
| 力源信息 | 300184 | MLCC | AI服务器MLCC分销、华为海思芯片代理、存储芯片分销、碳化硅（SiC）... | core | L1_L3_candidate | 20 |
| 天马新材 | 920971 | MLCC | 电子陶瓷用粉体（MLCC上游）、高压电器用粉体、高导热球形氧化铝 | core | L1_L3_candidate | 20 |
| 达利凯普 | 301566 | MLCC | 达利凯普年报披露的MLCC相关主营业务 | core | L2 | 20 |
| 鸿远电子 | 603267 | MLCC | 高可靠MLCC（瓷介电容器）、滤波器、集成电路、微波模块 | core | L1_L3_candidate | 20 |
| 厦门钨业 | 600549 | MLCC | 钨全产业链龙头（光伏钨丝份额超80%/PCB钻针棒材/MLCC碳酸钡/半... | core | L3 | 20 |
| 斯迪克 | 300806 | MLCC | MLCC 离型膜龙头，月产 5000w 平/总产能 20e 平/年 | core | L2 | 20 |
| 洁美科技 | 002859 | MLCC | 上游离型膜材料 | core | L1_L3_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-67715fd2baf4441f42a1 artifact_sha=0fa8570794566e6cabdcbc8fddbfaf6f04a4df0fb826ddfc2dbc52dfc19b390f manifest_sha=3639fc763914130ff8cb3291f58df216618f07af8735cf4de1d5f423d5444e77 -->
