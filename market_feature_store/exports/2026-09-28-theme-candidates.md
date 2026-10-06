# 2026-09-28 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：17026.6
- **上涨家数**：898
- **涨停 / 跌停**：33 / 59
- **容量前三行业**：1.电子(27.5%, super_capacity)、2.机械设备(8.5%, normal)、3.通信(8.3%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 一带一路 | 一带一路 | 机械设备 | 194.18 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 2 | 新能源车 | 新能源车 | 汽车 | 102.02 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 3 | 疫苗 | 疫苗 | - | 100.0 | multi_period_rank | 5 | 12 | 1 | - |
| 4 | 核电核能 | 核电 | 建筑材料 | 92.7 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 5 | 小家电 | 小家电 | - | 90.0 | multi_period_rank、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 6 | 风电零部件 | 风电零部件 | - | 86.8 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 7 | 机械设备 | 机械设备 | 机械设备 | 83.02 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 8 | 高端装备 | 高端装备 | 机械设备 | 82.54 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |
| 9 | 诊断试剂 | 诊断试剂 | - | 82.4 | multi_period_rank、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 10 | 人形机器人 | 人形机器人 | 机械设备 | 76.3 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 电子 | EDA（电子设计自动化） | 电子 | 76.04 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 12 | 通用设备 | 通用设备 | 机械设备 | 75.03 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 13 | 商业航天 | 商业航天 | 国防军工 | 73.68 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 14 | 风电 | 风电 | 电力设备 | 73.09 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 4 | - |
| 15 | 汽车 | 新能源汽车 | 汽车 | 72.86 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 16 | 新零售 | 零售 | - | 72.78 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 17 | 工业互联 | 工业互联网 | - | 72.46 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 18 | 电力设备 | 电力设备 | 电力设备 | 72.17 | limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 19 | 光学光电 | 光学 | 电子 | 68.13 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 20 | 无人驾驶 | 无人驾驶 | 汽车 | 68.08 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 21 | 锂电池概念 | 锂 | - | 67.87 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 22 | 国防军工 | 国防军工 | 国防军工 | 67.28 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 23 | 存储芯片 | 存储芯片 | 电子 | 67.05 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 24 | 医药医疗 | 医疗 | 医药生物 | 67.03 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 25 | 先进封装 | 先进封装 | 电子 | 66.86 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 26 | 数据中心 | 数据中心 | 计算机 | 65.68 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 27 | 特斯拉概念 | 特斯拉概念 | - | 63.5 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 28 | 乡村振兴 | 乡村振兴 | - | 62.66 | limit_heat、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 29 | 智能交通 | 智能交通 | - | 62.22 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 30 | 折叠屏 | 折叠屏 | 电子 | 61.85 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 车联网 | 车联网 | - | 61.21 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 32 | 物联网 | 物联网 | - | 60.47 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 33 | 海峡西岸 | 海峡西岸 | - | 59.7 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 34 | 华为汽车 | 华为汽车 | 汽车 | 59.28 | new_high_direction、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 35 | 卫星导航 | 卫星导航 | - | 59.25 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 36 | 无人机 | 无人机 | - | 59.08 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 37 | OLED概念 | LED | 电子 | 58.33 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 38 | 智能穿戴 | 智能穿戴 | 电子 | 58.16 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 39 | 玻璃基板 | 玻璃基板 | 电子 | 58.06 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 40 | 小米概念 | 小米概念 | - | 57.83 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 41 | 合成生物 | 合成生物 | 医药生物 | 57.68 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 42 | 绿色电力 | 绿色电力 | 电力设备 | 55.75 | limit_heat、limit_advance_cluster、new_high_cluster | 2 | 12 | 1 | - |
| 43 | 百度概念 | 百度概念 | - | 55.15 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 44 | 生物制药 | 生物制药 | - | 54.4 | multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 45 | 汽车整车 | 汽车整车 | - | 53.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 46 | CXO概念 | CXO | - | 52.4 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 47 | 东数西算 | 东数西算 | - | 51.49 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 48 | 传媒 | 传媒 | 传媒 | 51.0 | limit_advance_cluster、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 49 | 免疫治疗 | 免疫治疗 | - | 48.4 | multi_period_rank、new_high_cluster | 2 | 5 | 0 | missing_evidence |
| 50 | 旅游概念 | 旅游 | - | 48.16 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：一带一路

- **标准概念**：一带一路
- **申万一级**：机械设备
- **评分**：194.18
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 119.0 | 连板股3只，最高3板，容量前三=True |
| new_high_direction | 42.03 | 新高股31只，新高成交162.2178亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.15 | 涨停9只，市场占比27.27，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 一带一路 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 上海港湾 | 605598 | 一带一路 | 深耕东南亚/中东等一带一路沿线市场的岩土工程与新能源基建承包商 | core | L2 | 20 |
| 中色股份 | 000758 | 一带一路 | 有色金属国际工程承包先行者 | core | L2 | 20 |
| 宁波港 | 601018 | 一带一路 | 宁波港年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 安泰科技 | 000969 | 一带一路 | 安泰科技年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 敦煌种业 | 600354 | 一带一路 | 敦煌种业年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 重庆港 | 600279 | 一带一路 | 重庆港年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 青岛港 | 601298 | 一带一路 | 青岛港年报披露的一带一路相关主营业务 | core | L2 | 20 |
| 中国能建 | 601868 | 一带一路 | "一带一路"能源基建出海主力（境外收入高增长） | related | L2 | 20 |

## 候选 2：新能源车

- **标准概念**：新能源车
- **申万一级**：汽车
- **评分**：102.02
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.92 | 新高股37只，新高成交233.36599999999996亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比18.18，排名3 |

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
| 北京双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 华鲁恒升 | 600426 | 新能源 | 煤化工平台向新能源新材料延伸，新能源新材料已成第一大产品 | core | L2 | 20 |
| 双杰电气 | 300444 | 新能源 | 新能源业务 | core | L2 | 20 |
| 固德威 | 688390 | 新能源 | 固德威年报披露的新能源相关主营业务 | core | L2 | 20 |
| 浙江新能 | 600032 | 新能源 | 风光水综合型可再生能源发电企业（控股装机690.76万千瓦） | core | L2 | 20 |
| 润建股份 | 002929 | 新能源 | 新能源电站（光伏/风力/储能）开发建设运维全生命周期服务商 | core | L2 | 20 |
| 涪陵电力 | 600452 | 新能源 | 涪陵电力年报披露的新能源相关主营业务 | core | L2 | 20 |
| 珠海港 | 000507 | 新能源 | 新能源板块收入24.7亿元占比56.34%（风电珠海港昇+管道燃气） | core | L2 | 20 |

## 候选 3：疫苗

- **标准概念**：疫苗
- **申万一级**：-
- **评分**：100.0
- **触发类型**：multi_period_rank
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 28.2 | day5排名第2，区间涨幅5.73% |
| multi_period_rank | 26.6 | day10排名第4，区间涨幅9.49% |
| multi_period_rank | 22.6 | daily排名第9，区间涨幅0.16% |
| multi_period_rank | 22.6 | day3排名第9，区间涨幅-0.81% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 疫苗 | 20 |
| DC疫苗 | 5 |
| HIV疫苗 | 5 |
| HPV疫苗 | 5 |
| mRNA疫苗 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 智飞生物 | 300122 | mRNA疫苗 | mRNA技术平台布局者（带状疱疹/新冠mRNA疫苗获临床批件） | peripheral | L2 | 20 |
| 沃森生物 | 300142 | mRNA疫苗 | 与合作方共建mRNA疫苗技术平台 | related | L2 | 20 |
| 科前生物 | 688526 | mRNA疫苗 | 科前生物年报披露的mRNA疫苗相关主营业务 | core | L2 | 20 |
| 生物股份 | 600201 | mRNA疫苗 | 兽用生物制品（猪、牛、禽 | related | L1_L3_candidate | 20 |
| 康泰生物 | 300601 | mRNA疫苗 | mRNA核酸疫苗研发平台（储备） | related | L2 | 20 |
| 石药创新 | 300765 | mRNA疫苗 | mRNA疫苗平台储备 | related | L2 | 20 |
| 瑞普生物 | 300119 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |
| 金河生物 | 002688 | mRNA疫苗 | 图谱弱关联 | peripheral | graph_only | 20 |

## 候选 4：核电核能

- **标准概念**：核电
- **申万一级**：建筑材料
- **评分**：92.7
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 34.65 | 新高股11只，新高成交99.9657亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比9.09，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 核电 | 10 |
| 核能 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 瑞奇智造 | 920781 | 核电 | 核能装备和试验装置（华龙一号安全系统试验装置、控制棒换料专用套筒等）及核... | core | L2 | 20 |
| 电投产融 | 000958 | 核电 | 核能发电、热电联产、新能源（风电、光伏） | core | L1_L3_candidate | 20 |
| 中国核电 | 601985 | 核电 | 中核集团旗下核电运营平台 | core | L2 | 20 |
| 中国一重 | 601106 | 核电 | 核岛一回路核电设备全覆盖制造，承担国家绝大多数核电锻件和核反应堆压力容器... | core | L2 | 20 |
| 中国广核 | 003816 | 核电 | 中广核集团核能发电唯一平台，国内核电运营双寡头之一（华龙一号自主三代技术... | core | L2 | 20 |
| 中国核建 | 601611 | 核电 | 核电工程建设国家队，全球唯一41年不间断从事核电建造的企业 | core | L2 | 20 |
| 中核科技 | 000777 | 核电 | 核电及核化工关键阀门龙头（中核集团旗下阀门平台） | core | L2 | 20 |
| 景业智能 | 688290 | 核电 | 核工业特种机器人及智能装备、军工智能装备、AI+具身智能 | core | L1_L3_candidate | 20 |

## 候选 5：小家电

- **标准概念**：小家电
- **申万一级**：-
- **评分**：90.0
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（4），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 23.2 | daily排名第2，区间涨幅1.14% |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅0.67% |
| multi_period_rank | 22.4 | day5排名第3，区间涨幅4.17% |
| new_high_cluster | 22.0 | 题材内新高股5只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 小家电 | 20 |
| 家电 | 12 |
| 厨房小家电 | 5 |
| 小家电代工出海 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 利仁科技 | 001259 | 厨房小家电 | 自主品牌"利仁Liven"厨房小家电企业，国内电饼铛领域先驱（电饼铛/空... | core | L2 | 20 |
| 鑫汇科 | 920267 | 厨房小家电 | 小家电整机与核心部件（IH电磁炉/电陶炉等厨电）ODM制造商 | core | L2 | 20 |
| 万朗磁塑 | 603150 | 厨房小家电 | 战略增量业务：控股智享生活电器切入电风扇/取暖器/加湿器等小家电 | related | L2 | 20 |
| 和而泰 | 002402 | 家电 | 大小家电智能控制器制造商，覆盖空调、冰箱、洗衣机、厨电等品类 | core | L2 | 20 |
| 和晶科技 | 300279 | 家电 | 家电类智能控制相关产品/服务商 | core | L2 | 20 |
| 四川长虹 | 600839 | 家电 | 综合家电与电子龙头：电视、冰箱、空调及ICT综合服务等多元业务 | core | L2 | 20 |
| 奇精机械 | 603677 | 家电 | 家电零部件相关产品/服务商 | core | L2 | 20 |
| 好太太 | 603848 | 家电 | 智能家居产品、晾衣架产品相关产品/服务商 | core | L2 | 20 |

## 候选 6：风电零部件

- **标准概念**：风电零部件
- **申万一级**：-
- **评分**：86.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅1.56% |
| multi_period_rank | 18.4 | daily排名第8，区间涨幅0.24% |
| multi_period_rank | 18.4 | day10排名第8，区间涨幅6.93% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 风电零部件 | 20 |
| 风电 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三一重能 | 688349 | 风电 | 风电整机厂商：风机全产业链（核心部件自主研发、整机一体化集成）+风电场设... | core | L2 | 20 |
| 中环海陆 | 301040 | 风电 | 风电轴承/法兰/齿圈锻件供应商（国家级专精特新小巨人） | core | L2 | 20 |
| 中船科技 | 600072 | 风电 | 中船系风电整机制造商（风电收入75.63亿元，装机高峰放量） | core | L2 | 20 |
| 光威复材 | 300699 | 风电 | 风电碳梁等拉挤碳纤维复合材料标准型材制造商 | core | L2 | 20 |
| 国投电力 | 600886 | 风电 | 雅砻江流域水电梯级开发、水风光一体化清洁能源基地、火电（煤电+燃气）、风... | core | L1_L3_candidate | 20 |
| 大唐发电 | 601991 | 风电 | 风电装机约1,120万千瓦，布局全国资源富集区域 | core | L2 | 20 |
| 天晟新材 | 300169 | 风电 | 风电叶片夹芯结构泡沫材料供应 | core | L2 | 20 |
| 威力传动 | 300904 | 风电 | 风电齿轮箱国内市场前列供应商 | core | L2 | 20 |

## 候选 7：机械设备

- **标准概念**：机械设备
- **申万一级**：机械设备
- **评分**：83.02
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.62 | 新高股25只，新高成交129.95340000000004亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比12.12，排名12 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光格科技 | 688450 | AIoT | 分布式光纤传感、AIoT资产运维、四足巡检机器人 | core | L2 | 1 |
| 卓兆点胶 | 920026 | AI眼镜 | 消费电子点胶设备/阀体（果链核心供应商）、Meta AI眼镜点胶阀、点胶... | core | L1_L3_candidate | 1 |
| 武进不锈 | 603878 | 不锈钢管 | 工业用不锈钢管（无缝管/焊管/管件），下游为石化、电力设备、机械设备制造 | core | L2 | 1 |
| 双元科技 | 688623 | 人形机器人 | 人形机器人自动化检测装配设备、在线自动化测控系统、机器视觉智能检测系统 | core | L2 | 1 |
| 锐科激光 | 300747 | 低空经济 | 连续光纤激光器、超快激光器、脉冲光纤激光器、特种光纤 | core | L1_L3_candidate | 1 |
| 海伦哲 | 300201 | 储能消防 | 储能消防（气溶胶灭火）、高空作业车、电力应急保障车、军品及消防车 | core | L1_L3_candidate | 1 |
| 理工光科 | 300557 | 可控核聚变 | 光纤传感监测系统、消防报警一体化服务、智能化应用系统、智慧物联平台 | core | L1_L3_candidate | 1 |
| 联赢激光 | 688518 | 固态电池 | 锂电激光焊接、消费电子焊接、固态电池设备、TGV玻璃基板激光加工 | core | L1_L3_candidate | 1 |

## 候选 8：高端装备

- **标准概念**：高端装备
- **申万一级**：机械设备
- **评分**：82.54
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.14 | 新高股17只，新高成交91.0973亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比12.12，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 高端装备 | 20 |
| 高端装备与自主可控制造 | 5 |
| 高端装备制造 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 通裕重工 | 300185 | 高端装备 | 能源电力/石化/船舶/海工/核电等大型装备核心部件平台 | related | L2 | 20 |
| 三花智控 | 002050 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 光威复材 | 300699 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 德赛西威 | 002920 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 拓普集团 | 601689 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 汇川技术 | 300124 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 航天电子 | 600879 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |
| 莱斯信息 | 688631 | 高端装备与自主可控制造 | 受益标的 | core | L1 | 20 |

## 候选 9：诊断试剂

- **标准概念**：诊断试剂
- **申万一级**：-
- **评分**：82.4
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 24.0 | day5排名第1，区间涨幅5.97% |
| multi_period_rank | 20.0 | day10排名第6，区间涨幅8.72% |
| new_high_cluster | 20.0 | 题材内新高股4只 |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅-0.43% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 丽珠集团 | 000513 | IVD | 诊断试剂与设备业务板块经营者 | related | L2 | 1 |
| 之江生物 | 688317 | 体外诊断 | 分子诊断试剂与仪器厂商 | core | L2 | 1 |
| 利德曼 | 300289 | 体外诊断 | 体外诊断试剂、诊断仪器相关产品/服务商 | core | L2 | 1 |
| 圣湘生物 | 688289 | 体外诊断 | 体外诊断行业、诊断试剂相关产品/服务商 | core | L2 | 1 |
| 奥泰生物 | 688606 | 体外诊断 | 体外诊断行业、传染病类相关产品/服务商 | core | L2 | 1 |
| 新产业 | 300832 | 体外诊断 | 国产化学发光龙头，四大技术平台（磁性微球/试剂关键原料/全自动仪器/诊断... | core | L2 | 1 |
| 浩欧博 | 688656 | 体外诊断 | 过敏试剂产品、自免试剂产品相关产品/服务商 | core | L2 | 1 |
| 硕世生物 | 688399 | 体外诊断 | 体外诊断试剂+仪器+服务一体化企业：分子诊断为主，销往疾控、医院、第三方... | core | L2 | 1 |

## 候选 10：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：76.3
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 50.3 | 新高股15只，新高成交103.96830000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人形机器人 | 20 |
| 机器人 | 12 |
| 人形机器人丝杠 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三瑞智能 | 301696 | 人形机器人 | CubeMars品牌深耕机器人关节：机器人电机、驱动板、高度集成动力模组 | core | L2 | 20 |
| 中控技术 | 688777 | 人形机器人 | TPT工业大模型、DCS、SIS控制系统、UCS通用控制系统 | core | L1_L3_candidate | 20 |
| 五洲新春 | 603667 | 人形机器人 | 机器人执行器核心零部件丝杠供应商 | core | L2 | 20 |
| 博众精工 | 688097 | 人形机器人 | 人形机器人组装线 | core | L1_L3_candidate | 20 |
| 唯科科技 | 301196 | 人形机器人 | MPO光通信零部件、机器人轻量化部件、新能源汽车零部件、精密注塑模具 | core | L1_L3_candidate | 20 |
| 安洁科技 | 002635 | 人形机器人 | 安洁科技年报披露的人形机器人相关主营业务 | core | L2 | 20 |
| 拓斯达 | 300607 | 人形机器人 | 拓斯达年报披露的人形机器人相关主营业务 | core | L2 | 20 |
| 旭光电子 | 600353 | 人形机器人 | 旭光电子年报披露的人形机器人相关主营业务 | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-28b35fe8616c8671cd95 artifact_sha=6cf6a93f08cdb5b2c0507807d208bbafd73f3a977f452705f65d8538faa535dc manifest_sha=6f4a6e7a1282a0b61c3fe8c9985ed60b1c0dd00b610fa8e5f85f7da416c8bb3b -->
