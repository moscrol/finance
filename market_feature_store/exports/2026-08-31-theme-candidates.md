# 2026-08-31 市场触发候选简报

> 说明：本简报由本地 market_feature_store 与知识库 relations JSON 只读生成；不调用大模型，不包含买卖指令。

## 一、市场上下文

- **市场阶段**：下跌阶段
- **成交额**：21305.63
- **上涨家数**：3181
- **涨停 / 跌停**：88 / 11
- **容量前三行业**：1.电子(25.2%, super_capacity)、2.机械设备(7.7%, normal)、3.电力设备(7.4%, normal)

## 二、核心候选 Deep（Top 10）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | AIGC概念 | AIGC | - | 169.68 | double_red、limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 2 | 抖音概念 | 抖音概念 | - | 169.62 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 3 | 腾讯概念 | 腾讯概念 | - | 168.57 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 4 | 阿里概念 | 阿里概念 | - | 167.46 | double_red、limit_heat、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 5 | 智能家居 | 智能家居 | - | 166.38 | double_red、limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 1 | - |
| 6 | 中特估 | 中特估 | - | 160.07 | double_red、new_high_direction、new_high_cluster | 1 | 0 | 1 | missing_entity_exposures |
| 7 | 车联网 | 车联网 | - | 158.9 | double_red、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 8 | 百度概念 | 百度概念 | - | 158.65 | double_red、new_high_direction、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 9 | 短剧游戏 | 游戏 | 传媒 | 153.4 | double_red、limit_heat、multi_period_rank、new_high_cluster | 2 | 12 | 0 | missing_evidence |
| 10 | 算力租赁 | 算力租赁 | 计算机 | 140.0 | double_red、limit_advance_cluster、new_high_cluster | 2 | 12 | 5 | - |

## 三、观察候选 Watch（Top 11-30）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | 传媒 | 传媒 | 传媒 | 132.5 | double_red、limit_heat、multi_period_rank、new_high_cluster | 3 | 12 | 0 | missing_evidence |
| 12 | 人工智能 | 人工智能 | 计算机 | 128.4 | double_red、limit_heat、new_high_cluster | 3 | 12 | 1 | - |
| 13 | 机器视觉 | 机器视觉 | 机械设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 14 | 虚拟电厂 | 虚拟电厂 | 电力设备 | 126.0 | double_red、capacity_industry、new_high_cluster | 1 | 12 | 1 | - |
| 15 | 农业 | 农业 | 基础化工 | 125.0 | limit_advance_cluster | 5 | 12 | 1 | - |
| 16 | IP经济 | IP经济 | 传媒 | 124.55 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 17 | AI智能体 | AI智能体 | 计算机 | 124.2 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 18 | 虚拟现实 | 虚拟现实 | - | 123.85 | double_red、limit_heat、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 19 | 跨境电商 | 跨境电商 | - | 123.5 | double_red、limit_heat、new_high_cluster | 2 | 12 | 1 | - |
| 20 | 数据要素 | 数据要素 | 计算机 | 123.15 | double_red、limit_heat、new_high_cluster | 1 | 12 | 1 | - |
| 21 | ChatGPT概念 | ChatGPT概念 | 计算机 | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 22 | 元宇宙概念 | 元宇宙 | - | 116.0 | double_red、new_high_cluster | 1 | 2 | 0 | missing_evidence |
| 23 | 养老概念 | 养老概念 | - | 116.0 | double_red、new_high_cluster | 0 | 0 | 0 | missing_concept、missing_entity_exposures、missing_evidence |
| 24 | 多模态AI | 多模态AI | 计算机 | 116.0 | double_red、new_high_cluster | 1 | 3 | 1 | - |
| 25 | 大飞机 | 大飞机 | 国防军工 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 26 | 操作系统 | 操作系统 | 计算机 | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 27 | 智能交通 | 智能交通 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |
| 28 | 智能医疗 | 医疗 | - | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 29 | 网络游戏 | 游戏 | 传媒 | 116.0 | double_red、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 30 | 边缘计算 | 边缘计算 | - | 116.0 | double_red、new_high_cluster | 2 | 12 | 1 | - |

## 四、长尾候选 Long Tail（Top 31-50）

| 排名 | 题材 | 标准概念 | 申万一级 | 评分 | 触发 | 概念 | 公司暴露 | 证据 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | 雄安新区 | 雄安新区 | - | 116.0 | double_red、new_high_cluster | 0 | 2 | 0 | missing_concept、missing_evidence |
| 32 | 房地产 | 房地产 | 计算机 | 115.0 | limit_advance_cluster、new_high_cluster | 2 | 12 | 1 | - |
| 33 | 化工 | 化工 | 基础化工 | 96.3 | limit_advance_cluster、new_high_direction、new_high_cluster | 5 | 12 | 2 | - |
| 34 | 液冷服务器 | 液冷服务器 | 电力设备 | 91.5 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 2 | - |
| 35 | 涤纶 | 涤纶 | - | 90.8 | multi_period_rank、new_high_cluster | 4 | 12 | 2 | - |
| 36 | 影视制作 | 影视 | - | 90.4 | multi_period_rank、new_high_cluster | 1 | 12 | 0 | missing_evidence |
| 37 | 电子 | EDA（电子设计自动化） | 电子 | 89.66 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 0 | missing_evidence |
| 38 | 机械设备 | 机械设备 | 机械设备 | 88.41 | limit_heat、new_high_direction、new_high_cluster、capacity_industry | 0 | 12 | 0 | missing_concept、missing_evidence |
| 39 | 新能源车 | 新能源车 | - | 87.54 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 40 | 数据中心 | 数据中心 | 计算机 | 84.79 | limit_heat、new_high_direction、new_high_cluster | 5 | 12 | 1 | - |
| 41 | 商业航天 | 商业航天 | 国防军工 | 82.8 | limit_heat、new_high_direction、new_high_cluster | 2 | 12 | 5 | - |
| 42 | 东数西算 | 东数西算 | - | 82.75 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 2 | - |
| 43 | 一带一路 | 一带一路 | - | 81.82 | limit_heat、new_high_direction、new_high_cluster | 1 | 12 | 1 | - |
| 44 | 氢能源 | 氢能源 | 电力设备 | 80.56 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 1 | - |
| 45 | 人形机器人 | 人形机器人 | 机械设备 | 79.88 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 5 | - |
| 46 | 高端装备 | 高端装备 | 机械设备 | 79.64 | new_high_direction、new_high_cluster、capacity_industry | 3 | 12 | 0 | missing_evidence |
| 47 | 风电 | 风电 | 电力设备 | 79.15 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 4 | - |
| 48 | AI眼镜 | AI眼镜 | 电子 | 78.78 | new_high_direction、new_high_cluster、capacity_industry | 2 | 12 | 2 | - |
| 49 | 燃料电池 | 燃料电池 | 电力设备 | 78.78 | new_high_direction、new_high_cluster、capacity_industry | 5 | 12 | 3 | - |
| 50 | 乡村振兴 | 乡村振兴 | - | 78.12 | limit_heat、new_high_direction、new_high_cluster | 0 | 4 | 0 | missing_concept、missing_evidence |

## 五、核心候选明细

## 候选 1：AIGC概念

- **标准概念**：AIGC
- **申万一级**：-
- **评分**：169.68
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 3.21%，边际量 34.19%，成交额 1610.38 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅3.21%，边际量34.19%，成交1610.38亿 |
| new_high_direction | 43.73 | 新高股44只，新高成交298.29亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 9.95 | 涨停17只，市场占比19.32，排名5 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| AIGC | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 中文在线 | 300364 | AIGC | AI内容生产平台（逍遥大模型支持14种语言创作，自研全栈创作引擎Flar... | core | L2 | 20 |
| 峨眉山A | 000888 | AIGC | 峨眉山A年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 捷成股份 | 300182 | AIGC | 捷成股份年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 数码视讯 | 300079 | AIGC | AI+超高清视频、AIGC、AI Agent、数据安全 | core | L2 | 20 |
| 昆仑万维 | 300418 | AIGC | 昆仑万维年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 芒果超媒 | 300413 | AIGC | 芒果超媒年报披露的AIGC相关主营业务 | core | L2 | 20 |
| 万事利 | 301066 | AIGC | 丝绸行业首个垂类图形AIGC大模型应用方 | related | L2 | 20 |
| 元隆雅图 | 002878 | AIGC | IP文创业务、特许商品业务、体育IP开发 | related | L1_L3_candidate | 20 |

## 候选 2：抖音概念

- **标准概念**：抖音概念
- **申万一级**：-
- **评分**：169.62
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.74%，边际量 17.98%，成交额 1925.69 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.74%，边际量17.98%，成交1925.69亿 |
| new_high_direction | 44.72 | 新高股40只，新高成交377.2900000000001亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 8.9 | 涨停14只，市场占比15.91，排名9 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 3：腾讯概念

- **标准概念**：腾讯概念
- **申万一级**：-
- **评分**：168.57
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.39%，边际量 20.02%，成交额 2078.47 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.39%，边际量20.02%，成交2078.47亿 |
| new_high_direction | 44.72 | 新高股42只，新高成交377.86000000000007亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.85 | 涨停11只，市场占比12.5，排名19 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 4：阿里概念

- **标准概念**：阿里概念
- **申万一级**：-
- **评分**：167.46
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.22%，边际量 11.45%，成交额 2496.56 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.22%，边际量11.45%，成交2496.56亿 |
| new_high_direction | 43.96 | 新高股37只，新高成交317.11999999999995亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比11.36，排名24 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 5：智能家居

- **标准概念**：智能家居
- **申万一级**：-
- **评分**：166.38
- **触发类型**：double_red、limit_heat、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.18%，边际量 17.5%，成交额 1168.35 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.18%，边际量17.5%，成交1168.35亿 |
| new_high_direction | 42.88 | 新高股67只，新高成交230.26000000000002亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_heat | 7.5 | 涨停10只，市场占比11.36，排名25 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 智能家居 | 20 |
| 家居 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 嘉益股份 | 301004 | 家居 | 不锈钢器皿相关产品/服务商 | core | L2 | 20 |
| 欧派家居 | 603833 | 家居 | 定制家居龙头（橱柜/衣柜/卫浴/木门） | core | L2 | 20 |
| 皮阿诺 | 002853 | 家居 | 中高端定制家居品牌：整体橱柜、全屋定制及门墙三大核心品类，柔性化规模定制... | core | L2 | 20 |
| 美之高 | 920765 | 家居 | 金属收纳置物架ODM/OEM厂商（家用类为主、工业类为辅），主要客户为日... | core | L2 | 20 |
| 美克家居 | 600337 | 家居 | 多品牌家居零售+国际批发商：直营品牌美克美家（连续十三年入选中国500最... | core | L2 | 20 |
| 顶固集创 | 300749 | 家居 | 定制衣柜及配套家居相关产品/服务商 | core | L2 | 20 |
| 茶花股份 | 603615 | 家居 | 塑料制品、非塑料制品相关产品/服务商 | related | L2 | 20 |
| 创源股份 | 300703 | 家居 | 家居相关产品/服务商 | related | L2 | 20 |

## 候选 6：中特估

- **标准概念**：中特估
- **申万一级**：-
- **评分**：160.07
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 0.07%，边际量 27.08%，成交额 991.58 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=否（0），evidence=是（1）
- **缺口标记**：missing_entity_exposures

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅0.07%，边际量27.08%，成交991.58亿 |
| new_high_direction | 44.07 | 新高股28只，新高成交325.84000000000003亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 中特估 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 7：车联网

- **标准概念**：车联网
- **申万一级**：-
- **评分**：158.9
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 1.52%，边际量 14.45%，成交额 1232.89 亿，容量前三=否
- **知识库状态**：concept=是（1），exposure=是（12），evidence=是（1）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅1.52%，边际量14.45%，成交1232.89亿 |
| new_high_direction | 42.9 | 新高股34只，新高成交232.23999999999998亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 车联网 | 20 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 万马科技 | 300698 | 车联网 | 车联网连接平台及服务与工具链：2025年车联网业务收入同比+49.33%... | core | L2 | 20 |
| 移为通信 | 300590 | 车联网 | 车载信息智能终端与视频车联网产品（集成ADAS/DMS/BSD）供应商，... | core | L2 | 20 |
| 东软集团 | 600718 | 车联网 | 车联网软件与标准制定参与者（参与国家首部V2X应用层标准制定） | related | L2 | 20 |
| 兴民智通 | 002355 | 车联网 | 车载信息化硬件与车联网系统解决方案及运营服务提供商 | related | L2 | 20 |
| 创远信科 | 920961 | 车联网 | C-V2X、汽车电子车联网通信测试业务提供商 | related | L2 | 20 |
| 映翰通 | 688080 | 车联网 | 商用车车载网关与车载AI（ADAS/DMS）方案供应商（欧洲公交、北美商... | related | L2 | 20 |
| 有方科技 | 688159 | 车联网 | 车载通信模组与车联网终端供应商（车规级模组、智能座舱模组、OBD整机、应... | related | L2 | 20 |
| 宜通世纪 | 300310 | 车联网 | 通信网络工程服务、通信网络维护服务、通信网络优化服务 | related | L2 | 20 |

## 候选 8：百度概念

- **标准概念**：百度概念
- **申万一级**：-
- **评分**：158.65
- **触发类型**：double_red、new_high_direction、new_high_cluster
- **盘面信号**：涨幅 2.25%，边际量 18.8%，成交额 1359.36 亿，容量前三=否
- **知识库状态**：concept=否（0），exposure=否（0），evidence=否（0）
- **缺口标记**：missing_concept、missing_entity_exposures、missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.25%，边际量18.8%，成交1359.36亿 |
| new_high_direction | 42.65 | 新高股30只，新高成交211.87999999999997亿，容量前三=False |
| new_high_cluster | 26.0 | 题材内新高股10只 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| - | - |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |

## 候选 9：短剧游戏

- **标准概念**：游戏
- **申万一级**：传媒
- **评分**：153.4
- **触发类型**：double_red、limit_heat、multi_period_rank、new_high_cluster
- **盘面信号**：涨幅 4.99%，边际量 76.1%，成交额 567.25 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=否（0）
- **缺口标记**：missing_evidence

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅4.99%，边际量76.1%，成交567.25亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| multi_period_rank | 16.6 | daily排名第4，区间涨幅4.99% |
| multi_period_rank | 12.6 | day5排名第9，区间涨幅8.21% |
| limit_heat | 8.2 | 涨停12只，市场占比13.64，排名17 |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 游戏 | 10 |
| 短剧 | 10 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 世纪华通 | 002602 | 游戏 | 游戏出海龙头：点点互动《Whiteout Survival》《Kings... | core | L2 | 20 |
| 冰川网络 | 300533 | 游戏 | 网络游戏充值收、移动游戏充值收相关产品/服务商 | core | L2 | 20 |
| 凯撒文化 | 002425 | 游戏 | 移动端网络游戏研发与运营商（子公司酷牛互动、天上友嘉），以联合运营模式为... | core | L2 | 20 |
| 华立科技 | 301011 | 游戏 | 商用游戏游艺设备设计、研发、生产、销售及运营商 | core | L2 | 20 |
| 吉比特 | 603444 | 游戏 | 游戏收入相关产品/服务商 | core | L2 | 20 |
| 名臣健康 | 002919 | 游戏 | 游戏研发+发行商（海南星炫/星际奥游/杭州雷焰，SLG/MMORPG/二... | core | L2 | 20 |
| 姚记科技 | 002605 | 游戏 | 休闲益智类精品手游研运一体（捕鱼系列等） | core | L2 | 20 |
| 完美世界 | 002624 | 游戏 | 自研引擎端手游全平台研发发行（诛仙/幻塔/异环等） | core | L2 | 20 |

## 候选 10：算力租赁

- **标准概念**：算力租赁
- **申万一级**：计算机
- **评分**：140.0
- **触发类型**：double_red、limit_advance_cluster、new_high_cluster
- **盘面信号**：涨幅 2.24%，边际量 17.67%，成交额 1407.76 亿，容量前三=否
- **知识库状态**：concept=是（2），exposure=是（12），evidence=是（5）
- **缺口标记**：-

**评分明细**

| 信号 | 加分 | 原因 |
| --- | --- | --- |
| double_red | 90.0 | 涨幅2.24%，边际量17.67%，成交1407.76亿 |
| new_high_cluster | 26.0 | 题材内新高股10只 |
| limit_advance_cluster | 24.0 | 连板股1只，最高2板，容量前三=False |

**匹配概念**

| 概念 | 分数 |
| --- | --- |
| 算力租赁 | 20 |
| 算力 | 12 |

**候选公司暴露**

| 公司 | 代码 | 概念 | 角色/摘要 | 强度 | 证据层 | 分数 |
| --- | --- | --- | --- | --- | --- | --- |
| 云天励飞 | 688343 | 算力 | 智算集群与AI训练推理算力服务商 | core | L2 | 20 |
| 华胜天成 | 600410 | 算力 | 以服务AI智能算力需求为代表的新基建服务商 | core | L2 | 20 |
| 曙光数创 | 872808 | 算力 | AI算力中心散热基础设施供应商 | core | L2 | 20 |
| 深南电路 | 002916 | 算力 | AI服务器/交换机高多层PCB核心供应商 | core | L2 | 20 |
| 直真科技 | 003007 | 算力 | 算力服务收入1.14亿元（新增），战略布局智算中心建设与运营服务 | core | L2 | 20 |
| 软通动力 | 301236 | 算力 | 计算产品与智能电子+智算服务，软硬一体 | core | L2 | 20 |
| 云赛智联 | 600602 | 算力 | 上海算力建设及城市大脑运营主力军 | core | L1 | 20 |
| 中电港 | 001287 | 算力 | AI处理器/GPU等算力芯片分销与方案服务商 | related | L2 | 20 |


<!-- fidelity_contract=fidelity-contract-1.2 run_id=theme-candidates-a6c8dcb1628a84a707b3 artifact_sha=82a93250985ce485f4046c411f9b50e3a619f3c65e389ab4a62551a32bc5abd7 manifest_sha=4bd652d9b599854b11ca63ef3b74e8f6c0731128d8b1fdb1a44131869d2f6fa3 -->
