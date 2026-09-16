# 2026-09-01 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：20328.97
- **上涨家数**：3387
- **涨停 / 跌停**：83 / 0
- **容量前三行业**：1.电子(22.7%, capacity)、2.机械设备(7.7%, normal)、3.通信(7.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 乡村振兴 | 乡村振兴 | - | 173.25 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 2 | IP经济 | IP经济 | 传媒 | 167.61 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 3 | 华为鸿蒙 | 华为鸿蒙 | 计算机 | 167.14 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 4 | 区块链 | 区块链 | - | 166.9 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 9 | 1 | - |
| 5 | 传媒 | 传媒 | 传媒 | 166.7 | double_red、limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 6 | 互联金融 | 互联金融 | - | 165.98 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | 非银金融 | 非银金融 | 非银金融 | 160.03 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 8 | 元宇宙概念 | 元宇宙 | - | 159.63 | double_red、new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 9 | 跨境支付CIPS | IP | 计算机 | 159.34 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 10 | ChatGPT概念 | ChatGPT概念 | 计算机 | 159.17 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 多模态AI | 多模态AI | 计算机 | 158.81 | double_red、new_high_direction、new_high_cluster | 1 | 3 | 1 | - |
| 12 | 短剧游戏 | 游戏 | 传媒 | 152.0 | double_red、limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 13 | 粮食概念 | 粮食概念 | - | 144.15 | limit_heat、multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 14 | 种植业 | 种植业 | - | 144.0 | limit_heat、multi_period_rank、new_high_cluster | 1 | 8 | 1 | - |
| 15 | AI长剧 | AI长剧 | 传媒 | 141.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 16 | 网络游戏 | 游戏 | 传媒 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 17 | 农业 | 农业 | 农林牧渔 | 113.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 18 | 影视音像 | 影视 | - | 90.0 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 19 | 水产品 | 水产 | - | 86.8 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 20 | 一带一路 | 一带一路 | - | 82.57 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 21 | AI营销 | AI营销 | - | 82.0 | multi_period_rank、new_high_cluster | 0 | 3 | 0 | missing_concept、missing_evidence |
| 22 | 新能源车 | 新能源车 | - | 80.58 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | AIGC概念 | AIGC | - | 80.35 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 24 | 电子 | EDA（电子设计自动化） | 电子 | 80.21 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 25 | 抖音概念 | 抖音概念 | - | 80.17 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 26 | 机械设备 | 机械设备 | 机械设备 | 79.78 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 27 | 新零售 | 零售 | - | 79.3 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 28 | 阿里概念 | 阿里概念 | - | 78.62 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 29 | 腾讯概念 | 腾讯概念 | - | 78.23 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 30 | 农林牧渔 | 农林牧渔 | 农林牧渔 | 77.86 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 数据要素 | 数据要素 | 计算机 | 77.11 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 32 | 物联网 | 物联网 | - | 76.65 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 33 | 绿色电力 | 绿色电力 | - | 76.61 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 34 | 跨境电商 | 跨境电商 | - | 76.06 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 35 | 数据中心 | 数据中心 | 计算机 | 74.47 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 化工 | 化工 | 基础化工 | 71.74 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 37 | 中特估 | 中特估 | - | 71.56 | new_high_direction、new_high_cluster | 1 | 0 | 1 | missing_entity_exposures |
| 38 | 东数西算 | 东数西算 | - | 71.49 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 39 | 锂电池概念 | 锂 | - | 70.67 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 40 | 液冷服务器 | 液冷服务器 | 电力设备 | 70.34 | new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 41 | 无人机 | 无人机 | - | 70.3 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 42 | 无人驾驶 | 无人驾驶 | 汽车 | 70.16 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 43 | 国防军工 | 国防军工 | 国防军工 | 70.02 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 44 | 百度概念 | 百度概念 | - | 69.99 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 银行 | 银行 | 银行 | 69.88 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 46 | 车联网 | 车联网 | - | 69.77 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 47 | 氢能源 | 氢能源 | 电力设备 | 69.76 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 48 | 计算机 | 计算机外设 | 计算机 | 69.65 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 49 | 信息安全 | 信息安全 | 计算机 | 69.64 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 50 | 智能家居 | 智能家居 | - | 69.63 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：乡村振兴

- **标准概念**：乡村振兴
- **申万一级**：-
- **评分**：173.25
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.23%，边际量 11.6%，成交额 1327.24 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=是（4），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.23%，边际量11.6%，成交1327.24亿 |
| new_high_direction | 47.3 | 新高股148只，新高成交584.1999999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.95 | 涨停17只，市场占比20.48，排名3 |

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

## 候选 2：IP经济

- **标准概念**：IP经济
- **申万一级**：传媒
- **评分**：167.61
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.23%，边际量 21.46%，成交额 640.38 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.23%，边际量21.46%，成交640.38亿 |
| new_high_direction | 43.41 | 新高股71只，新高成交272.83亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比14.46，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| IP经济 | 20 |
| IP | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 游族网络 | 002174 | IP | 自有「少年」系列IP与HBO《权力的游戏》正版授权IP的游戏化运营商 | related | L2 | 20 |
| 奥飞娱乐 | 002292 | IP | IP相关产品/材料供应商 | related | L2 | 20 |
| 慈文传媒 | 002343 | IP | 慈文传媒年报披露的IP相关主营业务 | related | L2 | 20 |
| 曲江文旅 | 600706 | IP | 曲江文旅年报披露的IP相关主营业务 | related | L2 | 20 |
| 渤海轮渡 | 603167 | IP | 渤海轮渡年报披露的IP相关主营业务 | related | L2 | 20 |
| 视觉中国 | 000681 | IP | 视觉中国年报披露的IP相关主营业务 | related | L2 | 20 |
| 首创环保 | 600008 | IP | 首创环保年报披露的IP相关主营业务 | related | L2 | 20 |
| 实丰文化 | 002862 | IP | 光伏营收0.29亿元/占比6.92%/同比+200.14% | related | L2 | 20 |

## 候选 3：华为鸿蒙

- **标准概念**：华为鸿蒙
- **申万一级**：计算机
- **评分**：167.14
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.84%，边际量 15.02%，成交额 1052.88 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.84%，边际量15.02%，成交1052.88亿 |
| new_high_direction | 43.99 | 新高股51只，新高成交319.2亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比10.84，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 华为鸿蒙 | 20 |
| 鸿蒙 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 科蓝软件 | 300663 | 华为鸿蒙 | 鸿蒙首批全生态认证服务商：鸿蒙智能高柜机器人小蓝、科蓝鸿蒙移动金融技术平... | core | L2 | 20 |
| 华勤技术 | 603296 | 鸿蒙 | 中游制造 | core | L2_candidate | 20 |
| 均胜电子 | 600699 | 鸿蒙 | 上游设备 | core | L1_L3_candidate | 20 |
| 德赛西威 | 002920 | 鸿蒙 | 上游设备 | core | L1_L3_candidate | 20 |
| 有方科技 | 688159 | 鸿蒙 | 算力云服务/算力租赁、云基础设施（存算服务器）、物联网无线通信模组、电力... | core | L1_L3_candidate | 20 |
| 莱宝高科 | 002106 | 鸿蒙 | 上游设备 | core | L1_L3_candidate | 20 |
| 软通动力 | 301236 | 鸿蒙 | 产业链供应商 | core | L2_candidate | 20 |
| 中国软件 | 600536 | 鸿蒙 | 国产操作系统（麒麟软件）、党政核心应用解决方案、信创基础软件 | related | L1_L3_candidate | 20 |

## 候选 4：区块链

- **标准概念**：区块链
- **申万一级**：-
- **评分**：166.9
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.11%，边际量 16.35%，成交额 1256.53 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.11%，边际量16.35%，成交1256.53亿 |
| new_high_direction | 43.05 | 新高股51只，新高成交244.27000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比13.25，排名10 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 区块链 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 远光软件 | 002063 | 区块链 | 区块链 | related | L2 | 20 |
| 恒宝股份 | 002104 | 区块链 | 恒宝股份年报披露的区块链相关主营业务 | related | L2 | 20 |
| 四方精创 | 300468 | 区块链 | 软件开发及维护供应商/运营商 | related | L2 | 20 |
| 拉卡拉 | 300773 | 人工智能 | 拉卡拉年报披露的人工智能相关主营业务 | related | L2 | 1 |
| 彩讯股份 | 300634 | 信创 | 智算服务与数据智能、Voice AI Agent、协同办公 | related | L1_L3_candidate | 1 |
| 安妮股份 | 002235 | 数字版权 | “版权家”数字版权综合服务平台运营方（区块链确权存证） | related | L2 | 1 |
| 易华录 | 300212 | 数据要素 | 数据资产化与可信数据空间服务商，2025年数据运营及服务收入2.01亿元... | core | L2 | 1 |
| 东方中科 | 002819 | 数据要素 | 可信数据空间技术服务布局者（区块链+隐私计算，研发项目已完成V1.0） | peripheral | L2 | 1 |

## 候选 5：传媒

- **标准概念**：传媒
- **申万一级**：传媒
- **评分**：166.7
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.63%，边际量 23.06%，成交额 826.65 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.63%，边际量23.06%，成交826.65亿 |
| new_high_direction | 42.85 | 新高股42只，新高成交227.9000000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比13.25，排名12 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 传媒 | 20 |
| 出版传媒 | 5 |
| 文化传媒 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 川网传媒 | 300987 | 传媒 | 新媒体整合营销、移动信息服务相关产品/服务商 | core | L2 | 20 |
| 新华网 | 603888 | 传媒 | 新华社控股网络媒体平台，2025年全媒广告服务收入7.85亿元（毛利率4... | core | L2 | 20 |
| 粤传媒 | 002181 | 传媒 | 广州市唯一国有控股文化传媒类上市企业，依托《广州日报》开展整合营销传播、... | core | L2 | 20 |
| 人民网 | 603000 | 传媒 | 广告及宣传服务相关产品供应商 | related | L2 | 20 |
| 佳创视讯 | 300264 | 传媒 | 传媒相关产品/服务商 | related | L2 | 20 |
| 凤凰传媒 | 601928 | 传媒 | 传媒相关产品/服务商 | related | L2 | 20 |
| 出版传媒 | 601999 | 传媒 | 出版相关产品供应商 | related | L2 | 20 |
| 分众传媒 | 002027 | 传媒 | 楼宇媒体相关产品供应商 | related | L2 | 20 |

## 候选 6：互联金融

- **标准概念**：互联金融
- **申万一级**：-
- **评分**：165.98
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.15%，边际量 16.2%，成交额 770.19 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.15%，边际量16.2%，成交770.19亿 |
| new_high_direction | 42.83 | 新高股55只，新高成交226.4亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比10.84，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：非银金融

- **标准概念**：非银金融
- **申万一级**：非银金融
- **评分**：160.03
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.55%，边际量 24.77%，成交额 566.25 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.55%，边际量24.77%，成交566.25亿 |
| new_high_direction | 44.03 | 新高股37只，新高成交322.69亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 非银金融 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中油资本 | 000617 | 非银金融 | 中国石油集团旗下全方位综合性金融服务平台（昆仑银行、中油财务、昆仑金融租... | core | L2 | 20 |
| 永安期货 | 600927 | 非银金融 | 头部全牌照期货公司（期货经纪+风险管理+资管+基金销售，分类监管评价连续... | core | L2 | 20 |
| 浙江东方 | 600120 | 非银金融 | 浙江省国有上市金融控股平台（旗下浙商金汇信托、大地期货、东方嘉富人寿、国... | core | L2 | 20 |
| 越秀资本 | 000987 | 非银金融 | 广州市国资委下属多元金融控股平台（融资租赁+不良资产管理+投资管理+战略... | core | L2 | 20 |
| 长城证券 | 002939 | 非银金融 | 非银金融（证券）标的，参控股覆盖公募基金、期货、私募、资管、国际金融的长... | core | L2 | 20 |
| 香溢融通 | 600830 | 非银金融 | 以融资租赁为核心引擎的类金融控股平台（融资租赁+典当+担保+特殊资产+私... | core | L2 | 20 |
| 东方财富 | 300059 | 非银金融 | 证券经纪、两融业务、基金代销（天天基金） | related | L1_L3_candidate | 20 |
| 中信证券 | 600030 | 非银金融 | 证券经纪、投资银行、资产管理 | related | L1_L3_candidate | 20 |

## 候选 8：元宇宙概念

- **标准概念**：元宇宙
- **申万一级**：-
- **评分**：159.63
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.36%，边际量 12.78%，成交额 1061.92 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.36%，边际量12.78%，成交1061.92亿 |
| new_high_direction | 43.63 | 新高股41只，新高成交290.06亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 元宇宙 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天地在线 | 002995 | 元宇宙 | 数字营销（互联网广告投放/代运营）、VR大空间/数字文旅、AI数字人（参... | related | L2 | 20 |
| 格灵深瞳 | 688207 | 机器人 | 机器人相关产品/材料供应商 | related | L2 | 1 |

## 候选 9：跨境支付CIPS

- **标准概念**：IP
- **申万一级**：计算机
- **评分**：159.34
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.4%，边际量 14.65%，成交额 524.49 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4%，边际量14.65%，成交524.49亿 |
| new_high_direction | 43.34 | 新高股23只，新高成交267.01亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| IP | 10 |
| 跨境支付 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 游族网络 | 002174 | IP | 自有「少年」系列IP与HBO《权力的游戏》正版授权IP的游戏化运营商 | related | L2 | 20 |
| 中文在线 | 300364 | IP | IP相关产品/材料供应商 | related | L2 | 20 |
| 奥飞娱乐 | 002292 | IP | IP相关产品/材料供应商 | related | L2 | 20 |
| 慈文传媒 | 002343 | IP | 慈文传媒年报披露的IP相关主营业务 | related | L2 | 20 |
| 曲江文旅 | 600706 | IP | 曲江文旅年报披露的IP相关主营业务 | related | L2 | 20 |
| 渤海轮渡 | 603167 | IP | 渤海轮渡年报披露的IP相关主营业务 | related | L2 | 20 |
| 视觉中国 | 000681 | IP | 视觉中国年报披露的IP相关主营业务 | related | L2 | 20 |
| 首创环保 | 600008 | IP | 首创环保年报披露的IP相关主营业务 | related | L2 | 20 |

## 候选 10：ChatGPT概念

- **标准概念**：ChatGPT概念
- **申万一级**：计算机
- **评分**：159.17
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.75%，边际量 15.61%，成交额 944.22 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.75%，边际量15.61%，成交944.22亿 |
| new_high_direction | 43.17 | 新高股33只，新高成交253.83亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-6380afad0b51ad095191 artifact_sha=e6e391db2e7df4d12c37057c0732fe8d759438bfc586dde681b11b3dde50ea4d manifest_sha=3c234f6fdc3e9e1b2bd5d81377f3c7f1ba9d986b8235267f5026c96916f5db77 -->
