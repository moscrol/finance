# 2026-06-09 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：26401.08
- **上涨家数**：3322
- **涨停 / 跌停**：130 / 9
- **容量前三行业**：1.电子(29.4%, super_capacity)、2.通信(10.1%, normal)、3.机械设备(9.0%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光刻胶 | 光刻胶 | 电子 | 168.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | MLCC | MLCC | 电子 | 152.11 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 3 | CCL | 高端CCL | 电子 | 107.0 | limit_advance_cluster、capacity_industry | 3 | 5 | 0 | missing_evidence |
| 4 | 物理AI | 物理AI | 计算机 | 101.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 5 | 共封装光学(CPO) | CPO | 电子 | 96.95 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 6 | 人形机器人 | 人形机器人 | 机械设备 | 94.4 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 7 | 数据中心 | 数据中心 | 计算机 | 91.93 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 存储芯片 | 存储芯片 | 电子 | 90.69 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 9 | PCB | PCB | 电子 | 86.37 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 10 | 商业航天 | 商业航天 | 国防军工 | 85.23 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 风电 | 风电 | 电力设备 | 84.14 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 液冷服务器 | 液冷服务器 | 电力设备 | 81.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 元件 | 电子元件 | 电子 | 81.13 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 14 | 新型工业化 | 新型工业化 | 机械设备 | 80.22 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 15 | 机器视觉 | 机器视觉 | 机械设备 | 79.28 | new_high_direction、new_high_cluster、capacity_industry | 0 | 2 | 0 | missing_concept、missing_evidence |
| 16 | 先进封装 | 先进封装 | 电子 | 79.27 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 17 | 通用设备 | 金属制品 | 机械设备 | 78.59 | new_high_direction、new_high_cluster、capacity_industry | 1 | 1 | 0 | missing_evidence |
| 18 | 氢能源 | 氢能源 | 电力设备 | 77.56 | limit_heat、new_high_direction、new_high_cluster | 5 | 4 | 1 | - |
| 19 | 半导体 | 半导体 | 电子 | 77.41 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 20 | 无人驾驶 | 无人驾驶 | 汽车 | 77.04 | limit_heat、new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 21 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 76.15 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 22 | 信创 | 信创 | 计算机 | 76.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 燃料电池 | SOFC燃料电池 | 电力设备 | 75.95 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 24 | 传感器 | 传感器 | 机械设备 | 72.55 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 25 | 数据要素 | 数据要素 | 计算机 | 72.29 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 工业母机 | 工业母机 | 机械设备 | 66.86 | new_high_direction、new_high_cluster、capacity_industry | 4 | 11 | 1 | - |
| 27 | 海峡两岸 | 海峡两岸 | 综合 | 66.64 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 28 | 英伟达 | 英伟达Rubin架构 | 电子 | 66.41 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 29 | AIGC | AIGC | 传媒 | 65.19 | new_high_direction、new_high_cluster | 5 | 5 | 1 | - |
| 30 | 6G | 6G | 通信 | 63.97 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | ChatGPT | ChatGPT | 传媒 | 63.06 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 32 | 多模态AI | 多模态AI | 计算机 | 62.64 | new_high_direction、new_high_cluster | 1 | 1 | 1 | - |
| 33 | 光刻机 | 光刻机 | 电子 | 62.38 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 34 | PET铜箔 | PET铜箔 | 电力设备 | 62.27 | limit_heat、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 35 | 长安汽车 | 长安汽车 | 汽车 | 60.49 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 36 | 通信设备 | 通信设备 | 通信 | 59.47 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 37 | 低空经济 | 低空经济 | 国防军工 | 58.2 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 2 | - |
| 38 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 57.86 | new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 39 | 钠离子电池 | 储能 | 电力设备 | 57.43 | new_high_direction、new_high_cluster | 5 | 9 | 0 | missing_evidence |
| 40 | 大飞机 | 大飞机 | 国防军工 | 56.11 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 机器人 | 机器人 | 机械设备 | 56.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 42 | 云计算 | 云计算 | 计算机 | 55.91 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 特高压 | 特高压 | 电力设备 | 53.6 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 电子化学品 | 电子化学品 | 基础化工 | 52.81 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 45 | IT服务 | IT服务 | 计算机 | 52.15 | new_high_direction、new_high_cluster | 5 | 7 | 1 | - |
| 46 | 超级电容 | 超级电容 | 电力设备 | 51.3 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 毫米波雷达 | 毫米波雷达 | 汽车 | 49.1 | new_high_direction、new_high_cluster | 5 | 11 | 1 | - |
| 48 | 可控核聚变 | 可控核聚变 | 电力设备 | 47.53 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 49 | 氟化工 | 氟化工 | 基础化工 | 45.95 | new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 50 | 量子科技 | 量子科技 | 计算机 | 45.58 | new_high_direction、new_high_cluster | 2 | 7 | 1 | - |

## 五、核心候选明细

## 候选 1：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：168.95
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.14%，边际量 10.2%，成交额 652.19 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.14%，边际量10.2%，成交652.19亿 |
| new_high_direction | 42.95 | 新高股9只，新高成交187.91000000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光刻胶 | 10 |
| EUV光刻胶 | 5 |
| g线光刻胶 | 5 |
| i线光刻胶 | 5 |
| 光刻胶树脂 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万润股份 | 002643 | 光刻胶 | 光刻胶上游材料潜在相关 | related | L1 | 10 |
| 上海新阳 | 300236 | 光刻胶 | 产业链供应商 | related | L2_candidate | 10 |
| 中芯国际 | 688981 | 光刻胶 | 2025 年国内 12 英寸晶圆产能同比增长 25%，带动成熟制程光刻胶... | peripheral | L1_L3_candidate | 10 |
| 八亿时空 | 688181 | 光刻胶 | 百吨级KrF高端光刻胶配方树脂国产化自主突破及生产平台 | related | L1 | 10 |
| 华特气体 | 688268 | 光刻胶 | 上游材料 | peripheral | graph_only | 10 |
| 南大光电 | 300346 | 光刻胶 | 高端193nm ArF光刻胶及配套底漆、电子特气与高纯MO源核心攻坚大厂 | core | L1 | 10 |
| 容大感光 | 300576 | 光刻胶 | 光刻胶相关产品/材料供应商 | related | L2 | 10 |
| 广信材料 | 300537 | 光刻胶 | 光刻胶相关产品/材料供应商 | related | L2 | 10 |

## 候选 2：MLCC

- **标准概念**：MLCC
- **申万一级**：电子
- **评分**：152.11
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.76%，边际量 29.66%，成交额 957.19 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.76%，边际量29.66%，成交957.19亿 |
| new_high_direction | 34.11 | 新高股3只，新高成交152.92000000000002亿，容量前三=True |
| new_high_cluster | 18.0 | 题材内新高股3只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MLCC | 10 |
| MLCC微型化 | 5 |
| MLCC材料 | 5 |
| MLCC镍粉 | 5 |
| 高阶MLCC | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 博杰股份 | 002975 | MLCC | 电子测试与自动化设备供应商，覆盖AI服务器测试、液冷方案、MLCC测试分... | related | L1_L3_candidate | 10 |
| 国瓷材料 | 300285 | MLCC | 上游材料/电子陶瓷与固态电解质 | related | L3_candidate | 10 |
| 洁美科技 | 002859 | MLCC | MLCC用离型膜供应商，拟拓展离子束抛光等超精密加工设备 | related | L1_L3_candidate | 10 |
| 风华高科 | 000636 | MLCC | MLCC、片式电阻器、电感器等被动元器件供应商，拓展AI服务器与车规电子... | related | L1_L3_candidate | 10 |
| 博迁新材 | 605376 | MLCC材料 | 全球MLCC（多层陶瓷电容器）内电极用纳米级超细镍粉绝对破局和保供垄断巨... | peripheral | graph_only | 10 |
| 三环集团 | 300408 | 高阶MLCC | MLCC/被动元件潜在相关 | related | L1 | 10 |
| 火炬电子 | 603678 | 高阶MLCC | 图谱弱关联 | peripheral | graph_only | 10 |
| 鸿远电子 | 603267 | 高阶MLCC | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 3：CCL

- **标准概念**：高端CCL
- **申万一级**：电子
- **评分**：107.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（5），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 高端CCL | 5 |
| PCB钻针 | 2 |
| SST | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 沪电股份 | 002463 | 1.6T交换机PCB | 高端PCB | peripheral | L1_L3_candidate | 1 |
| 南亚新材 | 688519 | AI服务器 | 高端覆铜板(CCL)厂商，M6-M9高速材料切入AI服务器算力链 | related | L1_L3_candidate | 1 |
| 德福科技 | 301511 | AI服务器 | 电子电路铜箔企业，签署高端铜箔合作意向书 | related | L1_L3_candidate | 1 |
| 华正新材 | 603186 | PCB | 高多层PCB板核心上游基板——环氧玻纤布覆铜板及高频高速CCL材料商 | core | L1 | 1 |
| 圣泉集团 | 605589 | 特种树脂 | 全球酚醛树脂巨头、国内先进制程绿色环氧塑封料与CCL高频高速覆铜板用高纯... | core | L1 | 1 |

## 候选 4：物理AI

- **标准概念**：物理AI
- **申万一级**：计算机
- **评分**：101.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 101.0 | 连板股3只，最高3板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 物理AI | 10 |
| AIGC | 2 |
| AI大模型 | 2 |
| AI智能体产业链 | 2 |
| AI眼镜产业链 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万丰奥威 | 002085 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 三花智控 | 002050 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 中信海直 | 000099 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 中大力德 | 002896 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 中航光电 | 002179 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 光威复材 | 300699 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 凡拓数创 | 301313 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |
| 卫宁健康 | 300253 | 物理AI | 市场信号弱关联 | related | L2_candidate | 10 |

## 候选 5：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：96.95
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 63.45 | 新高股17只，新高成交1075.72亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比7.69，排名23 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |
| CPO（共封装光学） | 10 |
| CPO微透镜与高功率CW光源 | 5 |
| 6G产业 | 2 |
| MPO光纤连接器 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光莆股份 | 300632 | CPO | 共封装光学（CPO）新型光引擎精密光电对准封测代工商 | related | L2_candidate | 11 |
| Coherent（COHR） | - | CPO | 菊东光客户，光器件供应商 | peripheral | L1 | 10 |
| 东山精密 | 002384 | CPO | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 东材科技 | 601208 | CPO | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 中芯国际 | 688981 | CPO | 光通信电芯片代工与制造受益名单 | peripheral | graph_only | 10 |
| 中际旭创 | 300308 | CPO | 光通信芯片与半导体激光芯片供应商 | related | L1_L3_candidate | 10 |
| 乾照光电 | 300102 | CPO | 光通信/CPO用光电感测及芯片潜在研发送样方 | peripheral | L1 | 10 |
| 亨通光电 | 600487 | CPO | 市场信号弱关联 | related | L2_candidate | 10 |

## 候选 6：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：94.4
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 58.8 | 新高股26只，新高成交703.5999999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比12.31，排名11 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人形机器人 | 10 |
| MIM金属注射成型 | 2 |
| PEEK材料 | 2 |
| 传感器 | 2 |
| 固态电池 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三花智控 | 002050 | 人形机器人 | 热管理及执行器供应商，特斯拉V3产业链标的 | peripheral | L1 | 10 |
| 中大力德 | 002896 | 人形机器人 | 机器人核心零部件供应商 | related | L2 | 10 |
| 中研股份 | 688716 | 人形机器人 | 机器人关节轻量化PEEK材料潜在供应商 | related | L1 | 10 |
| 丰立智能 | 301368 | 人形机器人 | 减速器 | core | - | 10 |
| 亿嘉和 | 603666 | 人形机器人 | 基础业务暴露 | related | L2 | 10 |
| 信质集团 | 002704 | 人形机器人 | 全T链 | core | - | 10 |
| 光威复材 | 300699 | 人形机器人 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 北特科技 | 603009 | 人形机器人 | 丝杠 | core | - | 10 |

## 候选 7：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：91.93
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.18 | 新高股22只，新高成交1054.54亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 12.75 | 涨停25只，市场占比19.23，排名6 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 10 |
| AI数据中心储能 | 5 |
| 数据中心交换机 | 5 |
| 数据中心供电 | 5 |
| 数据中心液冷 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | 数据中心 | 数据中心光模块产品供应商 | related | L1 | 10 |
| 东阳光 | 600673 | 数据中心 | OpenClaw算力链与国产算力/华为系/字节系受益名单 | peripheral | graph_only | 10 |
| 中天科技 | 600522 | 数据中心 | 数据中心光纤光缆和空芯光纤受益名单公司 | peripheral | graph_only | 10 |
| 中恒电气 | 002364 | 数据中心 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 中电鑫龙 | 002298 | 数据中心 | 智能配电和智慧用能潜在硬件配套供应商 | related | L1 | 10 |
| 中科曙光 | 603019 | 数据中心 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 中航光电 | 002179 | 数据中心 | AI服务器液冷连接与组件相关受益名单公司 | peripheral | graph_only | 10 |
| 中际旭创 | 300308 | 数据中心 | 4.4 光模块领域核心上市公司 | peripheral | L1 | 10 |

## 候选 8：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：90.69
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 56.84 | 新高股15只，新高成交627.2900000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比8.46，排名21 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 存储芯片 | 10 |
| HBM（高带宽存储） | 2 |
| 先进封装 | 2 |
| 半导体 | 2 |
| 半导体材料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士（000660.KS） | 000660 | 存储芯片 | 图谱弱关联 | peripheral | graph_only | 10 |
| 上峰水泥 | 000672 | 存储芯片 | 股权投资潜在相关 | peripheral | L2_candidate | 10 |
| 上海合晶 | 688584 | 存储芯片 | 存储晶圆制造上游硅片材料潜在供应商 | peripheral | L2_candidate | 10 |
| 东芯股份 | 688110 | 存储芯片 | 中小容量通用型存储芯片设计商 | core | L2_candidate | 10 |
| 中微公司 | 688012 | 存储芯片 | 上游设备 | peripheral | L1 | 10 |
| 中科飞测 | 688361 | 存储芯片 | 存储晶圆制造量检测设备供应商 | related | L2_candidate | 10 |
| 中船特气 | 688146 | 存储芯片 | 存储芯片扩产关键特气材料供应商 | related | L2_candidate | 10 |
| 中芯国际 | 688981 | 存储芯片 | 芯片/核心器件 | peripheral | L1_L3_candidate | 10 |

## 候选 9：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：86.37
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.37 | 新高股26只，新高成交829.7400000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 10 |
| PCB印制电路板 | 5 |
| PCB概念 | 5 |
| PCB油墨 | 5 |
| PCB钻针 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 世运电路 | 603920 | PCB | 印制电路板生产商 | core | L1 | 10 |
| 东威科技 | 688700 | PCB | PCB电镀设备、复合集流体水电镀设备及先进封装电镀线供应商 | related | L1_L3_candidate | 10 |
| 东山精密 | 002384 | PCB | 光模块/光芯片与高多层AI PCB/HDI供应商，通过索尔思和Multe... | related | L1_L3_candidate | 10 |
| 东材科技 | 601208 | PCB | 覆铜板上游电子材料潜在供应商 | related | L2_candidate | 10 |
| 中国巨石 | 600176 | PCB | 上游材料 | related | L2_candidate | 10 |
| 中富电路 | 300814 | PCB | PCB研发生产销售企业 | core | L1 | 10 |
| 中金岭南 | 000060 | PCB | 参股PCB高端钻针生产商 | peripheral | L2_candidate | 10 |
| 中钨高新 | 000657 | PCB | PCB钻针/耗材链受益名单 | peripheral | graph_only | 10 |

## 候选 10：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：85.23
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 49.63 | 新高股21只，新高成交770.66亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比12.31，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| 低轨卫星星座 | 2 |
| 卫星产业 | 2 |
| 电磁弹射 | 2 |
| 航天装备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 10 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 10 |
| 中国卫通 | 601698 | 商业航天 | 卫星通信运营商 | peripheral | L2 | 10 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 商业航天 | 商业航天高性能碳纤维本土供应商，推进卫星端验证 | related | L1_L3_candidate | 10 |
| 中科星图 | 688568 | 商业航天 | 卫星互联网/太空算力 | core | - | 10 |
| 中集集团 | 000039 | 商业航天 | 模块化/预制化数据中心与海工、航天储罐高端装备制造交付商 | related | L1_L3_candidate | 10 |
