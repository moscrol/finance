# 2026-07-10 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：33883.62
- **上涨家数**：3774
- **涨停 / 跌停**：92 / 4
- **容量前三行业**：1.电子(35.4%, super_capacity)、2.通信(8.4%, normal)、3.机械设备(7.6%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 人形机器人 | 人形机器人 | 机械设备 | 191.02 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 2 | 商业航天 | 商业航天 | 国防军工 | 182.7 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 3 | 机器视觉 | 机器视觉 | 机械设备 | 180.86 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 11 | 0 | missing_evidence |
| 4 | 6G | 6G | 通信 | 178.57 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 5 | 无人驾驶 | 无人驾驶 | 汽车 | 177.51 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 6 | 星闪 | 星闪技术 | 通信 | 173.24 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 3 | 0 | missing_evidence |
| 7 | 云计算 | 云计算 | 计算机 | 173.06 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 8 | 新型工业化 | 新型工业化 | 机械设备 | 171.59 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 9 | 算力租赁 | 算力租赁 | 计算机 | 168.3 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 10 | 数据要素 | 数据要素 | 计算机 | 166.99 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 创新药 | 创新药 | 医药生物 | 165.28 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 12 | 军工信息化 | 军工信息化 | 国防军工 | 163.55 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 13 | 海峡两岸 | 海峡两岸 | 综合 | 161.47 | double_red、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 14 | 大飞机 | 大飞机 | 国防军工 | 159.36 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | ChatGPT | ChatGPT | 传媒 | 158.75 | double_red、new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 16 | 风电 | 风电 | 电力设备 | 158.2 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 17 | 军工装备 | 军工装备 | 国防军工 | 157.83 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 毫米波雷达 | 毫米波雷达 | 汽车 | 157.15 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 多模态AI | 多模态AI | 计算机 | 155.93 | double_red、new_high_direction、new_high_cluster | 2 | 3 | 1 | - |
| 20 | 军工电子 | 军工电子 | 国防军工 | 155.52 | double_red、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 21 | IT服务 | IT服务 | 计算机 | 155.01 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 22 | 长安汽车 | 长安汽车 | 汽车 | 150.23 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 23 | 计算机设备 | 计算机设备 | 计算机 | 149.55 | double_red、new_high_direction、new_high_cluster | 1 | 9 | 1 | - |
| 24 | 华为昇腾 | 华为昇腾 | 计算机 | 148.68 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 25 | 数字货币 | 数字货币 | 计算机 | 148.29 | double_red、new_high_direction、new_high_cluster | 5 | 3 | 1 | - |
| 26 | 飞行汽车(eVTOL) | 飞行汽车 | 汽车 | 146.96 | double_red、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 27 | 连板未映射 | - | 国防军工 | 145.0 | limit_advance_cluster | 0 | 0 | 0 | placeholder_market_theme |
| 28 | 高压快充 | 超充 | 电力设备 | 142.3 | double_red、new_high_direction、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 29 | 智谱AI | 智谱AI | 计算机 | 136.63 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 30 | Web3.0 | Web3.0 | 计算机 | 133.59 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 太赫兹 | 6G产业 | 国防军工 | 132.78 | double_red、new_high_direction、new_high_cluster | 1 | 4 | 0 | missing_evidence |
| 32 | 通用设备 | 金属制品 | 机械设备 | 131.75 | double_red、capacity_industry、limit_heat、new_high_cluster | 1 | 7 | 0 | missing_evidence |
| 33 | 军工 | 军工 | 国防军工 | 128.4 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 人工智能 | 人工智能 | 计算机 | 128.05 | double_red、limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 35 | 机器人 | 机器人 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 2 | - |
| 36 | 低空经济 | 低空经济 | 国防军工 | 125.25 | double_red、limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 37 | 储能 | 储能 | 电力设备 | 124.9 | double_red、limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 38 | 化学制药 | 化学制药 | 医药生物 | 122.1 | double_red、limit_heat、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 39 | MR(混合现实) | HAMR | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 40 | 3D打印 | 3D打印 | 机械设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 41 | DeepSeek | DeepSeek | 计算机 | 116.0 | double_red、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 42 | IP经济(谷子经济) | 谷子经济 | 传媒 | 116.0 | double_red、new_high_cluster | 4 | 7 | 0 | missing_evidence |
| 43 | 减速器 | 减速器 | 机械设备 | 116.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 1 | - |
| 44 | 合成生物 | 合成生物 | 医药生物 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 45 | 汽车零部件 | 汽车零部件 | 汽车 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 航空发动机 | 航空发动机 | 国防军工 | 116.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 47 | 小米汽车 | 小米汽车 | 汽车 | 114.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 短剧游戏 | 短剧游戏 | 传媒 | 112.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 特高压 | 特高压 | 电力设备 | 106.0 | double_red、new_high_cluster | 5 | 12 | 1 | - |
| 50 | 工业母机 | 工业母机 | 机械设备 | 100.0 | double_red、capacity_industry | 5 | 12 | 2 | - |

## 五、核心候选明细

## 候选 1：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：191.02
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.38%，边际量 17.01%，成交额 4993.73 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.38%，边际量17.01%，成交4993.73亿 |
| new_high_direction | 56.82 | 新高股22只，新高成交545.5799999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比13.04，排名12 |

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

## 候选 2：商业航天

- **标准概念**：商业航天
- **申万一级**：国防军工
- **评分**：182.7
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.07%，边际量 30.93%，成交额 5724.69 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.07%，边际量30.93%，成交5724.69亿 |
| new_high_direction | 51.85 | 新高股41只，新高成交947.9300000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 14.85 | 涨停31只，市场占比33.7，排名1 |

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

## 候选 3：机器视觉

- **标准概念**：机器视觉
- **申万一级**：机械设备
- **评分**：180.86
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.4%，边际量 22.94%，成交额 1994.96 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（11），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.4%，边际量22.94%，成交1994.96亿 |
| new_high_direction | 54.86 | 新高股17只，新高成交388.7699999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 机器视觉 | 10 |
| 光学元件 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天准科技 | 688003 | 机器视觉 | 工业视觉装备供应商（量检测+制程装备） | core | L2 | 10 |
| 宇瞳光学 | 300790 | 机器视觉 | 机器视觉相关产品/材料供应商 | related | L2 | 10 |
| 联创电子 | 002036 | 800G_1.6T光模块 | 车载光学（ADAS镜头、影像模组）、机器视觉 | related | L1_L3_candidate | 1 |
| 大华股份 | 002236 | AI大模型 | AI大模型（星汉大模型）、AI服务器（华启智慧）、创新业务（机器视觉、机... | core | L1_L3_candidate | 1 |
| 弘景光电 | 301479 | AI眼镜 | 光学镜头及摄像模组产品研发、设计、生产和销售 | related | L1_L3_candidate | 1 |
| 联合光电 | 300691 | AI眼镜 | 安全监控镜头、新型显示(AR、投影) | related | L1_L3_candidate | 1 |
| 凌云光 | 688400 | OCS光交换机 | 机器视觉（消费电子、新能源、印刷包装、新型显示） | core | L1_L3_candidate | 1 |
| 双元科技 | 688623 | 人形机器人 | 人形机器人自动化检测装配设备、在线自动化测控系统、机器视觉智能检测系统 | core | L2 | 1 |

## 候选 4：6G

- **标准概念**：6G
- **申万一级**：通信
- **评分**：178.57
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.06%，边际量 28.59%，成交额 2398.97 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.06%，边际量28.59%，成交2398.97亿 |
| new_high_direction | 52.57 | 新高股12只，新高成交621.8799999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 6G | 10 |
| 5G_6G | 5 |
| 5G_6G融合 | 5 |
| 5G_6G通信 | 5 |
| 6G产业 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万丰奥威 | 002085 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |
| 三安光电 | 600703 | 6G | 6G前置射频器件潜在相关 | peripheral | L1 | 10 |
| 东方财富 | 300059 | 6G | 证券业务、金融电子商务服务业务、金融数据服务业务研发/生产商 | related | L2 | 10 |
| 中信海直 | 000099 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |
| 中兴通讯 | 000063 | 6G | - | - | - | 10 |
| 中国卫通 | 601698 | 6G | 空天地一体化前置卫星通信环节 | related | L1 | 10 |
| 中国移动 | 600941 | 6G | 6G网络架构和场景牵引方 | related | L2_candidate | 10 |
| 中瓷电子 | 003031 | 6G | 图谱弱关联 | peripheral | graph_only | 10 |

## 候选 5：无人驾驶

- **标准概念**：无人驾驶
- **申万一级**：汽车
- **评分**：177.51
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.78%，边际量 23.33%，成交额 4695.74 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.78%，边际量23.33%，成交4695.74亿 |
| new_high_direction | 54.71 | 新高股22只，新高成交1177.0300000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比8.7，排名16 |

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

## 候选 6：星闪

- **标准概念**：星闪技术
- **申万一级**：通信
- **评分**：173.24
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.66%，边际量 15.19%，成交额 714.83 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（3），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.66%，边际量15.19%，成交714.83亿 |
| new_high_direction | 47.24 | 新高股11只，新高成交307.4200000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 通信 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 星闪技术 | 5 |
| 人工智能 | 2 |
| 信创 | 2 |
| 开源鸿蒙 | 2 |
| 鸿蒙 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 利尔达 | 920249 | 星闪技术 | 物联网模块及系统解决方案、IC增值分销、AI模组、5G RedCap模组 | related | L1_L3_candidate | 10 |
| 润和软件 | 300339 | 星闪技术 | AI智能体、开源鸿蒙、开源欧拉 | related | L1_L3_candidate | 10 |
| 艾融软件 | 920799 | 信创 | 银行核心系统国产化改造服务商（鸿蒙/星闪适配、华为鲲鹏昇腾双认证） | core | L2 | 1 |

## 候选 7：云计算

- **标准概念**：云计算
- **申万一级**：计算机
- **评分**：173.06
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.74%，边际量 23.87%，成交额 2097.68 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.74%，边际量23.87%，成交2097.68亿 |
| new_high_direction | 51.31 | 新高股21只，新高成交905.1500000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.75 | 涨停5只，市场占比5.43，排名29 |

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

## 候选 8：新型工业化

- **标准概念**：新型工业化
- **申万一级**：机械设备
- **评分**：171.59
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.53%，边际量 21.82%，成交额 1927.67 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.53%，边际量21.82%，成交1927.67亿 |
| new_high_direction | 45.59 | 新高股10只，新高成交287.09亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新型工业化 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东土科技 | 300353 | 新型工业化 | 工业操作系统 / 工业软件-操作系统 / 半导体设备映射标的 | core | L2_curated_research | 10 |
| 中控技术 | 688777 | 新型工业化 | DCS（集散控制系统） / 工业AI大模型 / 工业软件-DCS/AI ... | core | L2_curated_research | 10 |
| 乔锋智能 | 301603 | 新型工业化 | 机床整机（主机厂） / 工业母机-整机映射标的 | related | L2_curated_research | 10 |
| 信捷电气 | 603416 | 新型工业化 | 运动控制/PLC / 工控-小型PLC / PLC（大中型）映射标的 | core | L2_curated_research | 10 |
| 创世纪 | 300083 | 新型工业化 | 机床整机（主机厂）映射标的 | related | L2_curated_research | 10 |
| 华中数控 | 300161 | 新型工业化 | 数控系统 / 工业母机-数控系统映射标的 | core | L2_curated_research | 10 |
| 国盛智科 | 688558 | 新型工业化 | 机床整机（主机厂）映射标的 | related | L2_curated_research | 10 |
| 埃斯顿 | 002747 | 新型工业化 | 工业机器人整机 / 机器人-整机 / 新能源汽车映射标的 | core | L2_curated_research | 10 |

## 候选 9：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：168.3
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.59%，边际量 21.26%，成交额 2077.93 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.59%，边际量21.26%，成交2077.93亿 |
| new_high_direction | 52.3 | 新高股17只，新高成交983.6700000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 算力租赁 | 10 |
| AI基础设施与国产算力 | 2 |
| AI处理器 | 2 |
| AI应用 | 2 |
| AI服务器电源 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| CoreWeave | - | 算力租赁 | 图谱弱关联 | peripheral | graph_only | 10 |
| Lambda | - | 算力租赁 | 受益标的 | related | L3 | 10 |
| 东方国信 | 300166 | 算力租赁 | 算力租赁（AutoDL/中科视拓） | related | L1_L3_candidate | 10 |
| 东阳光 | 600673 | 算力租赁 | 算力租赁 | related | L1_L3_candidate | 10 |
| 中国电信 | 601728 | 算力租赁 | 算力服务套餐潜在运营方 | peripheral | L2_candidate | 10 |
| 中科曙光 | 603019 | 算力租赁 | 上游材料/设备 | peripheral | L1 | 10 |
| 中贝通信 | 603220 | 算力租赁 | 智算（算力租赁）业务、5G新基建 | core | L1_L3_candidate | 10 |
| 云赛智联 | 600602 | 算力租赁 | 云计算及大数据、行业解决方案、智能产品 | related | L1_L3_candidate | 10 |

## 候选 10：数据要素

- **标准概念**：数据要素
- **申万一级**：计算机
- **评分**：166.99
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.92%，边际量 24.46%，成交额 1970.79 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.92%，边际量24.46%，成交1970.79亿 |
| new_high_direction | 44.19 | 新高股17只，新高成交335.4亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.8 | 涨停8只，市场占比8.7，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 数据要素 | 10 |
| AI智能体 | 2 |
| 数字孪生 | 2 |
| 新型城镇化 | 2 |
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
