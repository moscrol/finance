# 2026-04-02 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：横盘
- **成交额**：18428.0
- **上涨家数**：1052
- **涨停 / 跌停**：28 / 20
- **容量前三行业**：1.电子(15.0%, normal)、2.电力设备(12.1%, normal)、3.医药生物(9.2%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 医药 | 医药 | 医药生物 | 127.0 | limit_advance_cluster、capacity_industry | 5 | 12 | 1 | - |
| 2 | 商业航天 | 商业航天 | 电力设备 | 96.29 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 3 | 创新药 | 创新药 | 医药生物 | 93.07 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 4 | 化学制药 | 原料药 | 医药生物 | 86.97 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 1 | 1 | 0 | missing_evidence |
| 5 | 减肥药 | 减肥药 | 医药生物 | 84.09 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 1 | 0 | missing_concept、missing_evidence |
| 6 | 辅助生殖 | 辅助生殖 | 医药生物 | 83.16 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 8 | 1 | - |
| 7 | 合成生物 | 合成生物学 | 医药生物 | 79.47 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 8 | CRO | CRO | 医药生物 | 79.29 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 9 | 医疗服务 | 医疗服务 | 医药生物 | 78.56 | new_high_direction、new_high_cluster、capacity_industry | 5 | 7 | 1 | - |
| 10 | 共封装光学(CPO) | CPO | 电子 | 78.24 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 数据中心 | 数据中心 | 计算机 | 77.6 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 生物制品 | 生物制品 | 医药生物 | 77.46 | new_high_direction、new_high_cluster、capacity_industry | 0 | 6 | 0 | missing_concept、missing_evidence |
| 13 | 风电 | 风电 | 电力设备 | 76.29 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | 阿尔茨海默 | 阿尔茨海默 | 医药生物 | 76.21 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 15 | 医疗器械 | 医疗器械 | 医药生物 | 74.74 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 16 | 特高压 | 特高压 | 电力设备 | 73.33 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 17 | 通信设备 | 通信设备 | 通信 | 70.67 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 光纤 | AI算力驱动下的MPO光纤连接器产业 | 通信 | 69.54 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 19 | 海峡两岸 | 海峡两岸 | 综合 | 69.21 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 20 | 人形机器人 | 人形机器人 | 机械设备 | 67.63 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 无人驾驶 | 无人驾驶 | 汽车 | 67.38 | new_high_direction、new_high_cluster | 4 | 10 | 1 | - |
| 22 | 液冷服务器 | 液冷服务器 | 电力设备 | 67.17 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | 维生素 | 维生素 | 基础化工 | 67.15 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 24 | 燃料电池 | SOFC燃料电池 | 电力设备 | 65.27 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 25 | 可控核聚变 | 可控核聚变 | 电力设备 | 54.86 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 26 | 铜缆高速连接 | 铜缆高速连接 | 电力设备 | 54.7 | new_high_direction、new_high_cluster、capacity_industry | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | AIGC | AIGC | 传媒 | 51.62 | new_high_direction、new_high_cluster | 5 | 5 | 1 | - |
| 28 | 港口航运 | 港口航运 | 交通运输 | 51.52 | new_high_direction、new_high_cluster | 1 | 10 | 1 | - |
| 29 | 银行 | 区块链 | 银行 | 51.49 | new_high_direction、new_high_cluster | 3 | 1 | 0 | missing_evidence |
| 30 | 3D打印 | 3D打印 | 机械设备 | 49.74 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 量子科技 | 量子科技 | 计算机 | 49.5 | new_high_direction、new_high_cluster | 2 | 7 | 1 | - |
| 32 | 算力租赁 | 算力租赁 | 计算机 | 48.48 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 33 | 塑料制品 | 膜材料 | 基础化工 | 46.09 | limit_heat、new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 34 | 盐湖提锂 | 外部供锂 | 有色金属 | 45.93 | limit_heat、new_high_direction、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 35 | 6G | 6G | 通信 | 45.58 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | 小米汽车 | 小米汽车 | 汽车 | 44.82 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 37 | 长安汽车 | 长安汽车 | 汽车 | 44.67 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | 太赫兹 | 6G产业 | 国防军工 | 42.42 | new_high_direction、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 39 | 电力 | 新型电力系统 | 电力设备 | 38.05 | limit_heat、limit_advance_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 40 | 储能 | 储能 | - | 32.1 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 军工 | 军工 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 氢能源 | 氢能源 | - | 31.05 | limit_heat、new_high_cluster | 5 | 4 | 1 | - |
| 43 | 医药商业 | 医药流通 | - | 30.7 | limit_heat、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 44 | 股权变更 | 股权变更 | 基础化工 | 27.0 | limit_advance_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 虚拟电厂 | 虚拟电厂 | - | 22.7 | limit_heat、new_high_cluster | 1 | 1 | 1 | - |
| 46 | 电网设备 | 电网设备 | - | 21.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 石油加工贸易 | 石油加工贸易 | - | 21.05 | limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 光伏概念 | 光伏概念 | - | 5.4 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 光纤概念 | 空芯光纤产业 | - | 5.4 | limit_heat | 1 | 1 | 0 | missing_evidence |
| 50 | 油气开采及服务 | 油气开采及服务 | - | 5.05 | limit_heat | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 五、核心候选明细

## 候选 1：医药

- **标准概念**：医药
- **申万一级**：医药生物
- **评分**：127.0
- **触发类型**：limit_advance_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 127.0 | 连板股3只，最高5板，容量前三=True |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医药 | 10 |
| AI+生物医药 | 5 |
| 医药分销 | 5 |
| 医药流通 | 5 |
| 医药生物 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 丽珠集团 | 000513 | 医药 | 综合性制药及生物制药、原料药一体化企业 | peripheral | graph_only | 10 |
| 亚虹医药 | 688176 | 医药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 10 |
| 仙琚制药 | 002332 | 医药 | 综合西药原料及特色制剂开发企业 | peripheral | graph_only | 10 |
| 上海医药 | 601607 | 医药分销 | 药品分销渠道商 | peripheral | graph_only | 10 |
| 达嘉维康 | 301126 | 医药流通 | 小建中颗粒相关产品供应商 | related | L2 | 10 |
| 万泽股份 | 000534 | 医药生物 | 微生态活菌药品与健康产品企业 | peripheral | graph_only | 10 |
| 伟思医疗 | 688580 | 医药生物 | 经颅磁刺激仪相关产品供应商 | related | L2 | 10 |
| 信立泰 | 002294 | 医药生物 | 心脑血管相关产品供应商 | related | L2 | 10 |

## 候选 2：商业航天

- **标准概念**：商业航天
- **申万一级**：电力设备
- **评分**：96.29
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 37.29 | 新高股11只，新高成交310.81亿，容量前三=False |
| limit_advance_cluster | 33.0 | 连板股1只，最高3板，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| 低轨卫星星座 | 2 |
| 卫星产业 | 2 |
| 电磁弹射 | 2 |
| 航天装备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 10 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 10 |
| 中国卫通 | 601698 | 商业航天 | 卫星通信运营商 | peripheral | L2 | 10 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 商业航天 | 商业航天高性能碳纤维本土供应商，推进卫星端验证 | related | L1_L3_candidate | 10 |
| 中科星图 | 688568 | 商业航天 | 卫星互联网/太空算力 | core | - | 10 |
| 中集集团 | 000039 | 商业航天 | 模块化/预制化数据中心与海工、航天储罐高端装备制造交付商 | related | L1_L3_candidate | 10 |

## 候选 3：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：93.07
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 60.97 | 新高股122只，新高成交877.24亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比21.43，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 10 |
| 创新药RWA | 5 |
| CDMO | 2 |
| RWA代币化 | 2 |
| 小分子 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | 创新药 | 院外零售渠道潜在相关 | peripheral | L1 | 10 |
| 上海医药 | 601607 | 创新药 | 医药流通渠道潜在相关 | peripheral | L1 | 10 |
| 东富龙 | 300171 | 创新药 | 创新药生产装备潜在供应商 | related | L1 | 10 |
| 九洲药业 | 603456 | 创新药 | 创新药定制研发生产/CDMO服务商 | core | L1 | 10 |
| 亚虹医药 | 688176 | 创新药 | 泌尿生殖系统和肿瘤相关创新药/药械一体化治疗产品开发商，核心产品APL-... | related | L1_L3_candidate | 10 |
| 信立泰 | 002294 | 创新药 | 心血管重磅创新药（S086等）研发商 | core | L2_candidate | 10 |
| 凯莱英 | 002821 | 创新药 | 小分子创新药CDMO服务商 | peripheral | graph_only | 10 |
| 和元生物 | 688238 | 创新药 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 4：化学制药

- **标准概念**：原料药
- **申万一级**：医药生物
- **评分**：86.97
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 55.57 | 新高股72只，新高成交445.7999999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比14.29，排名3 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 原料药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 圣诺生物 | 688117 | 多肽药物 | 国内多肽合成领先、深度受益全球GLP-1减重/降糖（司美格鲁肽等）大爆发... | core | L1 | 1 |

## 候选 5：减肥药

- **标准概念**：减肥药
- **申万一级**：医药生物
- **评分**：84.09
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（1），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.39 | 新高股28只，新高成交271.58000000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 4.7 | 涨停2只，市场占比7.14，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 圣诺生物 | 688117 | 多肽药物 | 国内多肽合成领先、深度受益全球GLP-1减重/降糖（司美格鲁肽等）大爆发... | core | L1 | 1 |

## 候选 6：辅助生殖

- **标准概念**：辅助生殖
- **申万一级**：医药生物
- **评分**：83.16
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（8），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.11 | 新高股21只，新高成交168.46亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比10.71，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 辅助生殖 | 10 |
| 促排卵药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 丽珠集团 | 000513 | 辅助生殖 | 下游应用 | peripheral | L1 | 10 |
| 仙琚制药 | 002332 | 辅助生殖 | 4.4.1 药物制剂类企业 | peripheral | L1 | 10 |
| 共同药业 | 300966 | 辅助生殖 | 上游材料/设备 | peripheral | L1_L3_candidate | 10 |
| 华大基因 | 300676 | 辅助生殖 | 7.1 重点关注标的推荐 | peripheral | L1 | 10 |
| 开立医疗 | 300633 | 辅助生殖 | 上游设备 | related | L1_L3_candidate | 10 |
| 昌红科技 | 300151 | 辅助生殖 | 7.1 重点关注标的推荐 | related | L1_L3_candidate | 10 |
| 贝瑞基因 | 000710 | 辅助生殖 | 下游应用 | peripheral | L1_L3_candidate | 10 |
| 迈瑞医疗 | 300760 | 辅助生殖 | 上游设备 | peripheral | L1 | 10 |

## 候选 7：合成生物

- **标准概念**：合成生物学
- **申万一级**：医药生物
- **评分**：79.47
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.47 | 新高股35只，新高成交277.33000000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 合成生物学 | 5 |
| 3D生物打印 | 2 |
| 保健品 | 2 |
| 功能性食品 | 2 |
| 化妆品 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | - | 合成生物 | 受益标的 | related | - | 10 |
| 凯赛生物 | 688065 | 合成生物 | 受益标的 | related | - | 10 |
| 利民股份 | 002734 | 合成生物 | 受益标的 | related | - | 10 |
| 华恒生物 | 688639 | 合成生物 | 受益标的 | related | - | 10 |
| 奥翔药业 | 603229 | 合成生物 | 受益标的 | related | - | 10 |
| 富祥药业 | 300497 | 合成生物 | 受益标的 | related | - | 10 |
| 川宁生物 | 301301 | 合成生物 | 受益标的 | related | - | 10 |
| 巨子生物 | - | 合成生物 | 受益标的 | related | - | 10 |

## 候选 8：CRO

- **标准概念**：CRO
- **申万一级**：医药生物
- **评分**：79.29
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 53.29 | 新高股32只，新高成交263.52000000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CRO | 10 |
| Micro LED | 5 |
| Micro LED光互连 | 5 |
| Micro OLED | 5 |
| 临床前CRO | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| TCL科技 | 000100 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 三友化工 | 600409 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 三超新材 | 300554 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 东旭光电 | 000413 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 中兴通讯 | 000063 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 中瓷电子 | 003031 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 中际旭创 | 300308 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |
| 乾照光电 | 300102 | Micro LED光互连 | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 9：医疗服务

- **标准概念**：医疗服务
- **申万一级**：医药生物
- **评分**：78.56
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（7），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.56 | 新高股19只，新高成交205.01000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗服务 | 10 |
| BCI | 2 |
| FDA | 2 |
| 互联网医疗 | 2 |
| 医疗信息化 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三博脑科 | 301293 | 医疗服务 | 专科医院/医疗服务提供方 | peripheral | graph_only | 10 |
| 新开源 | 300109 | 医疗服务 | 医疗服务相关产品/材料供应商 | related | L2 | 10 |
| 麦迪科技 | 603990 | 医疗服务 | 医疗服务相关产品/材料供应商 | related | L2 | 10 |
| 乐普医疗 | 300003 | FDA | FDA及国际认证医疗器械潜在出口商 | peripheral | graph_only | 1 |
| 创新医疗 | 002173 | 医药生物 | 医疗服务业务相关产品供应商 | related | L2 | 1 |
| 康芝药业 | 300086 | 医药生物 | 儿童药相关产品供应商 | related | L2 | 1 |
| 金域医学 | 603882 | 医药生物 | 医学诊断服务相关产品供应商 | related | L2 | 1 |

## 候选 10：共封装光学(CPO)

- **标准概念**：CPO
- **申万一级**：电子
- **评分**：78.24
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.24 | 新高股13只，新高成交483.14亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |
| CPO（共封装光学） | 10 |
| CPO微透镜与高功率CW光源 | 5 |
| 6G产业 | 2 |
| MPO光纤连接器 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光莆股份 | 300632 | CPO | 共封装光学（CPO）新型光引擎精密光电对准封测代工商 | related | L2_candidate | 11 |
| Coherent（COHR） | - | CPO | 菊东光客户，光器件供应商 | peripheral | L1 | 10 |
| 东山精密 | 002384 | CPO | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 东材科技 | 601208 | CPO | M9 PCB材料/高速互联受益标的 | peripheral | graph_only | 10 |
| 中芯国际 | 688981 | CPO | 光通信电芯片代工与制造受益名单 | peripheral | graph_only | 10 |
| 中际旭创 | 300308 | CPO | 光通信芯片与半导体激光芯片供应商 | related | L1_L3_candidate | 10 |
| 乾照光电 | 300102 | CPO | 光通信/CPO用光电感测及芯片潜在研发送样方 | peripheral | L1 | 10 |
| 亨通光电 | 600487 | CPO | 市场信号弱关联 | related | L2_candidate | 10 |
