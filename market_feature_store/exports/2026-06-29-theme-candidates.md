# 2026-06-29 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：探底阶段
- **成交额**：35175.16
- **上涨家数**：2469
- **涨停 / 跌停**：107 / 38
- **容量前三行业**：1.电子(35.7%, super_capacity)、2.机械设备(8.0%, normal)、3.电力设备(7.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | MCU芯片 | MCU芯片 | 电子 | 189.56 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 4 | 1 | - |
| 2 | 光刻胶 | 光刻胶 | 电子 | 188.35 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 3 | 半导体设备 | 半导体设备 | 电子 | 186.33 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 4 | 创新药 | 创新药 | 医药生物 | 175.45 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 5 | 电子化学品 | 电子化学品 | 基础化工 | 165.75 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 化学制药 | 原料药 | 医药生物 | 124.2 | double_red、limit_heat、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 7 | 材料 | AI材料 | 电子 | 123.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 8 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 商业航天 | 商业航天 | 国防军工 | 114.57 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 10 | 洁净室 | 半导体洁净室 | 电子 | 107.0 | limit_advance_cluster、capacity_industry | 4 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 存储芯片 | 存储芯片 | 电子 | 102.55 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 12 | 先进封装 | 先进封装 | 电子 | 100.45 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 13 | 半导体 | 半导体 | 电子 | 100.45 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | 传感器 | 传感器 | 机械设备 | 92.88 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 15 | 氢能源 | 氢能源 | 电力设备 | 90.16 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 6 | 1 | - |
| 16 | 共封装光学(CPO) | CPO | 电子 | 90.08 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 17 | AI眼镜 | AI眼镜 | 电子 | 89.59 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 18 | 液冷服务器 | 液冷服务器 | 电力设备 | 89.39 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 19 | 人形机器人 | 人形机器人 | 机械设备 | 89.18 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 20 | 数据中心 | 数据中心 | 计算机 | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | PCB | PCB | 电子 | 83.26 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 22 | 风电 | 风电 | 电力设备 | 82.72 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | 可控核聚变 | 可控核聚变 | 电力设备 | 81.96 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 24 | 光刻机 | 光刻机 | 电子 | 81.72 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 25 | 机器视觉 | 机器视觉 | 机械设备 | 81.58 | new_high_direction、new_high_cluster、capacity_industry | 2 | 9 | 0 | missing_evidence |
| 26 | MLCC | MLCC | 电子 | 81.41 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 27 | 无人驾驶 | 无人驾驶 | 汽车 | 81.12 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 海峡两岸 | 海峡两岸 | 综合 | 80.99 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 29 | 高压快充 | 超充 | 电力设备 | 80.53 | new_high_direction、new_high_cluster、capacity_industry | 1 | 6 | 0 | missing_evidence |
| 30 | 3D打印 | 3D打印 | 机械设备 | 79.44 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 78.26 | new_high_direction、new_high_cluster、capacity_industry | 0 | 6 | 0 | missing_concept、missing_evidence |
| 32 | 专用设备 | 专用设备 | 机械设备 | 77.84 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 33 | 燃料电池 | 燃料电池 | 电力设备 | 76.87 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 34 | 光纤 | 光纤 | 通信 | 74.64 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 35 | 光学光电子 | LED芯片 | 电子 | 73.8 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 36 | 元件 | 光学元件 | 电子 | 72.61 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 37 | HJT电池 | HJT电池 | 电力设备 | 71.51 | new_high_direction、new_high_cluster、capacity_industry | 5 | 4 | 1 | - |
| 38 | TOPCON电池 | TOPCon电池 | 电力设备 | 71.38 | new_high_direction、new_high_cluster、capacity_industry | 5 | 8 | 0 | missing_evidence |
| 39 | CRO | CRO | 医药生物 | 69.74 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | BC电池 | BC电池 | 电力设备 | 69.67 | new_high_direction、new_high_cluster、capacity_industry | 5 | 10 | 1 | - |
| 41 | 医疗服务 | 医疗服务 | 医药生物 | 69.6 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 化学制品 | 化工周期 | 基础化工 | 69.23 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 43 | 氟化工 | 氟化工 | 基础化工 | 68.48 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 信创 | 信创 | 计算机 | 68.16 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 45 | 小金属 | 小金属 | 有色金属 | 66.97 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 46 | 建筑装饰 | 工程 | 建筑装饰 | 66.56 | limit_heat、new_high_direction、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 47 | 消费电子 | 消费电子 | 电子 | 64.21 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 48 | 磷化工 | 磷化工 | 基础化工 | 62.25 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 49 | 智能座舱 | 智能座舱 | 汽车 | 62.12 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 超级电容 | 超级电容 | 电力设备 | 61.63 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：MCU芯片

- **标准概念**：MCU芯片
- **申万一级**：电子
- **评分**：189.56
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.12%，边际量 10.89%，成交额 1961.47 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（4），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.12%，边际量10.89%，成交1961.47亿 |
| new_high_direction | 63.56 | 新高股16只，新高成交1084.7099999999998亿，容量前三=True |
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

## 候选 2：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：188.35
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.57%，边际量 20.02%，成交额 1326.72 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.57%，边际量20.02%，成交1326.72亿 |
| new_high_direction | 62.35 | 新高股30只，新高成交988.1100000000001亿，容量前三=True |
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
| 光华股份 | 001333 | 光刻胶 | 粉末涂料用聚酯树脂的研发、生产和销售 | related | L1_L3_candidate | 10 |
| 八亿时空 | 688181 | 光刻胶 | 百吨级KrF高端光刻胶配方树脂国产化自主突破及生产平台 | related | L1 | 10 |
| 兴福电子 | 688545 | 光刻胶 | 湿电子化学品（电子级磷酸、硫酸、双氧水 | related | L1_L3_candidate | 10 |
| 凤凰光学 | 600071 | 光刻胶 | 半导体制造级、精密超高解像度光刻镜头精密抛光及在研平台 | related | L1 | 10 |

## 候选 3：半导体设备

- **标准概念**：半导体设备
- **申万一级**：电子
- **评分**：186.33
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 7.16%，边际量 14.21%，成交额 881.23 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅7.16%，边际量14.21%，成交881.23亿 |
| new_high_direction | 60.33 | 新高股19只，新高成交826.7600000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体设备 | 10 |
| 半导体设备材料 | 5 |
| 半导体设备零部件 | 5 |
| AI基础设施与国产算力 | 2 |
| AI芯片散热 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东威科技 | 688700 | 半导体设备 | PCB电镀设备（VCP/脉冲VCP/水平镀三合一/MSAP移载式VCP）... | related | L1_L3_candidate | 10 |
| 中微公司 | 688012 | 半导体设备 | 待补充 | related | L3 | 10 |
| 中科仪 | 920186 | 半导体设备 | 干式真空泵（集成电路65%）、真空科学仪器（18.5%）、维修服务及零部... | related | L1_L3_candidate | 10 |
| 九州一轨 | 688485 | 半导体设备 | 待补充 | related | L3 | 10 |
| 亚翔集成 | 603929 | 半导体设备 | 洁净室工程服务商，受益半导体/AI基建洁净室工程量价齐升 | related | L1_L3_candidate | 10 |
| 京仪装备 | 688652 | 半导体设备 | 半导体专用温控设备(Chiller)、工艺废气处理设备(Local Sc... | related | L1_L3_candidate | 10 |
| 先导基电 | 600641 | 半导体设备 | 离子注入机（凯世通）、铋材料（安徽万岛） | related | L1_L3_candidate | 10 |
| 先锋精科 | 688605 | 半导体设备 | 半导体刻蚀、薄膜沉积设备关键零部件（腔体、内衬、加热器、静电卡盘） | related | L1_L3_candidate | 10 |

## 候选 4：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：175.45
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 6.08%，边际量 57.95%，成交额 1239.13 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅6.08%，边际量57.95%，成交1239.13亿 |
| new_high_direction | 47.05 | 新高股42只，新高成交564.13亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 12.4 | 涨停24只，市场占比22.43，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 10 |
| 创新药RWA | 5 |
| AI辅助生殖 | 2 |
| CDMO | 2 |
| ICL | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | 创新药 | 院外零售渠道潜在相关 | peripheral | L1 | 10 |
| 三生制药 | 01530.HK | 创新药 | 双抗BD出海标杆 | related | - | 10 |
| 上海医药 | 601607 | 创新药 | 医药流通渠道潜在相关 | peripheral | L1 | 10 |
| 东富龙 | 300171 | 创新药 | 创新药生产装备潜在供应商 | related | L1 | 10 |
| 丽珠集团 | 000513 | 创新药 | - | related | L1 | 10 |
| 乐普医疗 | 300003 | 创新药 | 创新药（GLP-1 | related | L1_L3_candidate | 10 |
| 九洲药业 | 603456 | 创新药 | 创新药定制研发生产/CDMO服务商 | core | L1 | 10 |
| 亚虹医药 | 688176 | 创新药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 10 |

## 候选 5：电子化学品

- **标准概念**：电子化学品
- **申万一级**：基础化工
- **评分**：165.75
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.29%，边际量 11.82%，成交额 1210.23 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.29%，边际量11.82%，成交1210.23亿 |
| new_high_direction | 49.75 | 新高股18只，新高成交779.98亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子化学品 | 10 |
| 湿电子化学品 | 5 |
| AIPCB专用油墨 | 2 |
| PCB油墨 | 2 |
| g线光刻胶 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 江化微 | 603078 | 湿电子化学品 | 湿电子化学品相关产品/材料供应商 | related | L2 | 10 |
| 万润股份 | 002643 | 电子化学品 | - | - | - | 10 |
| 三友化工 | 600409 | 电子化学品 | 电子化学品（G5级湿电子化学品，试生产阶段） | related | L1_L3_candidate | 10 |
| 三孚新科 | 688359 | 电子化学品 | 表面工程专用化学品与电子化学品供应商 | related | L2 | 10 |
| 上海新阳 | 300236 | 电子化学品 | 电子化学品研发生产商 | peripheral | graph_only | 10 |
| 中巨芯 | 688549 | 电子化学品 | - | - | - | 10 |
| 兴发集团 | 600141 | 电子化学品 | 电子化学品 | related | L1_L3_candidate | 10 |
| 兴福电子 | 688545 | 电子化学品 | 湿电子化学品（电子级磷酸 | related | L1_L3_candidate | 10 |

## 候选 6：化学制药

- **标准概念**：原料药
- **申万一级**：医药生物
- **评分**：124.2
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 5.89%，边际量 67.75%，成交额 596.84 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.89%，边际量67.75%，成交596.84亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比11.21，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 原料药 | 2 |
| 多肽药物 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 百利天恒 | 688506 | ADC药物 | ADC创新药研发、生产及销售 | core | L1_L3_candidate | 1 |
| 科伦药业 | 002422 | ADC药物 | 创新药业务（SKB264、sac-TMT）、输液业务 | related | L1_L3_candidate | 1 |
| 奥翔药业 | 603229 | CDMO | CDMO | related | L2 | 1 |
| 翰宇药业 | 300199 | RWA代币化 | 多肽制剂、原料药、小核酸与CRDMO | related | L1_L3_candidate | 1 |
| 亚虹医药 | 688176 | 仿制药 | 抗肿瘤仿制药（欧优比 | related | L1_L3_candidate | 1 |
| 丽珠集团 | 000513 | 制药 | - | related | L1 | 1 |
| 九洲药业 | 603456 | 制药 | 小分子CDMO、TIDES（多肽、小核酸 | related | L1_L3_candidate | 1 |
| 共同药业 | 300966 | 制药 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 1 |

## 候选 7：材料

- **标准概念**：AI材料
- **申万一级**：电子
- **评分**：123.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 123.0 | 连板股4只，最高2板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI材料 | 5 |
| AI材料设计 | 5 |
| EMI屏蔽材料 | 5 |
| MLCC材料 | 5 |
| MOF材料 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 博迁新材 | 605376 | AI材料 | 高端MLCC镍粉 | peripheral | L1_L3_candidate | 10 |
| 中石科技 | 300684 | EMI屏蔽材料 | EMI电磁屏蔽材料供应商 | peripheral | graph_only | 10 |
| 国瓷材料 | 300285 | MLCC材料 | 上游陶瓷粉体龙头 | core | L1_image_extraction | 10 |
| 瑞泰新材 | 301238 | MOF材料 | 图谱弱关联 | peripheral | graph_only | 10 |
| 立中集团 | 300428 | MOF材料 | 图谱弱关联 | peripheral | graph_only | 10 |
| 金宏气体 | 688106 | MOF材料 | 图谱弱关联 | peripheral | graph_only | 10 |
| 万华化学 | 600309 | 光学材料 | 光学塑料/新材料潜在供应商 | peripheral | graph_only | 5 |
| 万润新能 | 688275 | 前驱体材料 | 磷酸铁锂正极材料（含高压实密度新品）、钠离子电池正极材料、固态电池材料（... | related | L1_L3_candidate | 5 |

## 候选 8：合成生物

- **标准概念**：合成生物
- **申万一级**：医药生物
- **评分**：116.0
- **触发类型**：double_red、new_high_cluster
- **盘面信号**：涨幅 3.08%，边际量 22.97%，成交额 629.21 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.08%，边际量22.97%，成交629.21亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 合成生物 | 10 |
| 合成生物学 | 5 |
| 3D生物打印 | 2 |
| 保健品 | 2 |
| 功能性食品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | - | 合成生物 | 受益标的 | related | - | 10 |
| 中油工程 | 600339 | 合成生物 | 合成生物学等） | related | L1_L3_candidate | 10 |
| 共同药业 | 300966 | 合成生物 | 甾体药物起始物料、中间体、原料药全产业链 | related | L1_L3_candidate | 10 |
| 凯赛生物 | 688065 | 合成生物 | 受益标的 | related | - | 10 |
| 利民控股 | 002734 | 合成生物 | 农用杀菌剂（代森锰锌、百菌清）、农用杀虫剂（阿维菌素 | related | L1_L3_candidate | 10 |
| 利民股份 | 002734 | 合成生物 | 受益标的 | related | - | 10 |
| 华恒生物 | 688639 | 合成生物 | 受益标的 | related | - | 10 |
| 华熙生物 | 688363 | 合成生物 | 透明质酸原料、医疗终端（医美、骨科 | related | L1_L3_candidate | 10 |

## 候选 9：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：114.57
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 56.37 | 新高股41只，新高成交1309.4999999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 8.2 | 涨停12只，市场占比11.21，排名6 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| 商业航天光学载荷 | 5 |
| AI基础设施与国产算力 | 2 |
| AI算力基础设施 | 2 |
| SOFC燃料电池 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 受益标的 | core | L3 | 10 |
| 三角防务 | 300775 | 商业航天 | 航空、航天、船舶等行业锻件产品的研制 | related | L1_L3_candidate | 10 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 10 |
| 上海瀚讯 | 300762 | 商业航天 | 卫星通信载荷、地面信关站、用户终端 | core | L1_L3_candidate | 10 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 10 |
| 东方钽业 | 000962 | 商业航天 | 钽铌铍金属及合金制品 | core | L1_L3_candidate | 10 |
| 中国卫通 | 601698 | 商业航天 | 应用端 | core | L2 | 10 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |

## 候选 10：洁净室

- **标准概念**：半导体洁净室
- **申万一级**：电子
- **评分**：107.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 107.0 | 连板股2只，最高2板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体洁净室 | 5 |
| 洁净室工程 | 5 |
| HBM | 2 |
| 超聚变 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士 | 000660 | 半导体洁净室 | 市场信号弱关联 | related | L2_candidate | 10 |
| 中微公司 | 688012 | 半导体洁净室 | 市场信号弱关联 | related | L2_candidate | 10 |
| 中际旭创 | 300308 | 半导体洁净室 | 市场信号弱关联 | related | L2_candidate | 10 |
| 亚翔集成 | 603929 | 半导体洁净室 | 半导体、光电等高科技电子厂房高等级洁净室工程服务商 | core | L2_candidate | 10 |
| 兆易创新 | 603986 | 半导体洁净室 | 市场信号弱关联 | related | L2_candidate | 10 |
| 北方华创 | 002371 | 半导体洁净室 | 市场信号弱关联 | related | L2_candidate | 10 |
| 圣晖集成 | 603163 | 半导体洁净室 | 市场信号弱关联 | related | L2_candidate | 10 |
| 大普微 | 301666 | 半导体洁净室 | - | - | - | 10 |
