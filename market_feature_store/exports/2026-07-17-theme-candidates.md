# 2026-07-17 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：26547.43
- **上涨家数**：482
- **涨停 / 跌停**：33 / 193
- **容量前三行业**：1.电子(30.7%, super_capacity)、2.通信(8.6%, normal)、3.医药生物(7.3%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 电力 | 电力 | 公用事业 | 198.41 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 2 | 银行 | 银行 | 银行 | 178.27 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 3 | 连板未映射 | - | 计算机 | 149.0 | limit_advance_cluster | 0 | 0 | 0 | placeholder_market_theme |
| 4 | 公路铁路运输 | 铁路运输 | - | 124.4 | multi_period_rank、new_high_cluster | 1 | 6 | 0 | missing_evidence |
| 5 | 白酒 | 白酒 | 食品饮料 | 120.45 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 6 | 中药 | 中药 | 医药生物 | 112.13 | multi_period_rank、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 7 | 保险 | 低空经济 | - | 100.0 | multi_period_rank | 5 | 7 | 0 | missing_evidence |
| 8 | 维生素 | 维生素 | 基础化工 | 92.41 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 10 | 0 | missing_evidence |
| 9 | 港口航运 | 港口航运 | - | 85.2 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 10 | 创新药 | 创新药 | 医药生物 | 83.35 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 医疗器械 | 医疗器械 | 医药生物 | 77.27 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 2 | - |
| 12 | 合成生物 | 合成生物 | 医药生物 | 77.06 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 13 | 数据中心 | 数据中心 | 计算机 | 74.07 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 14 | 无人驾驶 | 无人驾驶 | 汽车 | 72.71 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 数据要素 | 数据要素 | 计算机 | 72.4 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 16 | IP经济(谷子经济) | 谷子经济 | 传媒 | 72.23 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 17 | 氢能源 | 氢能源 | 电力设备 | 72.21 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 18 | 三胎 | 三胎 | 社会服务 | 67.84 | new_high_direction、new_high_cluster | 0 | 1 | 0 | missing_concept、missing_evidence |
| 19 | 宠物经济 | 宠物经济 | 社会服务 | 67.19 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 20 | AIGC | AIGC | 传媒 | 67.02 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 21 | 云计算 | 云计算 | 计算机 | 63.59 | new_high_direction、new_high_cluster | 5 | 12 | 3 | - |
| 22 | 信创 | 信创 | 计算机 | 63.35 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 23 | 医药商业 | 医药商业 | - | 63.2 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 24 | 算力租赁 | 算力租赁 | 计算机 | 62.47 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 5 | - |
| 25 | 空气能热泵 | 空气能热泵 | 家用电器 | 56.34 | new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 26 | 供销社 | 供销社 | - | 54.4 | multi_period_rank | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 27 | 厨卫电器 | 厨卫电器 | - | 51.2 | multi_period_rank、new_high_cluster | 1 | 1 | 0 | missing_evidence |
| 28 | 钠离子电池 | 钠离子电池 | 电力设备 | 48.12 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 29 | 液冷服务器 | 液冷服务器 | 电力设备 | 44.91 | new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 30 | 盐湖提锂 | 盐湖提锂 | 有色金属 | 44.74 | new_high_direction、new_high_cluster | 5 | 9 | 2 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 医疗服务 | 医疗服务 | - | 34.4 | multi_period_rank、new_high_cluster | 5 | 12 | 1 | - |
| 32 | 油气开采及服务 | 油气 | - | 34.0 | multi_period_rank | 2 | 12 | 0 | missing_evidence |
| 33 | 旅游及酒店 | 旅游 | - | 33.6 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 34 | 人工智能 | 人工智能 | - | 33.5 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 35 | 影视院线 | 影视院线 | - | 33.2 | multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 36 | 储能 | 储能 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 37 | 风电 | 风电 | - | 32.45 | limit_heat、new_high_cluster | 5 | 12 | 4 | - |
| 38 | 光伏 | 光伏 | - | 31.75 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 39 | AI应用 | AI应用 | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 40 | DeepSeek | DeepSeek | - | 31.4 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 41 | 军工 | 军工 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 商业航天 | 商业航天 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 5 | - |
| 43 | 机器人 | 机器人 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 44 | 芯片 | 芯片 | - | 31.05 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 45 | 虚拟电厂 | 虚拟电厂 | - | 31.05 | limit_heat、new_high_cluster | 3 | 12 | 1 | - |
| 46 | AI智能体 | AI智能体 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 1 | - |
| 47 | AI眼镜 | AI眼镜 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 2 | - |
| 48 | 低空经济 | 低空经济 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 3 | - |
| 49 | 建筑装饰 | 建筑装饰 | - | 30.7 | limit_heat、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 50 | 服装家纺 | 家纺 | - | 30.7 | limit_heat、new_high_cluster | 2 | 7 | 0 | missing_evidence |

## 五、核心候选明细

## 候选 1：电力

- **标准概念**：电力
- **申万一级**：公用事业
- **评分**：198.41
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.25%，边际量 59.86%，成交额 607.09 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.25%，边际量59.86%，成交607.09亿 |
| new_high_direction | 39.31 | 新高股14只，新高成交137.05999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 19.0 | daily排名第1，区间涨幅1.25% |
| multi_period_rank | 16.6 | day3排名第4，区间涨幅1.35% |
| limit_heat | 7.5 | 涨停10只，市场占比28.57142857142857，排名1 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 电力 | 20 |
| 数据中心电力设备 | 5 |
| 新型电力系统 | 5 |
| 新能源电力 | 5 |
| 新能源电力系统与能源技术革命 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中恒电气 | 002364 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 四方股份 | 601126 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 科士达 | 002518 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 金盘科技 | 688676 | 数据中心电力设备 | 数据中心电力设备受益名单企业 | peripheral | graph_only | 20 |
| 中国西电 | 601179 | 新型电力系统 | 全产业链 | core | - | 20 |
| 中国能建 | 601868 | 新型电力系统 | 算电协同/三电协同 | core | - | 20 |
| 卧龙电驱 | 600580 | 新型电力系统 | 机器人组件及系统应用、数据中心HVAC电机、电动航空电推进系统 | related | L1_L3_candidate | 20 |
| 国电南瑞 | 600406 | 新型电力系统 | 算电协同/三电协同 | core | - | 20 |

## 候选 2：银行

- **标准概念**：银行
- **申万一级**：银行
- **评分**：178.27
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 42.67 | 新高股23只，新高成交213.55999999999997亿，容量前三=False |
| multi_period_rank | 29.0 | day10排名第1，区间涨幅5.95% |
| multi_period_rank | 28.2 | daily排名第2，区间涨幅0.4% |
| multi_period_rank | 27.4 | day5排名第3，区间涨幅3.76% |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.0 | day3排名第6，区间涨幅1.1% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 银行 | 20 |
| 银行IT | 5 |
| AI应用 | 2 |
| 供应链金融 | 2 |
| 信创 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 兴业银行 | 601166 | 银行 | 全国性股份制商业银行，以银行为主体的现代综合金融服务集团（2007年上交... | core | L2 | 20 |
| 北京银行 | 601169 | 银行 | 银行相关产品/材料供应商 | related | L2 | 20 |
| 南京银行 | 601009 | 银行 | 城商行——公司金融、零售金融、金融市场三大板块 | core | L2 | 20 |
| 宁波银行 | 002142 | 银行 | 优质城商行 | core | L2 | 20 |
| 紫金银行 | 601860 | 银行 | 总部位于江苏南京的地方法人农村商业银行，主营存贷款、票据贴现等传统银行业... | core | L2 | 20 |
| 西安银行 | 600928 | 银行 | 深耕陕西本土的城商行，业务含公司金融、零售金融、普惠金融，推进“数智西银... | core | L2 | 20 |
| 齐鲁银行 | 601665 | 银行 | 银行相关产品/材料供应商 | related | L2 | 20 |
| 天阳科技 | 300872 | 银行IT | 银行信贷/信用卡等核心系统IT服务商 | core | L2 | 20 |

## 候选 3：连板未映射

- **标准概念**：-
- **申万一级**：计算机
- **评分**：149.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：placeholder_market_theme

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 149.0 | 连板股8只，最高5板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 4：公路铁路运输

- **标准概念**：铁路运输
- **申万一级**：-
- **评分**：124.4
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（6），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 25.8 | daily排名第5，区间涨幅-0.58% |
| multi_period_rank | 25.8 | day10排名第5，区间涨幅2.12% |
| multi_period_rank | 25.0 | day5排名第6，区间涨幅2.22% |
| multi_period_rank | 21.8 | day3排名第10，区间涨幅0.65% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 铁路运输 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 西部创业 | 000557 | 铁路运输 | 宁东能源化工基地区域铁路运营商，铁路运营里程315公里、总延展长度642... | core | L2 | 20 |
| 淮河能源 | 600575 | 光伏 | 火力发电、煤炭开采与销售、铁路运输、配煤贸易 | related | L1_L3_candidate | 1 |
| 中国中车 | 601766 | 央企改革 | 国务院国资委控股轨道交通制造核心央企 | peripheral | graph_only | 1 |
| 伊泰B股 | 900948 | 煤炭 | 动力煤生产运输销售一体化大型能源企业（10座煤矿+3条自营铁路） | core | L2 | 1 |
| 大秦铁路 | 601006 | 煤炭 | 铁路货运（以煤炭运输为主） | related | L1_L3_candidate | 1 |
| 昊华能源 | 601101 | 煤炭 | 动力煤生产销售、甲醇（煤化工）、铁路运输、煤炭物流 | core | L1_L3_candidate | 1 |

## 候选 5：白酒

- **标准概念**：白酒
- **申万一级**：食品饮料
- **评分**：120.45
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 30.45 | 新高股8只，新高成交99.94000000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股8只 |
| multi_period_rank | 24.0 | day3排名第1，区间涨幅3.55% |
| multi_period_rank | 20.8 | day5排名第5，区间涨幅2.71% |
| multi_period_rank | 19.2 | day10排名第7，区间涨幅1.42% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 白酒 | 20 |
| 节能装备 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 五粮液 | 000858 | 白酒 | 千元价格带龙头 | core | - | 20 |
| 今世缘 | 603369 | 白酒 | 江苏区域酒 | peripheral | - | 20 |
| 伊力特 | 600197 | 白酒 | 新疆区域白酒龙头（中国白酒工业百强企业） | core | L2 | 20 |
| 口子窖 | 603589 | 白酒 | 安徽区域白酒 | peripheral | - | 20 |
| 古井贡酒 | 000596 | 白酒 | 安徽区域名酒龙头 | related | - | 20 |
| 天佑德酒 | 002646 | 白酒 | 青稞白酒龙头（天佑德/互助/永庆和/八大作坊/世义德品牌） | core | L2 | 20 |
| 山西汾酒 | 600809 | 白酒 | 清香白酒全国化龙头 | core | - | 20 |
| 水井坊 | 600779 | 白酒 | 高端浓香型白酒，高档产品（第一坊/水井坊系列）占酒业收入约94% | core | L2 | 20 |

## 候选 6：中药

- **标准概念**：中药
- **申万一级**：医药生物
- **评分**：112.13
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.33 | 新高股26只，新高成交106.31亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 18.2 | day5排名第2，区间涨幅3.87% |
| multi_period_rank | 16.6 | day10排名第4，区间涨幅2.78% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中药 | 20 |
| 中药材 | 5 |
| 创新中药 | 5 |
| 中成药 | 2 |
| 兽药 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一心堂 | 002727 | 中药 | 延伸中药全产业链相关业务 | related | L2 | 20 |
| 万邦德 | 002082 | 中药 | 现代中药+化学原料药/制剂完整产业链，覆盖心脑血管、神经、呼吸、消化、精... | core | L2 | 20 |
| 三力制药 | 603439 | 中药 | 苗药/中成药制造商：开喉剑喷雾剂（儿童型）为核心大单品，另有芪胶升白胶囊... | core | L2 | 20 |
| 上海凯宝 | 300039 | 中药 | 现代中药企业：痰热清注射液为独家品种，92个药品纳入国家医保目录 | core | L2 | 20 |
| 千金药业 | 600479 | 中药 | 口服妇科炎症中成药领域领先品牌，'千金'为国家驰名商标，妇科千金片（胶囊... | core | L2 | 20 |
| 太极集团 | 600129 | 中药 | 西成药相关产品供应商 | related | L2 | 20 |
| 康芝药业 | 300086 | 中药 | 儿童药研发生产销售、中成药、母婴健康用品 | related | L1_L3_candidate | 20 |
| 新里程 | 002219 | 中药 | 以中国驰名商标"独一味"为核心的中成药制造，2025年医药行业收入4.0... | related | L2 | 20 |

## 候选 7：保险

- **标准概念**：低空经济
- **申万一级**：-
- **评分**：100.0
- **触发类型**：multi_period_rank
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（7），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| multi_period_rank | 26.6 | day5排名第4，区间涨幅2.72% |
| multi_period_rank | 25.0 | daily排名第6，区间涨幅-0.63% |
| multi_period_rank | 25.0 | day10排名第6，区间涨幅1.82% |
| multi_period_rank | 23.4 | day3排名第8，区间涨幅0.91% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 低空经济 | 2 |
| 新能源汽车零部件 | 2 |
| 智能交通与低空空天基础设施 | 2 |
| 汽车后市场 | 2 |
| 金融IT | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中科软 | 603927 | AI应用 | 保险等行业AI技术应用方与整合方（记录型软件向约束型软件转型） | related | L2 | 1 |
| 亿航智能 | - | 低空经济 | 运营端 | core | - | 1 |
| 友升股份 | 603418 | 新能源汽车零部件 | 产品主要应用于新能源汽车领域（门槛梁/电池托盘/保险杠/副车架等） | core | L2 | 1 |
| 中信海直 | 000099 | 智能交通与低空空天基础设施 | 运营端 | core | - | 1 |
| 世纪恒通 | 301428 | 汽车后市场 | 综合性车主服务生态：为保险公司、银行、运营商、高速集团提供车主服务解决方... | core | L2 | 1 |
| 凌云股份 | 600480 | 汽车零部件 | 车身结构件（热成型/辊压/门环）、保险杠、管路系统等金属+非金属零部件供... | core | L2 | 1 |
| 新致软件 | 688590 | 金融IT | 面向银行、保险金融机构的软件服务商，布局金融知识语料库等AI技术 | core | L2 | 1 |

## 候选 8：维生素

- **标准概念**：维生素
- **申万一级**：基础化工
- **评分**：92.41
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（10），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 41.21 | 新高股19只，新高成交97.03亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 13.4 | day5排名第8，区间涨幅1.53% |
| multi_period_rank | 11.8 | day10排名第10，区间涨幅0.33% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 维生素 | 20 |
| 动物疫苗 | 2 |
| 化学制药 | 2 |
| 原料药 | 2 |
| 精细化工 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 亿帆医药 | 002019 | 维生素 | 维生素B5（泛酸钙）及原B5全球主要供应商 | core | L2 | 20 |
| 兄弟科技 | 002562 | 维生素 | 全球知名维生素生产商（维生素K3/B1/B3/B5产业平台） | core | L2 | 20 |
| 圣达生物 | 603079 | 维生素 | 全球生物素、叶酸主要供应商 | core | L2 | 20 |
| 天新药业 | 603235 | 维生素 | 维生素相关产品/材料供应商 | related | L2 | 20 |
| 中牧股份 | 600195 | 动物疫苗 | 重大动物疫病疫苗国家队（口蹄疫、高致病性禽流感定点生产企业） | core | L2 | 1 |
| 卫信康 | 603676 | 化学制药 | 化学药品制剂及原料药企业（复合维生素类、微量元素类、电解质类领域竞争力较... | core | L2 | 1 |
| 誉衡药业 | 002437 | 化学制药 | 哈尔滨药企，产品覆盖心脑血管、骨骼肌肉、维生素、电解质、抗肿瘤等领域，代... | core | L2 | 1 |
| 振华股份 | 603067 | 化工 | 铬化学品相关产品供应商 | related | L2 | 1 |

## 候选 9：港口航运

- **标准概念**：港口航运
- **申万一级**：-
- **评分**：85.2
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 22.4 | daily排名第3，区间涨幅-0.4% |
| multi_period_rank | 19.2 | day5排名第7，区间涨幅1.7% |
| multi_period_rank | 17.6 | day10排名第9，区间涨幅0.51% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 港口航运 | 20 |
| 航运 | 12 |
| 港口 | 10 |
| 5G智慧港口 | 2 |
| 集运 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天津港 | 600717 | 港口 | 商品储存相关产品供应商 | related | L2 | 20 |
| 盐田港 | 000088 | 港口 | 立足盐田港的港口开发运营商，控股经营惠州荃湾煤炭港、深汕小漠港、黄石新港... | core | L2 | 20 |
| 上港集团 | 600018 | 港口航运 | 全球最大集装箱枢纽港核心运营商 | core | L1 | 20 |
| 中信海直 | 000099 | 港口航运 | 低空经济、海上石油服务、港口引航 | related | L1_L3_candidate | 20 |
| 中国船舶 | 600150 | 港口航运 | 全球最大、技术领先的集装箱、散货、油船等核心海运装备建造龙头 | core | L1 | 20 |
| 中船防务 | 600685 | 港口航运 | 中游制造 | peripheral | L1 | 20 |
| 中远海控 | 601919 | 港口航运 | 全球第三大、中国第一大集装箱班轮运输及码头投资运营商 | core | L1 | 20 |
| 中远海能 | 600026 | 港口航运 | 全球第一大油轮船队和中国最大的LNG海上运输服务商 | core | L1 | 20 |

## 候选 10：创新药

- **标准概念**：创新药
- **申万一级**：医药生物
- **评分**：83.35
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 52.65 | 新高股46只，新高成交211.70999999999998亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 4.7 | 涨停2只，市场占比5.714285714285714，排名26 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 创新药 | 20 |
| 创新药RWA | 5 |
| AI辅助生殖 | 2 |
| CDMO | 2 |
| CRO | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 一品红 | 300723 | 创新药 | 核心创新药AR882为高效选择性URAT1抑制剂，覆盖降尿酸治疗痛风、溶... | core | L2 | 20 |
| 一心堂 | 002727 | 创新药 | 院外零售渠道潜在相关 | peripheral | L1 | 20 |
| 三元基因 | 920344 | 创新药 | 布局重组全人胶原蛋白系列原料与组织工程材料，延伸消费医学、类器官等高增长... | related | L2 | 20 |
| 三生制药 | 01530.HK | 创新药 | 双抗BD出海标杆 | related | - | 20 |
| 上海医药 | 601607 | 创新药 | 医药流通渠道潜在相关 | peripheral | L1 | 20 |
| 上海谊众 | 688091 | 创新药 | 抗肿瘤创新药企业：紫杉醇胶束等纳米制剂，研产销一体化 | core | L2 | 20 |
| 东富龙 | 300171 | 创新药 | 创新药生产装备潜在供应商 | related | L1 | 20 |
| 丽珠集团 | 000513 | 创新药 | - | related | L1 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-76a44286f3a3bf8f4c61 artifact_sha=a0a37b83cddd0eb5d5f779157e97662385955c913bd67ceb47810be43a612b72 manifest_sha=a24033471369705af620d642c1422a891c20b95023d813f835fa1f04b00f5837 -->
