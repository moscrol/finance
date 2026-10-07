# 检查层地图与离线取证 — 2026-10-07

## 结论与适用版本

本页服务两条仍在途的目标：A 逐张合入、部署并验收；B 提高真实回答能力。
这里只完成 B 的行为定位，**不是新留出验收、候选方案上线或质量提升证明**。

受测运行时代码来自 review `cdaf54a6485a6d1ce1c4bc8b91e4a0a786b2e579`。
本轮核过 `conversation_orchestrator`、`continuous_turn_adapter`、`episode_semantic_verifier`、
`episode_verifier`、`research_harness`、`judge_mode` 六文件：与生产版本
`d5d7c5f6017e12ce5be9414abe31cf763c161f50` 无 Git 内容差异。
这不证明实际服务配置或自然模型选择了受测路径。#64/#66 的新核验器不借用本结果。

两个现有开关都不能组成“只标注、作者最多修一轮、语义层不删句”的候选：

- `ASK_SEMANTIC_JUDGE=off` 只关闭第二次模型判官，记录为 `deterministic`，确定性检查仍工作。
- `FINANCE_NUMERIC_CONDITION_MARK=1` 只改变部分无出处数字条件；日期、走势、财务及后续交付门仍可能删改。
- 语义核验器结束后还有正文消费者。只修改 `_repair()` 会漏掉实际落盘前的删句。

## 按实际消费顺序分层

“可比较”指实验候选可把质量处置改成反馈，不代表已经允许关闭。安全、授权、来源身份、
只读、预算、截止、取消与持久化围栏始终保留。路径均相对仓根，函数名优先于易漂移行号。

| 层 / 调用者 | 输入 → 输出及正文变化 | 模型与预算 | 候选边界 |
|---|---|---|---|
| 任务与工具准入：`research_harness`、Episode loop | 当前合同/授权/工具状态 → 已接纳观察、稿件；可拒绝非法提交 | 原研究预算与保存围栏 | 不消融；失败/空值不能伪造为事实 |
| 结构核验：`episode_verifier.verify_episode_outcome` | 合同、frame身份、输出绑定 → `VerifiedEpisodeOutcome`/缺口 | 本地检查 | 身份与权限保留；模板义务需另与用户义务区分，不能整层旁路 |
| 语义入口：`SemanticEpisodeVerifier.verify/_verify_inner` | 核对当前context、合同、hash、partial放行资格；失败可交缺口稿 | 不合格时不调用判官 | 保留身份与结构前置；partial不是“语义已经正确” |
| 确定性前检：`_numeric_condition_deletion_indexes` 等 | 数字/财务/星期/路径/证据日期 → 拒句索引及判决账 | 不用模型；off照常 | 内容判据可改反馈，伪来源/越权仍硬拒；须逐理由分类 |
| 第二模型判官及定向回检索 | 原稿/合法证据 → passed/rejected/unavailable；回检索受授权与剩余时间限制 | 显式llm才开启；不能免费增加修订预算 | 三臂先冻结同一判官配置，不同时调模型与处置方式 |
| 机械修复：`_repair` | 删句、修悬空回指、pending rewrites、恢复连坐观察、重算缺口，再结构复核 | 无作者模型调用 | “修复”不等于作者修稿；候选在此禁止语义删改，保留原稿和诊断 |
| 核验器公开出口 | `_sanitize_public_answer`、数字标注、材料公开复核、题设计算表准入 | 本地处理，可能改变正文或状态 | 安全净化/程序拥有表的完整性保留；内容标注与硬身份分开 |
| 作者修订：`continuous_turn_adapter.handle` → `_resume_for_gap` | 语义反馈、缺口、原稿/账本 → 新完整稿；重验新稿 | 原session、根deadline/预算、取消；quick/standard上限1，deep/max上限3，交付修订另有一次限制 | 候选要显式最多一轮且纳入总成本；不能把修订耗尽改成progress再开工具 |
| adapter发布投影 | `_safe_public_text`、引用投影、publication上限、日历披露、`recheck_material_public_delivery`、`_with_semantic_contract_gaps`、`_track_public_delivery` | 本地；可改正文/降级；`review_public_claim_scope`另记审查 | 完整追踪修改前后，不把状态completed当质量通过 |
| 编排器接收handled结果：`_complete_continuous_turn` | 再脱敏；有stance pack时`lint_public_answer`会删袋外价格句；加视角头/公开文字 | 无新作者修订机会 | 先验来源身份保留，价格内容删改须进入候选处置账 |
| 编排器晚期交付门：`outlook_delivery_gate.py` | forecast门删“已验证”等分句；market_watch门删未注册方法阈值；追加未核网格 | 不受上述两个开关控制 | 真正“不语义删句”必须覆盖这里；只在helper调用不能推断自然路由 |
| 最终交付：`public_delivery_gate.review_public_delivery` | 覆盖/体量/悬空指引 → 正文披露及状态；可去掉开头悬空指引 | 本地；不发模型 | 可保留诚实未完成状态，不能静默删结论；引用/正文/发布事件须同版本 |
| 持久化：消息、`answer.md`、report、私有Episode与终态事件 | 用户最终看到的正文及来源 | 共享原终态仲裁 | 真实评测以这里的全文为准，不拿较好的中间草稿替代 |

旧 `_sanitize_market_cause_answer_text` 在 legacy 两处分支，handled Episode 提前返回会绕过它；
这只排除了该旧过滤器，**不排除表中晚期交付门**。源码入口参见
[产品门](../agent-product-door.md)，原legacy探针见 `scripts/review_probes/market_cause_filter_review.py`。

## 同稿同证据的离线观察

脚本 `scripts/review_probes/answer_check_mode_review.py`：5 个已知合成案例 × 2 个判官开关 × 2 个
数字处置开关 = **20 条核验器观察**；另有 **20 条晚期门helper观察**，不混为40道质量题。
判官是注入的恒通过函数，无真实模型。只开放两个新建隔离SQLite用户库用于脚本化交付，DuckDB和其它
数据库路径拒绝；socket连接阻断并计数。所有目录保留，不覆盖前次输出。

`off + mark=1` 的代表读数（其它模式全文留原件）：

| 输入 | 实际公开结果 | 可断言的内容 |
|---|---|---|
| 若成交额跌破1800亿则量能失效。 | 保留并就地标“1800亿未在证据中找到出处” | 数字标注成立，修稿反馈为空 |
| 7月17日（周四），上证下跌约3.05%。 | 整句删除，`calendar_weekday`，1条反馈 | 合成材料日期为2026-07-17，实际是周五；本例不证明删句有净收益 |
| 同句改成周五 | 原文保留 | 正确星期对照 |
| 五日成交额“一路滑落”，材料中间两天上涨 | 整句删除，`path_trend`，1条反馈 | 确定性走势门在off照常工作 |
| 含合成内部hash的句子 | 不公开内部标识句 | 安全净化在四配置均保留；这不是语义消融对象 |
| forecast：“不能说已经验证了剧本。” | helper返回空串、dropped=1 | 否定限定被关键词门误删，不是仅拦断言 |
| 同句非forecast | 原文保留，applied=false | 题型对照 |
| market_watch：“按MA20观察趋势。” | 空网格删句；网格含MA20时保留 | helper有条件门；未声称正常Episode会接market_watch |

### 误删是否能到用户正文

再用脚本化Controller/Adapter投递同一合成forecast稿，实际运行 `TurnOrchestrator.run_turn`，
并读取真实隔离 `ConversationStore` 的最终消息：

- outlook门调用 **1**，legacy原因过滤器调用 **0**；
- “不能说已经验证了剧本。”在输入，**最终返回与落盘正文均已删除**；其余判断/边界保留；
- 返回/消息均completed，run留下 `outlook_delivery_gate` 降级记录；返回正文与落盘相同。

这是**真实编排消费者 + 脚本化上游**，不是HTTP会话端到端、真实模型自然路由或新的金融答卷。
尚未修复产品规则；先通知运行时owner，候选从本案例取得回归，但本题退出未来新留出分母。

### 原件与复现

私有证据根：`~/.finance-runtime/reviews/release-resume-20261007/`。

- `answer-check-modes-01/`：最初20条；`-02/`：加helper及前后源hash，均保留。
- `answer-check-modes-03/`：首次接真实store时被“禁止所有SQLite”的探针守卫拦截，未产出完整报告。
  这是探针隔离设定不适用于真实store，**不是产品失败**；改为仅允许两个新隔离路径，未放开生产库。
- `answer-check-modes-04/mode-results.json`：11:48:07 +08，20+20+1观察；网络/越界数据库尝试0，
  真实模型0；107次SQLite连接均在两份新隔离库。前后HEAD、状态与记录源hash一致，受测树当时有本会话未提交探针/测试。
- 开发定向 `answer-check-dev-v2-pytest.json`：生产解释器3.12.13、依赖指纹`e1c50cb821a30f00`，
  **106P/0F/0E，collected=106，dirty=true**。只供开发，不签提交身份；干净提交另验。
- 探针回归测试检查记录完整性、模式/调用数、原稿留存、隔离路径、真实消费者与不可覆盖，
  **不把否定句删除写成期望正确行为**，否则会用测试固化缺陷。

复现（输出选仓外新目录）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/answer_check_mode_review.py --output-dir <new-private-directory>
```

成功exit只表示取证完成。源码与测试本身进入版本控制；完整回答、用户库和运行收据留私有目录。

## 下一步与否决理由

| 选择 | 否决 | 原因 |
|---|---|---|
| 先列实际消费者，再实现单owner候选 | 用off或mark开关命名“无删句臂” | 本轮已直接证伪这种等价 |
| 原稿+诊断交作者修一轮，保留安全投影 | 整个verifier直接恒passed | 后者撤掉身份/权限，比较不再合法 |
| 原入口全文对照；先离线再真题 | 只看中间draft或离线投影评分 | 用户实际收到的文本还会改变 |
| #66 owner协调并保留D类失败 | 另开竞争核验器或给旧题改名 | 多owner交叠、留出污染会毁掉结论 |

正式新实验仍待题集、独立真值、身份、预算和授权冻结；候选尚未实现。
准备合同见 [新比较草案](2026-10-07-answer-check-comparison-draft.md)。
现有 `judge_loss_point_replay.py` 可定位结构首损，但语义只读历史存证；
`run_quality_ablation.py` 可复用盲评/噪声逻辑，其旧CLI入口不能代签Workbench实验。
