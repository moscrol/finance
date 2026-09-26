# feat/methodology-promotion-certification · 工单 #42（OPT-04 两刀）

## 这个分支做什么
第一刀：`lifecycle.derive_state` 只认**同身份 + 预声明阶段 + 顶层最终结论**的收据链，按身份变化 / refuted 切验证轮次。堵 PR #607 留下的四个误晋升路径：跨版本拼链、读 `stats.verdict` 忽略 BH、任意 supported 贪心成链、失效后一份成功复活。
第二刀（09-11 用户拍板「经验卡入口尚未接统一认证，另一入口仍可能放行」）：经验卡门接同一道认证——`lifecycle.state_for_rule`（规则文件字节 sha 锁身份，与 run/scan/queue 同口径）+ `gate_promotion(method_state)` 晋升档只认 `in_method_library`；**单份 supported 收据不再放行常驻卡**。`answer-score --rules-dir`；卡新增 `rule_lifecycle_state`。工单 `2026-09-08-methodology-promotion-certification-workorder.md` §2.4。

## 决策与被否方案
- 状态仍从收据**推导**，不落实验账；否了新建 `validation_cycle_id` 账本——多一个真源会漂。
- 字段叫 `declared_stage` 不叫 `stage`——`by_market_stage[].stage` 已是大盘阶段。
- 证伪不需要声明阶段，晋升需要；经验卡 `invalidated` 门维持「最近收据 refuted」——证据不对称：推翻不用预注册。
- 同窗重跑取**最新**一份、同级不许换窗；否了「任一 supported 即过」——事后挑窗。
- `gate_promotion` 保持纯函数：读收据 / 锁身份在调用方（`state_for_rule`），门本身不做 IO；否了门内自读目录——测试喂不进反例。
- `state_for_rule` 找不到规则文件返回 None → 门按「无认证状态」拒晋升；否了「无文件按旧 verdict 判」——那又开回旁门。

## 当前状态
两刀已提交：`ca9cae5d`（第一刀）→ `5ad33a26`（merge gitea/main@c714eb60，解 INDEX 冲突）→ `927f4f2f`（第二刀）。已推送 gitea，PR 待开/待用户确认合并。

## 已验证
- 认证树全量等价 CI：**ruff 全过 + 9228 passed / 0 failed / 77 skipped / 1 xfailed（323s）**，收据 `~/.finance-runtime/test-receipts/20260911T133633Z-5ad33a26.json` 起。
- 第二刀新回归:单份 supported 拒晋升（gate 层 + CLI 端到端）、三段链放行且卡带 `rule_lifecycle_state`、改规则文件字节后与 queue 一致回 candidate（`StateForRule` 4 测）、invalidated 门不变。
- 第一刀既有:新夹具对旧 `lifecycle.py` 实测 17 红;本机 `methodology/receipts/` 无规则收据，无存量方法被降档。

## 未验证 / 已知边界
- 未跑真库 `run --stage`（旁路库未建）。
- 别的机器旧收据无 `declared_stage` → 队列显示 candidate + 历史观察，需按阶段重跑；存量常驻卡（已落 jsonl 的）不追溯拆除，门只拦新落卡。
- 无期限探索的尝试账是 OPT-05（正在另一分支 `feat/opt05-correlated-samples` 做相关样本部分）。

## 下一步
1. 用户确认合 PR；合后 INDEX #42 行改 ✅ 并写合入 sha。
2. OPT-05（相关样本 / 块重采样）与 OPT-01 第二刀（内容版本）在后续分支推进（见 HEAD 交接与本轮总结）。
