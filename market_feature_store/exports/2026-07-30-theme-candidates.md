# 2026-07-30 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：底部横盘阶段
- **成交额**：23425.75
- **上涨家数**：1768
- **涨停 / 跌停**：52 / 74
- **容量前三行业**：1.电子(28.7%, super_capacity)、2.通信(8.6%, normal)、3.电力设备(7.2%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 食品饮料 | 食品饮料 | - | 225.38 | double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 2 | 中特估 | 中特估 | - | 162.84 | double_red、new_high_direction、new_high_cluster | 3 | 0 | 1 | missing_entity_exposures |
| 3 | 跨境支付CIPS | IP | - | 161.14 | double_red、new_high_direction、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 4 | 白酒 | 白酒 | 食品饮料 | 135.79 | multi_period_rank、new_high_direction、new_high_cluster | 2 | 12 | 2 | - |
| 5 | 银行 | 银行 | 银行 | 125.26 | multi_period_rank、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 6 | 股权 | 私募股权投资 | 基础化工 | 113.0 | limit_advance_cluster | 5 | 12 | 0 | missing_evidence |
| 7 | 汽车整车 | 汽车整车 | - | 93.2 | multi_period_rank、new_high_cluster | 5 | 9 | 0 | missing_evidence |
| 8 | 大消费 | 消费 | - | 93.0 | limit_advance_cluster | 1 | 12 | 0 | missing_evidence |
| 9 | 摩托车 | Robotaxi | - | 86.8 | multi_period_rank、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 10 | 燃料电池 | 燃料电池 | 电力设备 | 82.86 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 3 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 新能源车 | 新能源车 | - | 79.93 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 12 | 锂电池 | 锂电池 | 电力设备 | 79.1 | limit_advance_cluster、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 5 | - |
| 13 | 氢能源 | 氢能源 | 电力设备 | 78.8 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 1 | - |
| 14 | 一带一路 | 一带一路 | - | 78.53 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 15 | 风电 | 风电 | 电力设备 | 78.28 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 16 | 新零售 | 零售 | - | 77.25 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 17 | 锂电池概念 | 锂 | - | 77.01 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 18 | 电力设备 | 电力设备 | - | 76.8 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 19 | 数据中心 | 数据中心 | 计算机 | 75.09 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 20 | 乡村振兴 | 基建 | - | 75.07 | limit_heat、new_high_direction、new_high_cluster | 3 | 4 | 0 | missing_evidence |
| 21 | 粤港澳 | 东数西算 | - | 74.74 | limit_heat、new_high_direction、new_high_cluster | 5 | 9 | 0 | missing_evidence |
| 22 | 化工 | 化工 | - | 74.41 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 23 | 绿色电力 | 绿色电力 | - | 74.41 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 24 | 汽车 | 新能源汽车 | - | 74.33 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 25 | 信创 | 信创 | 计算机 | 73.58 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 26 | 计算机 | 计算机外设 | - | 73.57 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 27 | 充电桩 | 充电桩 | - | 73.24 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 28 | 海峡西岸 | 海峡西岸 | - | 70.22 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 29 | 白酒概念 | 白酒 | - | 69.54 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 30 | 物联网 | 物联网 | - | 69.32 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 工业互联 | 工业互联网 | - | 69.17 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 32 | 特斯拉概念 | 特斯拉概念 | - | 69.1 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 33 | 数据要素 | 数据要素 | 计算机 | 69.09 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 34 | 阿里概念 | 阿里概念 | - | 69.0 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 35 | 跨境电商 | 跨境电商 | - | 68.91 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 36 | AIGC概念 | AIGC | - | 68.8 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 37 | 区块链 | 区块链 | - | 68.42 | new_high_direction、new_high_cluster | 5 | 6 | 1 | - |
| 38 | 腾讯概念 | 腾讯概念 | - | 68.35 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 39 | 无人驾驶 | 无人驾驶 | 汽车 | 68.33 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | IP经济 | IP经济 | 传媒 | 68.2 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 智能家居 | 智能家居 | - | 68.08 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 42 | 智能电网 | 智能电网 | - | 67.96 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 43 | 国产软件 | 软件 | - | 67.93 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 44 | 软件服务 | 软件 | - | 67.93 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 45 | 大数据 | 大数据 | - | 67.92 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 46 | 华为鸿蒙 | 华为鸿蒙 | - | 67.85 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 47 | 智能医疗 | 医疗 | - | 67.81 | new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 48 | 互联金融 | 互联金融 | - | 67.76 | new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 49 | 高端装备 | 高端装备 | - | 67.68 | new_high_direction、new_high_cluster | 5 | 12 | 0 | missing_evidence |
| 50 | 预制菜 | 预制菜 | - | 67.66 | new_high_direction、new_high_cluster | 5 | 12 | 1 | - |

## 五、核心候选明细

## 候选 1：食品饮料

- **标准概念**：食品饮料
- **申万一级**：-
- **评分**：225.38
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.48%，边际量 23.14%，成交额 575.71 亿，容量前三=否
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.48%，边际量23.14%，成交575.71亿 |
| new_high_direction | 46.03 | 新高股78只，新高成交482.2700000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 20.8 | day3排名第5，区间涨幅6.2% |
| multi_period_rank | 19.2 | daily排名第7，区间涨幅2.48% |
| multi_period_rank | 17.6 | day5排名第9，区间涨幅5.39% |
| limit_heat | 5.75 | 涨停5只，市场占比9.62，排名16 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 食品饮料 | 20 |
| 食品 | 10 |
| 饮料 | 10 |
| 食品饮料设备 | 5 |
| 乳制品深加工 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 天邦食品 | 002124 | 食品 | 养殖-屠宰-加工-深加工全产业链猪肉食品业务 | core | L2 | 20 |
| 天马科技 | 603668 | 食品 | 烤鳗等食品业务，活鳗具备出口日韩等资质 | related | L2 | 20 |
| 龙大美食 | 002726 | 食品 | 食品相关产品/材料供应商 | related | L2 | 20 |
| 中炬高新 | 600872 | 食品饮料 | 食品饮料行业调味品企业 | core | L1 | 20 |
| 五芳斋 | 603237 | 食品饮料 | 粽子第一品牌（中华老字号，食品+餐饮协同） | core | L2 | 20 |
| 养元饮品 | 603156 | 食品饮料 | 植物蛋白饮料+功能性饮料双品类（2025年销售植物蛋白饮料47.90万吨... | related | L2 | 20 |
| 品渥食品 | 300892 | 食品饮料 | 全球优质食品资源整合商（乳制品/酒饮/粮油） | core | L2 | 20 |
| 均瑶健康 | 605388 | 食品饮料 | 常温乳酸菌饮品（味动力）+益生菌食品双品类企业，另有商品供应链业务 | core | L2 | 20 |

## 候选 2：中特估

- **标准概念**：中特估
- **申万一级**：-
- **评分**：162.84
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.07%，边际量 10.09%，成交额 1250.46 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=否（0），evidence=是（1）
- **缺口标记**：missing_entity_exposures

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.07%，边际量10.09%，成交1250.46亿 |
| new_high_direction | 46.84 | 新高股51只，新高成交547.2199999999999亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中特估 | 20 |
| 国企改革 | 2 |
| 央国企改革 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 3：跨境支付CIPS

- **标准概念**：IP
- **申万一级**：-
- **评分**：161.14
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.73%，边际量 23.21%，成交额 538.18 亿，容量前三=否
- **知识库状态**：concept=是（3），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.73%，边际量23.21%，成交538.18亿 |
| new_high_direction | 45.14 | 新高股31只，新高成交410.94999999999993亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| IP | 10 |
| 跨境支付 | 10 |
| 东数西算 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中文在线 | 300364 | IP | IP相关产品/材料供应商 | related | L2 | 20 |
| 奥飞娱乐 | 002292 | IP | IP相关产品/材料供应商 | related | L2 | 20 |
| 实丰文化 | 002862 | IP | 光伏营收0.29亿元/占比6.92%/同比+200.14% | related | L2 | 20 |
| 先进数通 | 300541 | 跨境支付 | IT基础设施建设（算力服务器/数据中心）、软件解决方案（Starring... | related | L1_L3_candidate | 20 |
| 信雅达 | 600571 | 跨境支付 | SWIFT全球合作伙伴（ISO 20022报文迁移服务） | related | L2 | 20 |
| 四方精创 | 300468 | 跨境支付 | 软件开发及维护供应商/运营商 | related | L2 | 20 |
| 天阳科技 | 300872 | 跨境支付 | 跨境支付 | related | L1_L3_candidate | 20 |
| 广电运通 | 002152 | 跨境支付 | 跨境支付 | related | L1_L3_candidate | 20 |

## 候选 4：白酒

- **标准概念**：白酒
- **申万一级**：食品饮料
- **评分**：135.79
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（2）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 43.39 | 新高股18只，新高成交270.95000000000005亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 24.0 | daily排名第1，区间涨幅3.52% |
| multi_period_rank | 22.4 | day3排名第3，区间涨幅6.36% |
| multi_period_rank | 20.0 | day5排名第6，区间涨幅5.74% |

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

## 候选 5：银行

- **标准概念**：银行
- **申万一级**：银行
- **评分**：125.26
- **触发类型**：multi_period_rank、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 45.66 | 新高股40只，新高成交452.48999999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 20.0 | daily排名第6，区间涨幅2.53% |
| multi_period_rank | 16.8 | day10排名第10，区间涨幅8.6% |
| multi_period_rank | 16.8 | day5排名第10，区间涨幅5.24% |

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

## 候选 6：股权

- **标准概念**：私募股权投资
- **申万一级**：基础化工
- **评分**：113.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 113.0 | 连板股2只，最高8板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 私募股权投资 | 5 |
| IC载板 | 2 |
| PI薄膜 | 2 |
| 交换机 | 2 |
| 低空经济 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 四川双马 | 000935 | 私募股权投资 | 私募股权投资基金管理业务 | related | L2 | 20 |
| 中国动力 | 600482 | AIDC发电设备 | 船用柴油机、燃气轮机、后市场维保 | related | L1_L3_candidate | 1 |
| 上峰水泥 | 000672 | IC载板 | 跨界投资/IC载板 | related | L3_candidate | 1 |
| 万丰奥威 | 002085 | 低空经济 | 通用飞机制造业务（收购钻石飞机55%股权起步），形成汽车轻量化+通航飞机... | core | L2 | 1 |
| 万通发展 | 600246 | 低轨卫星 | PCIe高速交换芯片、毫米波射频芯片、AI算力运营 | related | L1_L3_candidate | 1 |
| 中晶科技 | 003026 | 功率半导体 | 半导体功率芯片及器件制造商（广泛应用于微波炉、激光打印机、X光机、高压电... | core | L2 | 1 |
| 中牧股份 | 600195 | 原料药 | 化药原料药及制剂 | related | L1_L3_candidate | 1 |
| 东方国信 | 300166 | 大模型 | AI大模型（幕僚智数/图灵系列） | related | L1_L3_candidate | 1 |

## 候选 7：汽车整车

- **标准概念**：汽车整车
- **申万一级**：-
- **评分**：93.2
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（9），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 23.2 | day3排名第2，区间涨幅6.95% |
| multi_period_rank | 22.4 | daily排名第3，区间涨幅3.05% |
| multi_period_rank | 21.6 | day5排名第4，区间涨幅6.08% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 汽车整车 | 20 |
| 新能源汽车 | 2 |
| 新能源汽车产业链 | 2 |
| 智能装备 | 2 |
| 汽车物流 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 众泰汽车 | 000980 | 汽车整车 | 整车业务复工复产阶段（现阶段收入主要来自汽车配件和门业） | core | L2 | 20 |
| 扬杰科技 | 300373 | AI服务器电源 | AI服务器电源器件 | related | L1_L3_candidate | 1 |
| 溯联股份 | 301397 | 新能源汽车 | 汽车用塑料流体管路总成供应商，广布新能源产业链客户 | core | L2 | 1 |
| 联测科技 | 688113 | 新能源汽车产业链 | 为新能源汽车整车、动力总成及零部件厂商提供测试装备与测试验证服务，测试验... | related | L2 | 1 |
| 比亚迪 | 002594 | 无人驾驶 | 新能源汽车整车厂商与智能驾驶车型应用方 | peripheral | L1 | 1 |
| 天奇股份 | 002009 | 智能装备 | 汽车整车制造装备（总装/涂装生产系统）及智能仓储物流装备 | core | L2 | 1 |
| 三羊马 | 001317 | 汽车物流 | 汽车整车综合物流服务商：商品车物流+在用车物流，行业内较早通过多式联运从... | core | L2 | 1 |
| 光庭信息 | 301221 | 汽车电子 | 汽车电子相关产品/材料供应商 | related | L2 | 1 |

## 候选 8：大消费

- **标准概念**：消费
- **申万一级**：-
- **评分**：93.0
- **触发类型**：limit_advance_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| limit_advance_cluster | 93.0 | 连板股2只，最高3板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 消费 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中体产业 | 600158 | 消费 | 体育赛事运营与场馆经营受益名单 | peripheral | graph_only | 20 |
| 华夏航空 | 002928 | 消费 | 支线航空运营商，地方政府采购+中央支线补贴商业模式，覆盖下沉市场 | related | L1_L3_candidate | 20 |
| 盈趣科技 | 002925 | 消费 | 电子烟（创新消费电子）、健康环境产品、汽车电子、智能控制部件 | core | L1_L3_candidate | 20 |
| 立华股份 | 300761 | 消费 | 图谱弱关联 | peripheral | graph_only | 20 |
| 酒鬼酒 | 000799 | 消费 | 深度联动胖东来联合开发「酒鬼酒・自由爱」新品成为核心增长引擎，启动光瓶湘... | related | L2 | 20 |
| 锦江酒店 | 600754 | 消费 | 连锁酒店集团，受益休闲需求与RevPAR修复 | peripheral | graph_only | 20 |
| 首旅酒店 | 600258 | 消费 | 连锁酒店集团，受益休闲需求与RevPAR修复 | peripheral | graph_only | 20 |
| 一致魔芋 | 920273 | 健康消费 | 魔芋粉、魔芋食品（茶饮小料、休闲素食、魔芋食材） | core | L1_L3_candidate | 5 |

## 候选 9：摩托车

- **标准概念**：Robotaxi
- **申万一级**：-
- **评分**：86.8
- **触发类型**：multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_cluster | 26.0 | 题材内新高股7只 |
| multi_period_rank | 23.2 | day5排名第2，区间涨幅8.8% |
| multi_period_rank | 19.2 | day3排名第7，区间涨幅5.31% |
| multi_period_rank | 18.4 | daily排名第8，区间涨幅2.14% |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| Robotaxi | 2 |
| 两轮车 | 2 |
| 数据中心液冷 | 2 |
| 新能源汽车零部件 | 2 |
| 汽车轻量化 | 2 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 宗申动力 | 001696 | AIDC发电设备 | 通用机械、摩托车发动机、航空动力 | related | L1_L3_candidate | 1 |
| 千里科技 | 601777 | Robotaxi | 汽车与摩托车零部件企业，转型AI+车/Robotaxi闭环平台 | related | L1_L3_candidate | 1 |
| 亚太股份 | 002284 | 两轮车 | 两轮车ABS | related | L1_L3_candidate | 1 |
| 今飞凯达 | 002863 | 快充技术 | 铝合金车轮（汽车、摩托车、电动车） | related | L1_L3_candidate | 1 |
| 双环传动 | 002472 | 新能源汽车零部件 | 齿轮传动龙头：新能源汽车电驱齿轮核心供应商，覆盖乘用车/商用车/工程机械... | core | L2 | 1 |
| 万通智控 | 300643 | 汽车电子 | TPMS传感器前装+售后双市场：前装配套上汽、北汽、长安、五菱等主机厂，... | core | L2 | 1 |
| 万丰奥威 | 002085 | 汽车轻量化 | 以铝合金-镁合金为主线的汽车金属部件轻量化业务（含汽车/摩托车轮毂、镁合... | core | L2 | 1 |
| 新坐标 | 603040 | 汽车零部件 | 冷精密成形工艺的发动机配气机构零部件供应商，客户覆盖大众全球/比亚迪/潍... | core | L2 | 1 |

## 候选 10：燃料电池

- **标准概念**：燃料电池
- **申万一级**：电力设备
- **评分**：82.86
- **触发类型**：limit_heat、new_high_direction、new_high_cluster、capacity_industry
- **盘面信号**：涨幅 -%，边际量 -%，成交额 - 亿，容量前三=-
- **知识库状态**：concept=是（5），exposure=是（12），evidence=是（3）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| new_high_direction | 51.81 | 新高股36只，新高成交144.77亿，容量前三=True |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 5.05 | 涨停3只，市场占比5.77，排名30 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 燃料电池 | 20 |
| SOFC燃料电池 | 5 |
| SOFC（固体氧化物燃料电池） | 5 |
| 固体氧化物燃料电池(SOFC) | 5 |
| 氢燃料电池 | 5 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 三环集团 | 300408 | SOFC燃料电池 | MLCC（片式多层陶瓷电容器）、光通信陶瓷组件（光纤插芯、MT插芯、陶瓷... | core | L1_L3_candidate | 20 |
| 东方锆业 | 002167 | SOFC燃料电池 | SOFC电解质材料潜在供应商 | related | L1 | 20 |
| 冰轮环境 | 000811 | SOFC燃料电池 | 高功率平板式SOFC电堆、系统冷热电一体集成潜在参与商 | related | L1 | 20 |
| 春晖智控 | - | SOFC燃料电池 | BE 温度传感器核心供应商，份额 70%→90%+/单GW净利0.6e | core | L2 | 20 |
| 三花智控 | 002050 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国巨石 | 600176 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中国船舶 | 600150 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |
| 中材科技 | 002080 | SOFC（固体氧化物燃料电池） | 市场信号弱关联 | related | L2_candidate | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-23d695d329af079d946e artifact_sha=3a325deb96f4a055a493dfb08a69783ac9326c1ae65f51df12a5b1fbfe227656 manifest_sha=68d74258942f2c5f22097e9ec6682dd6fccb7fd3805af8ed6d076278b8b1e085 -->
