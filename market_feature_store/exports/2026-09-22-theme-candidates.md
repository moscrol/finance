# 2026-09-22 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：主升阶段
- **成交额**：21315.86
- **上涨家数**：2371
- **涨停 / 跌停**：64 / 3
- **容量前三行业**：1.电子(29.9%, super_capacity)、2.通信(8.4%, normal)、3.医药生物(7.0%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 人工智能 | 人工智能 | 计算机 | 252.35 | double_red、limit_heat、limit_advance_cluster、new_high_cluster | 3 | 12 | 1 | - |
| 2 | 新零售 | 零售 | 医药生物 | 242.85 | double_red、limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 3 | 智能穿戴 | 智能穿戴 | 电子 | 222.88 | double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 4 | 集成电路设计 | 集成电路 | 电子 | 216.91 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 5 | 医药医疗 | 医疗 | 医药生物 | 212.17 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 0 | missing_evidence |
| 6 | 电子 | EDA（电子设计自动化） | 电子 | 201.15 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 7 | PCB | PCB | 电子 | 198.11 | double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 8 | 百度概念 | 百度概念 | 传媒 | 193.61 | double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 9 | 半导体 | 半导体 | 电子 | 192.08 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 汽车芯片 | 汽车芯片 | 电子 | 185.61 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | AI眼镜 | AI眼镜 | 电子 | 183.83 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 12 | MCU芯片 | MCU芯片 | 电子 | 183.14 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 13 | AI手机PC | AI手机 | 电子 | 183.04 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 14 | 东数西算 | 东数西算 | - | 176.96 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 15 | 阿里概念 | 阿里概念 | - | 171.07 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 16 | 腾讯概念 | 腾讯概念 | - | 171.02 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 17 | 云计算 | 云计算 | 计算机 | 170.12 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 18 | 小米概念 | 小米概念 | - | 169.0 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 19 | 信创 | 信创 | 计算机 | 168.17 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 信息安全 | 信息安全 | 计算机 | 168.17 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 21 | 苹果概念 | 苹果概念 | - | 164.09 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 22 | 量子科技 | 量子科技 | 计算机 | 164.02 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 23 | 抖音概念 | 抖音概念 | - | 162.51 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | DeepSeek概念 | DeepSeek | 医药生物 | 155.6 | double_red、limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry | 1 | 12 | 0 | missing_evidence |
| 25 | 传媒 | 传媒 | 传媒 | 130.4 | double_red、limit_heat、multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 26 | 无线耳机 | 无线耳机 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | AI智能体 | AI智能体 | 计算机 | 123.5 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 28 | 华为鸿蒙 | 华为鸿蒙 | 计算机 | 123.5 | double_red、limit_heat、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 29 | 数据要素 | 数据要素 | 计算机 | 123.5 | double_red、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 30 | 区块链 | 区块链 | - | 122.45 | double_red、limit_heat、new_high_cluster | 1 | 9 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 大数据 | 大数据 | 计算机 | 122.45 | double_red、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 32 | AIGC概念 | AIGC | - | 122.1 | double_red、limit_heat、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 33 | PCB概念 | PCB概念 | 轻工制造 | 120.01 | limit_heat、limit_advance_cluster、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 3 | - |
| 34 | ChatGPT概念 | ChatGPT概念 | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 元宇宙概念 | 元宇宙 | - | 116.0 | double_red、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 36 | 国产软件 | 软件 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 37 | 多模态AI | 多模态AI | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 3 | 1 | - |
| 38 | 智能交通 | 智能交通 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 39 | 智能医疗 | 医疗 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 40 | 有色 | 有色冶炼装备 | 有色金属 | 116.0 | double_red、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 41 | 机器视觉 | 机器视觉 | 机械设备 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | 算力租赁 | 算力租赁 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 5 | - |
| 43 | 网络游戏 | 游戏 | 传媒 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 计算机 | 计算机外设 | 计算机 | 116.0 | double_red、new_high_cluster | 4 | 12 | 0 | missing_evidence |
| 45 | 车联网 | 车联网 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 1 | - |
| 46 | 软件服务 | 软件 | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 47 | 边缘计算 | 边缘计算 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 48 | 物联网 | 物联网 | 轻工制造 | 115.91 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 4 | 12 | 1 | - |
| 49 | 一带一路 | 一带一路 | 交通运输 | 107.82 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 50 | 智能家居 | 智能家居 | 房地产 | 104.12 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：人工智能

- **标准概念**：人工智能
- **申万一级**：计算机
- **评分**：252.35
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 1.0111%，边际量 19.0256%，成交额 4698.0753 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 125.0 | 连板股6只，最高3板，容量前三=False |
| double_red | 90.0 | 涨幅1.0111%，边际量19.0256%，成交4698.0753亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 11.35 | 涨停21只，市场占比32.81，排名1 |

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

## 候选 2：新零售

- **标准概念**：零售
- **申万一级**：医药生物
- **评分**：242.85
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 0.332%，边际量 13.8276%，成交额 889.8708 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 119.0 | 连板股2只，最高5板，容量前三=True |
| double_red | 90.0 | 涨幅0.332%，边际量13.8276%，成交889.8708亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比17.19，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 零售 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中国中免 | 601888 | 零售 | 免税+有税全渠道旅游零售运营商（线下门店+自营电商及第三方平台） | core | L2 | 20 |
| 博士眼镜 | 300622 | 零售 | 眼镜零售连锁运营商，直营+加盟+联营覆盖全国，截至2025年末门店589... | core | L2 | 20 |
| 天虹股份 | 002419 | 零售 | 全渠道多业态零售商（百货/购物中心/超市） | core | L2 | 20 |
| 居然智家 | 000785 | 零售 | 全国连锁家居卖场龙头运营商（居然之家），372家卖场覆盖国内30省区市及... | core | L2 | 20 |
| 明牌珠宝 | 002574 | 零售 | 珠宝首饰全渠道连锁零售商（直营/专营/经销/加盟+电商直播） | core | L2 | 20 |
| 曼卡龙 | 300945 | 零售 | 珠宝首饰零售连锁企业（直营+专柜+加盟+电商全渠道，电商收入占比过半） | core | L2 | 20 |
| 来伊份 | 603777 | 零售 | 休闲食品连锁零售商（直营+加盟+特通+电商全渠道） | core | L2 | 20 |
| 深粮控股 | 000019 | 零售 | 粮油产品批发贸易商+"互联网+粮食"零售/团餐供应运营商 | core | L2 | 20 |

## 候选 3：智能穿戴

- **标准概念**：智能穿戴
- **申万一级**：电子
- **评分**：222.88
- **触发类型**：double_red、capacity_industry、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.9105%，边际量 14.6885%，成交额 2150.1256 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.9105%，边际量14.6885%，成交2150.1256亿 |
| new_high_direction | 60.88 | 新高股68只，新高成交870.0632999999997亿，容量前三=True |
| limit_advance_cluster | 36.0 | 连板股1只，最高6板，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能穿戴 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 佰维存储 | 688525 | 智能穿戴 | AI/AR眼镜、智能手表等端侧ePOP存储供应商 | related | L2 | 20 |
| 佳禾智能 | 300793 | 智能穿戴 | 智能手表、智能眼镜等可穿戴产品制造商 | related | L2 | 20 |
| 则成电子 | 920821 | 智能穿戴 | 声学/汽车/医疗电子装联与定制化模组模块（AI智能穿戴高多层AIR-GA... | related | L2 | 20 |
| 天键股份 | 301383 | 智能穿戴 | 声学技术向智能穿戴/智能家居/车载电子等领域延伸 | related | L2 | 20 |
| 萤石网络 | 688475 | 智能穿戴 | 萤石网络年报披露的智能穿戴相关主营业务 | related | L2 | 20 |
| 金太阳 | 300606 | 智能穿戴 | 金太阳年报披露的智能穿戴相关主营业务 | related | L2 | 20 |
| 中科蓝讯 | 688332 | 智能穿戴 | 智能穿戴和智能手表等SoC芯片供应商 | peripheral | graph_only | 20 |
| 唯捷创芯 | 688153 | 射频芯片 | 国内射频前端行业先行者（Fabless模式，产品应用于智能手机、车载通信... | core | L2 | 1 |

## 候选 4：集成电路设计

- **标准概念**：集成电路
- **申万一级**：电子
- **评分**：216.91
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.5752%，边际量 35.9107%，成交额 1801.3334 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.5752%，边际量35.9107%，成交1801.3334亿 |
| new_high_direction | 61.71 | 新高股43只，新高成交936.6501999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 15.8 | day5排名第5，区间涨幅11.24% |
| multi_period_rank | 13.4 | day3排名第8，区间涨幅6.91% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 5：医药医疗

- **标准概念**：医疗
- **申万一级**：医药生物
- **评分**：212.17
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 123.0 | 连板股3只，最高4板，容量前三=True |
| new_high_direction | 56.72 | 新高股103只，新高成交537.5658000000002亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 6.45 | 涨停7只，市场占比10.94，排名23 |

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

## 候选 6：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：201.15
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.3202%，边际量 10.6048%，成交额 6370.6376 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.3202%，边际量10.6048%，成交6370.6376亿 |
| new_high_direction | 68.0 | 新高股155只，新高成交2380.7339亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 7.15 | 涨停9只，市场占比14.06，排名13 |

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

## 候选 7：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：198.11
- **触发类型**：double_red、capacity_industry、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.7431%，边际量 14.166%，成交额 1235.1435 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.7431%，边际量14.166%，成交1235.1435亿 |
| new_high_direction | 58.11 | 新高股26只，新高成交648.7670999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 14.0 | day10排名第1，区间涨幅19.77% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB | 20 |
| 1.6T交换机PCB | 5 |
| AI PCB | 5 |
| AIPCB专用油墨 | 5 |
| AI服务器PCB | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东山精密 | 002384 | PCB | 全球电子电路（软板+硬板+软硬结合板）平台型制造商，高多层PCB/高阶H... | core | L2 | 21 |
| 沪电股份 | 002463 | PCB | 受益标的 | core | L2 | 21 |
| 天承科技 | 688603 | PCB | 受益于AI算力驱动的高多层板/HDI/封装基板需求 | core | L2 | 21 |
| 本川智能 | 300964 | PCB | 中高端PCB定制化制造商，以通信设备为核心，布局汽车电子、新能源、AI服... | core | L2 | 21 |
| 胜宏科技 | 300476 | PCB | 高密度印制线路板制造商 | core | L2 | 21 |
| 三孚新科 | 688359 | PCB | 高端PCB电镀专用化学品与电镀设备供应商 | related | L2 | 21 |
| 超颖电子 | 603175 | PCB | 汽车电子PCB供应商，布局高多层服务器板、汽车板、存储板等高阶PCB产能 | related | L1_L3_candidate | 21 |
| 容大感光 | 300576 | AIPCB专用油墨 | PCB光刻胶/高端油墨核心验证标的 | core | L1_L3_candidate | 20 |

## 候选 8：百度概念

- **标准概念**：百度概念
- **申万一级**：传媒
- **评分**：193.61
- **触发类型**：double_red、limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.4399%，边际量 36.8055%，成交额 1449.3876 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.4399%，边际量36.8055%，成交1449.3876亿 |
| new_high_direction | 46.46 | 新高股44只，新高成交516.6362亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |
| limit_heat | 7.15 | 涨停9只，市场占比14.06，排名14 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 9：半导体

- **标准概念**：半导体
- **申万一级**：电子
- **评分**：192.08
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.4499%，边际量 18.1463%，成交额 3229.0323 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.4499%，边际量18.1463%，成交3229.0323亿 |
| new_high_direction | 66.08 | 新高股70只，新高成交1286.7468亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 10：汽车芯片

- **标准概念**：汽车芯片
- **申万一级**：电子
- **评分**：185.61
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.6067%，边际量 11.8297%，成交额 1546.3403 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.6067%，边际量11.8297%，成交1546.3403亿 |
| new_high_direction | 59.61 | 新高股47只，新高成交768.6365000000001亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 汽车芯片 | 20 |
| 芯片 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 四维图新 | 002405 | 汽车芯片 | 车规级芯片自研，舱驾融合芯片AC8025AE | core | L2 | 20 |
| 聚辰股份 | 688123 | 汽车芯片 | DDR5 SPD芯片、VPD芯片、EEPROM（车规&工业） | related | L1_L3_candidate | 20 |
| 银河微电 | 688689 | 汽车芯片 | 车规级半导体分立器件、SiC、GaN第三代半导体 | related | L1_L3_candidate | 20 |
| 国芯科技 | 688262 | 汽车芯片 | 汽车电子芯片(域控MCU)国产替代厂商，RISC-V车规MCU与量子安全... | related | L1_L3_candidate | 20 |
| 气派科技 | 688216 | 汽车芯片 | 集成电路封装测试、功率器件封装测试、晶圆测试 | related | L1_L3_candidate | 20 |
| 利尔达 | 920249 | 芯片 | IC增值分销商，为客户提供芯片及一站式配套服务 | core | L2 | 20 |
| 复旦微电 | 688385 | 芯片 | 超大规模集成电路设计企业，产品线覆盖FPGA、安全与识别、非挥发存储器和... | core | L2 | 20 |
| 探路者 | 300005 | 芯片 | 集成电路业务覆盖触控IC、指纹识别芯片、图像及视频处理IP | related | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-0980359ba7192e5cf2f0 artifact_sha=af484ef0e5b59493aa4597392755ec16cf05ba580f16f823790fa371c0557d0d manifest_sha=7bcf02e5a2b9755b7a7d9d62c68cf8dc6715ac07558c4b382c75a8d8ab9f7eef -->
