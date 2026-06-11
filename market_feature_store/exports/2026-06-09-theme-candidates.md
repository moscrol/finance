# 2026-06-09 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：26401.08
- **上涨家数**：3322
- **涨停 / 跌停**：130 / 9
- **容量前三行业**：1.电子(29.4%, super_capacity)、2.通信(10.1%, normal)、3.机械设备(9.0%, normal)

## 二、候选总览

| 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 光刻胶 | 光刻胶 | 电子 | 168.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| MLCC | MLCC | 电子 | 152.11 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 9 | 1 |
| CCL | 高端CCL | 电子 | 107.0 | limit_advance_cluster、capacity_industry | 3 | 5 | 0 |
| 物理AI | 物理AI | 计算机 | 101.0 | limit_advance_cluster | 5 | 12 | 1 |
| 共封装光学(CPO) | CPO | 电子 | 96.95 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 |
| 人形机器人 | 人形机器人 | 机械设备 | 94.4 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 |
| 数据中心 | 数据中心 | 计算机 | 91.93 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 存储芯片 | 存储芯片 | 电子 | 90.69 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| PCB | PCB | 电子 | 86.37 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 |
| 商业航天 | 商业航天 | 国防军工 | 85.23 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 |
| 风电 | 风电 | 电力设备 | 84.14 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 液冷服务器 | 液冷服务器 | 电力设备 | 81.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 元件 | 电子元件 | 电子 | 81.13 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 |
| 新型工业化 | 新型工业化 | 机械设备 | 80.22 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 |
| 机器视觉 | 机器视觉 | 机械设备 | 79.28 | new_high_direction、new_high_cluster、capacity_industry | 0 | 2 | 0 |
| 先进封装 | 先进封装 | 电子 | 79.27 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 |
| 通用设备 | 金属制品 | 机械设备 | 78.59 | new_high_direction、new_high_cluster、capacity_industry | 1 | 1 | 0 |
| 氢能源 | 氢能源 | 电力设备 | 77.56 | limit_heat、new_high_direction、new_high_cluster | 5 | 4 | 1 |
| 半导体 | 半导体 | 电子 | 77.41 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| 无人驾驶 | 无人驾驶 | 汽车 | 77.04 | limit_heat、new_high_direction、new_high_cluster | 4 | 10 | 1 |
| 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 76.15 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 |
| 信创 | 信创 | 计算机 | 76.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 燃料电池 | SOFC燃料电池 | 电力设备 | 75.95 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 |
| 传感器 | 传感器 | 机械设备 | 72.55 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| 数据要素 | 数据要素 | 计算机 | 72.29 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 工业母机 | 工业母机 | 机械设备 | 66.86 | new_high_direction、new_high_cluster、capacity_industry | 4 | 11 | 1 |
| 海峡两岸 | 海峡两岸 | 综合 | 66.64 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 |
| 英伟达 | 英伟达Rubin架构 | 电子 | 66.41 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 |
| AIGC | AIGC | 传媒 | 65.19 | new_high_direction、new_high_cluster | 5 | 5 | 1 |
| 6G | 6G | 通信 | 63.97 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| ChatGPT | ChatGPT | 传媒 | 63.06 | new_high_direction、new_high_cluster | 0 | 0 | 0 |
| 多模态AI | 多模态AI | 计算机 | 62.64 | new_high_direction、new_high_cluster | 1 | 1 | 1 |
| 光刻机 | 光刻机 | 电子 | 62.38 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| PET铜箔 | PET铜箔 | 电力设备 | 62.27 | limit_heat、new_high_direction、new_high_cluster | 5 | 9 | 1 |
| 长安汽车 | 长安汽车 | 汽车 | 60.49 | new_high_direction、new_high_cluster | 0 | 0 | 0 |
| 通信设备 | 通信设备 | 通信 | 59.47 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| 低空经济 | 低空经济 | 国防军工 | 58.2 | limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 2 |
| 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 57.86 | new_high_direction、new_high_cluster | 0 | 4 | 0 |
| 钠离子电池 | 储能 | 电力设备 | 57.43 | new_high_direction、new_high_cluster | 5 | 9 | 0 |
| 大飞机 | 大飞机 | 国防军工 | 56.11 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 机器人 | 机器人 | 机械设备 | 56.0 | limit_advance_cluster、new_high_cluster、capacity_industry | 5 | 12 | 1 |
| 云计算 | 云计算 | 计算机 | 55.91 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 特高压 | 特高压 | 电力设备 | 53.6 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 电子化学品 | 电子化学品 | 基础化工 | 52.81 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| IT服务 | IT服务 | 计算机 | 52.15 | new_high_direction、new_high_cluster | 5 | 7 | 1 |
| 超级电容 | 超级电容 | 电力设备 | 51.3 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 毫米波雷达 | 毫米波雷达 | 汽车 | 49.1 | new_high_direction、new_high_cluster | 5 | 11 | 1 |
| 可控核聚变 | 可控核聚变 | 电力设备 | 47.53 | new_high_direction、new_high_cluster | 5 | 12 | 1 |
| 氟化工 | 氟化工 | 基础化工 | 45.95 | new_high_direction、new_high_cluster | 5 | 9 | 1 |
| 量子科技 | 量子科技 | 计算机 | 45.58 | new_high_direction、new_high_cluster | 2 | 7 | 1 |

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

## 候选 11：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：84.14
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 49.59 | 新高股21只，新高成交767.5400000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比10.0，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电 | 10 |
| 海上风电 | 5 |
| 深远海风电 | 5 |
| 漂浮式风电 | 5 |
| 陆上风电 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 海上风电 | 中游制造 | core | L1_L3_candidate | 10 |
| 东方电缆 | 603606 | 海上风电 | 5.2.3 海缆系统企业 | core | L1_L3_candidate | 10 |
| 中信海直 | 000099 | 海上风电 | 海上风电通航服务潜在相关 | related | L1 | 10 |
| 中天科技 | 600522 | 海上风电 | 5.2.3 海缆系统企业 | related | L1_L3_candidate | 10 |
| 亨通光电 | 600487 | 海上风电 | 3.4 海缆系统环节 | related | L1_L3_candidate | 10 |
| 中材科技 | 002080 | 风电 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 大金重工 | 002487 | 风电 | 海上风电塔筒/基础及出口海工装备供应商，具备欧洲项目交付和海工运输能力 | related | L3 | 10 |
| 天顺风能 | 002531 | 风电 | 产业链供应商 | related | L1_L3_candidate | 10 |

## 候选 12：液冷服务器

- **标准概念**：液冷服务器
- **申万一级**：电力设备
- **评分**：81.55
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 47.0 | 新高股14只，新高成交751.8亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比10.0，排名15 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 液冷服务器 | 10 |
| AI服务器 | 2 |
| AI服务器电源 | 2 |
| AI算力 | 2 |
| AI超节点 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三花智控 | 002050 | 液冷服务器 | 产业链供应商 | peripheral | L1 | 10 |
| 东阳光 | 600673 | 液冷服务器 | AI算力液冷组件、SST智能直流供电核心电容及AIDC运营闭环平台 | related | L1_L3_candidate | 10 |
| 中兴通讯 | 000063 | 液冷服务器 | 液冷服务器整机厂商待核验 | peripheral | L1 | 10 |
| 中石科技 | 300684 | 液冷服务器 | 导热/屏蔽材料配套供应商 | peripheral | L2 | 10 |
| 中科曙光 | 603019 | 液冷服务器 | 浸没式液冷服务器/算力中心液冷基础设施供应商 | related | L1_L3_candidate | 10 |
| 中航光电 | 002179 | 液冷服务器 | AI服务器液冷连接与组件相关受益名单公司 | peripheral | graph_only | 10 |
| 冰轮环境 | 000811 | 液冷服务器 | AIDC液冷一次侧冷水机组/压缩机国产替代受益名单 | peripheral | graph_only | 10 |
| 南风股份 | 300004 | 液冷服务器 | CDU/Manifold/冷板/UQD等液冷零部件相关标的 | peripheral | graph_only | 10 |

## 候选 13：元件

- **标准概念**：电子元件
- **申万一级**：电子
- **评分**：81.13
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 48.33 | 新高股11只，新高成交394.23亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比6.15，排名27 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元件 | 5 |
| 磁性元件 | 5 |
| 被动元件 | 5 |
| AI硬件 | 2 |
| OCS光电路交换机产业链 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | 电子元件 | 电子元件和基础材料生产商 | core | L1 | 10 |
| 博迁新材 | 605376 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 国瓷材料 | 300285 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 洁美科技 | 002859 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 深圳华强 | 000062 | 电子元件 | 半导体授权分销/边缘AI计算系统 | peripheral | L1_L3_candidate | 10 |
| 火炬电子 | 603678 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |
| 铜冠铜箔 | 301217 | 电子元件 | 市场信号弱关联 | related | L2_candidate | 10 |
| 风华高科 | 000636 | 电子元件 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 14：新型工业化

- **标准概念**：新型工业化
- **申万一级**：机械设备
- **评分**：80.22
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.22 | 新高股17只，新高成交337.34000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 15：机器视觉

- **标准概念**：机器视觉
- **申万一级**：机械设备
- **评分**：79.28
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（2），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.28 | 新高股16只，新高成交262.61000000000007亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 宇瞳光学 | 300790 | 机器视觉 | 机器视觉相关产品/材料供应商 | related | L2 | 10 |
| 联创电子 | 002036 | 集成电路 | 集成电路相关产品/材料供应商 | related | L2 | 1 |

## 候选 16：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：79.27
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 46.12 | 新高股10只，新高成交329.65000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比6.92，排名25 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 先进封装 | 10 |
| AI芯片 | 2 |
| CANN（华为昇腾异构计算架构） | 2 |
| CPO（共封装光学） | 2 |
| GPU（图形处理器） | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 上峰水泥 | 000672 | 先进封装 | 投资潜在相关（非直接产业链） | peripheral | L2_candidate | 10 |
| 上海新阳 | 300236 | 先进封装 | 先进封装用电镀液及添加剂供应商 | related | L1 | 10 |
| 东威科技 | 688700 | 先进封装 | PCB电镀设备、复合集流体水电镀设备及先进封装电镀线供应商 | related | L1_L3_candidate | 10 |
| 中国巨石 | 600176 | 先进封装 | 先进封装上游高端电子布潜在相关 | peripheral | L2_candidate | 10 |
| 中微公司 | 688012 | 先进封装 | 先进封装刻蚀/薄膜沉积设备供应商 | peripheral | L2_candidate | 10 |
| 中材科技 | 002080 | 先进封装 | Low-CTE电子布供应商，AI先进封装关键材料 | peripheral | L1 | 10 |
| 中科飞测 | 688361 | 先进封装 | 先进封装硅通孔等量检测设备供应商 | related | L2_candidate | 10 |
| 京东方A | 000725 | 先进封装 | 市场信号弱关联 | peripheral | L2_candidate | 10 |

## 候选 17：通用设备

- **标准概念**：金属制品
- **申万一级**：机械设备
- **评分**：78.59
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.59 | 新高股19只，新高成交207.28000000000006亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 金属制品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东睦股份 | 600114 | 金属制品 | 金属制品制造企业 | peripheral | graph_only | 1 |

## 候选 18：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：77.56
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（4），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.66 | 新高股14只，新高成交404.84999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.9 | 涨停14只，市场占比10.77，排名13 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 氢能源 | 10 |
| SOFC燃料电池 | 2 |
| 压缩机 | 2 |
| 天然气 | 2 |
| 氢能储运 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东岳硅材 | 300821 | 氢能源 | 参股材料平台潜在相关 | peripheral | L1 | 10 |
| 阳光电源 | 300274 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 隆基绿能 | 601012 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 雪人股份 | 002639 | 氢能源 | 上游设备 | peripheral | L1 | 10 |

## 候选 19：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：77.41
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.86 | 新高股8只，新高成交292.49亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| limit_heat | 8.55 | 涨停13只，市场占比10.0，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体 | 10 |
| 功率半导体 | 5 |
| 化合物半导体 | 5 |
| 半导体IP | 5 |
| 半导体产业链 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三安光电 | 600703 | 功率半导体 | 碳化硅功率半导体材料/器件相关厂商 | peripheral | L1 | 10 |
| 华润微 | 688396 | 功率半导体 | 国内功率半导体MOSFET、IGBT及宽禁带（SiC/GaN）IDM全产... | core | L1 | 10 |
| 华虹公司 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 士兰微 | 600460 | 功率半导体 | 国内极成熟、拥有多代特色晶圆制造代工线的一流功率分立器件IDM全产业链巨... | core | L1 | 10 |
| 天岳先进 | 688234 | 功率半导体 | 弱相关，待验证 | related | L2 | 10 |
| 斯达半导 | 603290 | 功率半导体 | 功率半导体相关产品/材料供应商 | related | L2 | 10 |
| 晶升股份 | 688478 | 功率半导体 | 核心设备及产品供应商 | related | L2_candidate | 10 |
| 晶盛机电 | 300316 | 功率半导体 | 首条12寸碳化硅衬底中试线，SiC设备龙头 | peripheral | L1 | 10 |

## 候选 20：无人驾驶

- **标准概念**：无人驾驶
- **申万一级**：汽车
- **评分**：77.04
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（10），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.84 | 新高股14只，新高成交418.82亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比9.23，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 无人驾驶 | 10 |
| 毫米波雷达 | 2 |
| 车路协同产业 | 2 |
| 高精地图 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万集科技 | 300552 | 无人驾驶 | 激光雷达/MEMS固态雷达供应商，适配城市NOA与L4客车场景 | related | L1_L3_candidate | 10 |
| 保隆科技 | 603197 | 无人驾驶 | 毫米波雷达与汽车传感器供应商 | related | L2_candidate | 10 |
| 千里科技 | 601777 | 无人驾驶 | Robotaxi闭环平台服务商 | related | L1_L3_candidate | 10 |
| 四维图新 | 002405 | 无人驾驶 | 高精地图与智能驾驶数据服务商 | related | L1_L3_candidate | 10 |
| 富临运业 | 002357 | 无人驾驶 | 公路客运运营商，与新石器合营切入L4无人驾驶物流，布局四川文旅低空物流 | related | L1_L3_candidate | 10 |
| 德赛西威 | 002920 | 无人驾驶 | 智能驾驶域控制器供应商 | related | L1_L3_candidate | 10 |
| 拓普集团 | 601689 | 无人驾驶 | 智能底盘供应商 | peripheral | L1 | 10 |
| 比亚迪 | 002594 | 无人驾驶 | 新能源汽车整车厂商与智能驾驶车型应用方 | peripheral | L1 | 10 |

## 候选 21：光纤

- **标准概念**：AI算力驱动下的MPO光纤连接器产业
- **申万一级**：通信
- **评分**：76.15
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 50.15 | 新高股9只，新高成交764.19亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI算力驱动下的MPO光纤连接器产业 | 5 |
| G.654.E光纤 | 5 |
| MPO光纤连接器 | 5 |
| 光纤光缆 | 5 |
| 光纤通信 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | AI算力驱动下的MPO光纤连接器产业 | 4.4 国产替代进程分析 | peripheral | graph_only | 10 |
| 仕佳光子 | 688313 | AI算力驱动下的MPO光纤连接器产业 | 2025 年净利润预计 4.77-5.1 亿元，对应 PE 约 33 倍 | peripheral | graph_only | 10 |
| 光库科技 | 300620 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 博创科技 | 300548 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 太辰光 | 300570 | AI算力驱动下的MPO光纤连接器产业 | 3.2.1 太辰光（300570） | peripheral | graph_only | 10 |
| 亨通光电 | 600487 | 光纤 | 光纤光缆及数据中心互联光纤供应商 | related | L1_L3_candidate | 10 |
| 长飞光纤 | 601869 | 光纤 | 光纤光缆及新型光纤产品供应商 | related | L1_L3_candidate | 10 |
| 中天科技 | 600522 | 光纤光缆 | 数据中心光纤光缆和空芯光纤受益名单公司 | peripheral | graph_only | 10 |

## 候选 22：信创

- **标准概念**：信创
- **申万一级**：计算机
- **评分**：76.1
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.25 | 新高股15只，新高成交259.65999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比8.46，排名22 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 信创 | 10 |
| 信创产业 | 5 |
| 金融信创 | 5 |
| FPGA | 2 |
| IT服务 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三六零 | 601360 | 信创 | 信创安全防护潜在参与方 | related | L1 | 10 |
| 中国软件 | 600536 | 信创 | 党政信创基础软件和解决方案平台 | core | L1 | 10 |
| 中国长城 | 000066 | 信创 | 信创整机和计算设备供应商 | core | L1 | 10 |
| 中望软件 | 688083 | 信创 | 国产工业软件替代潜在参与者 | related | L1 | 10 |
| 优刻得 | 688158 | 信创 | 中立云计算与国产化适配云平台 | core | L1 | 10 |
| 佰维存储 | 688525 | 信创 | 国产整机和服务器存储模块厂商 | core | L1 | 10 |
| 品高股份 | 688227 | 信创 | 图谱弱关联 | peripheral | graph_only | 10 |
| 恒生电子 | 600570 | 信创 | 产业链供应商 | peripheral | graph_only | 10 |

## 候选 23：燃料电池

- **标准概念**：SOFC燃料电池
- **申万一级**：电力设备
- **评分**：75.95
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.15 | 新高股15只，新高成交332.26亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比6.15，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| SOFC燃料电池 | 5 |
| SOFC（固体氧化物燃料电池） | 5 |
| 固体氧化物燃料电池(SOFC) | 5 |
| 储能电池 | 2 |
| 家电零部件 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | SOFC（固体氧化物燃料电池） | 陶瓷材料与零部件潜在相关 | peripheral | L1 | 20 |
| 三花智控 | 002050 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国巨石 | 600176 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国船舶 | 600150 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中材科技 | 002080 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中航光电 | 002179 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 京东方A | 000725 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 亿纬锂能 | 300014 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 24：传感器

- **标准概念**：传感器
- **申万一级**：机械设备
- **评分**：72.55
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 46.55 | 新高股11只，新高成交251.76000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 传感器 | 10 |
| AI传感器 | 5 |
| MEMS传感器 | 5 |
| ToF传感器 | 5 |
| 压力传感器 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华域汽车 | 600741 | 传感器 | 图谱弱关联 | peripheral | graph_only | 10 |
| 华润微 | 688396 | 传感器 | 图谱弱关联 | peripheral | graph_only | 10 |
| 士兰微 | 600460 | 传感器 | 4.2 相关业务布局公司分析 | peripheral | graph_only | 10 |
| 奥比中光 | 688322 | 传感器 | 物理agent传感器受益名单 | peripheral | graph_only | 10 |
| 安培龙 | 301413 | 传感器 | 传感器相关产品/材料供应商 | related | L2 | 10 |
| 敏芯股份 | 688286 | 传感器 | 传感器相关产品/材料供应商 | related | L2 | 10 |
| 晶华新材 | 603683 | 传感器 | 物理agent传感器受益名单 | peripheral | graph_only | 10 |
| 晶方科技 | 603005 | 传感器 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 25：数据要素

- **标准概念**：数据要素
- **申万一级**：计算机
- **评分**：72.29
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 46.29 | 新高股18只，新高成交502.96999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据要素 | 10 |
| AI智能体 | 2 |
| 新型城镇化 | 2 |
| 液冷 | 2 |
| 金融科技 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科曙光 | 603019 | 数据要素 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 太极股份 | 002368 | 数据要素 | 下游应用 | related | L1_L3_candidate | 10 |
| 奥飞数据 | 300738 | 数据要素 | 4.1 数据基础设施类上市公司 | related | L1_L3_candidate | 10 |
| 居然智家 | 000785 | 数据要素 | 空间AI设计平台 | peripheral | L1_L3_candidate | 10 |
| 恒生电子 | 600570 | 数据要素 | 下游应用 | peripheral | L1 | 10 |
| 拓尔思 | 300229 | 数据要素 | 图谱弱关联 | peripheral | graph_only | 10 |
| 数字政通 | 300075 | 数据要素 | 图谱弱关联 | peripheral | graph_only | 10 |
| 易华录 | 300212 | 数据要素 | 下游应用 | peripheral | L1 | 10 |

## 候选 26：工业母机

- **标准概念**：工业母机
- **申万一级**：机械设备
- **评分**：66.86
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（11），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 40.86 | 新高股8只，新高成交132.89000000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 工业母机 | 10 |
| 工业自动化 | 2 |
| 数控机床 | 2 |
| 注塑机 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 伊之密 | 300415 | 工业母机 | 金属压铸及塑料注射成型高端母机装备制造大厂 | peripheral | graph_only | 10 |
| 创世纪 | 300083 | 工业母机 | 中游制造 | peripheral | L1 | 10 |
| 华中数控 | 300161 | 工业母机 | 中游制造 | related | L2_candidate | 10 |
| 华锐精密 | 688059 | 工业母机 | 钨价上涨和国产刀具替代受益名单 | peripheral | graph_only | 10 |
| 国盛智科 | 688558 | 工业母机 | 中游制造 | related | L1_L3_candidate | 10 |
| 大族激光 | 002008 | 工业母机 | 紫外及超快激光器供应商/运营商 | related | L2 | 10 |
| 新锐股份 | 688257 | 工业母机 | 钨价上涨和国产刀具替代受益名单 | peripheral | graph_only | 10 |
| 汇川技术 | 300124 | 工业母机 | 产业链供应商 | related | L1_L3_candidate | 10 |

## 候选 27：海峡两岸

- **标准概念**：海峡两岸
- **申万一级**：综合
- **评分**：66.64
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 32.44 | 新高股9只，新高成交147.23999999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| limit_heat | 8.2 | 涨停12只，市场占比9.23，排名19 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 28：英伟达

- **标准概念**：英伟达Rubin架构
- **申万一级**：电子
- **评分**：66.41
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 40.41 | 新高股7只，新高成交208.9亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 英伟达Rubin架构 | 5 |
| 6G产业 | 2 |
| AI硬件 | 2 |
| AI算力驱动下的交换机产业 | 2 |
| HBM | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中际旭创 | 300308 | 英伟达 | 产业链供应商 | peripheral | L2_candidate | 10 |
| 华工科技 | 000988 | 英伟达 | 上游材料 | peripheral | L1 | 10 |
| 工业富联 | 601138 | 英伟达 | 芯片/核心器件 | core | L2_candidate | 10 |
| 新易盛 | 300502 | 英伟达 | 产业链供应商 | peripheral | L1 | 10 |
| 沪电股份 | 002463 | 英伟达 | 产业链供应商 | core | L2_candidate | 10 |
| 浪潮信息 | 000977 | 英伟达 | 下游应用 | peripheral | L1_L3_candidate | 10 |
| 生益科技 | 600183 | 英伟达 | 6.4 投资策略建议 | peripheral | L1 | 10 |
| 胜宏科技 | 300476 | 英伟达 | 产业链供应商 | core | L2_candidate | 10 |

## 候选 29：AIGC

- **标准概念**：AIGC
- **申万一级**：传媒
- **评分**：65.19
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（5），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 39.19 | 新高股13只，新高成交239.19亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AIGC | 10 |
| AI+办公 | 2 |
| AI+生物医药 | 2 |
| AI-RAN | 2 |
| AIoT | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万兴科技 | 300624 | AIGC | AI漫剧/短剧创作工具「万兴剧厂」开发商，数字创意软件厂商 | related | L1_L3_candidate | 10 |
| 昆仑万维 | 300418 | AIGC | AIGC相关产品/材料供应商 | related | L2 | 10 |
| 海天瑞声 | 688787 | AIGC | 图谱弱关联 | peripheral | graph_only | 10 |
| 金山办公 | 688111 | AIGC | 图谱弱关联 | peripheral | graph_only | 10 |
| 智微智能 | 001339 | AI服务器 | ICT基础设施和算力服务供应商，拓展LPU推理芯片生态、AIGC算力基础... | related | L1_L3_candidate | 1 |

## 候选 30：6G

- **标准概念**：6G
- **申万一级**：通信
- **评分**：63.97
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.97 | 新高股5只，新高成交557.48亿，容量前三=True |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 6G | 10 |
| 5G_6G | 5 |
| 5G_6G融合 | 5 |
| 5G_6G通信 | 5 |
| 6G产业 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万丰奥威 | 002085 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |
| 三安光电 | 600703 | 6G | 6G前置射频器件潜在相关 | peripheral | L1 | 10 |
| 东方财富 | 300059 | 6G | 证券业务、金融电子商务服务业务、金融数据服务业务研发/生产商 | related | L2 | 10 |
| 中信海直 | 000099 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |
| 中兴通讯 | 000063 | 6G | 6G前置技术和主设备映射 | related | L2_candidate | 10 |
| 中国卫通 | 601698 | 6G | 空天地一体化前置卫星通信环节 | related | L1 | 10 |
| 中国移动 | 600941 | 6G | 6G网络架构和场景牵引方 | related | L2_candidate | 10 |
| 中瓷电子 | 003031 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 31：ChatGPT

- **标准概念**：ChatGPT
- **申万一级**：传媒
- **评分**：63.06
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 37.06 | 新高股12只，新高成交180.62亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 32：多模态AI

- **标准概念**：多模态AI
- **申万一级**：计算机
- **评分**：62.64
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（1），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 36.64 | 新高股12只，新高成交146.86亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 多模态AI | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 彩讯股份 | 300634 | 多模态AI | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 33：光刻机

- **标准概念**：光刻机
- **申万一级**：电子
- **评分**：62.38
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 38.38 | 新高股6只，新高成交158.27亿，容量前三=True |
| new_high_cluster | 24.0 | 题材内新高股6只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光刻机 | 10 |
| 电子束光刻机 | 5 |
| 电子束光刻机产业 | 5 |
| AI端侧 | 2 |
| DUV光刻 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凯美特气 | 002549 | 光刻机 | 图谱弱关联 | peripheral | graph_only | 10 |
| 北方华创 | 002371 | 光刻机 | 上游设备 | peripheral | graph_only | 10 |
| 晶方科技 | 603005 | 光刻机 | 图谱弱关联 | peripheral | graph_only | 10 |
| 波长光电 | 301136 | 光刻机 | 图谱弱关联 | peripheral | graph_only | 10 |
| 电科数字 | 600850 | 光刻机 | 市场信号弱关联 | related | L2_candidate | 10 |
| 福晶科技 | 002222 | 光刻机 | 上游材料 | peripheral | graph_only | 10 |
| 芯碁微装 | 688630 | 光刻机 | 下游应用 | peripheral | graph_only | 10 |
| 茂莱光学 | 688502 | 光刻机 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 34：PET铜箔

- **标准概念**：PET铜箔
- **申万一级**：电力设备
- **评分**：62.27
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.47 | 新高股6只，新高成交405.93亿，容量前三=False |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| limit_heat | 6.8 | 涨停8只，市场占比6.15，排名29 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PET铜箔 | 10 |
| PET基复合铜箔 | 2 |
| 固态电池 | 2 |
| 复合铜箔 | 2 |
| 水电镀设备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万顺新材 | 300057 | PET铜箔 | 复合铜箔材料潜在参与方 | related | L1 | 10 |
| 东威科技 | 688700 | PET铜箔 | 上游设备 | core | L1 | 10 |
| 中一科技 | 301150 | PET铜箔 | 中游制造/服务 | peripheral | graph_only | 10 |
| 先导智能 | 300450 | PET铜箔 | 上游设备 | peripheral | graph_only | 10 |
| 双星新材 | 002585 | PET铜箔 | 图谱弱关联 | peripheral | graph_only | 10 |
| 嘉元科技 | 688388 | PET铜箔 | 图谱弱关联 | peripheral | graph_only | 10 |
| 英联股份 | 002846 | PET铜箔 | 中游制造/服务 | peripheral | graph_only | 10 |
| 诺德股份 | 600110 | PET铜箔 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 35：长安汽车

- **标准概念**：长安汽车
- **申万一级**：汽车
- **评分**：60.49
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 34.49 | 新高股10只，新高成交199.45亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 36：通信设备

- **标准概念**：通信设备
- **申万一级**：通信
- **评分**：59.47
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 39.47 | 新高股4只，新高成交469.24亿，容量前三=True |
| new_high_cluster | 20.0 | 题材内新高股4只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 通信设备 | 10 |
| 5G通信 | 2 |
| AI-RAN | 2 |
| 低空经济 | 2 |
| 光纤光缆 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | 通信设备 | 通信设备组件和光模块供应商 | related | L1 | 10 |
| 中兴通讯 | 000063 | 通信设备 | 通信网络设备及器件供应商 | core | L2_candidate | 10 |
| 信科移动 | 688387 | 通信设备 | 无线网络5G-A宏基站及核心网网络整机制造商 | core | L1 | 10 |
| 意华股份 | 002897 | 通信设备 | 通讯连接器产品相关产品供应商 | related | L2 | 10 |
| 烽火通信 | 600498 | 通信设备 | 通信系统设备相关产品供应商 | related | L2 | 10 |
| 锐捷网络 | 301165 | 通信设备 | 市场信号弱关联 | related | L2_candidate | 10 |
| 大为股份 | 002213 | ABF载板 | 半导体存储器、通信设备、计算机及其他电子设备、新能源材料、汽车缓速器、房... | related | L2 | 1 |
| 德科立 | 688205 | 光器件 | 光通信设备与模块企业，布局DCI、光引擎、光收发模块和硅基OCS | related | L1_L3_candidate | 1 |

## 候选 37：低空经济

- **标准概念**：低空经济
- **申万一级**：国防军工
- **评分**：58.2
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 8.2 | 涨停12只，市场占比9.23，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 低空经济 | 10 |
| 中国低空经济 | 5 |
| eVTOL电机 | 2 |
| 无人机 | 2 |
| 深地经济 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光威复材 | 300699 | 中国低空经济 | 上游材料 | peripheral | graph_only | 10 |
| 航天彩虹 | 002389 | 中国低空经济 | 上游材料 | peripheral | graph_only | 10 |
| 万丰奥威 | 002085 | 低空经济 | 通航固定翼飞机制造平台 | related | L1 | 10 |
| 中信海直 | 000099 | 低空经济 | 通航运营服务商 | core | L1 | 10 |
| 中直股份 | 600038 | 低空经济 | 低空飞行器及民用直升机航空器供应商 | related | L1 | 10 |
| 亿航智能 | - | 低空经济 | 运营端 | core | - | 10 |
| 华设集团 | 603018 | 低空经济 | 基建/规划设计/设备 | core | - | 10 |
| 卧龙电驱 | 600580 | 低空经济 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 38：钙钛矿电池

- **标准概念**：钙钛矿电池
- **申万一级**：电力设备
- **评分**：57.86
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（4），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.86 | 新高股7只，新高成交324.7200000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方日升 | 300118 | 光伏 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 1 |
| 钧达股份 | 002865 | 光伏 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 1 |
| 中矿资源 | 002738 | 稀有金属 | 全球铷矿端资源及铷盐精细化工领域龙头 | related | L1_L3_candidate | 1 |
| 金银河 | 300619 | 稀有金属 | 锂云母全元素高值化提取，全球最大千吨级铷铯盐生产基地 | related | L1_L3_candidate | 1 |

## 候选 39：钠离子电池

- **标准概念**：储能
- **申万一级**：电力设备
- **评分**：57.43
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.43 | 新高股8只，新高成交178.3亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股8只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 储能 | 2 |
| 储能电池 | 2 |
| 动力电池 | 2 |
| 固态电池 | 2 |
| 电解液 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科电气 | 300035 | 钠离子电池 | 钠电硬碳负极及电极活性材料潜在研发布局商 | related | L1 | 10 |
| 亿纬锂能 | 300014 | 钠离子电池 | 中游制造/电池 | related | L3_candidate | 10 |
| 传艺科技 | 002866 | 钠离子电池 | 钠离子电池电芯、正负极材料及储能/动力电池系统集成全流程生产商 | related | L1 | 10 |
| 华阳股份 | 600348 | 钠离子电池 | 钠离子电池一体化（正极/负极/电芯及PACK）国内最先量产释放的战略布局... | related | L1 | 10 |
| 振华新材 | 688707 | 钠离子电池 | 钠离子电池相关产品/材料供应商 | related | L2 | 10 |
| 普利特 | 002324 | 化工 | 通用材料类相关产品供应商 | related | L2 | 1 |
| 同兴科技 | 300490 | 环保 | 环保相关产品/材料供应商 | related | L2 | 1 |
| 比亚迪 | 002594 | 电解液 | 3.3 钠离子电池电解液：新赛道竞争格局初定 | peripheral | L1 | 1 |

## 候选 40：大飞机

- **标准概念**：大飞机
- **申万一级**：国防军工
- **评分**：56.11
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 30.11 | 新高股7只，新高成交185.08亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 大飞机 | 10 |
| C919大飞机 | 5 |
| C919 | 2 |
| C929 | 2 |
| 中国低空经济 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万泽股份 | 000534 | 大飞机 | 高温合金/航空发动机材料相关企业 | peripheral | graph_only | 10 |
| 三角防务 | 300775 | 大飞机 | C919等大飞机机身及结构件大型模锻件核心供应商 | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 大飞机 | 上游材料 | related | L2_candidate | 10 |
| 中航光电 | 002179 | 大飞机 | 产业链供应商 | peripheral | L1 | 10 |
| 中航沈飞 | 600760 | 大飞机 | 民用商用大飞机机体（C919后机身、垂直尾翼）核心机体结构件供应商 | peripheral | graph_only | 10 |
| 中航西飞 | 000768 | 大飞机 | 产业链供应商 | related | L2_candidate | 10 |
| 光威复材 | 300699 | 大飞机 | 上游材料 | related | L1_L3_candidate | 10 |
| 北摩高科 | 002985 | 大飞机 | 航空刹车制动与起落架相关产品供应商，推进起落架批产交付和国产大飞机刹车盘... | related | L1_L3_candidate | 10 |

## 候选 41：机器人

- **标准概念**：机器人
- **申万一级**：机械设备
- **评分**：56.0
- **触发类型**：limit_advance_cluster、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 30.0 | 连板股1只，最高2板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 机器人 | 10 |
| AI机器人 | 5 |
| 人形机器人 | 5 |
| 外骨骼机器人 | 5 |
| 工业机器人 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中研股份 | 688716 | 人形机器人 | 机器人关节轻量化PEEK材料潜在供应商 | related | L1 | 10 |
| 丰立智能 | 301368 | 人形机器人 | 减速器 | core | - | 10 |
| 信质集团 | 002704 | 人形机器人 | 全T链 | core | - | 10 |
| 北特科技 | 603009 | 人形机器人 | 丝杠 | core | - | 10 |
| 双环传动 | 002472 | 人形机器人 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 埃夫特 | 688165 | 人形机器人 | 工业机器人整机制造及系统集成供应商 | related | L2 | 10 |
| 埃斯顿 | 002747 | 人形机器人 | 自动化核心部件及运动控制系统供应商 | related | L2 | 10 |
| 安培龙 | 301413 | 人形机器人 | 机器人传感器相关标的 | peripheral | graph_only | 10 |

## 候选 42：云计算

- **标准概念**：云计算
- **申万一级**：计算机
- **评分**：55.91
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 29.91 | 新高股7只，新高成交168.96亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股7只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 云计算 | 10 |
| ABF载板 | 2 |
| AI容器 | 2 |
| AI应用 | 2 |
| AI智能体 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国电信 | 601728 | 云计算 | 产业数字化和云网服务潜在平台 | related | L2_candidate | 10 |
| 中电鑫龙 | 002298 | 云计算 | 智慧城市信息化及云底座解决方案商 | related | L1 | 10 |
| 云赛智联 | 600602 | 云计算 | 云服务、MSP云管理平台及技术服务商 | core | L2_candidate | 10 |
| 优刻得 | 688158 | 云计算 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 协创数据 | 300857 | 云计算 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 南威软件 | 603636 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |
| 博睿数据 | 688229 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |
| 品高股份 | 688227 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 43：特高压

- **标准概念**：特高压
- **申万一级**：电力设备
- **评分**：53.6
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 31.6 | 新高股5只，新高成交528.3499999999999亿，容量前三=False |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 特高压 | 10 |
| 中国盾构机 | 2 |
| 换流变压器 | 2 |
| 换流阀 | 2 |
| 汽车板 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国西电 | 601179 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 伊戈尔 | 002922 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 佛塑科技 | 000973 | 特高压 | 国家电网特高压电容器专用高等级电工绝缘薄膜核心供应商 | peripheral | graph_only | 10 |
| 国电南瑞 | 600406 | 特高压 | 特高压/电网设备受益名单 | peripheral | graph_only | 10 |
| 宝钢股份 | 600019 | 特高压 | 3.2.1 变压器产业链分析 | related | L2_candidate | 10 |
| 平高电气 | 600312 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 思源电气 | 002028 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |
| 特变电工 | 600089 | 特高压 | 美国765kV输电扩建与高压变压器外溢需求受益名单 | peripheral | graph_only | 10 |

## 候选 44：电子化学品

- **标准概念**：电子化学品
- **申万一级**：基础化工
- **评分**：52.81
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 28.81 | 新高股6只，新高成交192.59亿，容量前三=False |
| new_high_cluster | 24.0 | 题材内新高股6只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子化学品 | 10 |
| g线光刻胶 | 2 |
| i线光刻胶 | 2 |
| 封装基板药水 | 2 |
| 推理芯片 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三孚新科 | 688359 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 上海新阳 | 300236 | 电子化学品 | 电子化学品研发生产商 | peripheral | graph_only | 10 |
| 中巨芯 | 688549 | 电子化学品 | 电子化学品供应商 | peripheral | graph_only | 10 |
| 兴福电子 | 688545 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 华特气体 | 688268 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 南大光电 | 300346 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 国瓷材料 | 300285 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 天承科技 | 688603 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |

## 候选 45：IT服务

- **标准概念**：IT服务
- **申万一级**：计算机
- **评分**：52.15
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 28.15 | 新高股6只，新高成交140.33亿，容量前三=False |
| new_high_cluster | 24.0 | 题材内新高股6只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| IT服务 | 10 |
| CANN | 2 |
| ECALL | 2 |
| IT分销 | 2 |
| IT基础设施服务 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东华软件 | 002065 | IT服务 | 行业IT服务和系统集成商 | peripheral | graph_only | 10 |
| 东方国信 | 300166 | IT服务 | 企业IT服务和系统集成商 | peripheral | graph_only | 10 |
| 东软集团 | 600718 | IT服务 | 医疗医保与政企行业软件系统集成商 | peripheral | graph_only | 10 |
| 中国软件 | 600536 | IT服务 | 党政信创基础软件与行业信息化平台 | peripheral | graph_only | 10 |
| 亚康股份 | 301017 | IT服务 | 算力设备集成销售相关产品供应商 | related | L2 | 10 |
| 荣科科技 | 300290 | IT服务 | 智慧医疗相关产品供应商 | related | L2 | 10 |
| 四方精创 | 300468 | 区块链 | 软件开发及维护供应商/运营商 | related | L2 | 1 |

## 候选 46：超级电容

- **标准概念**：超级电容
- **申万一级**：电力设备
- **评分**：51.3
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 29.3 | 新高股5只，新高成交343.59999999999997亿，容量前三=False |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 超级电容 | 10 |
| 电容 | 2 |
| 电容薄膜 | 2 |
| 电解液 | 2 |
| 铝电解电容 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三花智控 | 002050 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 东山精密 | 002384 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 东方财富 | 300059 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 东阳光 | 600673 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中兴通讯 | 000063 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中材科技 | 002080 | 超级电容 | 超级电容活性炭相关供应商 | related | L1_L3_candidate | 10 |
| 中际旭创 | 300308 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 京东方A | 000725 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |

## 候选 47：毫米波雷达

- **标准概念**：毫米波雷达
- **申万一级**：汽车
- **评分**：49.1
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（11），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 27.1 | 新高股5只，新高成交167.78亿，容量前三=False |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 毫米波雷达 | 10 |
| 传感器 | 2 |
| 光波导 | 2 |
| 均热板 | 2 |
| 安防监控 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中石科技 | 300684 | 毫米波雷达 | 4.3.2 射频器件公司 | related | L1_L3_candidate | 10 |
| 保隆科技 | 603197 | 毫米波雷达 | 4.3.3 模组集成公司 | related | L2_candidate | 10 |
| 华域汽车 | 600741 | 毫米波雷达 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 卓胜微 | 300782 | 毫米波雷达 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 德赛西威 | 002920 | 毫米波雷达 | 产业链供应商 | related | L2_candidate | 10 |
| 欧菲光 | 002456 | 毫米波雷达 | 4.3.4 其他相关公司 | related | L2_candidate | 10 |
| 比亚迪 | 002594 | 毫米波雷达 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 硕贝德 | 300322 | 毫米波雷达 | 产业链供应商 | related | L2_candidate | 10 |

## 候选 48：可控核聚变

- **标准概念**：可控核聚变
- **申万一级**：电力设备
- **评分**：47.53
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 27.53 | 新高股4只，新高成交314.59999999999997亿，容量前三=False |
| new_high_cluster | 20.0 | 题材内新高股4只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 可控核聚变 | 10 |
| 核电 | 2 |
| 核聚变 | 2 |
| 管道 | 2 |
| 超导 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 可控核聚变 | 聚变托卡马克装置大型超导线圈及腔体外延设备集成商 | peripheral | graph_only | 10 |
| 中国核建 | 601611 | 可控核聚变 | 聚变堆（如ITER、CFETR）核岛安装与高难度工程总包商 | peripheral | graph_only | 10 |
| 中国核电 | 601985 | 可控核聚变 | 核聚变商业化国家级平台战略参股及未来运营方 | peripheral | graph_only | 10 |
| 中矿资源 | 002738 | 可控核聚变 | 上游材料 | peripheral | L1 | 10 |
| 久立特材 | 002318 | 可控核聚变 | 托卡马克超导磁体导管（特种合金管）供应商 | peripheral | L1 | 10 |
| 永鼎股份 | 600105 | 可控核聚变 | 上游材料 | related | L2_candidate | 10 |
| 西部超导 | 688122 | 可控核聚变 | 航空高端钛合金、NbTi/Nb3Sn低温超导线材和高温合金供应商 | related | L1_L3_candidate | 10 |
| 上海电气 | 601727 | 核电与可控核聚变 | 受益标的 | related | - | 5 |

## 候选 49：氟化工

- **标准概念**：氟化工
- **申万一级**：基础化工
- **评分**：45.95
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 25.95 | 新高股4只，新高成交187.64000000000001亿，容量前三=False |
| new_high_cluster | 20.0 | 题材内新高股4只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 氟化工 | 10 |
| DFBP | 2 |
| 三代制冷剂 | 2 |
| 六氟磷酸锂 | 2 |
| 氟酮 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三美股份 | 603379 | 氟化工 | 氟碳化学品和无机氟产品生产商 | peripheral | graph_only | 10 |
| 中欣氟材 | 002915 | 氟化工 | 氟精细化学品和无机氟产品供应商 | peripheral | graph_only | 10 |
| 华谊集团 | 600623 | 氟化工 | 国有控股综合化工企业，布局能源化工、绿色轮胎、先进材料、精细化工和化工服... | related | L3 | 10 |
| 巨化股份 | 600160 | 氟化工 | 氟化工相关产品/材料供应商 | related | L2 | 10 |
| 永和股份 | 605020 | 氟化工 | 图谱弱关联 | peripheral | graph_only | 10 |
| 联创股份 | 300343 | 氟化工 | 聚氨酯/异氰酸酯等化工材料供应商 | related | L2 | 10 |
| 金石资源 | 603505 | 氟化工 | 图谱弱关联 | peripheral | graph_only | 10 |
| 东阳光 | 600673 | 制冷剂 | 产业链供应商 | peripheral | graph_only | 1 |

## 候选 50：量子科技

- **标准概念**：量子科技
- **申万一级**：计算机
- **评分**：45.58
- **触发类型**：new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 27.58 | 新高股3只，新高成交430.63000000000005亿，容量前三=False |
| new_high_cluster | 18.0 | 题材内新高股3只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 量子科技 | 10 |
| 量子计算 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科曙光 | 603019 | 量子科技 | 产业链供应商 | peripheral | L1_L3_candidate | 10 |
| 光迅科技 | 002281 | 量子科技 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 华工科技 | 000988 | 量子科技 | 上游设备 | peripheral | L1 | 10 |
| 国盾量子 | 688027 | 量子科技 | 5.3 产能布局与扩产计划 | peripheral | L1 | 10 |
| 国芯科技 | 688262 | 量子科技 | 汽车电子芯片(域控MCU)国产替代厂商，RISC-V车规MCU与量子安全... | related | L1_L3_candidate | 10 |
| 神州信息 | 000555 | 量子科技 | 产业链供应商 | peripheral | L2_candidate | 10 |
| 腾景科技 | 688195 | 量子科技 | 产业链供应商 | core | L1_L3_candidate | 10 |
