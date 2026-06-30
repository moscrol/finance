# 2026-06-15 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：30310.15
- **上涨家数**：3906
- **涨停 / 跌停**：145 / 3
- **容量前三行业**：1.电子(28.3%, super_capacity)、2.有色金属(9.1%, normal)、3.通信(8.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 黄金 | 黄金 | 有色金属 | 190.49 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 2 | 金属铜 | 金属铜 | 有色金属 | 178.13 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 3 | 工业金属 | 工业金属 | 有色金属 | 169.55 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 4 | 金属镍 | 金属镍 | 有色金属 | 164.62 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 5 | 证券 | 证券IT | 非银金融 | 154.61 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 金属锌 | 金属锌 | 有色金属 | 120.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 7 | 金属铅 | 金属铅 | 有色金属 | 118.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 8 | 钼 | 小金属 | 有色金属 | 111.0 | limit_advance_cluster、capacity_industry | 3 | 7 | 0 | missing_evidence |
| 9 | 共封装光学(CPO) | CPO | 电子 | 99.08 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 10 | 小金属 | 小金属 | 有色金属 | 93.73 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 先进封装 | 先进封装 | 电子 | 92.22 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 12 | PCB | PCB | 电子 | 91.57 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 3 | - |
| 13 | 数据中心 | 数据中心 | 计算机 | 91.35 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 商业航天 | 商业航天 | 国防军工 | 85.87 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 15 | 存储芯片 | 存储芯片 | 电子 | 85.55 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 16 | 元件 | 电子元件 | 电子 | 84.95 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 17 | 海峡两岸 | 海峡两岸 | 综合 | 78.96 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 18 | 风电 | 风电 | 电力设备 | 78.65 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | PET铜箔 | PET铜箔 | 电力设备 | 78.61 | limit_heat、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 20 | 无人驾驶 | 无人驾驶 | 汽车 | 78.49 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | 传感器 | 传感器 | 机械设备 | 77.84 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 22 | 氢能源 | 氢能源 | 电力设备 | 77.54 | limit_heat、new_high_direction、new_high_cluster | 5 | 4 | 1 | - |
| 23 | 人形机器人 | 人形机器人 | 机械设备 | 77.03 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 24 | 半导体 | 半导体 | 电子 | 73.96 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 25 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 73.46 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 26 | 液冷服务器 | 液冷服务器 | 电力设备 | 70.68 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 化学制品 | 化工周期 | 基础化工 | 69.21 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 28 | AI眼镜 | AI眼镜 | 电子 | 68.83 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 29 | 光刻胶 | 光刻胶 | 电子 | 68.74 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 30 | 6G | 6G | 通信 | 68.23 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 银行 | 区块链 | 银行 | 68.2 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 32 | 燃料电池 | 燃料电池 | 电力设备 | 68.19 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 机器视觉 | 机器视觉 | 机械设备 | 68.15 | new_high_direction、new_high_cluster | 0 | 7 | 0 | missing_concept、missing_evidence |
| 34 | 华为手机 | 华为手机 | 电子 | 66.0 | new_high_direction、new_high_cluster、capacity_industry | 0 | 1 | 0 | missing_concept、missing_evidence |
| 35 | 稀土永磁 | 稀土永磁 | 有色金属 | 65.72 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 36 | MCU芯片 | MCU芯片 | 电子 | 63.28 | new_high_direction、new_high_cluster、capacity_industry | 3 | 4 | 1 | - |
| 37 | 光刻机 | 光刻机 | 电子 | 62.33 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 38 | 工业母机 | 工业母机 | 机械设备 | 61.58 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 可控核聚变 | 可控核聚变 | 电力设备 | 61.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 金属钴 | 金属钴 | 有色金属 | 61.5 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 氟化工 | 氟化工 | 基础化工 | 60.0 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | MLCC | MLCC | 电子 | 59.43 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 43 | 钠离子电池 | 储能 | 电力设备 | 58.67 | new_high_direction、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 44 | 电池 | 4C电池 | 电力设备 | 58.43 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 45 | 毫米波雷达 | 毫米波雷达 | 汽车 | 57.52 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 3D打印 | 3D打印 | 机械设备 | 57.23 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 智能座舱 | 智能座舱 | 汽车 | 55.73 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 通信设备 | 通信设备 | 通信 | 53.19 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 49 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 52.17 | new_high_direction、new_high_cluster、capacity_industry | 5 | 3 | 1 | - |
| 50 | 锂电池 | 锂电池 | 电力设备 | 49.45 | new_high_direction、new_high_cluster | 5 | 12 | 3 | - |

## 五、核心候选明细

## 候选 1：黄金

- **标准概念**：黄金
- **申万一级**：有色金属
- **评分**：190.49
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.73%，边际量 22.12%，成交额 1147.69 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.73%，边际量22.12%，成交1147.69亿 |
| new_high_direction | 38.49 | 新高股5只，新高成交279.5亿，容量前三=True |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 黄金 | 10 |
| 周期资源 | 2 |
| 小金属 | 2 |
| 白银 | 2 |
| 磁悬浮压缩机 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中金黄金 | 600489 | 黄金 | 集团平台与高股息黄金股 | core | L2_candidate | 10 |
| 宝鼎科技 | 002552 | 黄金 | AI铜箔（HVLP、HTE铜箔）、金矿业务 | core | L1_L3_candidate | 10 |
| 山东黄金 | 600947 | 黄金 | 国内纯金矿龙头 | core | L1_L3_candidate | 10 |
| 山金国际 | 000975 | 黄金 | 山东黄金集团旗下黄金平台 | related | L2_candidate | 10 |
| 湖南黄金 | 002155 | 黄金 | 黄金+锑双主业观察标的 | peripheral | L2_candidate | 10 |
| 特变电工 | 600089 | 黄金 | 塔国金矿项目运营商，券商研判其可能受益于金价上行 | peripheral | L1 | 10 |
| 紫金矿业 | 601899 | 黄金 | 铜金双核资源龙头 | core | L1_L3_candidate | 10 |
| 紫金黄金国际 | - | 黄金 | 紫金矿业分拆的港股黄金估值锚 | peripheral | L2_candidate | 10 |

## 候选 2：金属铜

- **标准概念**：金属铜
- **申万一级**：有色金属
- **评分**：178.13
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.56%，边际量 10.38%，成交额 1549.7 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.56%，边际量10.38%，成交1549.7亿 |
| new_high_direction | 52.13 | 新高股12只，新高成交586.37亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 3：工业金属

- **标准概念**：工业金属
- **申万一级**：有色金属
- **评分**：169.55
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.28%，边际量 28.89%，成交额 889.99 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.28%，边际量28.89%，成交889.99亿 |
| new_high_direction | 43.55 | 新高股8只，新高成交348.23亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中金岭南 | 000060 | 有色金属 | 有色金属矿产品及冶炼深加工商 | core | L2_candidate | 1 |

## 候选 4：金属镍

- **标准概念**：金属镍
- **申万一级**：有色金属
- **评分**：164.62
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.86%，边际量 16.42%，成交额 656.71 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.86%，边际量16.42%，成交656.71亿 |
| new_high_direction | 40.62 | 新高股6只，新高成交337.58000000000004亿，容量前三=True |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：证券

- **标准概念**：证券IT
- **申万一级**：非银金融
- **评分**：154.61
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.91%，边际量 26.08%，成交额 662.02 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.91%，边际量26.08%，成交662.02亿 |
| new_high_direction | 38.61 | 新高股12只，新高成交305.02000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 证券IT | 5 |
| 证券行业 | 5 |
| 两融 | 2 |
| 互联网券商 | 2 |
| 公募基金 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 财富趋势 | 688318 | 证券IT | 图谱弱关联 | peripheral | graph_only | 10 |
| 金证股份 | 600446 | 证券IT | 图谱弱关联 | peripheral | graph_only | 10 |
| 顶点软件 | 603383 | 证券IT | 图谱弱关联 | peripheral | graph_only | 10 |
| 三房巷 | 600370 | PTA | PTA产能集中与反内卷受益名单 | peripheral | graph_only | 1 |
| 三美股份 | 603379 | 制冷剂 | 三代制冷剂配额约束与涨价受益名单 | peripheral | graph_only | 1 |
| 万华化学 | 600309 | 化工 | 欧洲能源成本上行下国内化工竞争力提升受益名单 | peripheral | graph_only | 1 |
| 万凯新材 | 301216 | 化纤 | 聚酯瓶片相关标的 | peripheral | graph_only | 1 |
| 三友化工 | 600409 | 化纤 | 粘胶短纤相关标的 | peripheral | graph_only | 1 |

## 候选 6：金属锌

- **标准概念**：金属锌
- **申万一级**：有色金属
- **评分**：120.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 3.63%，边际量 15.71%，成交额 686.39 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.63%，边际量15.71%，成交686.39亿 |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：金属铅

- **标准概念**：金属铅
- **申万一级**：有色金属
- **评分**：118.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 3.69%，边际量 14.93%，成交额 689.08 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.69%，边际量14.93%，成交689.08亿 |
| new_high_cluster | 18.0 | 题材内新高股3只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 8：钼

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：111.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（7），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 111.0 | 连板股2只，最高3板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小金属 | 2 |
| 稀土永磁 | 2 |
| 铜 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 厦门钨业 | 600549 | 钨钼小金属 | 全球最大的钨冶炼与碳化钨精深加工、国家级稀土集团核心骨干与锂电材料双轮控... | core | L1 | 5 |
| 隆华科技 | 300263 | DRAM | 电子新材料（靶材：ITO/IZO/AZO/钼靶/银合金靶）、高分子复合材... | related | L1_L3_candidate | 1 |
| 江化微 | 603078 | 功率器件 | - | related | L1 | 1 |
| 高能环境 | 603588 | 固废处理 | 固废危废资源化企业，布局金银铅铜钼镍锌等稀贵金属资源化并延伸矿业端 | related | L1_L3_candidate | 1 |
| 国城矿业 | 000688 | 小金属 | 钼矿资源 | related | - | 1 |
| 金钼股份 | 601958 | 小金属 | 钼资源/钼制品 | core | - | 1 |
| 洛阳钼业 | 603993 | 铜 | 全球铜钴矿山龙头 | core | L1_L3_candidate | 1 |

## 候选 9：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：99.08
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.33 | 新高股22只，新高成交826.68亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 12.75 | 涨停25只，市场占比17.24，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |
| CPO（共封装光学） | 10 |
| 1.6T CPO | 5 |
| CPO一级封装 | 5 |
| CPO二级封装 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中瓷电子 | 003031 | 1.6T CPO | 陶瓷封装、高导热材料 | related | L1_image_extraction | 20 |
| 中际旭创 | 300308 | 1.6T CPO | 高速光模块龙头、完整方案交付 | core | L1_image_extraction | 20 |
| 光迅科技 | 002281 | 1.6T CPO | 光芯片/器件/模块 | related | L1_image_extraction | 20 |
| 华工科技 | 000988 | 1.6T CPO | 800G规模交付、1.6T LPO/LRO、3.2T CPO布局 | related | L1_image_extraction | 20 |
| 博众精工 | 688097 | 1.6T CPO | 贴片、耦合、检测自动化 | peripheral | L1_image_extraction | 20 |
| 天孚通信 | 300394 | 1.6T CPO | 高速光引擎、FAU、微光学器件 | core | L1_image_extraction | 20 |
| 新易盛 | 300502 | 1.6T CPO | 400G/800G/1.6T产品线 | related | L1_image_extraction | 20 |
| 水晶光电 | 002273 | 1.6T CPO | 微光学元件 | peripheral | L1_image_extraction | 20 |

## 候选 10：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：93.73
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 67.73 | 新高股20只，新高成交1418.5300000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小金属 | 10 |
| 二氧化锆 | 2 |
| 半导体设备材料 | 2 |
| 周期资源 | 2 |
| 战略金属 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方钽业 | 000962 | 小金属 | 钽铌材料/钽电容材料 | core | - | 10 |
| 东方锆业 | 002167 | 小金属 | 锆材料/其他小金属 | related | graph_only | 10 |
| 中国稀土 | 000831 | 小金属 | 中重稀土整合平台 | related | - | 10 |
| 中钨高新 | 000657 | 小金属 | 钨产业链/硬质合金刀具 | core | - | 10 |
| 凤形股份 | 002760 | 小金属 | 铟/锌/银回收深加工线索 | related | - | 10 |
| 北方稀土 | 600111 | 小金属 | 稀土/战略资源交叉 | related | - | 10 |
| 华钰矿业 | 601020 | 小金属 | 锑资源 | core | - | 10 |
| 华锡有色 | 600301 | 小金属 | 锑/锡资源端 | core | - | 10 |
