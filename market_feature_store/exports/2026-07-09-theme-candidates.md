# 2026-07-09 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：29135.4
- **上涨家数**：2486
- **涨停 / 跌停**：75 / 12
- **容量前三行业**：1.电子(35.6%, super_capacity)、2.通信(8.5%, normal)、3.机械设备(7.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 半导体 | 半导体 | 电子 | 195.96 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 先进封装 | 先进封装 | 电子 | 187.69 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 3 | 存储芯片 | 存储芯片 | 电子 | 186.91 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 4 | 数据中心 | 数据中心 | 计算机 | 174.46 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | AI眼镜 | AI眼镜 | 电子 | 170.96 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 6 | 英伟达 | 英伟达 | 电子 | 165.88 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 液冷服务器 | 液冷服务器 | 电力设备 | 165.07 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 8 | 共封装光学(CPO) | CPO | 电子 | 164.62 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 9 | 信创 | 信创 | 计算机 | 162.92 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 无人驾驶 | 无人驾驶 | 汽车 | 162.45 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 商业航天 | 商业航天 | 国防军工 | 162.42 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 12 | 算力租赁 | 算力租赁 | 计算机 | 161.23 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 13 | 星闪 | 星闪技术 | 通信 | 160.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 3 | 0 | missing_evidence |
| 14 | 云计算 | 云计算 | 计算机 | 160.05 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 15 | 6G | 6G | 通信 | 158.4 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | 数据要素 | 数据要素 | 计算机 | 156.74 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | AIGC | AIGC | 传媒 | 154.59 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 通信设备 | 通信设备 | 通信 | 153.65 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | AI手机 | AI手机 | 电子 | 153.26 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 4 | - |
| 20 | ChatGPT | ChatGPT | 传媒 | 149.77 | double_red、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 21 | 光纤 | 光纤 | 通信 | 149.5 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 22 | 多模态AI | 多模态AI | 计算机 | 149.41 | double_red、new_high_direction、new_high_cluster | 2 | 3 | 1 | - |
| 23 | 半导体设备 | 半导体设备 | 电子 | 148.64 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 24 | 海峡两岸 | 海峡两岸 | 综合 | 147.6 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 25 | 计算机设备 | 计算机设备 | 计算机 | 143.08 | double_red、new_high_direction、new_high_cluster | 1 | 9 | 1 | - |
| 26 | 风电 | 风电 | 电力设备 | 141.45 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 27 | 量子科技 | 量子科技 | 计算机 | 133.28 | double_red、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 28 | 芯片 | 芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 29 | 人工智能 | 人工智能 | 计算机 | 125.95 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 30 | 低空经济 | 低空经济 | 国防军工 | 123.85 | double_red、limit_heat、new_high_cluster | 5 | 12 | 3 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | PCB | PCB | 电子 | 122.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 32 | AI PC | AI PC | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 2 | - |
| 33 | AI应用 | AI应用 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 5 | - |
| 34 | AI智能体 | AI智能体 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 35 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 36 | 光刻胶 | 光刻胶 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 3 | - |
| 37 | 华为手机 | 华为手机 | 电子 | 116.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 38 | 长安汽车 | 长安汽车 | 汽车 | 114.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 39 | 大飞机 | 大飞机 | 国防军工 | 110.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 元件 | 光学元件 | 电子 | 106.1 | double_red、capacity_industry、limit_heat | 5 | 12 | 0 | missing_evidence |
| 41 | 可控核聚变 | 可控核聚变 | 电力设备 | 106.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 太赫兹 | 6G产业 | 国防军工 | 106.0 | double_red、new_high_cluster | 1 | 4 | 0 | missing_evidence |
| 43 | 特高压 | 特高压 | 电力设备 | 106.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 超级电容 | 超级电容 | 电力设备 | 106.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 45 | MR(混合现实) | HAMR | 电子 | 100.0 | double_red、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 46 | 自动化设备 | 自动化设备 | 机械设备 | 100.0 | double_red、capacity_industry | 5 | 12 | 2 | - |
| 47 | 毫米波雷达 | 毫米波雷达 | 汽车 | 97.15 | double_red、limit_heat | 5 | 12 | 1 | - |
| 48 | 业绩 | AI PC | 计算机 | 93.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 49 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 90.0 | double_red | 2 | 9 | 1 | - |
| 50 | 钙钛矿电池 | 钙钛矿电池 | 电力设备 | 90.0 | double_red | 0 | 6 | 0 | missing_concept、missing_evidence |

## 五、核心候选明细

## 候选 1：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：195.96
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 6.52%，边际量 18.21%，成交额 5898.4 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅6.52%，边际量18.21%，成交5898.4亿 |
| new_high_direction | 61.41 | 新高股17只，新高成交913.0199999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.55 | 涨停13只，市场占比17.33，排名1 |

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
| 上海合晶 | 688584 | 功率半导体 | 为功率器件/模拟芯片提供外延片衬底 | related | L2 | 10 |
| 东微半导 | 688261 | 功率半导体 | 受益标的 | core | pricing | 10 |
| 华天科技 | 002185 | 功率半导体 | - | - | - | 10 |
| 华润微 | 688396 | 功率半导体 | 功率半导体相关产品/材料供应商 | related | L2 | 10 |
| 华虹宏力 | 688347 | 功率半导体 | 市场信号弱关联 | related | L2_candidate | 10 |
| 士兰微 | 600460 | 功率半导体 | 分立器件产品营收63.79亿元/毛利率12.22%/同比+17.32% | core | L2 | 10 |
| 天岳先进 | 688234 | 功率半导体 | SiC衬底 | core | L2 | 10 |

## 候选 2：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：187.69
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.52%，边际量 16.6%，成交额 4790.99 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.52%，边际量16.6%，成交4790.99亿 |
| new_high_direction | 49.99 | 新高股13只，新高成交303.09999999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.7 | 涨停22只，市场占比29.33，排名1 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 3：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：186.91
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 6.1%，边际量 17.87%，成交额 6301.33 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅6.1%，边际量17.87%，成交6301.33亿 |
| new_high_direction | 49.91 | 新高股10只，新高成交632.9699999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.0 | 涨停20只，市场占比26.67，排名1 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 存储芯片 | 10 |
| AI存储 | 2 |
| AI手机 | 2 |
| AI芯片 | 2 |
| CPU | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士 | 000660 | 存储芯片 | 图谱弱关联 | peripheral | graph_only | 10 |
| 万润科技 | 002654 | 存储芯片 | 半导体存储器业务 | related | L1_L3_candidate | 10 |
| 上峰水泥 | 000672 | 存储芯片 | 股权投资潜在相关 | peripheral | L2_candidate | 10 |
| 上海合晶 | 688584 | 存储芯片 | 存储晶圆制造上游硅片材料潜在供应商 | peripheral | L2_candidate | 10 |
| 东芯股份 | 688110 | 存储芯片 | SLC NAND存储设计 | core | L1 | 10 |
| 中微公司 | 688012 | 存储芯片 | 上游设备 | peripheral | L1 | 10 |
| 中微半导 | 688380 | 存储芯片 | MCU（8位、32位）、SoC、ASIC | related | L1_L3_candidate | 10 |
| 中电港 | 001287 | 存储芯片 | 下游元器件分销平台龙头 | peripheral | L1_L3_candidate | 10 |

## 候选 4：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：174.46
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.64%，边际量 23.64%，成交额 8508.12 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.64%，边际量23.64%，成交8508.12亿 |
| new_high_direction | 50.26 | 新高股22只，新高成交820.42亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比16.0，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据中心 | 10 |
| AI数据中心 | 5 |
| AI数据中心储能 | 5 |
| IDC数据中心 | 5 |
| 云计算数据中心 | 5 |

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

## 候选 5：AI眼镜

- **标准概念**：AI眼镜
- **申万一级**：电子
- **评分**：170.96
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.22%，边际量 18.53%，成交额 2928.49 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.22%，边际量18.53%，成交2928.49亿 |
| new_high_direction | 40.51 | 新高股6只，新高成交328.50000000000006亿，容量前三=True |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 6.45 | 涨停7只，市场占比9.33，排名1 |

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

## 候选 6：英伟达

- **标准概念**：英伟达
- **申万一级**：电子
- **评分**：165.88
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.21%，边际量 24.51%，成交额 1646.64 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.21%，边际量24.51%，成交1646.64亿 |
| new_high_direction | 41.88 | 新高股6只，新高成交438.3500000000001亿，容量前三=True |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 英伟达 | 10 |
| 英伟达GB200 | 5 |
| 英伟达Rubin架构 | 5 |
| 6G产业 | 2 |
| AI PC | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中际旭创 | 300308 | 英伟达 | 产业链供应商 | peripheral | L2_candidate | 10 |
| 华工科技 | 000988 | 英伟达 | - | - | - | 10 |
| 工业富联 | 601138 | 英伟达 | 芯片/核心器件 | core | L2_candidate | 10 |
| 新易盛 | 300502 | 英伟达 | 产业链供应商 | peripheral | L1 | 10 |
| 沪电股份 | 002463 | 英伟达 | 产业链供应商 | core | L2_candidate | 10 |
| 浪潮信息 | 000977 | 英伟达 | 下游应用 | peripheral | L1_L3_candidate | 10 |
| 生益科技 | 600183 | 英伟达 | 6.4 投资策略建议 | peripheral | L1 | 10 |
| 胜宏科技 | 300476 | 英伟达 | 产业链供应商 | core | L2_candidate | 10 |

## 候选 7：液冷服务器

- **标准概念**：液冷服务器
- **申万一级**：电力设备
- **评分**：165.07
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.28%，边际量 20.85%，成交额 3983.64 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.28%，边际量20.85%，成交3983.64亿 |
| new_high_direction | 41.92 | 新高股11只，新高成交681.98亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比12.0，排名17 |

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

## 候选 8：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：164.62
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.35%，边际量 18.38%，成交额 6127.59 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.35%，边际量18.38%，成交6127.59亿 |
| new_high_direction | 36.42 | 新高股4只，新高成交225.74亿，容量前三=True |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比16.0，排名1 |

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

## 候选 9：信创

- **标准概念**：信创
- **申万一级**：计算机
- **评分**：162.92
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.24%，边际量 27.49%，成交额 2133.88 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.24%，边际量27.49%，成交2133.88亿 |
| new_high_direction | 46.92 | 新高股23只，新高成交553.47亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 信创 | 10 |
| 信创云 | 5 |
| 信创产业 | 5 |
| 信创存储 | 5 |
| 党政信创 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三六零 | 601360 | 信创 | 信创安全防护潜在参与方 | related | L1 | 10 |
| 三维天地 | 301159 | 信创 | AI+实验室（SunwayLink/S-tab/SW-Foundry/S... | related | L1_L3_candidate | 10 |
| 东土科技 | 300353 | 信创 | 工业操作系统（鸿道Intewell）、智能控制器（NewPre系列）、工... | related | L1_L3_candidate | 10 |
| 东方中科 | 002819 | 信创 | 测试技术与服务（占比~81%）、数字安全与数智应用（占比~19%） | related | L2 | 10 |
| 中创股份 | 688695 | 信创 | 中间件软件销售、中间件定制化开发、中间件运维服务 | core | L1_L3_candidate | 10 |
| 中国软件 | 600536 | 信创 | 党政信创基础软件和解决方案平台 | core | L1 | 10 |
| 中国长城 | 000066 | 信创 | 信创整机和计算设备供应商 | core | L1 | 10 |
| 中孚信息 | 300659 | 信创 | 密评（密码应用合规评估）业务、保密产品、数据安全 | related | L1_L3_candidate | 10 |

## 候选 10：无人驾驶

- **标准概念**：无人驾驶
- **申万一级**：汽车
- **评分**：162.45
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.48%，边际量 19.06%，成交额 3807.38 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.48%，边际量19.06%，成交3807.38亿 |
| new_high_direction | 37.2 | 新高股10只，新高成交416.34000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.25 | 涨停15只，市场占比20.0，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 无人驾驶 | 10 |
| Robotaxi | 2 |
| 低空经济 | 2 |
| 智能交通与低空空天基础设施 | 2 |
| 毫米波雷达 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万集科技 | 300552 | 无人驾驶 | 激光雷达/MEMS固态雷达供应商，适配城市NOA与L4客车场景 | related | L1_L3_candidate | 10 |
| 万马科技 | 300698 | 无人驾驶 | L4级无人驾驶高阶网联解决方案供应商 | related | L2 | 10 |
| 保隆科技 | 603197 | 无人驾驶 | 毫米波雷达与汽车传感器供应商 | related | L2_candidate | 10 |
| 千里科技 | 601777 | 无人驾驶 | Robotaxi闭环平台服务商 | related | L1_L3_candidate | 10 |
| 四维图新 | 002405 | 无人驾驶 | 高精地图与智能驾驶数据服务商 | related | L1_L3_candidate | 10 |
| 富临运业 | 002357 | 无人驾驶 | 公路客运运营商，与新石器合营切入L4无人驾驶物流，布局四川文旅低空物流 | related | L1_L3_candidate | 10 |
| 德赛西威 | 002920 | 无人驾驶 | 智能驾驶域控制器供应商 | related | L1_L3_candidate | 10 |
| 拓普集团 | 601689 | 无人驾驶 | 智能底盘供应商 | peripheral | L1 | 10 |
