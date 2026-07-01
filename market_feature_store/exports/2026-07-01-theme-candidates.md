# 2026-07-01 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：36397.84
- **上涨家数**：4240
- **涨停 / 跌停**：148 / 7
- **容量前三行业**：1.电子(34.7%, super_capacity)、2.电力设备(8.4%, normal)、3.机械设备(7.9%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 连板未映射 | - | 电力设备 | 279.0 | limit_advance_cluster、capacity_industry | 0 | 0 | 0 | placeholder_market_theme |
| 2 | 氢能源 | 氢能源 | 电力设备 | 194.57 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 3 | AI眼镜 | AI眼镜 | 电子 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 4 | 风电 | 风电 | 电力设备 | 188.62 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 光刻胶 | 光刻胶 | 电子 | 187.74 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 6 | 燃料电池 | 燃料电池 | 电力设备 | 182.52 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 信创 | 信创 | 计算机 | 176.14 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 数据要素 | 数据要素 | 计算机 | 174.74 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 9 | 超级电容 | 超级电容 | 电力设备 | 171.2 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 创新药 | 创新药 | 医药生物 | 171.17 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 算力租赁 | 算力租赁 | 计算机 | 170.86 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 12 | 化学制品 | 化工周期 | 基础化工 | 169.33 | double_red、limit_heat、new_high_direction、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 13 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 168.91 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 8 | 1 | - |
| 14 | 化学制药 | 原料药 | 医药生物 | 167.96 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 15 | 氟化工 | 氟化工 | 基础化工 | 166.62 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | AIGC | AIGC | 传媒 | 164.46 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 17 | 小金属 | 小金属 | 有色金属 | 161.14 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 18 | 证券 | 证券 | 非银金融 | 159.88 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 19 | 云计算 | 云计算 | 计算机 | 156.87 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 磷化工 | 磷化工 | 基础化工 | 155.21 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 储能 | 储能 | 电力设备 | 137.35 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 22 | 固态电池 | 固态电池 | 电力设备 | 132.8 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 23 | 人工智能 | 人工智能 | 计算机 | 129.8 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 光伏 | 光伏 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 25 | 光伏设备 | 光伏设备 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 电池 | 4C电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 27 | 钠离子电池 | 钠离子电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 28 | 存储芯片 | 存储芯片 | 计算机 | 125.85 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 29 | AI应用 | AI应用 | 计算机 | 124.9 | double_red、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 30 | AI智能体 | AI智能体 | 计算机 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 低空经济 | 低空经济 | 国防军工 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 32 | 雅下水电 | 雅下水电 | 电力设备 | 122.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 33 | ChatGPT | ChatGPT | 传媒 | 116.0 | double_red、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 34 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 35 | IT服务 | IT服务 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 华为昇腾 | 华为昇腾 | 计算机 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 37 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 多模态AI | 多模态AI | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 3 | 1 | - |
| 39 | 小米汽车 | 小米汽车 | 汽车 | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 40 | 稀土永磁 | 稀土永磁 | 有色金属 | 116.0 | double_red、new_high_cluster | 5 | 12 | 2 | - |
| 41 | 黄金 | 黄金 | 有色金属 | 116.0 | double_red、new_high_cluster | 5 | 12 | 2 | - |
| 42 | 软件开发 | AIGC | 计算机 | 114.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 43 | 数字货币 | 数字货币 | 计算机 | 112.0 | double_red、new_high_cluster | 4 | 3 | 1 | - |
| 44 | 智谱AI | 智谱AI | 计算机 | 110.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 106.0 | double_red、new_high_cluster | 5 | 6 | 1 | - |
| 46 | 共封装光学(CPO) | CPO | 电子 | 100.8 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 47 | 锂电池 | 锂电池 | 电力设备 | 100.0 | double_red、capacity_industry | 5 | 12 | 3 | - |
| 48 | 人形机器人 | 人形机器人 | 机械设备 | 99.05 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 49 | 数据中心 | 数据中心 | 计算机 | 95.0 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 新型工业化 | 新型工业化 | 机械设备 | 94.21 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：连板未映射

- **标准概念**：-
- **申万一级**：电力设备
- **评分**：279.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 279.0 | 连板股23只，最高3板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 2：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：194.57
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.61%，边际量 14.52%，成交额 3157.24 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（6），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.61%，边际量14.52%，成交3157.24亿 |
| new_high_direction | 62.12 | 新高股46只，新高成交969.5200000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 6.45 | 涨停7只，市场占比4.7，排名28 |

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
| 岱勒新材 | 300700 | 氢能源 | 氢能源石墨双极板 | related | L1_L3_candidate | 10 |
| 阳光电源 | 300274 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 隆基绿能 | 601012 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 雪人股份 | 002639 | 氢能源 | 上游设备 | peripheral | L1 | 10 |
| 航天工程 | 603698 | 氢能 | 氢能业务 | related | L1 | 1 |

## 候选 3：AI眼镜

- **标准概念**：AI眼镜
- **申万一级**：电子
- **评分**：194.0
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.51%，边际量 10.24%，成交额 3781.97 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.51%，边际量10.24%，成交3781.97亿 |
| new_high_direction | 68.0 | 新高股61只，新高成交1802.74亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 4：风电

- **标准概念**：风电
- **申万一级**：电力设备
- **评分**：188.62
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.14%，边际量 15.03%，成交额 3290.8 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.14%，边际量15.03%，成交3290.8亿 |
| new_high_direction | 55.82 | 新高股26只，新高成交465.33亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 6.8 | 涨停8只，市场占比5.37，排名22 |

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

## 候选 5：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：187.74
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.09%，边际量 11.02%，成交额 1305.58 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.09%，边际量11.02%，成交1305.58亿 |
| new_high_direction | 61.74 | 新高股39只，新高成交939.03亿，容量前三=True |
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

## 候选 6：燃料电池

- **标准概念**：燃料电池
- **申万一级**：电力设备
- **评分**：182.52
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.79%，边际量 11.67%，成交额 1604.29 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.79%，边际量11.67%，成交1604.29亿 |
| new_high_direction | 56.52 | 新高股25只，新高成交521.9800000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 燃料电池 | 10 |
| SOFC燃料电池 | 5 |
| SOFC（固体氧化物燃料电池） | 5 |
| 固体氧化物燃料电池(SOFC) | 5 |
| 储能电池 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 壹石通 | 688733 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 三环集团 | 300408 | SOFC（固体氧化物燃料电池） | 陶瓷材料与零部件潜在相关 | peripheral | L1 | 20 |
| 三花智控 | 002050 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国巨石 | 600176 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国船舶 | 600150 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中材科技 | 002080 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中航光电 | 002179 | SOFC（固体氧化物燃料电池） | - | - | - | 20 |
| 京东方A | 000725 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 7：信创

- **标准概念**：信创
- **申万一级**：计算机
- **评分**：176.14
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.11%，边际量 11.93%，成交额 2079.09 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.11%，边际量11.93%，成交2079.09亿 |
| new_high_direction | 51.59 | 新高股31只，新高成交927.0699999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比8.72，排名10 |

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

## 候选 8：数据要素

- **标准概念**：数据要素
- **申万一级**：计算机
- **评分**：174.74
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.53%，边际量 28.09%，成交额 2036.69 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.53%，边际量28.09%，成交2036.69亿 |
| new_high_direction | 50.54 | 新高股23只，新高成交843.3899999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比8.05，排名12 |

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
| 三维天地 | 301159 | 数据要素 | AI+实验室（SunwayLink/S-tab/SW-Foundry/S... | related | L1_L3_candidate | 10 |
| 东方国信 | 300166 | 数据要素 | 数据要素 | related | L1_L3_candidate | 10 |
| 东软集团 | 600718 | 数据要素 | 智能汽车互联、医疗健康信息化、数据价值化 | related | L1_L3_candidate | 10 |
| 中创股份 | 688695 | 数据要素 | 中间件软件销售、中间件定制化开发、中间件运维服务 | related | L1_L3_candidate | 10 |
| 中科曙光 | 603019 | 数据要素 | 芯片/核心器件 | related | L1_L3_candidate | 10 |
| 久远银海 | 002777 | 数据要素 | 数据要素 | related | L1_L3_candidate | 10 |
| 云赛智联 | 600602 | 数据要素 | 云计算及大数据、行业解决方案、智能产品 | related | L1_L3_candidate | 10 |
| 启明星辰 | 002439 | 数据要素 | AI应用安全（MAS产品矩阵）、中国移动协同业务、传统网络安全（防火墙/... | core | L1_L3_candidate | 10 |

## 候选 9：超级电容

- **标准概念**：超级电容
- **申万一级**：电力设备
- **评分**：171.2
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.27%，边际量 21.28%，成交额 1072.29 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.27%，边际量21.28%，成交1072.29亿 |
| new_high_direction | 45.2 | 新高股9只，新高成交368.30999999999995亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 超级电容 | 10 |
| MLCC | 2 |
| 电容 | 2 |
| 电容薄膜 | 2 |
| 电解液 | 2 |

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

## 候选 10：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：171.17
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.71%，边际量 29.97%，成交额 1333.34 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.71%，边际量29.97%，成交1333.34亿 |
| new_high_direction | 48.72 | 新高股81只，新高成交697.4100000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比4.7，排名30 |

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
