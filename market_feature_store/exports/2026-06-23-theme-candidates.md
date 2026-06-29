# 2026-06-23 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：探底阶段
- **成交额**：34404.92
- **上涨家数**：2764
- **涨停 / 跌停**：96 / 39
- **容量前三行业**：1.电子(30.3%, super_capacity)、2.有色金属(8.4%, normal)、3.电力设备(8.2%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光纤 | 光纤 | 国防军工 | 173.0 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | 创新药 | 创新药 | 医药生物 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 3 | 氧化锆 | 二氧化锆 | 有色金属 | 111.0 | limit_advance_cluster、capacity_industry | 2 | 5 | 0 | missing_evidence |
| 4 | 风电 | 风电 | 电力设备 | 100.12 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 5 | 液冷服务器 | 液冷服务器 | 电力设备 | 100.1 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 6 | 磷化工 | 磷化工 | 基础化工 | 95.68 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 7 | 先进封装 | 先进封装 | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 8 | 共封装光学(CPO) | CPO | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 9 | 半导体 | 半导体 | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 10 | 存储芯片 | 存储芯片 | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 小金属 | 小金属 | 有色金属 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 12 | 氢能源 | 氢能源 | 电力设备 | 93.78 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 6 | 1 | - |
| 13 | 特高压 | 特高压 | 电力设备 | 93.44 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | AI眼镜 | AI眼镜 | 电子 | 91.62 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 15 | 数据中心 | 数据中心 | 计算机 | 91.15 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | PCB | PCB | 电子 | 90.98 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 17 | 商业航天 | 商业航天 | 国防军工 | 89.4 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 18 | 大金融 | 大金融 | 计算机 | 89.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 19 | 钻石散热 | 钻石散热 | 公用事业 | 89.0 | limit_advance_cluster | 5 | 11 | 2 | - |
| 20 | 可控核聚变 | 可控核聚变 | 电力设备 | 88.1 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 21 | 人形机器人 | 人形机器人 | 机械设备 | 87.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 22 | MCU芯片 | MCU芯片 | 电子 | 85.34 | new_high_direction、new_high_cluster、capacity_industry | 3 | 4 | 1 | - |
| 23 | 光刻胶 | 光刻胶 | 电子 | 82.49 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 24 | 半导体设备 | 半导体设备 | 电子 | 82.4 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 25 | 钠离子电池 | 钠离子电池 | 电力设备 | 82.36 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 26 | 海峡两岸 | 海峡两岸 | 综合 | 82.02 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 27 | 金属铜 | 金属铜 | 有色金属 | 79.53 | new_high_direction、new_high_cluster、capacity_industry | 0 | 1 | 0 | missing_concept、missing_evidence |
| 28 | 化学制品 | 化工周期 | 基础化工 | 77.93 | limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 29 | 光刻机 | 光刻机 | 电子 | 77.7 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 30 | 证券 | 证券 | 非银金融 | 77.61 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | PET铜箔 | PET铜箔 | 电力设备 | 77.58 | new_high_direction、new_high_cluster、capacity_industry | 5 | 10 | 1 | - |
| 32 | 通信设备 | 通信设备 | 通信 | 77.53 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 无人驾驶 | 无人驾驶 | 汽车 | 76.8 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 通用设备 | 金属制品 | 机械设备 | 76.67 | limit_heat、new_high_direction、new_high_cluster | 1 | 8 | 0 | missing_evidence |
| 35 | 氟化工 | 氟化工 | 基础化工 | 76.25 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 稀土永磁 | 稀土永磁 | 有色金属 | 76.13 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 37 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 75.79 | new_high_direction、new_high_cluster、capacity_industry | 0 | 6 | 0 | missing_concept、missing_evidence |
| 38 | 数据要素 | 数据要素 | 计算机 | 75.74 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 39 | 3D打印 | 3D打印 | 机械设备 | 74.63 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 信创 | 信创 | 计算机 | 73.91 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 传感器 | 传感器 | 机械设备 | 73.63 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | AIGC | AIGC | 传媒 | 73.47 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 英伟达 | 英伟达 | 电子 | 72.56 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 44 | 超级电容 | 超级电容 | 电力设备 | 72.49 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 45 | AI PC | AI PC | 电子 | 70.46 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 46 | 机器视觉 | 机器视觉 | 机械设备 | 69.84 | new_high_direction、new_high_cluster | 2 | 9 | 0 | missing_evidence |
| 47 | 6G | 6G | 通信 | 65.94 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 48 | AI手机 | AI手机 | 电子 | 65.83 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 4 | - |
| 49 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 65.53 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | 量子科技 | 量子科技 | 计算机 | 64.95 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：光纤

- **标准概念**：光纤
- **申万一级**：国防军工
- **评分**：173.0
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_direction | 58.0 | 新高股35只，新高成交1886.9699999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 光纤 | 10 |
| AI算力驱动下的MPO光纤连接器产业 | 5 |
| G.654.E光纤 | 5 |
| MPO光纤连接器 | 5 |
| 光棒光纤一体化 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | AI算力驱动下的MPO光纤连接器产业 | 4.4 国产替代进程分析 | peripheral | graph_only | 10 |
| 仕佳光子 | 688313 | AI算力驱动下的MPO光纤连接器产业 | 2025 年净利润预计 4.77-5.1 亿元，对应 PE 约 33 倍 | peripheral | graph_only | 10 |
| 光库科技 | 300620 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 太辰光 | 300570 | AI算力驱动下的MPO光纤连接器产业 | 3.2.1 太辰光（300570） | peripheral | graph_only | 10 |
| 长芯博创 | 300548 | AI算力驱动下的MPO光纤连接器产业 | 上游设备 | peripheral | graph_only | 10 |
| 通光线缆 | 300265 | G.654.E光纤 | 光纤光缆（含OPGW、ADSS电力光缆、G.654.E高端光纤）、输电线... | related | L1_L3_candidate | 10 |
| 华丰科技 | 688629 | MPO光纤连接器 | 高速线模组、高速背板连接器、NPO连接器 | related | L1_L3_candidate | 10 |
| 唯科科技 | 301196 | MPO光纤连接器 | MPO光通信零部件、机器人轻量化部件、新能源汽车零部件、精密注塑模具 | related | L1_L3_candidate | 10 |

## 候选 2：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：123.5
- **触发类型**：double_red、limit_heat、new_high_cluster
- **盘面信号**：涨幅 3.04%，边际量 15.91%，成交额 897.93 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.04%，边际量15.91%，成交897.93亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比10.42，排名5 |

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

## 候选 3：氧化锆

- **标准概念**：二氧化锆
- **申万一级**：有色金属
- **评分**：111.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（5），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 111.0 | 连板股2只，最高3板，容量前三=True |

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

## 候选 4：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：100.12
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 67.67 | 新高股37只，新高成交1413.4900000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比7.29，排名12 |

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
| 中船科技 | 600072 | 海上风电 | 海上风电运维 | related | L1_L3_candidate | 10 |
| 亨通光电 | 600487 | 海上风电 | 3.4 海缆系统环节 | related | L1_L3_candidate | 10 |
| 大金重工 | 002487 | 海上风电 | 海上风电塔筒/基础及出口海工装备供应商，具备欧洲项目交付和海工运输能力 | related | L3 | 10 |
| 天顺风能 | 002531 | 海上风电 | 5.3 塔筒与桩基企业分析 | related | L1_L3_candidate | 10 |

## 候选 5：液冷服务器

- **标准概念**：液冷服务器
- **申万一级**：电力设备
- **评分**：100.1
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股49只，新高成交1504.98亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比6.25，排名15 |

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
| 中兴通讯 | 000063 | 液冷服务器 | - | - | - | 10 |
| 中石科技 | 300684 | 液冷服务器 | 导热/屏蔽材料配套供应商 | peripheral | L2 | 10 |
| 中科曙光 | 603019 | 液冷服务器 | 浸没式液冷服务器/算力中心液冷基础设施供应商 | related | L1_L3_candidate | 10 |
| 中航光电 | 002179 | 液冷服务器 | - | - | - | 10 |
| 冰轮环境 | 000811 | 液冷服务器 | AIDC液冷一次侧冷水机组/压缩机国产替代受益名单 | peripheral | graph_only | 10 |
| 利和兴 | 301013 | 液冷服务器 | MLCC（片式多层陶瓷电容器）制造、智能制造设备 | related | L1_L3_candidate | 10 |

## 候选 6：磷化工

- **标准概念**：磷化工
- **申万一级**：基础化工
- **评分**：95.68
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.68 | 新高股25只，新高成交454.35999999999996亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 磷化工 | 10 |
| 化工新材料 | 2 |
| 化肥 | 2 |
| 周期资源 | 2 |
| 垂直整合 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云图控股 | 002539 | 磷化工 | 远期磷矿增量/复合肥观察标的 | peripheral | L2_candidate | 10 |
| 云天化 | 600096 | 磷化工 | 磷矿资源/磷肥/磷酸铁一体化龙头 | core | L1_L3_candidate | 10 |
| 六国化工 | 600470 | 磷化工 | 磷复肥/磷酸二铵企业 | related | L2_candidate | 10 |
| 兴发集团 | 600141 | 磷化工 | 磷化工全产业链/草甘膦/电子化学品龙头 | core | L1_L3_candidate | 10 |
| 天赐材料 | 002709 | 磷化工 | 六氟磷酸锂/电解液验证指标 | peripheral | L2_candidate | 10 |
| 川发龙蟒 | 002312 | 磷化工 | 工业级磷酸一铵/磷酸铁锂一体化 | core | L1_L3_candidate | 10 |
| 川恒股份 | 002895 | 磷化工 | 磷酸铁细分龙头/磷矿增量标的 | core | L1_L3_candidate | 10 |
| 川金诺 | 300505 | 磷化工 | 湿法磷酸/磷酸盐企业 | related | L2_candidate | 10 |

## 候选 7：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：94.0
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股42只，新高成交1933.5199999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 8：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：94.0
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股34只，新高成交2052.5199999999995亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 9：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：94.0
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股57只，新高成交2337.71亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 10：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：94.0
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股56只，新高成交2802.01亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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
