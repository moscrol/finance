# 2026-06-17 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：30915.19
- **上涨家数**：1723
- **涨停 / 跌停**：86 / 1
- **容量前三行业**：1.电子(33.0%, super_capacity)、2.电力设备(9.0%, normal)、3.机械设备(8.0%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 先进封装 | 先进封装 | 电子 | 203.6 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 2 | 存储芯片 | 存储芯片 | 电子 | 201.15 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 3 | 半导体 | 半导体 | 电子 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 可控核聚变 | 可控核聚变 | 电力设备 | 190.41 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | AI PC | AI PC | 电子 | 186.78 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | MLCC | MLCC | 电子 | 184.43 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 7 | 光刻胶 | 光刻胶 | 电子 | 182.26 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | MCU芯片 | MCU芯片 | 电子 | 179.26 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 4 | 1 | - |
| 9 | 超级电容 | 超级电容 | 电力设备 | 178.85 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 毫米波雷达 | 毫米波雷达 | 汽车 | 172.02 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 半导体设备 | 半导体设备 | 电子 | 122.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 3 | - |
| 12 | 电容器 | MLCC材料 | 电力设备 | 119.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 13 | CCL | CCL | 电子 | 111.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 2 | - |
| 14 | 玻璃基板 | 玻璃基板 | 电子 | 111.0 | limit_advance_cluster、capacity_industry | 3 | 12 | 3 | - |
| 15 | 人形机器人 | 人形机器人 | 机械设备 | 102.55 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 16 | 元件 | 电子元件 | 电子 | 101.5 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 17 | 共封装光学(CPO) | CPO | 电子 | 101.5 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 18 | 风电 | 风电 | 电力设备 | 98.87 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 19 | 液冷服务器 | 液冷服务器 | 电力设备 | 98.51 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 20 | 大消费 | 大消费 | 商贸零售 | 97.0 | limit_advance_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 21 | 氢能源 | 氢能源 | 电力设备 | 94.66 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 4 | 1 | - |
| 22 | 商业航天 | 商业航天 | 国防军工 | 94.3 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 23 | AI眼镜 | AI眼镜 | 电子 | 94.15 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 24 | PCB | PCB | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 3 | - |
| 25 | 数据中心 | 数据中心 | 计算机 | 93.25 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 传感器 | 传感器 | 机械设备 | 89.12 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 27 | ABF载板 | ABF载板 | 计算机 | 89.0 | limit_advance_cluster | 5 | 12 | 2 | - |
| 28 | PET铜箔 | PET铜箔 | 电力设备 | 88.31 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 9 | 1 | - |
| 29 | 光学光电子 | LED芯片 | 电子 | 87.31 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 30 | 燃料电池 | 燃料电池 | 电力设备 | 84.73 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 3D打印 | 3D打印 | 机械设备 | 84.52 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 32 | 无人驾驶 | 无人驾驶 | 汽车 | 84.12 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 34 | 钠离子电池 | 储能 | 电力设备 | 82.2 | new_high_direction、new_high_cluster、capacity_industry | 5 | 10 | 0 | missing_evidence |
| 35 | 新型工业化 | 新型工业化 | 机械设备 | 81.76 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 36 | 海峡两岸 | 海峡两岸 | 综合 | 81.01 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 6G | 6G | 通信 | 80.45 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 通用设备 | 金属制品 | 机械设备 | 79.89 | new_high_direction、new_high_cluster、capacity_industry | 1 | 7 | 0 | missing_evidence |
| 39 | 特高压 | 特高压 | 电力设备 | 78.26 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 40 | 智能座舱 | 智能座舱 | 汽车 | 77.63 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 高压快充 | 超充 | 电力设备 | 77.57 | new_high_direction、new_high_cluster、capacity_industry | 1 | 5 | 0 | missing_evidence |
| 42 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 74.62 | new_high_direction、new_high_cluster、capacity_industry | 0 | 5 | 0 | missing_concept、missing_evidence |
| 43 | AI手机 | AI手机 | 电子 | 74.52 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 4 | - |
| 44 | 小金属 | 小金属 | 有色金属 | 72.73 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 45 | 电子化学品 | 电子化学品 | 基础化工 | 71.9 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 氟化工 | 氟化工 | 基础化工 | 70.25 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 通信设备 | 通信设备 | 通信 | 70.24 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 化学制品 | 化工周期 | 基础化工 | 70.12 | new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 49 | 塑料制品 | 膜材料 | 基础化工 | 69.78 | new_high_direction、new_high_cluster | 1 | 4 | 0 | missing_evidence |
| 50 | 信创 | 信创 | 计算机 | 69.36 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：203.6
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.9%，边际量 13.08%，成交额 4703.06 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.9%，边际量13.08%，成交4703.06亿 |
| new_high_direction | 68.0 | 新高股60只，新高成交2039.22亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 9.6 | 涨停16只，市场占比18.6，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 先进封装 | 10 |
| 1.6T CPO | 2 |
| 2.5D封装 | 2 |
| 3D封装 | 2 |
| ABF膜涨价 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三安光电 | 600703 | 先进封装 | 光芯片（AI算力光互联）、碳化硅（SiC功率器件）、Mini | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 先进封装 | 投资潜在相关（非直接产业链） | peripheral | L2_candidate | 10 |
| 上海新阳 | 300236 | 先进封装 | 集成电路制造及先进封装用关键工艺材料（电镀液 | related | L1_L3_candidate | 10 |
| 东威科技 | 688700 | 先进封装 | 半导体封装电镀设备 | related | L1_L3_candidate | 10 |
| 中京电子 | 002579 | 先进封装 | - | - | - | 10 |
| 中国巨石 | 600176 | 先进封装 | 先进封装上游高端电子布潜在相关 | peripheral | L2_candidate | 10 |
| 中微公司 | 688012 | 先进封装 | 封装设备 | related | L2_candidate | 10 |
| 中材科技 | 002080 | 先进封装 | Low-CTE电子布供应商，AI先进封装关键材料 | peripheral | L1 | 10 |

## 候选 2：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：201.15
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.02%，边际量 20.6%，成交额 5941.58 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.02%，边际量20.6%，成交5941.58亿 |
| new_high_direction | 68.0 | 新高股46只，新高成交2419.0400000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.15 | 涨停9只，市场占比10.47，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 存储芯片 | 10 |
| AI存储 | 2 |
| AI手机 | 2 |
| AI芯片 | 2 |
| CXL技术 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士 | 000660 | 存储芯片 | 图谱弱关联 | peripheral | graph_only | 10 |
| 万润科技 | 002654 | 存储芯片 | 半导体存储器业务 | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 存储芯片 | 股权投资潜在相关 | peripheral | L2_candidate | 10 |
| 上海合晶 | 688584 | 存储芯片 | 存储晶圆制造上游硅片材料潜在供应商 | peripheral | L2_candidate | 10 |
| 东芯股份 | 688110 | 存储芯片 | 中小容量存储芯片供应商，联营GPU(上海励算/砺算) | related | L1_L3_candidate | 10 |
| 中微公司 | 688012 | 存储芯片 | 上游设备 | peripheral | L1 | 10 |
| 中微半导 | 688380 | 存储芯片 | MCU（8位、32位）、SoC、ASIC | related | L1_L3_candidate | 10 |
| 中电港 | 001287 | 存储芯片 | 存储芯片分销、AI算力芯片分销、机器人解决方案、端侧AI | core | L1_L3_candidate | 10 |

## 候选 3：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：194.0
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.97%，边际量 21.95%，成交额 4760.78 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.97%，边际量21.95%，成交4760.78亿 |
| new_high_direction | 68.0 | 新高股33只，新高成交1506.9亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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
| 华天科技 | 002185 | 功率半导体 | - | - | - | 10 |
| 华润微 | 688396 | 功率半导体 | 功率器件（MOSFET/IGBT）、制造与代工服务（12寸晶圆）、第三代... | related | L1_L3_candidate | 10 |
| 华虹宏力 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 士兰微 | 600460 | 功率半导体 | 国内极成熟、拥有多代特色晶圆制造代工线的一流功率分立器件IDM全产业链巨... | core | L1 | 10 |
| 天岳先进 | 688234 | 功率半导体 | 弱相关，待验证 | related | L2 | 10 |
| 富乐德 | 301297 | 功率半导体 | 覆铜陶瓷载板（DCB/AMB/DPC）、泛半导体精密洗净服务、半导体核心... | core | L1_L3_candidate | 10 |
| 富满微 | 300671 | 功率半导体 | 功率半导体 | related | L1_L3_candidate | 10 |

## 候选 4：可控核聚变

- **标准概念**：可控核聚变
- **申万一级**：电力设备
- **评分**：190.41
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.78%，边际量 13.05%，成交额 1456.1 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.78%，边际量13.05%，成交1456.1亿 |
| new_high_direction | 58.31 | 新高股17只，新高成交664.6399999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 6.1 | 涨停6只，市场占比6.98，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 可控核聚变 | 10 |
| 核电与可控核聚变 | 5 |
| 核电 | 2 |
| 核聚变 | 2 |
| 管道 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 可控核聚变 | 聚变托卡马克装置大型超导线圈及腔体外延设备集成商 | peripheral | graph_only | 10 |
| 中国核建 | 601611 | 可控核聚变 | 聚变堆（如ITER、CFETR）核岛安装与高难度工程总包商 | peripheral | graph_only | 10 |
| 中国核电 | 601985 | 可控核聚变 | 核聚变商业化国家级平台战略参股及未来运营方 | peripheral | graph_only | 10 |
| 中矿资源 | 002738 | 可控核聚变 | 上游材料 | peripheral | L1 | 10 |
| 久立特材 | 002318 | 可控核聚变 | 托卡马克超导磁体导管（特种合金管）供应商 | peripheral | L1 | 10 |
| 合锻智能 | 603011 | 可控核聚变 | 核聚变核心部件、PCB、CCL层压设备、色选机 | related | L1_L3_candidate | 10 |
| 同方股份 | 600100 | 可控核聚变 | 可控核聚变（战略合作） | related | L1_L3_candidate | 10 |
| 四创电子 | 600990 | 可控核聚变 | 可控核聚变电源 | related | L1_L3_candidate | 10 |

## 候选 5：AI PC

- **标准概念**：AI PC
- **申万一级**：电子
- **评分**：186.78
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.73%，边际量 18.43%，成交额 1612.69 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.73%，边际量18.43%，成交1612.69亿 |
| new_high_direction | 54.68 | 新高股13只，新高成交678.2600000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 6.1 | 涨停6只，市场占比6.98，排名24 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI PC | 20 |
| AI PCB | 15 |
| AIPCB专用油墨 | 15 |
| AI智能化 | 9 |
| AI终端 | 9 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 奥士康 | 002913 | AI PC | AI服务器高多层板、AIPC高阶HDI板、汽车电子PCB | related | L1_L3_candidate | 20 |
| 慧为智能 | 920876 | AI PC | 智能终端ODM（AI PC、边缘计算设备、信创终端） | core | L2 | 20 |
| 泓淋电力 | 301439 | AI PC | 电源线组件（计算机/家电）、特种线缆、新能源汽车充电连接产品、高速铜缆（... | related | L1_L3_candidate | 20 |
| 泰嘉股份 | 002843 | AI PC | 电源业务（AI服务器电源 | related | L1_L3_candidate | 20 |
| 苏大维格 | 300331 | AI PC | 半导体光掩模缺陷检测设备、激光直写光刻设备、纳米压印光刻设备 | related | L1_L3_candidate | 20 |
| 英力股份 | 300956 | AI PC | 笔记本电脑结构件模组及精密模具 | related | L2 | 20 |
| 软通动力 | 301236 | AI PC | AI服务器（昇腾/鲲鹏）、AI PC（机械革命品牌）、信创PC与服务器（... | core | L1_L3_candidate | 20 |
| 雷神科技 | 920190 | AI PC | 电竞PC及外设、信创、AI工作站、服务器 | core | L1_L3_candidate | 20 |

## 候选 6：MLCC

- **标准概念**：MLCC
- **申万一级**：电子
- **评分**：184.43
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.29%，边际量 24.58%，成交额 1152.17 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（4）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.29%，边际量24.58%，成交1152.17亿 |
| new_high_direction | 58.43 | 新高股17只，新高成交674.5899999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MLCC | 10 |
| MLCC微型化 | 5 |
| MLCC材料 | 5 |
| MLCC镍粉 | 5 |
| Rubin MLCC | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | Rubin MLCC | 高端MLCC制造 / 垂直一体化 | core | L1_image_extraction | 20 |
| 利和兴 | 301013 | Rubin MLCC | 107高容算力MLCC落地标的 | related | L1_image_extraction | 20 |
| 博迁新材 | 605376 | Rubin MLCC | 纳米镍粉 / 内电极材料 | core | L1_image_extraction | 20 |
| 国瓷材料 | 300285 | Rubin MLCC | 上游陶瓷粉体龙头 | core | L1_image_extraction | 20 |
| 昀冢科技 | 688260 | Rubin MLCC | 高容MLCC扩产观察 / 非Rubin直接验证 | peripheral | L1_image_extraction_with_L3_official_conflict | 20 |
| 风华高科 | 000636 | Rubin MLCC | MLCC制造龙头 / AI服务器供应链 | core | L1_image_extraction | 20 |
| 中电港 | 001287 | MLCC | MLCC 产业链（国联民生推荐） | related | L3 | 10 |
| 中金岭南 | 000060 | MLCC | MLCC电极粉体（中金科技） | related | L1_L3_candidate | 10 |

## 候选 7：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：182.26
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.01%，边际量 10.36%，成交额 899.71 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.01%，边际量10.36%，成交899.71亿 |
| new_high_direction | 56.26 | 新高股22只，新高成交500.99亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
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
| 晶瑞电材 | 300655 | g线光刻胶 | 图谱弱关联 | peripheral | graph_only | 10 |
| 万润股份 | 002643 | 光刻胶 | - | - | - | 10 |
| 上海新阳 | 300236 | 光刻胶 | 光刻胶） | related | L1_L3_candidate | 10 |
| 中芯国际 | 688981 | 光刻胶 | 2025 年国内 12 英寸晶圆产能同比增长 25%，带动成熟制程光刻胶... | peripheral | L1_L3_candidate | 10 |
| 八亿时空 | 688181 | 光刻胶 | 百吨级KrF高端光刻胶配方树脂国产化自主突破及生产平台 | related | L1 | 10 |
| 兴福电子 | 688545 | 光刻胶 | 湿电子化学品（电子级磷酸、硫酸、双氧水 | related | L1_L3_candidate | 10 |
| 华特气体 | 688268 | 光刻胶 | - | - | - | 10 |
| 华虹宏力 | 688347 | 光刻胶 | 特色工艺晶圆代工、12英寸成熟制程扩产、华力微收购并表 | related | L1_L3_candidate | 10 |

## 候选 8：MCU芯片

- **标准概念**：MCU芯片
- **申万一级**：电子
- **评分**：179.26
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.4%，边际量 13.54%，成交额 1437.49 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（4），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.4%，边际量13.54%，成交1437.49亿 |
| new_high_direction | 53.26 | 新高股12只，新高成交676.9899999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| MCU芯片 | 10 |
| 智能控制器 | 2 |
| 车规芯片 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 乐鑫科技 | 688018 | MCU芯片 | 物联网Wi-Fi MCU芯片设计 | related | L1_L3_candidate | 10 |
| 力源信息 | 300184 | MCU芯片 | AI服务器MLCC分销、华为海思芯片代理、存储芯片分销、碳化硅（SiC）... | related | L1_L3_candidate | 10 |
| 恒烁股份 | 688416 | MCU芯片 | MCU芯片 | related | L1_L3_candidate | 10 |
| 兆易创新 | 603986 | 半导体涨价潮 | 存储+MCU芯片厂商，券商研判其可能受益于半导体涨价潮 | peripheral | L1 | 1 |

## 候选 9：超级电容

- **标准概念**：超级电容
- **申万一级**：电力设备
- **评分**：178.85
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.22%，边际量 10.3%，成交额 1043.71 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.22%，边际量10.3%，成交1043.71亿 |
| new_high_direction | 52.85 | 新高股12只，新高成交644.3900000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

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
| 中兴通讯 | 000063 | 超级电容 | - | - | - | 10 |
| 中材科技 | 002080 | 超级电容 | 超级电容活性炭相关供应商 | related | L1_L3_candidate | 10 |
| 中际旭创 | 300308 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |
| 京东方A | 000725 | 超级电容 | 市场信号待核验（非直接产业链） | peripheral | graph_only | 10 |

## 候选 10：毫米波雷达

- **标准概念**：毫米波雷达
- **申万一级**：汽车
- **评分**：172.02
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.47%，边际量 17.05%，成交额 2083.06 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.47%，边际量17.05%，成交2083.06亿 |
| new_high_direction | 49.92 | 新高股22只，新高成交793.4599999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比6.98，排名30 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 毫米波雷达 | 10 |
| 4D毫米波雷达 | 5 |
| 传感器 | 2 |
| 光波导 | 2 |
| 均热板 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中石科技 | 300684 | 毫米波雷达 | 4.3.2 射频器件公司 | related | L1_L3_candidate | 10 |
| 中英科技 | 300936 | 毫米波雷达 | 高频覆铜板（PTFE）、VC散热片、引线框架 | related | L1 | 10 |
| 依顿电子 | 603328 | 毫米波雷达 | 汽车电子PCB、AI算力、通信PCB | related | L1_L3_candidate | 10 |
| 保隆科技 | 603197 | 毫米波雷达 | 4.3.3 模组集成公司 | related | L2_candidate | 10 |
| 华域汽车 | 600741 | 毫米波雷达 | 产业链供应商 | related | L1_L3_candidate | 10 |
| 卓胜微 | 300782 | 毫米波雷达 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 强达电路 | 301628 | 毫米波雷达 | 毫米波雷达板 | related | L1_L3_candidate | 10 |
| 德赛西威 | 002920 | 毫米波雷达 | 产业链供应商 | related | L2_candidate | 10 |
