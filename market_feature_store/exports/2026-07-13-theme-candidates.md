# 2026-07-13 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：28175.78
- **上涨家数**：801
- **涨停 / 跌停**：29 / 172
- **容量前三行业**：1.电子(34.2%, super_capacity)、2.通信(7.4%, normal)、3.机械设备(7.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 商业航天 | 商业航天 | 机械设备 | 182.52 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 2 | 医药 | 医药 | 医药生物 | 101.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 3 | 半导体 | 半导体 | 基础化工 | 98.32 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 4 | 人形机器人 | 人形机器人 | 机械设备 | 79.43 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 5 | 数据中心 | 数据中心 | 计算机 | 79.07 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 信创 | 信创 | 计算机 | 76.02 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 创新药 | 创新药 | 医药生物 | 75.96 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 8 | 中药 | 中药 | 医药生物 | 72.72 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 9 | 先进封装 | 先进封装 | 电子 | 70.72 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 10 | 云计算 | 云计算 | 计算机 | 70.21 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 传感器 | 传感器 | 机械设备 | 68.98 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 12 | 算力租赁 | 算力租赁 | 计算机 | 68.8 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 13 | 新型工业化 | 新型工业化 | 机械设备 | 67.89 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 14 | 合成生物 | 合成生物 | 医药生物 | 66.09 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 液冷服务器 | 液冷服务器 | 电力设备 | 65.42 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 16 | 海峡两岸 | 海峡两岸 | 综合 | 63.34 | limit_heat、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 17 | CRO | CRO | 医药生物 | 63.33 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | AIGC | AIGC | 传媒 | 62.92 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 数据要素 | 数据要素 | 计算机 | 62.9 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 共封装光学(CPO) | CPO | 电子 | 62.82 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 21 | 存储芯片 | 存储芯片 | 电子 | 62.77 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 22 | 6G | 6G | 通信 | 62.07 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | IT服务 | IT服务 | 计算机 | 61.48 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 24 | 风电 | 风电 | 电力设备 | 59.92 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 25 | 减肥药 | 创新药 | 医药生物 | 59.17 | new_high_direction、new_high_cluster | 2 | 2 | 0 | missing_evidence |
| 26 | MCU芯片 | MCU芯片 | 电子 | 58.48 | new_high_direction、new_high_cluster、capacity_industry | 4 | 4 | 1 | - |
| 27 | 医疗服务 | 医疗服务 | 医药生物 | 57.66 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 软件开发 | IT服务 | 计算机 | 51.57 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 29 | 智能座舱 | 智能座舱 | 汽车 | 50.98 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 30 | 英伟达 | 英伟达 | 电子 | 49.46 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 军工信息化 | 军工信息化 | 国防军工 | 48.08 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 军工装备 | 军工装备 | 国防军工 | 46.53 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 毫米波雷达 | 毫米波雷达 | 汽车 | 43.32 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 无人驾驶 | 无人驾驶 | 汽车 | 43.09 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 35 | 大飞机 | 大飞机 | 国防军工 | 42.38 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 人工智能 | 人工智能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 37 | 化学制药 | 化学制药 | - | 31.4 | limit_heat、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 38 | 低空经济 | 低空经济 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 39 | 储能 | 储能 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 40 | 军工 | 军工 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 建筑装饰 | 工程 | - | 30.7 | limit_heat、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 42 | 氢能源 | 氢能源 | - | 28.7 | limit_heat、new_high_cluster | 5 | 6 | 1 | - |
| 43 | 业绩 | AI PC | 基础化工 | 27.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 44 | 退市整理 | 退市整理 | 计算机 | 27.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 专用设备 | 专用设备 | - | 24.7 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 氦气 | 氦气 | 国防军工 | 24.0 | limit_advance_cluster | 5 | 8 | 5 | - |
| 47 | 间接持股上海微 | 间接持股上海微 | 建筑装饰 | 24.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 通用设备 | 金属制品 | - | 22.7 | limit_heat、new_high_cluster | 1 | 7 | 0 | missing_evidence |
| 49 | 化学制品 | 化工周期 | - | 21.05 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 50 | 燃气 | 城市燃气 | - | 20.7 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：商业航天

- **标准概念**：商业航天
- **申万一级**：机械设备
- **评分**：182.52
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 111.0 | 连板股2只，最高3板，容量前三=True |
| new_high_direction | 40.12 | 新高股13只，新高成交313.78000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比13.79，排名6 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| 商业航天光学载荷 | 5 |
| AI算力基础设施 | 2 |
| SOFC燃料电池 | 2 |
| 东数西算 | 2 |

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

## 候选 2：医药

- **标准概念**：医药
- **申万一级**：医药生物
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
| 医药 | 10 |
| AI+医药 | 5 |
| AI+生物医药 | 5 |
| 中医药 | 5 |
| 医药CDMO | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | AI+医药 | 一心智云AI中台赋能万店运营（探索期） | related | L2 | 10 |
| 瑞康医药 | 002589 | 中医药 | 中医药种植/饮片/药食同源布局 | related | L2 | 10 |
| 丽珠集团 | 000513 | 医药 | 医药相关产品/材料供应商 | related | L2 | 10 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 10 |
| 仙琚制药 | 002332 | 医药 | 甾体类原料药相关产品供应商 | related | L2 | 10 |
| 千红制药 | 002550 | 医药 | 片剂相关产品供应商 | related | L2 | 10 |
| 奇正藏药 | 002287 | 医药 | 藏药相关产品供应商 | related | L2 | 10 |
| 山东药玻 | 600529 | 医药 | 各种药用玻璃瓶产品相关产品供应商 | related | L2 | 10 |

## 候选 3：半导体

- **标准概念**：半导体
- **申万一级**：基础化工
- **评分**：98.32
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 48.32 | 新高股9只，新高成交617.8000000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股9只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |

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

## 候选 4：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：79.43
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 48.73 | 新高股13只，新高成交202.36亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 4.7 | 涨停2只，市场占比6.9，排名24 |

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
| 万向钱潮 | 000559 | 人形机器人 | 研发布局人形机器人精密零部件（依托精密轴承技术平台） | peripheral | L2 | 10 |
| 万通液压 | 920839 | 人形机器人 | 研发人形机器人关节用高精度行星滚柱丝杠副、超大负载工业机器人油气分离平衡... | peripheral | L2 | 10 |
| 三花智控 | 002050 | 人形机器人 | 全产业链（执行器、减速器、丝杠、灵巧手） | core | L1 | 10 |
| 东睦股份 | 600114 | 人形机器人 | MIM金属注射成形（折叠屏铰链、AI连接器、机器人灵巧手零件）、P&S粉... | related | L1_L3_candidate | 10 |
| 东阳光 | 600673 | 人形机器人 | 具身智能（人形机器人） | core | L1_L3_candidate | 10 |
| 中大力德 | 002896 | 人形机器人 | 机器人核心零部件供应商 | related | L2 | 10 |
| 中控技术 | 688777 | 人形机器人 | TPT工业大模型、DCS、SIS控制系统、UCS通用控制系统 | core | L1_L3_candidate | 10 |

## 候选 5：数据中心

- **标准概念**：数据中心
- **申万一级**：计算机
- **评分**：79.07
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 48.02 | 新高股20只，新高成交641.25亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比10.34，排名10 |

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

## 候选 6：信创

- **标准概念**：信创
- **申万一级**：计算机
- **评分**：76.02
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 44.97 | 新高股17只，新高成交397.85亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比10.34，排名13 |

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

## 候选 7：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：75.96
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.51 | 新高股48只，新高成交281.08000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比24.14，排名1 |

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
| 一品红 | 300723 | 创新药 | AR882（URAT1抑制剂）中国区权益方，Ⅲ期临床推进 | core | L2 | 10 |
| 一心堂 | 002727 | 创新药 | 院外零售渠道潜在相关 | peripheral | L1 | 10 |
| 三生制药 | 01530.HK | 创新药 | 双抗BD出海标杆 | related | - | 10 |
| 上海医药 | 601607 | 创新药 | 医药流通渠道潜在相关 | peripheral | L1 | 10 |
| 东富龙 | 300171 | 创新药 | 创新药生产装备潜在供应商 | related | L1 | 10 |
| 丽珠集团 | 000513 | 创新药 | - | related | L1 | 10 |
| 乐普医疗 | 300003 | 创新药 | 创新药（GLP-1 | related | L1_L3_candidate | 10 |
| 九洲药业 | 603456 | 创新药 | 创新药定制研发生产/CDMO服务商 | core | L1 | 10 |

## 候选 8：中药

- **标准概念**：中药
- **申万一级**：医药生物
- **评分**：72.72
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.67 | 新高股27只，新高成交133.95亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比10.34，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中药 | 10 |
| 中药材 | 5 |
| 中成药 | 2 |
| 兽药 | 2 |
| 医药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万邦德 | 002082 | 中药 | 医药相关产品供应商 | related | L2 | 10 |
| 三力制药 | 603439 | 中药 | 药品相关产品供应商 | related | L2 | 10 |
| 太极集团 | 600129 | 中药 | 西成药相关产品供应商 | related | L2 | 10 |
| 康芝药业 | 300086 | 中药 | 儿童药研发生产销售、中成药、母婴健康用品 | related | L1_L3_candidate | 10 |
| 特一药业 | 002728 | 中药 | 中成药品相关产品供应商 | related | L2 | 10 |
| 上海医药 | 601607 | IT分销 | 医药制造、医药分销、医药零售 | related | L2 | 1 |
| 华润江中 | 600750 | 健康消费 | OTC药品、健康消费品、处方药 | core | L2 | 1 |
| 回盛生物 | 300871 | 兽药 | 国内领先、掌握核心复配纯化工艺的猪用抗菌兽药及中药制剂保供大厂 | peripheral | graph_only | 1 |

## 候选 9：先进封装

- **标准概念**：先进封装
- **申万一级**：电子
- **评分**：70.72
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 44.72 | 新高股7只，新高成交553.78亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股7只 |

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

## 候选 10：云计算

- **标准概念**：云计算
- **申万一级**：计算机
- **评分**：70.21
- **触发类型**：limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 39.16 | 新高股11只，新高成交461.0亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比10.34，排名12 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 云计算 | 10 |
| 云计算数据中心 | 5 |
| ABF载板 | 2 |
| AI容器 | 2 |
| AI应用 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国电信 | 601728 | 云计算 | 产业数字化和云网服务潜在平台 | related | L2_candidate | 10 |
| 中电鑫龙 | 002298 | 云计算 | 智慧城市信息化及云底座解决方案商 | related | L1 | 10 |
| 云赛智联 | 600602 | 云计算 | 云计算相关产品/材料供应商 | related | L2 | 10 |
| 优刻得 | 688158 | 云计算 | 云计算相关产品/材料供应商 | related | L2 | 10 |
| 光环新网 | 300383 | 云计算 | 云计算(AWS中国) | related | L1_L3_candidate | 10 |
| 利通电子 | 603629 | 云计算 | AI算力租赁、液晶电视精密金属结构件 | related | L1_L3_candidate | 10 |
| 协创数据 | 300857 | 云计算 | OpenClaw带动Token消耗和算力云服务需求受益名单 | peripheral | graph_only | 10 |
| 南威软件 | 603636 | 云计算 | 图谱弱关联 | peripheral | graph_only | 10 |
