# 2026-09-24 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：16526.49
- **上涨家数**：1118
- **涨停 / 跌停**：53 / 13
- **容量前三行业**：1.电子(27.1%, super_capacity)、2.机械设备(8.4%, normal)、3.医药生物(7.2%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 人工智能 | 人工智能 | 计算机 | 143.55 | limit_heat、limit_advance_cluster、new_high_cluster | 3 | 12 | 1 | - |
| 2 | 集成电路设计 | 集成电路 | 电子 | 130.26 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 3 | 低空经济 | 低空经济 | 基础化工 | 122.5 | limit_heat、limit_advance_cluster、new_high_cluster | 2 | 12 | 3 | - |
| 4 | 智慧城市 | 智慧城市 | 计算机 | 100.94 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 5 | 一带一路 | 一带一路 | 电力设备 | 98.92 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 6 | 半导体材料 | 半导体材料 | 电子 | 98.29 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 7 | 半导体 | 半导体 | 电子 | 89.16 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 8 | 机械设备 | 机械设备 | 机械设备 | 86.55 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 9 | 电子 | EDA（电子设计自动化） | 电子 | 85.2 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 10 | 医药医疗 | 医疗 | 医药生物 | 83.74 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 先进封装 | 先进封装 | 电子 | 80.26 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 5 | - |
| 12 | 存储芯片 | 存储芯片 | 电子 | 80.12 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 5 | - |
| 13 | 新能源车 | 新能源车 | - | 79.33 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 人形机器人 | 人形机器人 | 机械设备 | 78.99 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 15 | 智能穿戴 | 智能穿戴 | 电子 | 78.38 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 1 | - |
| 16 | AI眼镜 | AI眼镜 | 电子 | 78.27 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 17 | 通用设备 | 通用设备 | 机械设备 | 78.01 | new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 18 | 机器视觉 | 机器视觉 | 机械设备 | 77.79 | new_high_direction、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 19 | 出版业 | 出版 | - | 77.2 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 20 | OLED概念 | LED | 电子 | 76.75 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 21 | 商业航天 | 商业航天 | 国防军工 | 76.49 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 22 | 3D打印 | 3D打印 | 机械设备 | 74.09 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 23 | 化工 | 化工 | 基础化工 | 73.87 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 24 | 数据中心 | 数据中心 | 计算机 | 73.71 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 25 | 充电桩 | 充电桩 | - | 73.04 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 26 | 光刻机 | 光刻机 | 电子 | 72.62 | new_high_direction、new_high_cluster、capacity_industry | 4 | 12 | 2 | - |
| 27 | 锂电池概念 | 锂 | - | 71.03 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 28 | 无人驾驶 | 无人驾驶 | 汽车 | 70.24 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 29 | CPO概念 | CPO | - | 70.13 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 30 | 汽车芯片 | 汽车芯片 | 电子 | 70.12 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 国防军工 | 国防军工 | 国防军工 | 69.94 | new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 32 | 海峡西岸 | 海峡西岸 | 建筑材料 | 69.8 | limit_heat、limit_advance_cluster、multi_period_rank、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 物联网 | 物联网 | - | 69.55 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 34 | 卫星导航 | 卫星导航 | - | 69.48 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 35 | PCB概念 | PCB概念 | - | 69.43 | new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 36 | 东数西算 | 东数西算 | - | 69.11 | new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 37 | 氢能源 | 氢能源 | 电力设备 | 68.98 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 38 | 小米概念 | 小米概念 | - | 68.88 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 39 | 车联网 | 车联网 | - | 68.34 | new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 40 | 化工原料 | 化工 | 基础化工 | 68.23 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 41 | 无人机 | 无人机 | - | 68.08 | new_high_direction、new_high_cluster | 3 | 12 | 1 | - |
| 42 | 特斯拉概念 | 特斯拉概念 | - | 67.98 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 43 | 工业互联 | 工业互联网 | - | 67.88 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 腾讯概念 | 腾讯概念 | - | 67.82 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 45 | 智能家居 | 智能家居 | - | 67.81 | new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 46 | 华为鸿蒙 | 华为鸿蒙 | 计算机 | 67.76 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 47 | 核电核能 | 核电 | - | 67.76 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 48 | 阿里概念 | 阿里概念 | - | 67.75 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 毫米波雷达 | 毫米波雷达 | 汽车 | 67.69 | new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 50 | 汽车 | 新能源汽车 | 汽车 | 67.64 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：人工智能

- **标准概念**：人工智能
- **申万一级**：计算机
- **评分**：143.55
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 109.0 | 连板股3只，最高5板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.55 | 涨停13只，市场占比24.53，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 人工智能 | 20 |
| AI人工智能 | 5 |
| 人工智能AI | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 凡拓数创 | 301313 | AI人工智能 | AI 3D标准化产品、虚拟数智人与行业AI小模型服务商 | core | L2 | 20 |
| 云从科技 | 688327 | 人工智能 | AI平台厂商（人机协同操作系统+行业解决方案） | core | L2 | 20 |
| 华如科技 | 301302 | 人工智能 | 军事大模型及AI工具集（智能仿真、数字战场、智能体、数字兵力、数实互联）... | core | L2 | 20 |
| 天娱数科 | 002354 | 人工智能 | 以自研天星大模型为技术底座的AI能力平台，贯通基础模型-行业模型-智能体... | core | L2 | 20 |
| 安博通 | 688168 | 人工智能 | 智能、安全人工智能相关产品/服务商 | core | L2 | 20 |
| 宝兰德 | 688058 | 人工智能 | 宝兰德年报披露的人工智能相关主营业务 | core | L2 | 20 |
| 宝鹰股份 | 002047 | 人工智能 | 宝鹰股份年报披露的人工智能相关主营业务 | core | L2 | 20 |
| 广电运通 | 002152 | 人工智能 | 广电运通年报披露的人工智能相关主营业务 | core | L2 | 20 |

## 候选 2：集成电路设计

- **标准概念**：集成电路
- **申万一级**：电子
- **评分**：130.26
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.06 | 新高股11只，新高成交132.429亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅5.75% |
| multi_period_rank | 20.0 | day10排名第6，区间涨幅8.83% |
| multi_period_rank | 18.4 | day3排名第8，区间涨幅0.47% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 集成电路 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 全志科技 | 300458 | 集成电路 | 集成电路设计企业，SoC+模拟+无线互联芯片组合供应商 | core | L2 | 20 |
| 北京君正 | 300223 | 集成电路 | 集成电路芯片研发销售商，坚持存储+计算+模拟产品战略 | core | L2 | 20 |
| 华大九天 | 301269 | 集成电路 | 贯穿集成电路设计、制造、封装的EDA战略基础工具供应商 | core | L2 | 20 |
| 三安光电 | 600703 | 集成电路 | 射频/电力电子/光技术等化合物半导体集成电路 | core | L2 | 20 |
| 东软载波 | 300183 | 集成电路 | 软件及集成电路相关产品/服务商 | core | L2 | 20 |
| 中颖电子 | 300327 | 集成电路 | 集成电路产品相关产品/服务商 | core | L2 | 20 |
| 兴福电子 | 688545 | 集成电路 | 集成电路湿法蚀刻/清洗关键耗材供应商 | core | L2 | 20 |
| 创耀科技 | 688259 | 集成电路 | 软件及集成电路、芯片版图设计服务相关产品/服务商 | core | L2 | 20 |

## 候选 3：低空经济

- **标准概念**：低空经济
- **申万一级**：基础化工
- **评分**：122.5
- **触发类型**：limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 89.0 | 连板股2只，最高2板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比18.87，排名3 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 低空经济 | 20 |
| 中国低空经济 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 光威复材 | 300699 | 中国低空经济 | 上游材料 | peripheral | graph_only | 20 |
| 航天彩虹 | 002389 | 中国低空经济 | 上游材料 | peripheral | graph_only | 20 |
| 万丰奥威 | 002085 | 低空经济 | 通用飞机制造业务（收购钻石飞机55%股权起步），形成汽车轻量化+通航飞机... | core | L2 | 20 |
| 中信海直 | 000099 | 低空经济 | 探索低空经济业务新场景，打造国内领先的通航和低空综合运营商 | core | L2 | 20 |
| 天和防务 | 300397 | 低空经济 | 低空防御装备+低空数据服务（通用机场移动塔台、低空飞行服务系统） | core | L2 | 20 |
| 祥源文旅 | 600576 | 低空经济 | 景区运营、低空经济、资产整合 | core | L1_L3_candidate | 20 |
| 莱斯信息 | 688631 | 低空经济 | 低空经济 | core | L1_L3_candidate | 20 |
| 赛摩智能 | 300466 | 低空经济 | 无人机侦测反制与低空飞行管控平台，产业链中游系统商 | core | L2 | 20 |

## 候选 4：智慧城市

- **标准概念**：智慧城市
- **申万一级**：计算机
- **评分**：100.94
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.84 | 新高股27只，新高成交147.40569999999997亿，容量前三=False |
| limit_advance_cluster | 27.0 | 连板股1只，最高3板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.1 | 涨停6只，市场占比11.32，排名12 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智慧城市 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云赛智联 | 600602 | 智慧城市 | 智慧城市综合解决方案提供商和运营商 | core | L2 | 20 |
| 南威软件 | 603636 | 智慧城市 | 数字政府/公共安全/社会治理/智慧水利/智慧政法软件与解决方案商，互联网... | core | L2 | 20 |
| 君逸数码 | 301172 | 智慧城市 | 智慧城市系统集成与软件服务商（智慧政务/楼宇/场馆/管廊/水务/水利，"... | core | L2 | 20 |
| 大华股份 | 002236 | 智慧城市 | 新型智慧城市生态构建者，覆盖交通、交警、社会治理、公共民生、生态环境等行... | core | L2 | 20 |
| 太极股份 | 002368 | 智慧城市 | 党政/智慧城市/公共安全领域信息化服务商 | core | L2 | 20 |
| 延华智能 | 002178 | 智慧城市 | 智慧城市建设运营与云平台服务商 | core | L2 | 20 |
| 志晟信息 | 920171 | 智慧城市 | 北交所智慧城市系统集成与解决方案商（政务/产业/民生三线） | core | L2 | 20 |
| 恒锋信息 | 300605 | 智慧城市 | 智慧城市信息服相关产品/服务商 | core | L2 | 20 |

## 候选 5：一带一路

- **标准概念**：一带一路
- **申万一级**：电力设备
- **评分**：98.92
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.77 | 新高股35只，新高成交141.55180000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 7.15 | 涨停9只，市场占比16.98，排名4 |

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

## 候选 6：半导体材料

- **标准概念**：半导体材料
- **申万一级**：电子
- **评分**：98.29
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 38.69 | 新高股6只，新高成交183.0366亿，容量前三=True |
| new_high_cluster | 24.0 | 题材内新高股6只 |
| multi_period_rank | 19.0 | day10排名第1，区间涨幅11.75% |
| multi_period_rank | 16.6 | day3排名第4，区间涨幅1.14% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体材料 | 20 |
| 半导体 | 10 |
| 半导体材料去日化 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亚翔集成 | 603929 | 半导体 | IC半导体洁净室工程服务商（建厂工程核心配套） | core | L2 | 20 |
| 利尔达 | 920249 | 半导体 | 半导体IC分销与物联网模组厂商，覆盖芯片到模组的交付 | core | L2 | 20 |
| 力源信息 | 300184 | 半导体 | 国内外半导体原厂产品授权分销商，并开展自研MCU芯片 | core | L2 | 20 |
| 华大九天 | 301269 | 半导体 | 国产半导体设计与制造环节EDA工具龙头 | core | L2 | 20 |
| 华天科技 | 002185 | 半导体 | 半导体封测代工，受益全球半导体销售额增长与国内集成电路产量扩张 | core | L2 | 20 |
| 大为股份 | 002213 | 半导体 | 半导体存储为主业，2025年该业务营收突破10亿元 | core | L2 | 20 |
| 大普微 | 301666 | 半导体 | 半导体存储产品提供商，自研主控芯片委托晶圆制造与封测 | core | L2 | 20 |
| 英唐智控 | 300131 | 半导体 | 全资子公司英唐微技术采用IDM模式研发生产光电转换和图像处理IC，提供光... | core | L2 | 20 |

## 候选 7：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：89.16
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.76 | 新高股23只，新高成交381.01250000000005亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 8.4 | day10排名第8，区间涨幅8.12% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 半导体 | 20 |
| 功率半导体 | 5 |
| 化合物半导体 | 5 |
| 半导体IP | 5 |
| 半导体产业链 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中晶科技 | 003026 | 功率半导体 | 半导体功率芯片及器件制造商（广泛应用于微波炉、激光打印机、X光机、高压电... | core | L2 | 20 |
| 华润微 | 688396 | 功率半导体 | 中国本土最大功率半导体企业之一，IDM模式全产业链经营 | core | L2 | 20 |
| 协昌科技 | 301418 | 功率半导体 | 功率芯片（晶圆/封装成品）设计销售并向封测领域延伸 | core | L2 | 20 |
| 士兰微 | 600460 | 功率半导体 | 分立器件产品营收63.79亿元/毛利率12.22%/同比+17.32% | core | L2 | 20 |
| 富乐德 | 301297 | 功率半导体 | 富乐德年报披露的功率半导体相关主营业务 | core | L2 | 20 |
| 康强电子 | 002119 | 功率半导体 | 康强电子年报披露的功率半导体相关主营业务 | core | L2 | 20 |
| 新洁能 | 605111 | 功率半导体 | 受益标的 | core | L2 | 20 |
| 有研硅 | 688432 | 功率半导体 | 有研硅年报披露的功率半导体相关主营业务 | core | L2 | 20 |

## 候选 8：机械设备

- **标准概念**：机械设备
- **申万一级**：机械设备
- **评分**：86.55
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 54.1 | 新高股74只，新高成交327.8514999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比13.21，排名11 |

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

## 候选 9：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：85.2
- **触发类型**：new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 59.2 | 新高股52只，新高成交736.319亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| EDA（电子设计自动化） | 5 |
| LED电子器件 | 5 |
| 军工电子 | 5 |
| 柔性电子 | 5 |
| 水声电子防务 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| SK海力士 | 000660 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 上海新阳 | 300236 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中科蓝讯 | 688332 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中芯国际 | 688981 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中际旭创 | 300308 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 乐鑫科技 | 688018 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 兆易创新 | 603986 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |
| 全志科技 | 300458 | EDA（电子设计自动化） | 市场信号弱关联 | related | L2_candidate | 20 |

## 候选 10：医药医疗

- **标准概念**：医疗
- **申万一级**：医药生物
- **评分**：83.74
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.34 | 新高股46只，新高成交187.57760000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.4 | 涨停4只，市场占比7.55，排名28 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 医疗 | 10 |
| 医药 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 创新医疗 | 002173 | 医疗 | 医疗服务提供商，营收和利润主要来源于医疗服务 | core | L2 | 20 |
| 嘉事堂 | 002462 | 医疗 | 嘉事堂年报披露的医疗相关主营业务 | core | L2 | 20 |
| 常铝股份 | 002160 | 医疗 | 常铝股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 昊海生科 | 688366 | 医疗 | 昊海生科年报披露的医疗相关主营业务 | related | L2 | 20 |
| 朗姿股份 | 002612 | 医疗 | 朗姿股份年报披露的医疗相关主营业务 | related | L2 | 20 |
| 欧林生物 | 688319 | 医疗 | 欧林生物年报披露的医疗相关主营业务 | related | L2 | 20 |
| 航亚科技 | 688510 | 医疗 | 航亚科技年报披露的医疗相关主营业务 | related | L2 | 20 |
| 丽珠集团 | 000513 | 医药 | 大型综合性医药集团，中国医药工业百强榜第27位 | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-ae3f19b923696f0ec6b7 artifact_sha=41a6ef64fe750d3d72852c5bce57c18ba6d1341cdb7fd2bf805703b173b84eb3 manifest_sha=f23b9ff8af7ce0c19a1804b7aa3e6ff01ffa86d49782f606130128a17154c178 -->
