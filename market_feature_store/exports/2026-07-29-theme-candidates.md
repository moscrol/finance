# 2026-07-29 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：22963.39
- **上涨家数**：4253
- **涨停 / 跌停**：81 / 9
- **容量前三行业**：1.电子(29.5%, super_capacity)、2.电力设备(7.8%, normal)、3.通信(7.7%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 氢能源 | 氢能源 | 电力设备 | 178.37 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 一带一路 | 一带一路 | - | 168.85 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 3 | 新零售 | 零售 | - | 167.4 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 4 | 新能源车 | 新能源车 | - | 166.53 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 锂电池概念 | 锂 | - | 165.83 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 6 | 智能家居 | 智能家居 | - | 165.19 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | 充电桩 | 充电桩 | - | 164.57 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 8 | 乡村振兴 | 基建 | - | 164.5 | double_red、limit_heat、new_high_direction、new_high_cluster | 3 | 4 | 0 | missing_evidence |
| 9 | 华为鸿蒙 | 华为鸿蒙 | - | 164.5 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 10 | 无人机 | 无人机 | - | 164.45 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 电力设备 | 电力设备 | - | 164.32 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 小米概念 | 小米概念 | - | 158.06 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 13 | 区块链 | 区块链 | - | 158.04 | double_red、new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 14 | 软件服务 | 软件 | - | 157.92 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 15 | 国产软件 | 软件 | - | 157.91 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 16 | 百度概念 | 百度概念 | - | 157.68 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 元宇宙概念 | 元宇宙 | - | 156.52 | double_red、new_high_direction、new_high_cluster | 1 | 3 | 0 | missing_evidence |
| 18 | 人形机器人 | 人形机器人 | 机械设备 | 153.7 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 19 | 乳制品 | 乳制品 | - | 135.6 | multi_period_rank、new_high_cluster | 4 | 7 | 0 | missing_evidence |
| 20 | 固态电池 | 固态电池 | 电力设备 | 132.1 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 21 | 光伏 | 光伏 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 22 | 可控核聚变 | 可控核聚变 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 燃料电池 | 燃料电池 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 3 | - |
| 24 | 高压快充 | 超充 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 25 | 雄安新区 | 京津冀一体化 | - | 122.45 | double_red、limit_heat、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 26 | 电池 | 4680大圆柱电池 | 电力设备 | 120.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 27 | MCU芯片 | MCU芯片 | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 互联金融 | 互联金融 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 29 | 低空经济 | 低空经济 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 12 | 3 | - |
| 30 | 养老概念 | 养老概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 动力电池回收 | 动力电池回收 | - | 116.0 | double_red、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 32 | 华为汽车 | 华为汽车 | - | 116.0 | double_red、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 33 | 口罩防护 | 口罩防护 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 34 | 多模态AI | 多模态AI | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 3 | 1 | - |
| 35 | 大飞机 | 大飞机 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 新型工业化 | 新型工业化 | 机械设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 37 | 无线耳机 | 无线耳机 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 机器视觉 | 机器视觉 | 机械设备 | 116.0 | double_red、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 39 | 汽车 | 新能源汽车 | - | 116.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 40 | 特斯拉概念 | 特斯拉概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 苹果概念 | 苹果概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 42 | 钠电池 | 钠电池 | - | 116.0 | double_red、new_high_cluster | 3 | 12 | 3 | - |
| 43 | 黄金概念 | 黄金 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 石墨烯 | 石墨烯 | - | 112.0 | double_red、new_high_cluster | 4 | 10 | 2 | - |
| 45 | 网络游戏 | 游戏 | - | 112.0 | double_red、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 46 | 股权 | 私募股权投资 | - | 109.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 47 | 3D打印 | 3D打印 | 机械设备 | 108.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 48 | 工业母机 | 工业母机 | 机械设备 | 108.0 | double_red、new_high_cluster | 5 | 12 | 2 | - |
| 49 | 有色 | 有色冶炼装备 | - | 108.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 50 | 汽车芯片 | 汽车芯片 | - | 106.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：178.37
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.52%，边际量 19.67%，成交额 1755.17 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.52%，边际量19.67%，成交1755.17亿 |
| new_high_direction | 52.37 | 新高股38只，新高成交189.66亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 氢能源 | 20 |
| 氢能 | 10 |
| SOFC燃料电池 | 2 |
| 压缩机 | 2 |
| 天然气 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 氢能 | 重型燃气轮机与综合电力装备供应商，布局自主G50燃机、引进型燃机、电站服... | related | L1_L3_candidate | 20 |
| 中国中车 | 601766 | 氢能 | 氢能 | related | L1_L3_candidate | 20 |
| 中国能建 | 601868 | 氢能 | 氢能 | related | L1_L3_candidate | 20 |
| 中复神鹰 | 688295 | 氢能 | 高性能碳纤维生产销售（T700-T1200、M系列全覆盖） | related | L1_L3_candidate | 20 |
| 中材科技 | 002080 | 氢能 | 特种玻纤布、风电叶片、锂电池隔膜 | related | L1_L3_candidate | 20 |
| 佛燃能源 | 002911 | 氢能 | 氢能装备（隔膜压缩机） | related | L1_L3_candidate | 20 |
| 冰轮环境 | 000811 | 氢能 | AIDC冷水机组（一次侧）、冷链装备、能源化工装备 | related | L1_L3_candidate | 20 |
| 卧龙新能 | 600173 | 氢能 | AEM制氢技术实现兆瓦级产品交付 | related | L2 | 20 |

## 候选 2：一带一路

- **标准概念**：一带一路
- **申万一级**：-
- **评分**：168.85
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.98%，边际量 18.92%，成交额 2775.88 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.98%，边际量18.92%，成交2775.88亿 |
| new_high_direction | 45.35 | 新高股96只，新高成交427.6600000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比12.35，排名8 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 一带一路 | 20 |
| TBM掘进机 | 2 |
| 军贸出口 | 2 |
| 动力工具 | 2 |
| 国际工程 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中工国际 | 002051 | 一带一路 | 深度参与国家重大区域建设与一带一路的工程央企 | related | L2 | 20 |
| 中色股份 | 000758 | 一带一路 | 有色金属国际工程承包先行者 | core | L2 | 20 |
| 中铁工业 | 600528 | 一带一路 | 轨道及桥梁建设装备海外出口商 | peripheral | graph_only | 20 |
| 四川路桥 | 600039 | 一带一路 | 延链补链的海外/跨区域工程拓展 | related | L2 | 20 |
| 天津港 | 600717 | 一带一路 | 海陆交汇点、新亚欧大陆桥经济走廊重要节点 | related | L2 | 20 |
| 铁建重工 | 688425 | 一带一路 | 图谱弱关联 | peripheral | graph_only | 20 |
| 海螺水泥 | 600585 | 供给侧改革 | 水泥熟料自产销售、骨料、商品混凝土 | related | L1_L3_candidate | 1 |
| 中无人机 | 688297 | 军贸出口 | 我国军贸无人机出口主力型号供应商（翼龙系列出口十余个国家，覆盖一带一路） | core | L2 | 1 |

## 候选 3：新零售

- **标准概念**：零售
- **申万一级**：-
- **评分**：167.4
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.29%，边际量 21.29%，成交额 766.87 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.29%，边际量21.29%，成交766.87亿 |
| new_high_direction | 42.85 | 新高股59只，新高成交228.08000000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比16.05，排名3 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 零售 | 10 |
| AI+视讯 | 2 |
| LED显示 | 2 |
| 轮胎出海 | 2 |
| 饮料 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天虹股份 | 002419 | 零售 | 全渠道多业态零售商（百货/购物中心/超市） | core | L2 | 20 |
| 家家悦 | 603708 | 零售 | 超市连锁经营相关产品供应商 | related | L2 | 20 |
| 永辉超市 | 601933 | 零售 | 超市的连锁经营相关产品供应商 | related | L2 | 20 |
| 王府井 | 600859 | 零售 | 零售相关产品/材料供应商 | related | L2 | 20 |
| 致欧科技 | 301376 | 零售 | 跨境电商零售（亚马逊VC | related | L1_L3_candidate | 20 |
| 一心堂 | 002727 | 医药零售 | 西南地区医药零售连锁龙头：直营为主、加盟为辅，医药批发支撑，延伸互联网医... | core | L2 | 5 |
| 上海医药 | 601607 | 医药零售 | 医药零售渠道参与方 | peripheral | graph_only | 5 |
| 中百集团 | 000759 | 即时零售 | 线上超市前置仓与全渠道即时配送布局 | related | L2 | 5 |

## 候选 4：新能源车

- **标准概念**：新能源车
- **申万一级**：-
- **评分**：166.53
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.16%，边际量 21.88%，成交额 5154.75 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.16%，边际量21.88%，成交5154.75亿 |
| new_high_direction | 42.68 | 新高股60只，新高成交214.21999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比13.58，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新能源车 | 20 |
| 新能源 | 10 |
| 新能源车出海 | 5 |
| 新能源车热管理 | 5 |
| 新能源车齿轮 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云铝股份 | 000807 | 新能源 | 电解铝冶炼、铝加工、氧化铝 | related | L1_L3_candidate | 20 |
| 万润新能 | 688275 | 新能源 | 动力电池及储能电池核心化学品原料配套商 | core | L1 | 20 |
| 万顺新材 | 300057 | 新能源 | 电池材料链潜在相关 | peripheral | L1 | 20 |
| 三一重能 | 688349 | 新能源 | 新能源项目投资开发与风电场智慧运维 | related | L2 | 20 |
| 上海建工 | 600170 | 新能源 | 新能源等新兴产业 | related | L1_L3_candidate | 20 |
| 上海洗霸 | 603200 | 新能源 | 固态电池核心材料（硫化锂、硅碳负极、固态电解质） | related | L1_L3_candidate | 20 |
| 东方盛虹 | 000301 | 新能源 | 新能源新材料（EVA | related | L1_L3_candidate | 20 |
| 中仑新材 | 301565 | 新能源 | BOPP新能源膜材（薄膜电容器基膜） | related | L1_L3_candidate | 20 |

## 候选 5：锂电池概念

- **标准概念**：锂
- **申万一级**：-
- **评分**：165.83
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.55%，边际量 20.3%，成交额 3672.82 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.55%，边际量20.3%，成交3672.82亿 |
| new_high_direction | 41.63 | 新高股32只，新高成交130.15亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.2 | 涨停12只，市场占比14.81，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 锂 | 10 |
| 锂电池 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东威科技 | 688700 | 锂电池 | 锂电材料设备潜在相关 | peripheral | L1 | 20 |
| 中材科技 | 002080 | 锂电池 | 产业链供应商 | peripheral | L1_L3_candidate | 20 |
| 中矿资源 | 002738 | 锂电池 | 锂矿资源与海外锂盐项目企业 | related | L1_L3_candidate | 20 |
| 中科电气 | 300035 | 锂电池 | 负极（提价约1000元/吨/石墨化满产） | peripheral | L3 | 20 |
| 亿纬锂能 | 300014 | 锂电池 | 小型锂离子电池相关产品供应商 | related | L2 | 20 |
| 佛塑科技 | 000973 | 锂电池 | 隔膜（产能紧张/酝酿涨价） | peripheral | L3 | 20 |
| 厦钨新能 | 688778 | 锂电池 | 下游动力/3C/储能电池材料供应 | related | L2 | 20 |
| 厦门钨业 | 600549 | 锂电池 | 能源新材料（锂电池正极材料） | related | L1_L3_candidate | 20 |

## 候选 6：智能家居

- **标准概念**：智能家居
- **申万一级**：-
- **评分**：165.19
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.41%，边际量 19.59%，成交额 1295.61 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.41%，边际量19.59%，成交1295.61亿 |
| new_high_direction | 42.74 | 新高股29只，新高成交218.92000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比8.64，排名22 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能家居 | 20 |
| 家居 | 10 |
| AIoT | 2 |
| AI消费 | 2 |
| 半导体封装 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 欧派家居 | 603833 | 家居 | 定制家居龙头（橱柜/衣柜/卫浴/木门） | core | L2 | 20 |
| 皮阿诺 | 002853 | 家居 | 中高端定制家居品牌：整体橱柜、全屋定制及门墙三大核心品类，柔性化规模定制... | core | L2 | 20 |
| 美之高 | 920765 | 家居 | 金属收纳置物架ODM/OEM厂商（家用类为主、工业类为辅），主要客户为日... | core | L2 | 20 |
| 美克家居 | 600337 | 家居 | 多品牌家居零售+国际批发商：直营品牌美克美家（连续十三年入选中国500最... | core | L2 | 20 |
| 乐歌股份 | 300729 | 智能家居 | 线性驱动人体工学智能家居产品品牌商（升降桌为核心） | core | L2 | 20 |
| 凯迪股份 | 605288 | 智能家居 | 智能线性驱动系统供应商，覆盖智能家居/智慧办公/汽车零部件/医疗养护/工... | core | L2 | 20 |
| 友邦吊顶 | 002718 | 智能家居 | 集成吊顶、挂挂墙、百变柜、5K系统墙板 | core | L1 | 20 |
| 宇瞳光学 | 300790 | 智能家居 | 智能家居相关产品/材料供应商 | related | L2 | 20 |

## 候选 7：充电桩

- **标准概念**：充电桩
- **申万一级**：-
- **评分**：164.57
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.48%，边际量 18.07%，成交额 1762.83 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.48%，边际量18.07%，成交1762.83亿 |
| new_high_direction | 41.77 | 新高股32只，新高成交141.49亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比9.88，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 充电桩 | 20 |
| 充电模块 | 2 |
| 充电运营 | 2 |
| 光储充 | 2 |
| 固态变压器 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万马股份 | 002276 | 充电桩 | 国内首批充电桩企业：设备制造（家用桩到兆瓦群充/重卡充电/V2G/液冷超... | core | L2 | 20 |
| 中恒电气 | 002364 | 充电桩 | 国内最早从事新能源汽车充电桩研发生产的企业之一（大功率直流快充、全液冷超... | related | L2 | 20 |
| 中电鑫龙 | 002298 | 充电桩 | 智慧用能（智能输配电设备）、智慧新能源（储能、光伏、充电桩） | core | L1_L3_candidate | 20 |
| 中航光电 | 002179 | 充电桩 | - | - | - | 20 |
| 京泉华 | 002885 | 充电桩 | 大功率超充/液冷充电模块磁性器件及高频扼流圈供应商 | related | L1 | 20 |
| 伊戈尔 | 002922 | 充电桩 | 上游材料/设备 | peripheral | graph_only | 20 |
| 宝馨科技 | 002514 | 充电桩 | 新能源充/换电桩及配套产品制造商，践行智能制造+新能源双轮驱动战略 | related | L2 | 20 |
| 康尼机电 | 603111 | 充电桩 | 轨道交通门系统、新能源汽车充电连接系统 | related | L1_L3_candidate | 20 |

## 候选 8：乡村振兴

- **标准概念**：基建
- **申万一级**：-
- **评分**：164.5
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.74%，边际量 21.29%，成交额 906.81 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（4），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.74%，边际量21.29%，成交906.81亿 |
| new_high_direction | 42.05 | 新高股52只，新高成交164.1亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比8.64，排名21 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 基建 | 2 |
| 景观设计 | 2 |
| 粮食安全 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 神农集团 | 605296 | 农业 | 生猪养殖业务（核心）、屠宰及食品加工（协同） | related | L2 | 1 |
| 荃银高科 | 300087 | 农业 | 种子业务（水稻、玉米、小麦等） | related | L1_L3_candidate | 1 |
| 园林股份 | 605303 | 基建 | 市政园林工程施工承包（含EPCO/设计-施工总承包） | related | L2 | 1 |
| 维维股份 | 600300 | 粮食安全 | 国有上市公司定位，围绕粮食收储、加工、销售打造粮食产业平台，粮油仓储贸易... | related | L2 | 1 |

## 候选 9：华为鸿蒙

- **标准概念**：华为鸿蒙
- **申万一级**：-
- **评分**：164.5
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.23%，边际量 19.37%，成交额 895.71 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.23%，边际量19.37%，成交895.71亿 |
| new_high_direction | 41.7 | 新高股24只，新高成交135.70000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比9.88，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 华为鸿蒙 | 20 |
| 鸿蒙 | 10 |
| AI PC | 2 |
| 东数西算 | 2 |
| 智能座舱 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 科蓝软件 | 300663 | 华为鸿蒙 | 鸿蒙首批全生态认证服务商：鸿蒙智能高柜机器人小蓝、科蓝鸿蒙移动金融技术平... | core | L2 | 20 |
| 国轩高科 | 002074 | 鸿蒙 | 动力电池系统、储能电池系统、固态电池（全固态+固液混合） | related | L1_L3_candidate | 20 |
| 万兴科技 | 300624 | 鸿蒙 | 下游应用 | peripheral | L1 | 20 |
| 中国软件 | 600536 | 鸿蒙 | 国产操作系统（麒麟软件）、党政核心应用解决方案、信创基础软件 | related | L1_L3_candidate | 20 |
| 中芯国际 | 688981 | 鸿蒙 | 中游制造 | related | L1_L3_candidate | 20 |
| 亚华电子 | 301337 | 鸿蒙 | OpenHarmony医疗场景适配落地 | related | L2 | 20 |
| 华勤技术 | 603296 | 鸿蒙 | 中游制造 | core | L2_candidate | 20 |
| 华天科技 | 002185 | 鸿蒙 | - | - | - | 20 |

## 候选 10：无人机

- **标准概念**：无人机
- **申万一级**：-
- **评分**：164.45
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.18%，边际量 17.15%，成交额 1891.63 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.18%，边际量17.15%，成交1891.63亿 |
| new_high_direction | 41.65 | 新高股22只，新高成交132.0亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比9.88，排名15 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 无人机 | 20 |
| 军工无人机 | 5 |
| 无人机反制 | 5 |
| PCB电机 | 2 |
| 三北工程 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三瑞智能 | 301696 | 无人机 | 无人机电动动力系统领先制造商 | core | L2 | 20 |
| 中无人机 | 688297 | 无人机 | 无人机系统的设计研发 | core | L1_L3_candidate | 20 |
| 兴图新科 | 688081 | 无人机 | 智能视频指挥（军品）、视频智算（民品）、无人装备配套 | related | L2 | 20 |
| 创益通 | 300991 | 无人机 | 无人机 | related | L2 | 20 |
| 北方长龙 | 301357 | 无人机 | 军用车辆非金属复合材料配套装备、拟并购军用智能检测装备（顺义科技） | core | L1_L3_candidate | 20 |
| 声迅股份 | 003004 | 无人机 | 智能安防解决方案、城市安全运营服务、特种光电器件（拟并购中科锐择）、智慧... | related | L1_L3_candidate | 20 |
| 天和防务 | 300397 | 无人机 | 便携式防空导弹指挥系统、5G射频器件及芯片、低空智能防务装备、天融智航低... | related | L1_L3_candidate | 20 |
| 宇瞳光学 | 300790 | 无人机 | 安防镜头、车载光学、新消费光学 | related | L1_L3_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-bf7160c186c19e80de6a artifact_sha=105b0c22a35d34f07ddc3ed275d8a2aed73cd796472c65e7b537547a5f52b0e1 manifest_sha=75f92533066d2e349ee49c1258057649c395652a575a635a47c201d821acb08b -->
