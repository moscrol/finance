# 2026-06-12 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：反弹阶段
- **成交额**：32147.62
- **上涨家数**：3923
- **涨停 / 跌停**：89 / 15
- **容量前三行业**：1.电子(29.5%, super_capacity)、2.电力设备(8.8%, normal)、3.有色金属(8.1%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PCB | PCB | 有色金属 | 206.94 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 3 | - |
| 2 | 小金属 | 小金属 | 有色金属 | 194.0 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 3 | 氢能源 | 氢能源 | 电力设备 | 184.85 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 4 | 1 | - |
| 4 | 金属铜 | 金属铜 | 有色金属 | 180.64 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 5 | 商业航天 | 商业航天 | 国防军工 | 177.53 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 6 | 燃料电池 | 燃料电池 | 电力设备 | 176.76 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 7 | PET铜箔 | PET铜箔 | 电力设备 | 175.77 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 9 | 1 | - |
| 8 | 稀土永磁 | 稀土永磁 | 有色金属 | 175.15 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 9 | 海峡两岸 | 海峡两岸 | 综合 | 169.05 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 10 | 可控核聚变 | 可控核聚变 | 电力设备 | 168.37 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 人形机器人 | 人形机器人 | 机械设备 | 168.06 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 12 | 电池 | 4C电池 | 电力设备 | 167.7 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 13 | 化学制品 | 化工周期 | 基础化工 | 164.95 | double_red、limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 14 | 锂电池 | 锂电池 | 电力设备 | 159.72 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 15 | 传感器 | 传感器 | 机械设备 | 154.35 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | 金属钴 | 金属钴 | 有色金属 | 153.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 机器视觉 | 机器视觉 | 机械设备 | 153.04 | double_red、new_high_direction、new_high_cluster | 0 | 7 | 0 | missing_concept、missing_evidence |
| 18 | 工业母机 | 工业母机 | 机械设备 | 152.1 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 信创 | 信创 | 计算机 | 151.58 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 低空经济 | 低空经济 | 国防军工 | 148.9 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 5 | 12 | 2 | - |
| 21 | 3D打印 | 3D打印 | 机械设备 | 147.56 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 22 | 碳纤维 | 碳纤维 | 基础化工 | 143.2 | double_red、new_high_direction、new_high_cluster | 5 | 10 | 1 | - |
| 23 | 磷化工 | 磷化工 | 基础化工 | 139.31 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 24 | 储能 | 储能 | 电力设备 | 134.2 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 工业金属 | 工业金属 | 有色金属 | 133.85 | double_red、capacity_industry、limit_heat、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 26 | 固态电池 | 固态电池 | 电力设备 | 132.45 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 4 | - |
| 27 | 金属锌 | 金属锌 | 有色金属 | 126.45 | double_red、capacity_industry、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 28 | 光伏 | 光伏 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 3 | - |
| 29 | 钠离子电池 | 储能 | 电力设备 | 124.0 | double_red、capacity_industry、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 30 | 人工智能 | 人工智能 | 计算机 | 123.5 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 飞行汽车(eVTOL) | 飞行汽车 | 汽车 | 122.45 | double_red、limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 32 | AI应用 | AI应用 | 计算机 | 122.1 | double_red、limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 33 | 金属铅 | 金属铅 | 有色金属 | 122.1 | double_red、capacity_industry、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 34 | 黄金 | 黄金 | 有色金属 | 122.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 2 | - |
| 35 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 120.0 | double_red、capacity_industry、new_high_cluster | 5 | 3 | 1 | - |
| 36 | 大飞机 | 大飞机 | 国防军工 | 118.1 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 37 | 金属镍 | 金属镍 | 有色金属 | 118.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 38 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 39 | IP经济(谷子经济) | 谷子经济 | 传媒 | 116.0 | double_red、new_high_cluster | 4 | 6 | 0 | missing_evidence |
| 40 | 专用设备 | 专用设备 | 机械设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 创新药 | 创新药 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 3 | - |
| 42 | 机器人 | 机器人 | 机械设备 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 电池化学品 | 电池化学品 | 电力设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 44 | 军工装备 | 军工装备 | 国防军工 | 114.1 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 45 | 减速器 | 减速器 | 机械设备 | 114.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 46 | AIGC | AIGC | 传媒 | 110.0 | double_red、new_high_cluster | 5 | 10 | 1 | - |
| 47 | 证券 | 证券IT | 非银金融 | 108.0 | double_red、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 48 | 钼 | 小金属 | 有色金属 | 107.0 | limit_advance_cluster、capacity_industry | 3 | 7 | 0 | missing_evidence |
| 49 | 小米汽车 | 小米汽车 | 汽车 | 106.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 50 | 量子科技 | 量子科技 | 计算机 | 106.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：PCB

- **标准概念**：PCB
- **申万一级**：有色金属
- **评分**：206.94
- **触发类型**：limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 115.0 | 连板股2只，最高4板，容量前三=True |
| new_high_direction | 65.94 | 新高股38只，新高成交1275.58亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 10 |
| AI PCB | 5 |
| AIPCB专用油墨 | 5 |
| PCB印制电路板 | 5 |
| PCB微钻 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东威科技 | 688700 | AI PCB | PCB精密电镀设备（核心） | related | L1_L3_candidate | 20 |
| 东山精密 | 002384 | AI PCB | 光模块（含光芯片，索尔思光电）、AI PCB（高多层硬板/RPCB）、F... | core | L1_L3_candidate | 20 |
| 中京电子 | 002579 | AI PCB | - | - | - | 20 |
| 中富电路 | 300814 | AI PCB | AI服务器三次电源PCB、二次电源PCB（HVDC）、埋感埋容嵌入式PC... | related | L1_L3_candidate | 20 |
| 中钨高新 | 000657 | AI PCB | PCB微钻、铣刀（金洲公司，AI+光模块耗材） | related | L1_L3_candidate | 20 |
| 南亚新材 | 688519 | AI PCB | 高频高速CCL国产替代和涨价弹性标的 | related | - | 20 |
| 嘉元科技 | 688388 | AI PCB | 高端电子电路铜箔（PCB铜箔/HVLP/RTF） | related | L1_L3_candidate | 20 |
| 大族数控 | 301200 | AI PCB | PCB钻孔设备核心受益标的 | core | - | 20 |

## 候选 2：小金属

- **标准概念**：小金属
- **申万一级**：有色金属
- **评分**：194.0
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.24%，边际量 36.48%，成交额 2819.38 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.24%，边际量36.48%，成交2819.38亿 |
| new_high_direction | 68.0 | 新高股21只，新高成交1480.0299999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小金属 | 10 |
| 二氧化锆 | 2 |
| 半导体设备材料 | 2 |
| 周期资源 | 2 |
| 战略金属 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方钽业 | 000962 | 小金属 | 钽铌材料/钽电容材料 | core | - | 10 |
| 东方锆业 | 002167 | 小金属 | 锆材料/其他小金属 | related | graph_only | 10 |
| 中国稀土 | 000831 | 小金属 | 中重稀土整合平台 | related | - | 10 |
| 中钨高新 | 000657 | 小金属 | 钨产业链/硬质合金刀具 | core | - | 10 |
| 凤形股份 | 002760 | 小金属 | 铟/锌/银回收深加工线索 | related | - | 10 |
| 北方稀土 | 600111 | 小金属 | 稀土/战略资源交叉 | related | - | 10 |
| 华钰矿业 | 601020 | 小金属 | 锑资源 | core | - | 10 |
| 华锡有色 | 600301 | 小金属 | 锑/锡资源端 | core | - | 10 |

## 候选 3：氢能源

- **标准概念**：氢能源
- **申万一级**：电力设备
- **评分**：184.85
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.9%，边际量 25.98%，成交额 2853.57 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（4），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.9%，边际量25.98%，成交2853.57亿 |
| new_high_direction | 53.1 | 新高股18只，新高成交248.01000000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |
| limit_heat | 5.75 | 涨停5只，市场占比5.62，排名28 |

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
| 阳光电源 | 300274 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 隆基绿能 | 601012 | 氢能源 | 上游设备 | related | L1_L3_candidate | 10 |
| 雪人股份 | 002639 | 氢能源 | 上游设备 | peripheral | L1 | 10 |

## 候选 4：金属铜

- **标准概念**：金属铜
- **申万一级**：有色金属
- **评分**：180.64
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.37%，边际量 65.3%，成交额 1404.0 亿，容量前三=是
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.37%，边际量65.3%，成交1404.0亿 |
| new_high_direction | 46.44 | 新高股10只，新高成交355.43亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比13.48，排名7 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：177.53
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.88%，边际量 20.71%，成交额 5446.4 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.88%，边际量20.71%，成交5446.4亿 |
| new_high_direction | 52.98 | 新高股28只，新高成交1038.73亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比14.61，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 商业航天 | 10 |
| AI基础设施与国产算力 | 2 |
| AI算力基础设施 | 2 |
| 低轨卫星星座 | 2 |
| 光伏 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SpaceX | - | 商业航天 | 受益标的 | core | L3 | 10 |
| 上海港湾 | 605598 | 商业航天 | 太阳翼/太空光伏 | core | - | 10 |
| 上海瀚讯 | 300762 | 商业航天 | 卫星通信载荷、地面信关站、用户终端 | core | L1_L3_candidate | 10 |
| 东方日升 | 300118 | 商业航天 | 太空算力卫星太阳翼与钙钛矿电池产业链受益名单公司 | peripheral | graph_only | 10 |
| 中国卫通 | 601698 | 商业航天 | 应用端 | core | L2 | 10 |
| 中国星网 | - | 商业航天 | 图谱待核验（非直接产业链） | peripheral | graph_only | 10 |
| 中复神鹰 | 688295 | 商业航天 | 商业航天高性能碳纤维本土供应商，推进卫星端验证 | related | L1_L3_candidate | 10 |
| 中海油服 | 601808 | 商业航天 | 钻井服务、油田技术服务、船舶服务 | related | L1_L3_candidate | 10 |

## 候选 6：燃料电池

- **标准概念**：燃料电池
- **申万一级**：电力设备
- **评分**：176.76
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.88%，边际量 21.21%，成交额 1469.48 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.88%，边际量21.21%，成交1469.48亿 |
| new_high_direction | 50.76 | 新高股14只，新高成交252.84亿，容量前三=True |
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

## 候选 7：PET铜箔

- **标准概念**：PET铜箔
- **申万一级**：电力设备
- **评分**：175.77
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.45%，边际量 26.54%，成交额 1017.18 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（9），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.45%，边际量26.54%，成交1017.18亿 |
| new_high_direction | 49.77 | 新高股12只，新高成交397.46999999999997亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PET铜箔 | 10 |
| PET基复合铜箔 | 2 |
| 固态电池 | 2 |
| 复合铜箔 | 2 |
| 水电镀设备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万顺新材 | 300057 | PET铜箔 | 复合铜箔材料潜在参与方 | related | L1 | 10 |
| 东威科技 | 688700 | PET铜箔 | 上游设备 | core | L1 | 10 |
| 中一科技 | 301150 | PET铜箔 | 中游制造/服务 | peripheral | graph_only | 10 |
| 先导智能 | 300450 | PET铜箔 | 上游设备 | peripheral | graph_only | 10 |
| 双星新材 | 002585 | PET铜箔 | 图谱弱关联 | peripheral | graph_only | 10 |
| 嘉元科技 | 688388 | PET铜箔 | 图谱弱关联 | peripheral | graph_only | 10 |
| 英联股份 | 002846 | PET铜箔 | 中游制造/服务 | peripheral | graph_only | 10 |
| 诺德股份 | 600110 | PET铜箔 | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 8：稀土永磁

- **标准概念**：稀土永磁
- **申万一级**：有色金属
- **评分**：175.15
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.58%，边际量 42.18%，成交额 821.1 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.58%，边际量42.18%，成交821.1亿 |
| new_high_direction | 49.15 | 新高股12只，新高成交348.02亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 有色金属 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 稀土永磁 | 10 |
| 稀土永磁材料 | 5 |
| 半导体设备材料 | 2 |
| 压缩机 | 2 |
| 周期资源 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国稀土 | 000831 | 稀土永磁 | 中重稀土集团平台/冶炼分离 | core | - | 10 |
| 中科三环 | 000970 | 稀土永磁 | 钕铁硼永磁材料龙头 | core | L1_L3_candidate | 10 |
| 中稀有色 | 600259 | 稀土永磁 | 中重稀土资产整合平台 | core | - | 10 |
| 包钢股份 | 600010 | 稀土永磁 | 稀土精矿供应/资源端 | core | - | 10 |
| 北方稀土 | 600111 | 稀土永磁 | 上游轻稀土资源/冶炼分离龙头 | core | - | 10 |
| 华宏科技 | 002645 | 稀土永磁 | 稀土回收/磁材 | related | - | 10 |
| 厦门钨业 | 600549 | 稀土永磁 | 稀土冶炼/钨钼交叉 | peripheral | L1 | 10 |
| 奔朗新材 | 920807 | 稀土永磁 | 金刚石散热材料、稀土永磁元器件、金刚石工具 | core | L2 | 10 |

## 候选 9：海峡两岸

- **标准概念**：海峡两岸
- **申万一级**：综合
- **评分**：169.05
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.03%，边际量 21.6%，成交额 2631.82 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.03%，边际量21.6%，成交2631.82亿 |
| new_high_direction | 46.6 | 新高股18只，新高成交527.76亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比7.87，排名18 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 10：可控核聚变

- **标准概念**：可控核聚变
- **申万一级**：电力设备
- **评分**：168.37
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.95%，边际量 23.74%，成交额 1404.26 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.95%，边际量23.74%，成交1404.26亿 |
| new_high_direction | 42.37 | 新高股7只，新高成交365.9亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| capacity_industry | 10.0 | 所属申万一级 电力设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 可控核聚变 | 10 |
| 核电与可控核聚变 | 5 |
| 核电 | 2 |
| 核聚变 | 2 |
| 管道 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东方电气 | 600875 | 可控核聚变 | 聚变托卡马克装置大型超导线圈及腔体外延设备集成商 | peripheral | graph_only | 10 |
| 中国核建 | 601611 | 可控核聚变 | 聚变堆（如ITER、CFETR）核岛安装与高难度工程总包商 | peripheral | graph_only | 10 |
| 中国核电 | 601985 | 可控核聚变 | 核聚变商业化国家级平台战略参股及未来运营方 | peripheral | graph_only | 10 |
| 中矿资源 | 002738 | 可控核聚变 | 上游材料 | peripheral | L1 | 10 |
| 久立特材 | 002318 | 可控核聚变 | 托卡马克超导磁体导管（特种合金管）供应商 | peripheral | L1 | 10 |
| 合锻智能 | 603011 | 可控核聚变 | 核聚变核心部件、PCB、CCL层压设备、色选机 | related | L1_L3_candidate | 10 |
| 同方股份 | 600100 | 可控核聚变 | 可控核聚变（战略合作） | related | L1_L3_candidate | 10 |
| 四创电子 | 600990 | 可控核聚变 | 可控核聚变电源 | related | L1_L3_candidate | 10 |
