# 2026-06-10 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：26190.11
- **上涨家数**：1556
- **涨停 / 跌停**：70 / 25
- **容量前三行业**：1.电子(29.2%, super_capacity)、2.机械设备(9.0%, normal)、3.通信(8.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光刻胶 | 光刻胶 | 电子 | 180.09 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | PPE树脂 | PPE树脂 | 电子 | 123.0 | limit_advance_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 3 | 半导体设备 | 半导体设备 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 3 | - |
| 4 | 存储芯片 | 存储芯片 | 电子 | 93.56 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 5 | MLCC | MLCC | 电力设备 | 91.56 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 6 | 先进封装 | 先进封装 | 电子 | 89.36 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 7 | PCB | PCB | 电子 | 87.37 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 8 | 共封装光学(CPO) | CPO | 电子 | 86.7 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 9 | 人形机器人 | 人形机器人 | 机械设备 | 86.16 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 10 | 半导体 | 半导体 | 电子 | 85.63 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 商业航天 | 商业航天 | 国防军工 | 82.56 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 12 | 数据中心 | 数据中心 | 计算机 | 81.33 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 风电 | 风电 | 电力设备 | 78.96 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 机器视觉 | 机器视觉 | 机械设备 | 76.55 | new_high_direction、new_high_cluster、capacity_industry | 0 | 2 | 0 | missing_concept、missing_evidence |
| 15 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 75.82 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 16 | 海峡两岸 | 海峡两岸 | 综合 | 74.34 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 新型工业化 | 新型工业化 | 机械设备 | 73.43 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 18 | 化学制品 | 化工周期 | 基础化工 | 72.92 | limit_heat、new_high_direction、new_high_cluster | 3 | 7 | 0 | missing_evidence |
| 19 | 液冷服务器 | 液冷服务器 | 电力设备 | 71.77 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 氢能源 | 氢能源 | 电力设备 | 71.6 | limit_heat、new_high_direction、new_high_cluster | 5 | 4 | 1 | - |
| 21 | PET铜箔 | PET铜箔 | 电力设备 | 70.13 | new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 22 | 光刻机 | 光刻机 | 电子 | 70.11 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | 银行 | 区块链 | 银行 | 69.2 | new_high_direction、new_high_cluster | 3 | 1 | 0 | missing_evidence |
| 24 | 元件 | 电子元件 | 电子 | 69.02 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 25 | 光学光电子 | LED芯片 | 电子 | 68.22 | new_high_direction、new_high_cluster、capacity_industry | 2 | 2 | 0 | missing_evidence |
| 26 | 燃料电池 | SOFC燃料电池 | 电力设备 | 67.15 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 27 | 自动化设备 | 自动化设备 | 机械设备 | 66.97 | new_high_direction、new_high_cluster、capacity_industry | 5 | 6 | 1 | - |
| 28 | 3D打印 | 3D打印 | 机械设备 | 66.93 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 29 | 无人驾驶 | 无人驾驶 | 汽车 | 66.43 | new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 30 | 钠离子电池 | 储能 | 电力设备 | 65.9 | limit_heat、new_high_direction、new_high_cluster | 5 | 9 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 工业母机 | 工业母机 | 机械设备 | 65.63 | new_high_direction、new_high_cluster、capacity_industry | 4 | 11 | 1 | - |
| 32 | 6G | 6G | 通信 | 65.11 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 33 | 特高压 | 特高压 | 电力设备 | 64.98 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 数据要素 | 数据要素 | 计算机 | 64.44 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 35 | IP经济(谷子经济) | 谷子经济 | 传媒 | 64.01 | limit_heat、new_high_direction、new_high_cluster | 1 | 4 | 0 | missing_evidence |
| 36 | 小金属 | 小金属 | 有色金属 | 61.22 | new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 37 | 塑料制品 | 膜材料 | 基础化工 | 60.43 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 38 | AIGC | AIGC | 传媒 | 60.08 | new_high_direction、new_high_cluster | 5 | 5 | 1 | - |
| 39 | 电子化学品 | 电子化学品 | 基础化工 | 59.52 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 通信设备 | 通信设备 | 通信 | 57.98 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 41 | 稀土永磁 | 稀土永磁 | 有色金属 | 56.89 | new_high_direction、new_high_cluster | 5 | 5 | 1 | - |
| 42 | 信创 | 信创 | 计算机 | 56.85 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 氟化工 | 氟化工 | 基础化工 | 56.84 | new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 44 | 毫米波雷达 | 毫米波雷达 | 汽车 | 56.67 | new_high_direction、new_high_cluster | 5 | 11 | 1 | - |
| 45 | 可控核聚变 | 可控核聚变 | 电力设备 | 55.69 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 航空发动机 | 航空发动机 | 国防军工 | 52.01 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 电池 | 4C电池 | 电力设备 | 48.66 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 48 | 太赫兹 | 6G产业 | 国防军工 | 44.19 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 49 | 量子科技 | 量子科技 | 计算机 | 44.17 | new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 50 | 房地产 | 房地产 | 房地产 | 44.0 | limit_advance_cluster、new_high_cluster | 5 | 5 | 1 | - |

## 五、核心候选明细

## 候选 1：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：180.09
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.51%，边际量 11.2%，成交额 725.24 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.51%，边际量11.2%，成交725.24亿 |
| new_high_direction | 48.34 | 新高股12只，新高成交282.90000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比7.14，排名25 |

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

## 候选 2：PPE树脂

- **标准概念**：PPE树脂
- **申万一级**：电子
- **评分**：123.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 123.0 | 连板股4只，最高2板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 3：半导体设备

- **标准概念**：半导体设备
- **申万一级**：电子
- **评分**：116.0
- **触发类型**：double_red、capacity_industry、new_high_cluster
- **盘面信号**：涨幅 1.31%，边际量 27.02%，成交额 537.36 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.31%，边际量27.02%，成交537.36亿 |
| new_high_cluster | 16.0 | 题材内新高股2只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体设备 | 10 |
| CPO | 2 |
| GPU | 2 |
| GPU（图形处理器） | 2 |
| HBM | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中微公司 | 688012 | 半导体设备 | 半导体设备研发生产企业 | core | L2_candidate | 10 |
| 中科飞测 | 688361 | 半导体设备 | 半导体专用设备制造商 | core | L2_candidate | 10 |
| 亚翔集成 | 603929 | 半导体设备 | 洁净室工程服务商，受益半导体/AI基建洁净室工程量价齐升 | related | L1_L3_candidate | 10 |
| 光力科技 | 300480 | 半导体设备 | 半导体精密加工与检测设备供应商，推进激光划片、开槽和隐切设备验证 | related | L1_L3_candidate | 10 |
| 凤凰光学 | 600071 | 半导体设备 | 图谱弱关联 | peripheral | graph_only | 10 |
| 凯美特气 | 002549 | 半导体设备 | 图谱弱关联 | peripheral | graph_only | 10 |
| 北方华创 | 002371 | 半导体设备 | 国内前段核心制程（刻蚀、薄膜沉积、立式炉、清洗）谱系最全、份额最高的半导... | core | L2_candidate | 10 |
| 华峰测控 | 688200 | 半导体设备 | 国产半导体模拟及数模混合大功率测试机、数控核心测试信号采集装备絕對龙头 | core | L2_candidate | 10 |

## 候选 4：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：93.56
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.76 | 新高股22只，新高成交860.46亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比11.43，排名8 |

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

## 候选 5：MLCC

- **标准概念**：MLCC
- **申万一级**：电力设备
- **评分**：91.56
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.56 | 新高股8只，新高成交188.53000000000003亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |

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

## 候选 6：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：89.36
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 56.56 | 新高股19只，新高成交524.5499999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比11.43，排名9 |

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

## 候选 7：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：87.37
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 61.37 | 新高股39只，新高成交909.9700000000001亿，容量前三=True |
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

## 候选 8：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：86.7
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.7 | 新高股17只，新高成交855.95亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 9：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：86.16
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.16 | 新高股27只，新高成交813.1899999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 10：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：85.63
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.83 | 新高股14只，新高成交418.16000000000014亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比11.43，排名10 |

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
