# 2026-09-07 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：19451.91
- **上涨家数**：3167
- **涨停 / 跌停**：93 / 2
- **容量前三行业**：1.电子(26.4%, super_capacity)、2.通信(9.0%, normal)、3.机械设备(8.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 新零售 | 零售 | 传媒 | 199.1 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 2 | 电子 | EDA（电子设计自动化） | 电子 | 190.01 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | PCB | PCB | 电子 | 188.54 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 4 | 元器件 | 电子元器件 | 电子 | 188.44 | double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 5 | 乡村振兴 | 乡村振兴 | 农林牧渔 | 187.74 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |
| 6 | 人形机器人 | 人形机器人 | 机械设备 | 186.3 | double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster | 3 | 12 | 5 | - |
| 7 | CPO概念 | CPO | - | 185.2 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 8 | 高端装备 | 高端装备 | 机械设备 | 179.43 | double_red、capacity_industry、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 9 | 新型工业化 | 新型工业化 | 机械设备 | 177.44 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 10 | PCB概念 | PCB概念 | - | 174.84 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 数据中心 | 数据中心 | 计算机 | 172.51 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 一带一路 | 一带一路 | 电力设备 | 168.42 | limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 13 | 先进封装 | 先进封装 | 电子 | 167.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 5 | - |
| 14 | 东数西算 | 东数西算 | - | 167.15 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 15 | 汽车芯片 | 汽车芯片 | 电子 | 166.76 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 16 | 粤港澳 | 粤港澳 | - | 165.95 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 12 | 0 | missing_concept、missing_evidence |
| 17 | 腾讯概念 | 腾讯概念 | - | 165.48 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 18 | 通信设备 | 通信设备 | 通信 | 165.23 | double_red、capacity_industry、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 19 | 通信 | 通信 | 通信 | 165.2 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 20 | 光通信 | 光通信 | - | 160.55 | double_red、limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 21 | 半导体 | 半导体 | 电子 | 158.36 | double_red、capacity_industry、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 22 | 虚拟现实 | 虚拟现实 | - | 158.04 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 23 | 抖音概念 | 抖音概念 | - | 157.84 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | 阿里概念 | 阿里概念 | - | 157.64 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 25 | 传媒 | 传媒 | 传媒 | 157.59 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 26 | 汽车热管理 | 汽车热管理 | - | 157.23 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 27 | 网络游戏 | 游戏 | 传媒 | 156.7 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 28 | 苹果概念 | 苹果概念 | - | 155.65 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 29 | 液冷服务器 | 液冷服务器 | 电力设备 | 152.48 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 2 | - |
| 30 | 集成电路设计 | 集成电路 | 电子 | 147.95 | double_red、capacity_industry、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 芯片 | 芯片 | 电子 | 138.05 | double_red、capacity_industry、limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 32 | 智能穿戴 | 智能穿戴 | 电子 | 133.85 | double_red、capacity_industry、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 33 | 英伟达概念 | 英伟达 | - | 131.37 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 34 | MiniLED | Mini LED | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 2 | - |
| 35 | 存储芯片 | 存储芯片 | 电子 | 126.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 5 | - |
| 36 | 无人驾驶 | 无人驾驶 | 汽车 | 124.2 | double_red、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 37 | 毫米波雷达 | 毫米波雷达 | 汽车 | 124.2 | double_red、limit_heat、new_high_cluster | 4 | 12 | 1 | - |
| 38 | OLED概念 | LED | 电子 | 124.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 39 | 消费电子 | 消费电子 | 电子 | 124.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 5 | - |
| 40 | MicroLED | Micro LED | 电子 | 120.0 | double_red、capacity_industry、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 41 | AI手机PC | AI手机 | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 42 | 折叠屏 | 折叠屏 | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 4 | 12 | 1 | - |
| 43 | 玻璃基板 | 玻璃基板 | 电子 | 118.0 | double_red、capacity_industry、new_high_cluster | 2 | 12 | 5 | - |
| 44 | 云计算 | 云计算 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 3 | - |
| 45 | 小米概念 | 小米概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 46 | 汽车零部件 | 汽车零部件 | 汽车 | 116.0 | double_red、new_high_cluster | 3 | 12 | 1 | - |
| 47 | 特斯拉概念 | 特斯拉概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 48 | 算力租赁 | 算力租赁 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 5 | - |
| 49 | 高压快充 | 高压快充 | 电力设备 | 116.0 | double_red、new_high_cluster | 0 | 6 | 0 | missing_concept、missing_evidence |
| 50 | 第三代半导体 | 第三代半导体 | - | 114.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：新零售

- **标准概念**：零售
- **申万一级**：传媒
- **评分**：199.1
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 121.0 | 连板股4只，最高6板，容量前三=False |
| new_high_direction | 42.5 | 新高股60只，新高成交200.0329亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比17.2，排名10 |

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

## 候选 2：电子

- **标准概念**：EDA（电子设计自动化）
- **申万一级**：电子
- **评分**：190.01
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.8984%，边际量 32.6177%，成交额 5169.4637 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.8984%，边际量32.6177%，成交5169.4637亿 |
| new_high_direction | 53.71 | 新高股23只，新高成交297.0796亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 10.3 | 涨停18只，市场占比19.35，排名8 |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |

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

## 候选 3：PCB

- **标准概念**：PCB
- **申万一级**：电子
- **评分**：188.54
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 7.5355%，边际量 63.7722%，成交额 990.3795 亿，容量前三=是
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅7.5355%，边际量63.7722%，成交990.3795亿 |
| new_high_direction | 40.34 | 新高股8只，新高成交90.95389999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 14.0 | daily排名第1，区间涨幅7.54% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.2 | 涨停12只，市场占比12.9，排名17 |

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

## 候选 4：元器件

- **标准概念**：电子元器件
- **申万一级**：电子
- **评分**：188.44
- **触发类型**：double_red、capacity_industry、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 6.6741%，边际量 55.3394%，成交额 1222.863 亿，容量前三=是
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅6.6741%，边际量55.3394%，成交1222.863亿 |
| new_high_direction | 40.34 | 新高股8只，新高成交90.95389999999999亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 13.2 | daily排名第2，区间涨幅6.67% |
| capacity_industry | 10.0 | 所属申万一级 电子 位于容量前三 |
| limit_heat | 8.9 | 涨停14只，市场占比15.05，排名13 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电子元器件 | 5 |
| 电子元器件分销 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 华安鑫创 | 300928 | 电子元器件 | 通用器件分销相关产品/服务商 | core | L2 | 20 |
| 国力电子 | 688103 | 电子元器件 | 电子真空器件、直流接触器相关产品/服务商 | core | L2 | 20 |
| 利和兴 | 301013 | 电子元器件 | 向新型电子元器件领域拓展（孙公司利和兴电子），客户含摩尔线程、蓝思科技、... | related | L2 | 20 |
| 三友联众 | 300932 | 电子元器件 | 继电器相关产品供应商 | related | L2 | 20 |
| 灿勤科技 | 688182 | 电子元器件 | 高端先进电子陶瓷元器件相关产品供应商 | related | L2 | 20 |
| 中电港 | 001287 | 电子元器件分销 | 本土元器件分销商龙头（连续6年首位，近140条授权产品线） | core | L2 | 20 |
| 新亚制程 | 002388 | 电子元器件分销 | 电子信息产品销售服务为第一大业务，2025年收入13.45亿元（占比69... | core | L2 | 20 |
| 英唐智控 | 300131 | 电子元器件分销 | 电子元器件分销商，产品类型含被动元件、存储类、触控显示类、半导体类、模块... | core | L2 | 20 |

## 候选 5：乡村振兴

- **标准概念**：乡村振兴
- **申万一级**：农林牧渔
- **评分**：187.74
- **触发类型**：limit_heat、limit_advance_cluster、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=是（4），evidence=否（0）
- **缺口标记**：missing_concept、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 109.0 | 连板股4只，最高3板，容量前三=False |
| new_high_direction | 43.14 | 新高股53只，新高成交250.96590000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.6 | 涨停16只，市场占比17.2，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 神农集团 | 605296 | 农业 | 生猪养殖业务（核心）、屠宰及食品加工（协同） | related | L2 | 1 |
| 荃银高科 | 300087 | 农业 | 种子业务（水稻、玉米、小麦等） | related | L1_L3_candidate | 1 |
| 园林股份 | 605303 | 基建 | 市政园林工程施工承包（含EPCO/设计-施工总承包） | related | L2 | 1 |
| 维维股份 | 600300 | 粮食安全 | 国有上市公司定位，围绕粮食收储、加工、销售打造粮食产业平台，粮油仓储贸易... | related | L2 | 1 |

## 候选 6：人形机器人

- **标准概念**：人形机器人
- **申万一级**：机械设备
- **评分**：186.3
- **触发类型**：double_red、capacity_industry、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.8185%，边际量 21.5753%，成交额 2359.3389 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.8185%，边际量21.5753%，成交2359.3389亿 |
| new_high_direction | 51.4 | 新高股26只，新高成交112.25019999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |
| limit_heat | 8.9 | 涨停14只，市场占比15.05，排名12 |

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

## 候选 7：CPO概念

- **标准概念**：CPO
- **申万一级**：-
- **评分**：185.2
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 5.6832%，边际量 45.3176%，成交额 4096.0236 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅5.6832%，边际量45.3176%，成交4096.0236亿 |
| new_high_direction | 45.8 | 新高股20只，新高成交463.94640000000004亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 12.4 | daily排名第3，区间涨幅5.68% |
| limit_heat | 11.0 | 涨停20只，市场占比21.51，排名4 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| CPO | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 泰晶科技 | 603738 | CPO | 超高频差分晶振（光模块/AI算力） | core | L1_L3_candidate | 20 |
| 金信诺 | 300252 | CPO | 通信设备（信号互联产品） | core | L1_L3_candidate | 20 |
| 仕佳光子 | 688313 | CPO | MPO核心玩家/CW光源/CPO FAU，平台型光器件公司 | core | L1_L3_candidate | 20 |
| 天孚通信 | 300394 | CPO | 光模块无源器件/光引擎核心供应商 | core | L1_L3_candidate | 20 |
| 天通股份 | 600330 | CPO | 薄膜铌酸锂（TFLN）晶圆、压电晶体材料（铌酸锂/钽酸锂）、磁性材料（软... | core | L1_L3_candidate | 20 |
| 富信科技 | 688662 | CPO | 光模块温控 | core | L1_L3_candidate | 20 |
| 工业富联 | 601138 | CPO | CPO组装+AI服务器OEM | core | L3 | 20 |
| 环旭电子 | 601231 | CPO | SiP封装+光通信 | core | L3 | 20 |

## 候选 8：高端装备

- **标准概念**：高端装备
- **申万一级**：机械设备
- **评分**：179.43
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.2113%，边际量 17.325%，成交额 1528.5682 亿，容量前三=是
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.2113%，边际量17.325%，成交1528.5682亿 |
| new_high_direction | 53.43 | 新高股27只，新高成交274.45869999999996亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

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

## 候选 9：新型工业化

- **标准概念**：新型工业化
- **申万一级**：机械设备
- **评分**：177.44
- **触发类型**：double_red、capacity_industry、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.6692%，边际量 22.1985%，成交额 941.0996 亿，容量前三=是
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.6692%，边际量22.1985%，成交941.0996亿 |
| new_high_direction | 51.44 | 新高股16只，新高成交115.1015亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| capacity_industry | 10.0 | 所属申万一级 机械设备 位于容量前三 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 新型工业化 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 东土科技 | 300353 | 新型工业化 | 工业操作系统 / 工业软件-操作系统 / 半导体设备映射标的 | core | L2 | 20 |
| 中控技术 | 688777 | 新型工业化 | DCS（集散控制系统） / 工业AI大模型 / 工业软件-DCS/AI ... | core | L2 | 20 |
| 信捷电气 | 603416 | 新型工业化 | 运动控制/PLC / 工控-小型PLC / PLC（大中型）映射标的 | core | L2 | 20 |
| 华中数控 | 300161 | 新型工业化 | 数控系统 / 工业母机-数控系统映射标的 | core | L2 | 20 |
| 埃斯顿 | 002747 | 新型工业化 | 工业机器人整机 / 机器人-整机 / 新能源汽车映射标的 | core | L2 | 20 |
| 宝信软件 | 600845 | 新型工业化 | 钢铁信息化/PLC / 工业软件-钢铁信息化 / 钢铁行业AI赋能映射标... | core | L2 | 20 |
| 汇川技术 | 300124 | 新型工业化 | 通用自动化/伺服 / 工控-通用自动化 / 新能源汽车 / 人形机器人映... | core | L2 | 20 |
| 海天精工 | 601882 | 新型工业化 | 机床整机（主机厂） / 出口竞争力 / 工业母机-整机 / AI液冷精密... | core | L2 | 20 |

## 候选 10：PCB概念

- **标准概念**：PCB概念
- **申万一级**：-
- **评分**：174.84
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 4.2354%，边际量 27.7523%，成交额 2255.4035 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.2354%，边际量27.7523%，成交2255.4035亿 |
| new_high_direction | 40.59 | 新高股15只，新高成交127.41039999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 10.65 | 涨停19只，市场占比20.43，排名5 |
| multi_period_rank | 7.6 | daily排名第9，区间涨幅4.24% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| PCB概念 | 20 |
| PCB | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一博科技 | 301366 | PCB | PCB研发设计服务细分行业引领者，一站式硬件创新平台（设计+制板+PCB... | core | L2 | 20 |
| 万源通 | 920060 | PCB | 内资PCB企业第39位（CPCA 2024榜单），单/双/多层板+HDI... | core | L2 | 20 |
| 世运电路 | 603920 | PCB | 硬板营收49.19亿元/毛利率16.67%/同比+9.93% | core | L2 | 20 |
| 东山精密 | 002384 | PCB | 全球电子电路（软板+硬板+软硬结合板）平台型制造商，高多层PCB/高阶H... | core | L2 | 20 |
| 中京电子 | 002579 | PCB | PCB厂商：刚性板+柔性板，LED封装印制电路板具备省级研发平台 | core | L2 | 20 |
| 中富电路 | 300814 | PCB | 高可靠性定制化PCB制造商（通信及数据中心、工业控制、汽车电子等领域） | core | L2 | 20 |
| 依顿电子 | 603328 | PCB | 汽车电子、计算与通信、工控医疗、新能源及电源、多媒体与显示用PCB供应商 | core | L2 | 20 |
| 则成电子 | 920821 | PCB | 高精密线路板制造商（自研FIPIS细间距减除法，具备线宽/线距15μm/... | core | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-ba2d8cd5e5819baf4c2c artifact_sha=510d518075ff4f0908902005320c15725b3726fe6a8710525785f43577c3c650 manifest_sha=73e44ceb16daf0f6b7370d080a368eb119997055399259020a75c5913f0bc648 -->
