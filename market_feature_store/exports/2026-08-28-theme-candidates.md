# 2026-08-28 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：21014.72
- **上涨家数**：3013
- **涨停 / 跌停**：82 / 1
- **容量前三行业**：1.电子(26.7%, super_capacity)、2.通信(8.7%, normal)、3.机械设备(7.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 连板未映射 | - | 电力设备 | 181.0 | limit_advance_cluster | 0 | 0 | 0 | placeholder_market_theme |
| 2 | 化工 | 化工 | 基础化工 | 172.55 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 3 | 乡村振兴 | 乡村振兴 | - | 170.17 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 4 | 化工原料 | 化工 | 基础化工 | 165.44 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 5 | 粮食概念 | 粮食概念 | - | 135.6 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 6 | 种植业 | 种植业 | - | 133.2 | multi_period_rank、new_high_cluster | 1 | 7 | 1 | - |
| 7 | 化肥概念 | 化肥 | - | 126.0 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 8 | AIGC概念 | AIGC | - | 123.15 | double_red、limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 9 | 信创 | 信创 | 计算机 | 123.15 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 医药 | 医药 | 医药生物 | 123.0 | limit_advance_cluster、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | AI智能体 | AI智能体 | 计算机 | 122.8 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 12 | ChatGPT概念 | ChatGPT概念 | 计算机 | 122.8 | double_red、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 13 | 国产软件 | 软件 | 计算机 | 122.8 | double_red、limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 14 | 元宇宙概念 | 元宇宙 | - | 116.0 | double_red、new_high_cluster | 1 | 3 | 0 | missing_evidence |
| 15 | 华为鸿蒙 | 华为鸿蒙 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 16 | 海峡西岸 | 海峡西岸 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 计算机 | 计算机外设 | 计算机 | 116.0 | double_red、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 18 | 跨境电商 | 跨境电商 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 19 | 软件服务 | 软件 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 20 | 多模态AI | 多模态AI | 计算机 | 108.0 | double_red、new_high_cluster | 1 | 3 | 1 | - |
| 21 | 通信 | 通信 | 计算机 | 106.86 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 22 | 新能源车 | 新能源车 | - | 90.84 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 机器人 | 机器人 | 基础化工 | 89.0 | limit_advance_cluster | 5 | 12 | 2 | - |
| 24 | 数据中心 | 数据中心 | 计算机 | 88.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 水产品 | 水产 | - | 88.4 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 26 | 涤纶 | 涤纶 | - | 88.0 | multi_period_rank、new_high_cluster | 4 | 12 | 1 | - |
| 27 | 机械设备 | 机械设备 | 机械设备 | 87.26 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 28 | 石油化工 | 化工 | - | 86.8 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 29 | 电子 | EDA（电子设计自动化） | 电子 | 86.06 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 30 | 一带一路 | 一带一路 | - | 84.87 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 供销社 | 供销社 | - | 84.4 | multi_period_rank、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 32 | 虫害防治 | 虫害防治 | - | 83.6 | multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 人形机器人 | 人形机器人 | 机械设备 | 83.13 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 34 | 通信设备 | 通信设备 | 通信 | 82.95 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 35 | 东数西算 | 东数西算 | - | 81.77 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 36 | 商业航天 | 商业航天 | 国防军工 | 81.18 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 37 | 先进封装 | 先进封装 | 电子 | 81.15 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 38 | 国防军工 | 国防军工 | - | 80.98 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 39 | 存储芯片 | 存储芯片 | 电子 | 80.98 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 40 | 锂电池概念 | 锂 | - | 80.77 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 41 | 高端装备 | 高端装备 | 机械设备 | 80.36 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |
| 42 | 工业互联 | 工业互联网 | - | 80.2 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 43 | 智能穿戴 | 智能穿戴 | 电子 | 79.65 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 44 | OLED概念 | LED | 电子 | 79.2 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 45 | AI眼镜 | AI眼镜 | 电子 | 79.03 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 46 | CPO概念 | CPO | - | 77.55 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 47 | 光通信 | 光通信 | - | 77.07 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 48 | 氢能源 | 氢能源 | 电力设备 | 76.88 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 49 | 液冷服务器 | 液冷服务器 | 电力设备 | 74.13 | new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 50 | 风电 | 风电 | 电力设备 | 72.76 | new_high_direction、new_high_cluster | 5 | 12 | 4 | - |

## 五、核心候选明细

## 候选 1：连板未映射

- **标准概念**：-
- **申万一级**：电力设备
- **评分**：181.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 181.0 | 连板股11只，最高7板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 2：化工

- **标准概念**：化工
- **申万一级**：基础化工
- **评分**：172.55
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.67%，边际量 19.56%，成交额 1440.25 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.67%，边际量19.56%，成交1440.25亿 |
| new_high_direction | 46.95 | 新高股128只，新高成交555.9000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比19.51，排名2 |

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
| 元力股份 | 300174 | 化工 | 木质活性炭及硅化物（硅酸钠/硅胶/白炭黑）规模化生产商 | core | L2 | 20 |
| 利柏特 | 605167 | 化工 | 石化大型装置工业模块设计制造与工程服务商，服务巴斯夫等化工业主 | core | L2 | 20 |
| 华尔泰 | 001217 | 化工 | 基础化工产品制造商，拥有硝酸、硫酸、双氧水等大型成套装置 | core | L2 | 20 |
| 华鲁恒升 | 600426 | 化工 | 多业联产综合型化工企业，覆盖新能源新材料、有机胺、醋酸及衍生品等化工品 | core | L2 | 20 |
| 国际实业 | 000159 | 化工 | 化工产品多品种批发商，依托仓储物流服务下游市场 | core | L2 | 20 |
| 宇新股份 | 002986 | 化工 | 以LPG为原料的深加工有机化工产品生产商（化工行业收入占比99.99%） | core | L2 | 20 |

## 候选 3：乡村振兴

- **标准概念**：乡村振兴
- **申万一级**：-
- **评分**：170.17
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.23%，边际量 12.86%，成交额 1119.86 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（4），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.23%，边际量12.86%，成交1119.86亿 |
| new_high_direction | 45.27 | 新高股103只，新高成交421.45亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.9 | 涨停14只，市场占比17.07，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 神农集团 | 605296 | 农业 | 生猪养殖业务（核心）、屠宰及食品加工（协同） | related | L2 | 1 |
| 荃银高科 | 300087 | 农业 | 种子业务（水稻、玉米、小麦等） | related | L1_L3_candidate | 1 |
| 园林股份 | 605303 | 基建 | 市政园林工程施工承包（含EPCO/设计-施工总承包） | related | L2 | 1 |
| 维维股份 | 600300 | 粮食安全 | 国有上市公司定位，围绕粮食收储、加工、销售打造粮食产业平台，粮油仓储贸易... | related | L2 | 1 |

## 候选 4：化工原料

- **标准概念**：化工
- **申万一级**：基础化工
- **评分**：165.44
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.35%，边际量 18.89%，成交额 952.94 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.35%，边际量18.89%，成交952.94亿 |
| new_high_direction | 43.34 | 新高股57只，新高成交267.13000000000005亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比7.32，排名27 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 化工 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 元力股份 | 300174 | 化工 | 木质活性炭及硅化物（硅酸钠/硅胶/白炭黑）规模化生产商 | core | L2 | 20 |
| 利柏特 | 605167 | 化工 | 石化大型装置工业模块设计制造与工程服务商，服务巴斯夫等化工业主 | core | L2 | 20 |
| 华尔泰 | 001217 | 化工 | 基础化工产品制造商，拥有硝酸、硫酸、双氧水等大型成套装置 | core | L2 | 20 |
| 华鲁恒升 | 600426 | 化工 | 多业联产综合型化工企业，覆盖新能源新材料、有机胺、醋酸及衍生品等化工品 | core | L2 | 20 |
| 国际实业 | 000159 | 化工 | 化工产品多品种批发商，依托仓储物流服务下游市场 | core | L2 | 20 |
| 宇新股份 | 002986 | 化工 | 以LPG为原料的深加工有机化工产品生产商（化工行业收入占比99.99%） | core | L2 | 20 |
| 正丹股份 | 300641 | 化工 | 石油化工行业酸酐及酯类产品生产商（酸酐及酯类设计产能18.5万吨/年、在... | core | L2 | 20 |
| 皖维高新 | 600063 | 化工 | 聚乙烯醇（PVA）行业龙头 | core | L2 | 20 |

## 候选 5：粮食概念

- **标准概念**：粮食概念
- **申万一级**：-
- **评分**：135.6
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 28.2 | day10排名第2，区间涨幅17.77% |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅11.54% |
| multi_period_rank | 26.6 | daily排名第4，区间涨幅2.92% |
| multi_period_rank | 26.6 | day3排名第4，区间涨幅6.59% |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 6：种植业

- **标准概念**：种植业
- **申万一级**：-
- **评分**：133.2
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅22.95% |
| multi_period_rank | 29.0 | day5排名第1，区间涨幅12.95% |
| multi_period_rank | 27.4 | day3排名第3，区间涨幅7.22% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 21.8 | daily排名第10，区间涨幅2.36% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 种植业 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 北大荒 | 600598 | 种植业 | 寒地水稻、玉米、大豆种植土地承包与高产栽培技术推广 | core | L2 | 20 |
| 雪榕生物 | 300511 | 种植业 | 工厂化食用菌种植企业（设施农业），农业产业化国家重点龙头企业 | core | L2 | 20 |
| 登海种业 | 002041 | 种植业 | 登海种业年报披露的种植业相关主营业务 | related | L2 | 20 |
| 荃银高科 | 300087 | 种植业 | 荃银高科年报披露的种植业相关主营业务 | related | L2 | 20 |
| 浙农股份 | 002758 | 种植业 | 农场运营与土地托管服务方（流转类运营约8万亩、托管类运营约2万亩，「万亩... | peripheral | L2 | 20 |
| 苏垦农发 | 601952 | 粮食安全 | 大型国有农业平台，稻麦种植及粮油加工一体化 | related | L2 | 1 |
| 众兴菌业 | 002772 | 食用菌 | 工厂化食用菌培植与销售企业，产品以金针菇和双孢菇为主 | core | L2 | 1 |

## 候选 7：化肥概念

- **标准概念**：化肥
- **申万一级**：-
- **评分**：126.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 27.4 | daily排名第3，区间涨幅3.16% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.0 | day5排名第6，区间涨幅6.92% |
| multi_period_rank | 24.2 | day3排名第7，区间涨幅5.94% |
| multi_period_rank | 23.4 | day10排名第8，区间涨幅9.79% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 化肥 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云天化 | 600096 | 化肥 | 国内磷肥产能第二、全球第四的化肥龙头（磷肥555万吨/年、尿素超290万... | core | L2 | 20 |
| 六国化工 | 600470 | 化肥 | 磷肥、复合肥、尿素等化肥产品制造商，执行国家稳价保供 | core | L2 | 20 |
| 农发种业 | 600313 | 化肥 | 化肥贸易业务运营商，为第一大收入来源 | core | L2 | 20 |
| 农大科技 | 920159 | 化肥 | 复合肥料研发、生产和销售企业 | core | L2 | 20 |
| 史丹利 | 002588 | 化肥 | 硫基复合肥营收22.98亿元/占比18.70%/同比+3.45% | core | L2 | 20 |
| 四川美丰 | 000731 | 化肥 | 气头尿素+尿基/硝硫基复合肥，兼营车用尿素、三聚氰胺 | core | L2 | 20 |
| 新洋丰 | 000902 | 化肥 | 磷复肥龙头，2025年磷复肥收入170.48亿元（占比94.45%，同比... | core | L2 | 20 |
| 浙农股份 | 002758 | 化肥 | 全国供销社系统农资流通龙头（化肥分销为主+浙苏皖鲁鄂蒙7家肥料生产企业，... | core | L2 | 20 |

## 候选 8：AIGC概念

- **标准概念**：AIGC
- **申万一级**：-
- **评分**：123.15
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.57%，边际量 19.93%，成交额 1200.06 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.57%，边际量19.93%，成交1200.06亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比10.98，排名12 |

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

## 候选 9：信创

- **标准概念**：信创
- **申万一级**：计算机
- **评分**：123.15
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 0.28%，边际量 11.85%，成交额 1193.62 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.28%，边际量11.85%，成交1193.62亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比10.98，排名13 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 信创 | 20 |
| 信创云 | 5 |
| 信创产业 | 5 |
| 信创存储 | 5 |
| 党政信创 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中创股份 | 688695 | 信创 | 国产中间件厂商（山东中创软件），基础软件自主创新 | core | L2 | 20 |
| 中国软件 | 600536 | 信创 | 自主安全软件国家队（中国电子旗下，麒麟操作系统母公司） | core | L2 | 20 |
| 中国长城 | 000066 | 信创 | 中国电子旗下计算产业主力军（自主计算整机谱系最全厂商之一） | core | L2 | 20 |
| 中船汉光 | 300847 | 信创 | 打印耗材国产化龙头（墨粉+OPC鼓双规模化生产，信息安全复印机） | core | L2 | 20 |
| 启明星辰 | 002439 | 信创 | AI应用安全（MAS产品矩阵）、中国移动协同业务、传统网络安全（防火墙/... | core | L1_L3_candidate | 20 |
| 天玑科技 | 300245 | 信创 | 自研信创数据存储/数据库一体机实现国产化替代 | core | L2 | 20 |
| 太极股份 | 002368 | 信创 | 中国电科信创工程研究中心牵头单位，自主可控产业生态 | core | L2 | 20 |
| 新炬网络 | 605398 | 信创 | 多云全栈智能运维服务商，与阿里云/腾讯云/华为云深化国产数据库产业布局 | core | L2 | 20 |

## 候选 10：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：123.0
- **触发类型**：limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 97.0 | 连板股2只，最高4板，容量前三=False |
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


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-f0070a2bca2e6ca322dd artifact_sha=f5c7de88a7479179412949c90d9565e0d0e183edeb5d5087bedd096616d97a85 manifest_sha=f0b3e53ef0399b871225a2a9ffedea0055dd43132a10ed5d05cc3b8c3ceaf0fd -->
