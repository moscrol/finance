# 2026-06-11 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：25518.13
- **上涨家数**：1370
- **涨停 / 跌停**：69 / 33
- **容量前三行业**：1.电子(29.0%, super_capacity)、2.通信(9.3%, normal)、3.电力设备(8.5%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 光刻胶 | 光刻胶 | 电子 | 184.57 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 连板未映射 | 连板未映射 | 电子 | 183.0 | limit_advance_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 3 | 小金属 | 小金属 | 有色金属 | 163.23 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 4 | 电子化学品 | 电子化学品 | 基础化工 | 154.08 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 氟化工 | 氟化工 | 基础化工 | 152.28 | double_red、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 6 | 磷化工 | 磷化工 | 基础化工 | 145.98 | double_red、limit_heat、new_high_direction、new_high_cluster | 3 | 8 | 1 | - |
| 7 | 金属铜 | 金属铜 | 有色金属 | 141.71 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 8 | 金属钴 | 金属钴 | 有色金属 | 132.49 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 9 | 存储芯片 | 存储芯片 | 电子 | 95.45 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 10 | 先进封装 | 先进封装 | 电子 | 91.36 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 盐湖提锂 | 外部供锂 | 有色金属 | 90.0 | double_red | 1 | 1 | 0 | missing_evidence |
| 12 | 半导体 | 半导体 | 电子 | 87.82 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 13 | 氢能源 | 氢能源 | 电力设备 | 85.14 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 4 | 1 | - |
| 14 | PCB | PCB | 电子 | 84.57 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 15 | 风电 | 风电 | 电力设备 | 81.89 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 16 | 液冷服务器 | 液冷服务器 | 电力设备 | 80.57 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 17 | 商业航天 | 商业航天 | 国防军工 | 80.43 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 18 | 数据中心 | 数据中心 | 计算机 | 78.03 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 海峡两岸 | 海峡两岸 | 综合 | 75.44 | limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 20 | 燃料电池 | SOFC燃料电池 | 电力设备 | 75.44 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 21 | 共封装光学(CPO) | CPO | 电子 | 73.57 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 22 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 73.4 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 23 | 光刻机 | 光刻机 | 电子 | 72.46 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 24 | 化学制品 | 化工周期 | 基础化工 | 72.37 | limit_heat、new_high_direction、new_high_cluster | 3 | 7 | 0 | missing_evidence |
| 25 | PET铜箔 | PET铜箔 | 电力设备 | 70.83 | new_high_direction、new_high_cluster、capacity_industry | 5 | 9 | 1 | - |
| 26 | 可控核聚变 | 可控核聚变 | 电力设备 | 69.6 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 27 | 人形机器人 | 人形机器人 | 机械设备 | 69.55 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 28 | MLCC | MLCC | 电子 | 68.48 | new_high_direction、new_high_cluster、capacity_industry | 5 | 9 | 1 | - |
| 29 | 银行 | 区块链 | 银行 | 68.05 | new_high_direction、new_high_cluster | 3 | 1 | 0 | missing_evidence |
| 30 | 元件 | 电子元件 | 电子 | 67.38 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 钠离子电池 | 储能 | 电力设备 | 67.04 | new_high_direction、new_high_cluster、capacity_industry | 5 | 9 | 0 | missing_evidence |
| 32 | 无人驾驶 | 无人驾驶 | 汽车 | 66.86 | limit_heat、new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 33 | AI眼镜 | AI眼镜 | 电子 | 62.47 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 34 | 特高压 | 特高压 | 电力设备 | 61.48 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 35 | MCU芯片 | MCU芯片 | 电子 | 59.92 | new_high_direction、new_high_cluster、capacity_industry | 3 | 2 | 1 | - |
| 36 | 6G | 6G | 通信 | 53.4 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 37 | 传感器 | 传感器 | 机械设备 | 53.12 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 38 | 超级电容 | 超级电容 | 电力设备 | 52.77 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 39 | 华为手机 | 华为手机 | 电子 | 51.53 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 40 | 工业母机 | 工业母机 | 机械设备 | 49.59 | new_high_direction、new_high_cluster | 4 | 11 | 1 | - |
| 41 | 通信设备 | 通信设备 | 通信 | 49.29 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 42 | 稀土永磁 | 稀土永磁 | 有色金属 | 49.22 | new_high_direction、new_high_cluster | 5 | 5 | 1 | - |
| 43 | 数据要素 | 数据要素 | 计算机 | 49.1 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 雅下水电 | 雅下水电 | 电力设备 | 48.82 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 塑料制品 | 膜材料 | 基础化工 | 48.7 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 46 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 48.24 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 47 | 建筑材料 | 建筑材料 | 建筑材料 | 48.16 | new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 48 | 航空发动机 | 航空发动机 | 国防军工 | 45.1 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 49 | 合成生物 | 合成生物学 | 医药生物 | 45.0 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 3D打印 | 3D打印 | 机械设备 | 41.93 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：光刻胶

- **标准概念**：光刻胶
- **申万一级**：电子
- **评分**：184.57
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.21%，边际量 31.59%，成交额 954.38 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.21%，边际量31.59%，成交954.38亿 |
| new_high_direction | 52.82 | 新高股14只，新高成交417.31亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比7.25，排名24 |

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

## 候选 2：连板未映射

- **标准概念**：连板未映射
- **申万一级**：电子
- **评分**：183.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 183.0 | 连板股11只，最高3板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 3：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：163.23
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.26%，边际量 21.24%，成交额 2065.82 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（6），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.26%，边际量21.24%，成交2065.82亿 |
| new_high_direction | 40.78 | 新高股10只，新高成交702.65亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比10.14，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小金属 | 10 |
| 二氧化锆 | 2 |
| 战略金属 | 2 |
| 金属制品 | 2 |
| 金属增材制造 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方锆业 | 002167 | 小金属 | 其他小金属材料企业 | peripheral | graph_only | 10 |
| 新锐股份 | 688257 | 小金属 | 硬质合金工具企业，拟通过收购慧联电子切入PCB铣刀/钻针赛道 | related | L1_L3_candidate | 10 |
| 格林美 | 002340 | 小金属 | 新能源金属资源循环利用与电池材料前驱体企业，布局镍资源、废钨回收和固态电... | related | L3 | 10 |
| 厦门钨业 | 600549 | 钨钼小金属 | 全球最大的钨冶炼与碳化钨精深加工、国家级稀土集团核心骨干与锂电材料双轮控... | core | L1 | 5 |
| 永兴材料 | 002756 | 钽矿 | 锂云母副产品钽铌锡 | related | L1_L3_candidate | 1 |
| 云南锗业 | 002428 | 锗 | 锗矿开采、精炼及系列锗材料供应商 | core | L1 | 1 |

## 候选 4：电子化学品

- **标准概念**：电子化学品
- **申万一级**：基础化工
- **评分**：154.08
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.85%，边际量 18.24%，成交额 860.56 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.85%，边际量18.24%，成交860.56亿 |
| new_high_direction | 38.08 | 新高股11只，新高成交374.50999999999993亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

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

## 候选 5：氟化工

- **标准概念**：氟化工
- **申万一级**：基础化工
- **评分**：152.28
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.02%，边际量 42.08%，成交额 999.91 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.02%，边际量42.08%，成交999.91亿 |
| new_high_direction | 36.28 | 新高股9只，新高成交454.55亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股9只 |

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

## 候选 6：磷化工

- **标准概念**：磷化工
- **申万一级**：基础化工
- **评分**：145.98
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.03%，边际量 42.56%，成交额 572.96 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（8），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.03%，边际量42.56%，成交572.96亿 |
| new_high_direction | 27.88 | 新高股5只，新高成交230.44亿，容量前三=False |
| new_high_cluster | 22.0 | 题材内新高股5只 |
| limit_heat | 6.1 | 涨停6只，市场占比8.7，排名18 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 磷化工 | 10 |
| 复合肥 | 2 |
| 磷酸铁锂 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云图控股 | 002539 | 磷化工 | 化肥/磷化工受益名单 | peripheral | graph_only | 10 |
| 云天化 | 600096 | 磷化工 | 化肥/磷化工受益名单 | peripheral | graph_only | 10 |
| 兴发集团 | 600141 | 磷化工 | 化肥/磷化工受益名单 | peripheral | graph_only | 10 |
| 川发龙蟒 | 002312 | 磷化工 | 5.2 盈利能力分析 | related | L1_L3_candidate | 10 |
| 川恒股份 | 002895 | 磷化工 | 化肥/磷化工受益名单 | peripheral | graph_only | 10 |
| 川金诺 | 300505 | 磷化工 | 饲料级磷酸氢钙(Ⅰ型相关产品供应商 | related | L2 | 10 |
| 湖北宜化 | 000422 | 磷化工 | 化肥/磷化工受益名单 | peripheral | graph_only | 10 |
| 澄星股份 | 600078 | 磷化工 | 4.2 黄磷生产环节：产能集中，环保压力加大 | peripheral | L1 | 10 |

## 候选 7：金属铜

- **标准概念**：金属铜
- **申万一级**：有色金属
- **评分**：141.71
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.99%，边际量 16.8%，成交额 849.34 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.99%，边际量16.8%，成交849.34亿 |
| new_high_direction | 25.61 | 新高股4只，新高成交160.73999999999998亿，容量前三=False |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| limit_heat | 6.1 | 涨停6只，市场占比8.7，排名19 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 8：金属钴

- **标准概念**：金属钴
- **申万一级**：有色金属
- **评分**：132.49
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.55%，边际量 20.97%，成交额 555.84 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.55%，边际量20.97%，成交555.84亿 |
| new_high_direction | 24.49 | 新高股3只，新高成交183.39000000000001亿，容量前三=False |
| new_high_cluster | 18.0 | 题材内新高股3只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 9：存储芯片

- **标准概念**：存储芯片
- **申万一级**：电子
- **评分**：95.45
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.9 | 新高股23只，新高成交872.1499999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比18.84，排名3 |

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

## 候选 10：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：91.36
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 57.51 | 新高股20只，新高成交600.93亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比15.94，排名7 |

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
