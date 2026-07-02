# 2026-06-24 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：探底阶段
- **成交额**：32840.87
- **上涨家数**：1434
- **涨停 / 跌停**：98 / 12
- **容量前三行业**：1.电子(32.7%, super_capacity)、2.机械设备(8.1%, normal)、3.电力设备(7.8%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 消费电子 | 消费电子 | 电子 | 173.44 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 2 | MR(混合现实) | HAMR | 电子 | 168.41 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 氧化锆 | 二氧化锆 | 有色金属 | 105.0 | limit_advance_cluster | 2 | 5 | 0 | missing_evidence |
| 4 | 存储芯片 | 存储芯片 | 电子 | 102.9 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 5 | 共封装光学(CPO) | CPO | 电子 | 102.27 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 6 | 先进封装 | 先进封装 | 电子 | 101.15 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 7 | 半导体 | 半导体 | 电子 | 101.15 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 8 | 华为手机 | 华为手机 | 电子 | 100.0 | double_red、capacity_industry | 0 | 1 | 0 | missing_concept、missing_evidence |
| 9 | 人形机器人 | 人形机器人 | 机械设备 | 98.43 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 10 | 数据中心 | 数据中心 | 计算机 | 95.7 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | AI眼镜 | AI眼镜 | 电子 | 93.44 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 12 | 四氯化硅 | 电子特气 | 基础化工 | 93.0 | limit_advance_cluster | 1 | 3 | 0 | missing_evidence |
| 13 | 液冷服务器 | 液冷服务器 | 电力设备 | 92.71 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | 商业航天 | 商业航天 | 国防军工 | 90.58 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 15 | 机器视觉 | 机器视觉 | 机械设备 | 88.89 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 9 | 0 | missing_evidence |
| 16 | 传感器 | 传感器 | 机械设备 | 88.6 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 17 | MCU芯片 | MCU芯片 | 电子 | 87.52 | new_high_direction、new_high_cluster、capacity_industry | 3 | 4 | 1 | - |
| 18 | PCB | PCB | 电子 | 85.94 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 19 | 半导体设备 | 半导体设备 | 电子 | 84.83 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 20 | 光刻胶 | 光刻胶 | 电子 | 83.6 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 21 | 光刻机 | 光刻机 | 电子 | 82.23 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 22 | 3D打印 | 3D打印 | 机械设备 | 81.87 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | 无人驾驶 | 无人驾驶 | 汽车 | 81.71 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 海峡两岸 | 海峡两岸 | 综合 | 80.96 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 25 | 新型工业化 | 新型工业化 | 机械设备 | 80.73 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 26 | 燃料电池 | 燃料电池 | 电力设备 | 80.34 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 27 | 氢能源 | 氢能源 | 电力设备 | 80.28 | new_high_direction、new_high_cluster、capacity_industry | 5 | 6 | 1 | - |
| 28 | 光纤 | 光纤 | 通信 | 79.71 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 29 | 通用设备 | 金属制品 | 机械设备 | 79.68 | new_high_direction、new_high_cluster、capacity_industry | 1 | 8 | 0 | missing_evidence |
| 30 | 光学光电子 | LED芯片 | 电子 | 78.39 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 可控核聚变 | 可控核聚变 | 电力设备 | 73.94 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 32 | 特高压 | 特高压 | 电力设备 | 73.78 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 33 | 氟化工 | 氟化工 | 基础化工 | 73.77 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 信创 | 信创 | 计算机 | 72.22 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 35 | 小金属 | 小金属 | 有色金属 | 71.99 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 36 | 创新药 | 创新药 | 医药生物 | 71.38 | new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 37 | AI PC | AI PC | 电子 | 71.01 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 38 | 化学制品 | 化工周期 | 基础化工 | 69.92 | new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 39 | 自动化设备 | 自动化设备 | 机械设备 | 69.88 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 40 | 算力租赁 | 算力租赁 | 计算机 | 69.44 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 41 | CRO | CRO | 医药生物 | 69.13 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 工业母机 | 工业母机 | 机械设备 | 68.39 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 43 | 智能座舱 | 智能座舱 | 汽车 | 68.02 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | TOPCON电池 | TOPCon电池 | 电力设备 | 67.35 | new_high_direction、new_high_cluster、capacity_industry | 5 | 8 | 0 | missing_evidence |
| 45 | 减速器 | 减速器 | 机械设备 | 67.3 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 46 | 云计算 | 云计算 | 计算机 | 66.15 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 有机硅 | 有机硅 | 基础化工 | 65.25 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 英伟达 | 英伟达 | 电子 | 63.95 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 49 | 通信设备 | 通信设备 | 通信 | 61.42 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 电子化学品 | 电子化学品 | 基础化工 | 58.59 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：消费电子

- **标准概念**：消费电子
- **申万一级**：电子
- **评分**：173.44
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.63%，边际量 11.85%，成交额 1265.59 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.63%，边际量11.85%，成交1265.59亿 |
| new_high_direction | 47.44 | 新高股11只，新高成交322.94亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费电子 | 10 |
| 消费电子设备 | 5 |
| 3C制造 | 2 |
| 3D打印钛合金 | 2 |
| 8.6代OLED产线 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三利谱 | 002876 | 消费电子 | 显示面板材料间接相关 | peripheral | L1 | 10 |
| 东山精密 | 002384 | 消费电子 | FPC/PCB精密制造 | peripheral | L1 | 10 |
| 东睦股份 | 600114 | 消费电子 | 消费电子MIM结构件供应商 | related | L1 | 10 |
| 中石科技 | 300684 | 消费电子 | 消费电子高导热材料供应商 | core | L1 | 10 |
| 中科蓝讯 | 688332 | 消费电子 | 蓝牙耳机及音箱音频SoC芯片供应商 | core | L1 | 10 |
| 乐凯胶片 | 600135 | 消费电子 | 偏光片/显示薄膜及锂电外包装铝塑膜供应商 | related | L1 | 10 |
| 乐鑫科技 | 688018 | 消费电子 | 消费级及智能家居IoT芯片供应商 | core | L1 | 10 |
| 乾照光电 | 300102 | 消费电子 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 2：MR(混合现实)

- **标准概念**：HAMR
- **申万一级**：电子
- **评分**：168.41
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.44%，边际量 20.76%，成交额 1022.87 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.44%，边际量20.76%，成交1022.87亿 |
| new_high_direction | 42.41 | 新高股7只，新高成交368.74亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| HAMR | 5 |
| MRAM | 5 |
| MRI设备 | 5 |
| MRI超导磁体 | 5 |
| MR芯片 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 戈碧迦 | 920438 | HAMR | HAMR玻璃盘片基材供应商，切入西数/希捷供应链 | core | L1_L3_candidate | 10 |
| 水晶光电 | 002273 | HAMR | HAMR玻璃盘片加工，切入西数/希捷供应链 | core | L1_L3_candidate | 10 |
| 蓝思科技 | 300433 | HAMR | 玻璃基(CoPoS)及盘片加工(HAMR)储备受益厂商 | peripheral | L1 | 10 |
| 健信超导 | - | MRI超导磁体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 瑞普生物 | 300119 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 5 |
| 生物股份 | 600201 | mRNA疫苗 | 兽用生物制品（猪、牛、禽 | related | L1_L3_candidate | 5 |
| 科前生物 | 688526 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 5 |
| 金河生物 | 002688 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 5 |

## 候选 3：氧化锆

- **标准概念**：二氧化锆
- **申万一级**：有色金属
- **评分**：105.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（5），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 105.0 | 连板股3只，最高4板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 二氧化锆 | 5 |
| 锆材料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方锆业 | 002167 | 二氧化锆 | 二氧化锆及复合氧化锆产品供应商 | peripheral | graph_only | 10 |
| 三祥新材 | 603663 | 化工 | 电熔氧化锆相关产品供应商 | related | L2 | 1 |
| 爱迪特 | 301580 | 医疗器械 | 数字化齿科材料供应商，主营氧化锆瓷块等口腔修复材料，并向口腔种植手术机器... | related | L1_L3_candidate | 1 |
| 凯盛科技 | 600552 | 新材料 | 高熔点锆系熔融及微纳粉体新材料（氧化锆等）全球核心制造平台 | core | L1 | 1 |
| 国瓷材料 | 300285 | 氮化铝 | 氮化铝基板 | related | L1 | 1 |

## 候选 4：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：102.9
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股57只，新高成交2861.2500000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.9 | 涨停14只，市场占比14.29，排名10 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 存储芯片 | 10 |
| AI基础设施与国产算力 | 2 |
| AI存储 | 2 |
| AI手机 | 2 |
| AI芯片 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士 | 000660 | 存储芯片 | 图谱弱关联 | peripheral | graph_only | 10 |
| 万润科技 | 002654 | 存储芯片 | 半导体存储器业务 | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 存储芯片 | 股权投资潜在相关 | peripheral | L2_candidate | 10 |
| 上海合晶 | 688584 | 存储芯片 | 存储晶圆制造上游硅片材料潜在供应商 | peripheral | L2_candidate | 10 |
| 东芯股份 | 688110 | 存储芯片 | 中小容量存储(NOR/NAND/DRAM)+联营砺算GPU | peripheral | L1 | 10 |
| 中微公司 | 688012 | 存储芯片 | 上游设备 | peripheral | L1 | 10 |
| 中微半导 | 688380 | 存储芯片 | MCU（8位、32位）、SoC、ASIC | related | L1_L3_candidate | 10 |
| 中电港 | 001287 | 存储芯片 | 存储芯片分销、AI算力芯片分销、机器人解决方案、端侧AI | core | L1_L3_candidate | 10 |

## 候选 5：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：102.27
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 67.02 | 新高股31只，新高成交1361.42亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.25 | 涨停15只，市场占比15.31，排名8 |

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

## 候选 6：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：101.15
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股48只，新高成交1730.7099999999994亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比9.18，排名18 |

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
| 三孚新科 | 688359 | 先进封装 | TGV玻璃基板设备+药水 | related | L1_L3_candidate | 10 |
| 三安光电 | 600703 | 先进封装 | 光芯片（AI算力光互联）、碳化硅（SiC功率器件）、Mini | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 先进封装 | 投资潜在相关（非直接产业链） | peripheral | L2_candidate | 10 |
| 上海新阳 | 300236 | 先进封装 | 集成电路制造及先进封装用关键工艺材料（电镀液 | related | L1_L3_candidate | 10 |
| 东威科技 | 688700 | 先进封装 | 半导体封装电镀设备 | related | L1_L3_candidate | 10 |
| 中京电子 | 002579 | 先进封装 | - | - | - | 10 |
| 中国巨石 | 600176 | 先进封装 | 先进封装上游高端电子布潜在相关 | peripheral | L2_candidate | 10 |
| 中微公司 | 688012 | 先进封装 | 封装设备 | related | L2_candidate | 10 |

## 候选 7：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：101.15
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股58只，新高成交2449.2499999999995亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比9.18，排名19 |

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
| 宏微科技 | 688711 | 功率半导体 | IGBT模块、SiC模块、GaN器件 | related | L1_L3_candidate | 10 |
| 富乐德 | 301297 | 功率半导体 | 覆铜陶瓷载板（DCB/AMB/DPC）、泛半导体精密洗净服务、半导体核心... | core | L1_L3_candidate | 10 |

## 候选 8：华为手机

- **标准概念**：华为手机
- **申万一级**：电子
- **评分**：100.0
- **触发类型**：double_red、capacity_industry
- **盘面信号**：涨幅 0.6%，边际量 16.71%，成交额 771.46 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.6%，边际量16.71%，成交771.46亿 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 利和兴 | 301013 | 华为生态 | MLCC、半导体设备零部件、CPO、光模块设备 | core | L1_L3_candidate | 1 |

## 候选 9：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：98.43
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 64.58 | 新高股34只，新高成交1166.5000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比11.22，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人形机器人 | 10 |
| AI终端 | 2 |
| MIM金属注射成型 | 2 |
| PEEK材料 | 2 |
| 传感器 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万凯新材 | 301216 | 人形机器人 | 聚酯瓶片(PET)、天然气制乙二醇(MEG)、rPET生物酶法再生 | related | L1_L3_candidate | 10 |
| 三花智控 | 002050 | 人形机器人 | 全产业链（执行器、减速器、丝杠、灵巧手） | core | L1 | 10 |
| 东睦股份 | 600114 | 人形机器人 | MIM金属注射成形（折叠屏铰链、AI连接器、机器人灵巧手零件）、P&S粉... | related | L1_L3_candidate | 10 |
| 东阳光 | 600673 | 人形机器人 | 具身智能（人形机器人） | core | L1_L3_candidate | 10 |
| 中大力德 | 002896 | 人形机器人 | 机器人核心零部件供应商 | related | L2 | 10 |
| 中控技术 | 688777 | 人形机器人 | TPT工业大模型、DCS、SIS控制系统、UCS通用控制系统 | core | L1_L3_candidate | 10 |
| 中欣氟材 | 002915 | 人形机器人 | 电子级氢氟酸（半导体/光伏）、PEEK材料（DFBP核心单体）、BPEF... | related | L1_L3_candidate | 10 |
| 中研股份 | 688716 | 人形机器人 | 机器人关节轻量化PEEK材料潜在供应商 | related | L1 | 10 |

## 候选 10：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：95.7
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 58.0 | 新高股47只，新高成交1680.36亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.7 | 涨停22只，市场占比22.45，排名2 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 10 |
| AI数据中心 | 5 |
| AI数据中心储能 | 5 |
| 云计算数据中心 | 5 |
| 数据中心交换机 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中仑新材 | 301565 | AI数据中心 | BOPP新能源膜材（薄膜电容器基膜）、功能性BOPA膜材、生物降解BOP... | related | L1_L3_candidate | 10 |
| 中国西电 | 601179 | AI数据中心 | 特高压设备、主网一次设备、海外电力设备 | related | L1_L3_candidate | 10 |
| 亨通光电 | 600487 | AI数据中心 | 特别是AI数据中心需求驱动的光纤业务 | core | L1_L3_candidate | 10 |
| 京泉华 | 002885 | AI数据中心 | MFT高频变压器（AI数据中心） | related | L1_L3_candidate | 10 |
| 佛燃能源 | 002911 | AI数据中心 | 城市燃气（天然气销售与输配）、能源化工服务及延伸（油品/化工品贸易）、绿... | related | L1_L3_candidate | 10 |
| 天齐锂业 | 002466 | AI数据中心 | 锂矿采选、锂化工产品（碳酸锂、氢氧化锂 | related | L1_L3_candidate | 10 |
| 宏微科技 | 688711 | AI数据中心 | AI数据中心电源 | related | L1_L3_candidate | 10 |
| 宗申动力 | 001696 | AI数据中心 | 通用机械、摩托车发动机、航空动力 | related | L1_L3_candidate | 10 |
