# Disclosure Archive 证据分层与分类规则

> 本文件由 `skills/disclosure-archive/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

## 资料优先级

| 优先级 | 来源 | 对应 evidence_layer |
|--------|------|---------------------|
| P0 | 上市公司公告、年报/半年报/季报、招股书、募集说明书、交易所问询回复、监管披露 | L2 |
| P1 | 公司官网产品页、公司官网新闻、投资者关系活动记录表 | L2（官网产品页）/ L3（投关记录） |
| P2 | 互动易 / 上证 e 互动问答、官方公众号 | L3 |
| P3 | 权威媒体或交易所转发信息 | L4 |
| P4 | 普通新闻、行业媒体、转载内容 | L4 / reject |

## 证据分层规则

| 层级 | 来源 | 说明 |
|------|------|------|
| L1 | 已有知识库 raw 研报、外部研究报告线索 | 行业翻译/研报分析，不能单独作为公司级事实 |
| L2 | 公司公告、年报、半年报、招股书、募集说明书、交易所问询回复、公司官网正式产品页 | 最高置信度公司一手来源 |
| L3 | 互动易、上证 e 互动、投资者关系活动记录、调研纪要 | 可信但需审核，不直接等同于公告 |
| L4 | 媒体报道、行业网站、公众号、转载内容 | 弱信号，需交叉验证 |

## update_type 规则

| 类型 | 适用场景 | 证据层级下限 | 说明 |
|------|----------|-------------|------|
| `baseline` | 主营业务、主营产品、收入结构、毛利率、产能、产销量、客户行业、稳定产品能力 | L2 | 只能来自 L2 |
| `hard_delta` | 订单、合同、中标、认证、量产、投产、扩产、客户导入、明确供货、披露收入占比 | L2 | 只能来自 L2 |
| `review_candidate` | 互动易、调研纪要、官网新闻、投关记录中出现的公司级事实 | L3 | 可信但需审核 |
| `graph_only` | 只证明公司与概念有关，但不足以写入实体正文 | L1/L2/L3/L4 | 不限层级，重在"不足以写入正文" |
| `weak_signal` | 媒体/行业传闻/非官方概念关联 | L4 | 弱信号需交叉验证 |
| `reject` | 来源不明、无法核验、纯股价、纯概念、无公司级事实 | — | 不入库 |

**注意：** `source_type=other` 不得用于 `baseline`/`hard_delta`，因其来源不确定。

## fact_type 对照

| fact_type | 说明 | 典型 update_type |
|-----------|------|-----------------|
| `revenue_mix` | 收入结构/产品占比 | baseline |
| `capacity` | 产能/产线 | baseline / hard_delta |
| `shipment` | 产销量/出货量 | baseline / hard_delta |
| `product_launch` | 新产品/新方案发布 | hard_delta |
| `certification` | 认证/资质 | hard_delta |
| `customer_adoption` | 客户导入/明确供货 | hard_delta |
| `contract` | 合同/订单 | hard_delta |
| `tender_win` | 中标 | hard_delta |
| `mass_production` | 量产/投产 | hard_delta |
| `project_construction` | 扩产/项目建设 | hard_delta |
| `product_capability` | 产品能力/技术平台 | baseline |
| `official_claim` | 公司官方说法/互动易回复 | review_candidate |
| `media_signal` | 媒体报道 | weak_signal |

## fact_status 对照

| fact_status | 说明 | 示例 |
|-------------|------|------|
| `realized` | 已实现/已发生 | 产线已投产、产品已出货 |
| `disclosed` | 已披露但需验证 | 公告说了产能规划但还没投产 |
| `under_validation` | 待核验 | 互动易说"公司产品可用于XX"，但找不到实物证据 |
| `planned` | 规划中 | 拟投资XX项目、正在布局XX技术 |
| `framework` | 框架协议/意向合作 | 签了战略合作协议，无具体金额和交付 |
| `rumored` | 市场传闻 | 媒体报道"据悉公司已打入XX供应链" |
