# opinion-cross 三维交叉与 Tier 判定

> 本文件由 `skills/opinion-cross/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

脚本 import `theme-radar/scripts/radar.py` 的 `signal_dimension_rows` 与 `resonance_tier`（import 失败时有同契约的本地回退），逐标的量三把尺子：

| 维度 | 取数 | 含义 |
|---|---|---|
| 公告/事实 | 该标的句子里的🟢硬证据 + 催化 | 题材是不是纯叙事？有没有订单/入股/合同/官方表态 |
| 产业趋势 | 标的在 KB 命中的 concept（含 chain_layer/role） | 这条观点能不能映射到知识库里的发酵/布局方向 |
| 市场热点 | 该标的句子里的盘面措辞（涨停/大跌/异动/估值切换） | 市场今天是否在交易它 |

- 三维都硬（≥2 维 Tier1/2）→ **Tier 1 三重共振 ⭐⭐⭐**
- 两维有效 → **Tier 2 双重验证 ⭐⭐**
- 单维 → **Tier 3 观察池 ⭐**

> 关键实现细节：radar 的 `signal_dimension_rows` 会把 `signal["industry_progress"]` 同时计入"公告/事实"和"产业趋势"两维。为避免产业信号污染事实维度（否则纯卖方喊单也会被抬成 Tier 2），本脚本**事实维度只放硬证据/催化，产业信号只走 `context`**，从而让硬证据标的与软推演标的真正分层。
