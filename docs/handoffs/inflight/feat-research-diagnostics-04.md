# feat/research-diagnostics-04 · 个人研究流程诊断（研究进化 04）

## 这个分支做什么

实现规格 `docs/superpowers/specs/2026-09-13-research-evolution/04-personal-diagnostics.md`：五类流程检查（迟登 / 条件修改 / 过期证据沿用 / 阶段不适用 / 到期未回检）→ 带证据 finding、分母、不能归因项、一题练习。纯函数、无模型、无 IO；旧台账经只读适配器进来。

## 决策与被否方案

- 缺证一律 unknown+gap；否了复用 `is_late` 的「判不出=late」——那是校准准入，这里是给人定责，方向相反。
- 派生 checkpoint 行承担到期机会，剧本行 `due=None`；否了双计与只算剧本（verdict 挂在 checkpoint id 上）。
- 过期沿用按失效事实记录时间 ≤ 使用时刻判可知；否了强制曝光收据（存量无曝光日志会永久 unknown）。
- 策略无该对象类型规则 → excluded；当时不在效 → unknown；否了统一 unknown（memo 判断会进迟登分母）。
- 缺登记时刻但 as_of 已知 → `trade_date_only`（对齐主树未提交 09-06 §4.1）；两者都缺才 unverifiable。
- 同 key 合并 issue>context>unknown；输入按 id 去重。存量作者只看字段，否了按文本猜。
展开见 `docs/handoffs/2026-09-13-research-diagnostics-04.md`。

## 当前状态

- 已提交并推 gitea：`31ddec51` 规格 cherry-pick、`fea6ef98` 模块+测试+夹具、`a6395c82` docs、`4d457d7a` pit 对齐修补、本轮 docs 提交。未提交：无。
- engineering_complete；未 product_verified（归 06），未 field_evidence。树 `/Users/a77/fwp-wt-research-diagnostics-04`，基线 `gitea/main@5fb13a8c`。

## 已验证

收据见 `docs/superpowers/plans/2026-09-13-research-evolution/04/PROGRESS.md`（绑定 `4d457d7a`，按 revision 取时间戳文件）：collect-only 51 选中 exit 0；`-k research_diagnostics` 51 passed；旧读取器 78；相邻回归 60；ruff 0；pre-commit 11 道过。适配器测试用真实写入者造台账并断言 sha256 不变。与 `docs/river-next-specs` merge-tree 无冲突。

## 未验证 / 已知边界

- 全仓 `pytest -q` 未跑（只新增文件）；合并前跑等价 CI。
- 存量台账无 coverage / 版本链 / 曝光日志：真实用户会大面积 unknown，是数据现状不是 bug；补齐责任见 `…/04/BLOCKED.md`。
- 09-06 设计段仍在主树未提交，本轨只读对齐了 §4.1 一处；01 合同夹具按 01 规格手写，01 定稿后需对齐。

## 下一步

06 用 `adapters.load_legacy_inputs` 起步，按 BLOCKED 清单逐类补收据；合并 main 等用户确认。

## 踩过的坑

- `git commit -- <paths> -m` 把 `-m` 当 pathspec；用 `-F 文件 -- <paths>`。
- 真实写入者用 `checkpoints._now` 盖 `ts`，测试不钉时钟会被 cutoff 过滤掉派生行。
- 新树无 `.agent-memory` 软链，写 vault 用 `~/agent-memory` 绝对路径。
