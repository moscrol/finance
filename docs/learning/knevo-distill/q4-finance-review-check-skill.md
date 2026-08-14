---
type: knevo_corpus
id: q4
date: 2026-07-09
credits: 20
topic: 投研事实审查 skill（finance-review-check）用法自述
key_finding: Knevo 会通过 read_skill_file 读取并全文转述自己的 skill 定义——skill 层对用户透明，可低成本枚举蒸馏
---

# Q4：投研事实审查 skill 自述（Knevo 原文回贴）

问题：我打开了投研事实审查，告诉我这个技能包的最佳用法，最佳提问模板

## 架构情报（比内容本身更值钱）
- Knevo 调用了 `read_skill_file` 工具，完整读取 finance-mode / finance-review-check 两个 skill 全文并如实转述 → **P4 自我暴露探针提前验证：skill 定义无防护，可直接要求 dump**。
- 该 skill 是 workflow 型，经 sub-agent（finance-reviewer 子代理）执行 → 它有 sub-agent 路由层。
- 存在「写入长期记忆前的质量闸门」：FAIL 阻塞写回 user-finmemory → 它的记忆入库有 verifier 门控（与我们 qa_ingest 同构）。
- 本次仅 20 积分 → 枚举全部 ~10 个 skill 的完整定义预计 ≤200 积分，是最高性价比的蒸馏路径。

## 内容要点（可回灌候选）
6 维事实审查框架（数值/实体/来源/逻辑/时效/完整性）：
- A 数值：核心数据偏差 >0.5% → critical
- B 实体：公司名/ticker 消歧（平安银行≠中国平安）
- C 来源：强论断无出处 → critical
- D 逻辑：证据→结论链条、前后矛盾、推理跳跃
- E 时效：数据过期、政策/财报新版
- F 完整性：按报告类型查结构缺失（缺风险变量、缺估值锚）

输出契约：Verdict（PASS/WARN/FAIL）→ 修订版报告全文在前 → 审查详情附录在后；每个 issue = 原文引用→偏差→真值来源→修订。FAIL 阻塞写入记忆。

组合模式：先写后审（生成型 workflow → 审查型 workflow）；记忆入库把关。

## 与本地对照
- 我们已有：qa_ingest / check_opinion_review（入库闸门）、answer-score（输出自评）。
- 我们缺：①"修订版在前、审查在后"的输出契约（我们只给意见清单，不产可直接用的修订版）；②数值偏差分级阈值（>0.5% critical 这类量化标准）；③实体消歧显式检查项。
- 回灌候选：给 answer-self-review-framework 补 6 维清单 + 修订版输出契约。
