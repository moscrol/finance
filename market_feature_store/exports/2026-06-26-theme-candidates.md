# 2026-06-26 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：探底阶段
- **成交额**：35520.81
- **上涨家数**：790
- **涨停 / 跌停**：60 / 30
- **容量前三行业**：1.电子(34.1%, super_capacity)、2.电力设备(8.4%, normal)、3.通信(8.1%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光学光电子 | LED芯片 | 电子 | 194.75 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 2 | 光刻机 | 光刻机 | 电子 | 185.63 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 3 | 电子化学品 | 电子化学品 | 基础化工 | 165.57 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 连板未映射 | - | 计算机 | 153.0 | limit_advance_cluster | 0 | 0 | 0 | placeholder_market_theme |
| 5 | 存储芯片 | 存储芯片 | 电子 | 100.45 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 6 | 先进封装 | 先进封装 | 电子 | 99.75 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 7 | AI眼镜 | AI眼镜 | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 8 | 共封装光学(CPO) | CPO | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 9 | 半导体 | 半导体 | 电子 | 94.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 10 | 商业航天 | 商业航天 | 国防军工 | 92.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | PCB | PCB | 电子 | 92.0 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 12 | 氢能源 | 氢能源 | 电力设备 | 91.12 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 6 | 1 | - |
| 13 | 液冷服务器 | 液冷服务器 | 电力设备 | 90.99 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | 光纤 | 光纤 | 通信 | 90.73 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 15 | 风电 | 风电 | 电力设备 | 90.23 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 16 | 数据中心 | 数据中心 | 计算机 | 90.1 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | MCU芯片 | MCU芯片 | 电子 | 87.38 | new_high_direction、new_high_cluster、capacity_industry | 3 | 4 | 1 | - |
| 18 | 人形机器人 | 人形机器人 | 机械设备 | 85.85 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 19 | 海峡两岸 | 海峡两岸 | 综合 | 84.93 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 20 | 光刻胶 | 光刻胶 | 电子 | 84.74 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 21 | 半导体设备 | 半导体设备 | 电子 | 84.43 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 22 | 传感器 | 传感器 | 机械设备 | 84.0 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | AI PC | AI PC | 电子 | 83.97 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 24 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 83.91 | new_high_direction、new_high_cluster、capacity_industry | 0 | 6 | 0 | missing_concept、missing_evidence |
| 25 | MLCC | MLCC | 电子 | 83.77 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 26 | 元件 | 光学元件 | 电子 | 82.05 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 27 | 无人驾驶 | 无人驾驶 | 汽车 | 81.77 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 智能座舱 | 智能座舱 | 汽车 | 79.56 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 29 | 机器视觉 | 机器视觉 | 机械设备 | 79.42 | limit_heat、new_high_direction、new_high_cluster | 2 | 9 | 0 | missing_evidence |
| 30 | 新型工业化 | 新型工业化 | 机械设备 | 78.54 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 毫米波雷达 | 毫米波雷达 | 汽车 | 76.72 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 超级电容 | 超级电容 | 电力设备 | 75.62 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 33 | 消费电子 | 消费电子 | 电子 | 75.35 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 34 | TOPCON电池 | TOPCon电池 | 电力设备 | 73.84 | new_high_direction、new_high_cluster、capacity_industry | 5 | 8 | 0 | missing_evidence |
| 35 | 6G | 6G | 通信 | 73.69 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 36 | 信创 | 信创 | 计算机 | 73.37 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 37 | MR(混合现实) | HAMR | 电子 | 68.91 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 38 | HJT电池 | HJT电池 | 电力设备 | 68.58 | new_high_direction、new_high_cluster、capacity_industry | 5 | 4 | 1 | - |
| 39 | 3D打印 | 3D打印 | 机械设备 | 67.81 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 小金属 | 小金属 | 有色金属 | 67.38 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 41 | AI手机 | AI手机 | 电子 | 67.29 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 4 | - |
| 42 | 算力租赁 | 算力租赁 | 计算机 | 66.67 | new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 43 | 氟化工 | 氟化工 | 基础化工 | 62.05 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 长安汽车 | 长安汽车 | 汽车 | 61.1 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 59.73 | new_high_direction、new_high_cluster、capacity_industry | 2 | 8 | 1 | - |
| 46 | 工业母机 | 工业母机 | 机械设备 | 58.96 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 47 | 建筑材料 | 建筑材料 | 建筑材料 | 58.93 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 磷化工 | 磷化工 | 基础化工 | 58.88 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 49 | 玻璃玻纤 | 玻璃纤维 | 建筑材料 | 55.45 | new_high_direction、new_high_cluster | 1 | 3 | 0 | missing_evidence |
| 50 | 量子科技 | 量子科技 | 计算机 | 54.68 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：光学光电子

- **标准概念**：LED芯片
- **申万一级**：电子
- **评分**：194.75
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.11%，边际量 22.98%，成交额 1638.12 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.11%，边际量22.98%，成交1638.12亿 |
| new_high_direction | 63.35 | 新高股26只，新高成交1068.2299999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 5.4 | 涨停4只，市场占比6.67，排名26 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| LED芯片 | 2 |
| 显示材料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 戈碧迦 | 920438 | 6G通信 | 光学玻璃、特种功能玻璃、半导体玻璃载板 | related | L1_L3_candidate | 1 |
| 洲明科技 | 300232 | 8K超高清 | 智慧显示、智能照明、AI及光显解决方案 | related | L1_L3_candidate | 1 |
| 万润科技 | 002654 | AI存储 | 半导体存储器业务 | related | L1_L3_candidate | 1 |
| 宝明科技 | 002992 | AI服务器 | 复合铜箔业务（PP基复合铜箔）、HVLP5代高频高速铜箔业务 | related | L1_L3_candidate | 1 |
| 江苏日久光电 | 003015 | AI眼镜 | AI眼镜用ITO导电膜 | related | L1_L3_candidate | 1 |
| 沃格光电 | 603773 | CPI聚酰亚胺 | 玻璃基新型显示、泛半导体应用 | related | L1_L3_candidate | 1 |
| 五方光电 | 002962 | CPO | TGV玻璃通孔基板、红外截止滤光片、车载光学、AR/VR光学 | related | L1_L3_candidate | 1 |
| 水晶光电 | 002273 | CPO | AI光学(光通信+光存储) | related | L1_L3_candidate | 1 |

## 候选 2：光刻机

- **标准概念**：光刻机
- **申万一级**：电子
- **评分**：185.63
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.85%，边际量 23.32%，成交额 1076.37 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.85%，边际量23.32%，成交1076.37亿 |
| new_high_direction | 59.63 | 新高股19只，新高成交770.0900000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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
| 中旗新材 | 001212 | 光刻机 | 半导体设备资产注入预期（星空科技光刻机 | related | L2 | 10 |
| 凤凰光学 | 600071 | 光刻机 | 半导体制造级、精密超高解像度光刻镜头精密抛光及在研平台 | related | L1 | 10 |
| 凯美特气 | 002549 | 光刻机 | 图谱弱关联 | peripheral | graph_only | 10 |
| 北方华创 | 002371 | 光刻机 | 上游设备 | peripheral | graph_only | 10 |
| 同飞股份 | 300990 | 光刻机 | 精密温控系统 | related | L2_curated_research | 10 |
| 奥普光电 | 002338 | 光刻机 | 光源系统/科益虹源股东与整机布局 | core | L2_curated_research | 10 |
| 富创精密 | 688409 | 光刻机 | 半导体设备精密零部件 | related | L2_curated_research | 10 |
| 张江高科 | 600895 | 光刻机 | 上海微电子股权映射/整机链 | related | L2_curated_research | 10 |

## 候选 3：电子化学品

- **标准概念**：电子化学品
- **申万一级**：基础化工
- **评分**：165.57
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.26%，边际量 14.07%，成交额 1082.26 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.26%，边际量14.07%，成交1082.26亿 |
| new_high_direction | 49.57 | 新高股19只，新高成交765.8499999999999亿，容量前三=False |
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

## 候选 4：连板未映射

- **标准概念**：-
- **申万一级**：计算机
- **评分**：153.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 153.0 | 连板股8只，最高6板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：100.45
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股79只，新高成交4714.56亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比11.67，排名11 |

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

## 候选 6：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：99.75
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股64只，新高成交3597.1399999999994亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比8.33，排名16 |

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

## 候选 7：AI眼镜

- **标准概念**：AI眼镜
- **申万一级**：电子
- **评分**：94.0
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 68.0 | 新高股32只，新高成交2148.25亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AI眼镜 | 10 |
| AI眼镜产业链 | 5 |
| AR眼镜 | 2 |
| OCS（光电路交换机） | 2 |
| 全景相机产业 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 京东方A | 000725 | AI眼镜 | 近眼显示/显示面板 | related | L2_curated_research | 10 |
| 佰维存储 | 688525 | AI眼镜 | 存储模组/可穿戴存储 | related | L2_curated_research | 10 |
| 佳禾智能 | 300793 | AI眼镜 | 电声产品设计研发、制造、销售 | core | L1_L3_candidate | 10 |
| 光库科技 | 300620 | AI眼镜 | 市场信号弱关联 | related | L2_candidate | 10 |
| 全志科技 | 300458 | AI眼镜 | 高性价比AI眼镜SoC及高性能AI-ISP处理芯片设计商 | core | L1 | 10 |
| 华勤技术 | 603296 | AI眼镜 | 智能硬件ODM | related | L2_curated_research | 10 |
| 华灿光电 | 300323 | AI眼镜 | Micro LED/显示芯片 | related | L2_curated_research | 10 |
| 卓兆点胶 | 920026 | AI眼镜 | 消费电子点胶设备/阀体（果链核心供应商）、Meta AI眼镜点胶阀、点胶... | core | L1_L3_candidate | 10 |

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
| new_high_direction | 68.0 | 新高股37只，新高成交2263.5099999999998亿，容量前三=True |
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
| new_high_direction | 68.0 | 新高股66只，新高成交3592.9200000000005亿，容量前三=True |
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

## 候选 10：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：92.55
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 58.0 | 新高股51只，新高成交1813.5700000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比21.67，排名2 |

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
