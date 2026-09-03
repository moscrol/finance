# 设计：本轮主动检查（漏检闸）

日期：2026-08-22
状态：已落地 P0（问答 + 复盘两条消费面）；前瞻/出卡、DuckDB 自动 HIT/MISS 未做
权威来源：2026-08-19 判读方法 / 判断倾向分层；`docs/superpowers/specs/2026-08-19-user-framework-perspective-bootstrap-design.md` §1.2
实现：`intelligence/services/proactive_checks.py`

## 0. 一句话结论

用户要的「主动服务」是**读盘漏检闸**，不是默认 SPT 口吻。正在下冰点 / 新主线 / 主升这类结论时，把该核的结构条件列为强制检查（HIT / MISS / INSUFFICIENT）。不把 `sptfei.json` 打进中立，不翻 `perspective_mode` 默认值。

把 SPT 升格成主视角是另一步：复盘数据本来就是按他的读法采的，漏检闸是过渡——先让中立答案按他的结构条件自检，口吻与倾向仍要显式选视角。

## 1. 为什么不直接默认 SPT

08-19 红线仍有效：**读法可默认，倾向必须显式**。

| 层 | 是什么 | 默认 |
|---|---|---|
| `reading_baseline` | 怎么读数 | 开 |
| `proactive_checks` | 本轮该核的几条结构条件 | 被触发才出现 |
| `perspective_lab` / `sptfei.json` | 怎么下注 + 口吻 + BM25 原文 | 关（`neutral`） |

中立 `perspective_mode` 被测试锁成「不选则逐字节不变」。偷偷改成默认 SPT，会移动全部基线读数，而且把判断倾向伪装成领域方法。升格主视角要单独开窗：A/B、live、与 #222 共存验证。

## 2. 与判读基线正交

- 开关：`FINANCE_PROACTIVE_CHECKS`（0/false/no/off 整块关），与 `FINANCE_READING_BASELINE` 独立。
- 第一批 4 条来自 SPT 2026.34，**剥数字**，不进 `reading_baseline.py`。
- P0 **不算**确定性 HIT/MISS（缺 DuckDB 谓词）；只做触发 + 证据齐备性（调用方声明了 `present_kinds` 且缺 kinds → INSUFFICIENT）。模型必须逐条填结果。

## 3. 触发

`question_type ∈ {market_forecast, dated_market_review, market_watch, market_review}` **或** 查询含 主线 / 冰点 / 复盘 / 怎么看 等。

- 阶段题：跑 4 条全集。
- 其它题：按 `trigger_terms` 子集；被总触发词点到但没有点名具体条时，回退全集。
- 个股 / 产业链事实题不触发。

## 4. 四条（P0）

| id | 须核 | 所需证据 kinds |
|---|---|---|
| SPT-P12 冰点共振 | 单指数冰点不得升格为全市场冰点 | `index_breadth` |
| SPT-P13 断代日抢资金 | 临突破或部分放量不足以确认新主线 | `volume_structure`, `sector_flow` |
| SPT-P14 旗型一体两面 | 单次高潮不得升格为连续主升 | `volume_structure`, `index_level` |
| SPT-P15 伴身分轨 | 未临突破的底部强度不得断言新主线 | `sector_structure` |

## 5. 注入面（P0 已接）

漏检闸必须送到**模型真正写答案的那份 prompt**，不能只改配置。先例：2026-08-14 视角、2026-08 知识库模块——「配置生效、正文没看到」。

| 面 | 入口 | 形态 |
|---|---|---|
| ask 合成 | `ask_synthesis._prepare_answer_spec_synthesis` → `llm_refine.build_synthesis_messages` | system 段，基线之后、经验卡片之前 |
| continuous episode | `episode_protocol.build_episode_input` | payload 键 `proactive_checks` + `_rule`，不触发则键不出现 |
| CLI / ask 复盘专线 | `ask._market_review_system_content` | 复盘 system 常量后现拼；常量本身不变 |
| 工作台 daily-review | `workbench_skills/daily_review.py` `output_contract` | market_watch 不走 ask 合成，必须挂在契约上 |

未接（明确下一期）：

- 前瞻 / 复盘异步出卡
- `ask.prepare_existing_answer` 旧合成回退、`llm_refine.synthesize()` 裸调用
- grounded composer 专线（与视角同一类历史坑，若 live 发现复盘正文仍无漏检再补）

## 6. 非目标

- 不翻 `perspective_mode` 默认、不把 SPT 设成主视角。
- 不把 4 条升格进 `reading_baseline.py`。
- 不在本模块用未回测数字阈值自动买卖判断。
- 不冒充 SPT 口吻；注入标签必须含「漏检闸 / 不是 KOL 观点」。

## 7. 升格主视角时要单独做的事

用户判断：复盘数据最好的消费视角是 SPT。那一步不是把漏检闸写进中立，而是：

1. 产品：工作台默认 `perspective_mode=single` + `sptfei`，或「主框架」差分声明继承 SPT。
2. 评估：中立 vs SPT 默认的 A/B；现有「neutral 逐字节不变」测试要改契约，不能偷偷绿。
3. 数据：G1b `open_times` 等缺口仍阻塞部分 SPT-A 规则（见 reading-rules 分支交接）。
4. 够格升格的检查（本批 P12–P15）再考虑搬进 `reading_baseline` 或块级规则。
