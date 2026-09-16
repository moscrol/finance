# feat/research-diagnostics-04 · 个人研究流程诊断（研究进化 04）

## 这个分支做什么

实现规格 `docs/superpowers/specs/2026-09-13-research-evolution/04-personal-diagnostics.md`：五类流程检查（迟登 / 条件修改 / 过期证据沿用 / 阶段不适用 / 到期未回检）→ 带证据 finding、分母、不能归因项、一题练习。纯函数、无 IO；旧台账经只读适配器进来。

## 决策与被否方案

- 缺证一律 unknown+gap；否了复用 `is_late` 的「判不出=late」——那是校准准入，这里是给人定责，方向相反。
- 派生 checkpoint 行承担到期机会，剧本行 `due=None`；否了双计与只算剧本。
- 过期沿用按失效事实记录时间 ≤ 使用时刻判可知；否了强制曝光收据（存量无曝光日志会永久 unknown）。
- 报告级 provenance 是天花板：项级只能持平/降档，冲突压回 synthetic 并出 gap；否了项级覆盖（QC S4 合成洗白）。父子来源各自校验，未知枚举拒绝。
- supersedes 追责加 valid_from 生效条件（缺省退回记录日）；否了只看 recorded_at（QC D3）。
- time_unknown 压过 later（D4），且 `used_is_current → valid` 早退也不得盖过它（D5）——未生效/后知的 current 不能绕过时间裁决。
展开见 `docs/handoffs/2026-09-13-research-diagnostics-04.md`。

## 当前状态

- 本地最新 **`8db4bbd9`（QC 第三轮 D5 修复）**。旧版曾推 gitea（远端仍停在 `b5cee17a`）；第二/三轮新修复均未 push。未提交：无。
- QC 二/三轮原固定反例均转绿，扩大边界累计确证 13 项，本轨占 4 项（S4/D3/D4/D5）均已修。证据 `~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/`。**06 联测请用 `8db4bbd9`。**
- engineering_complete；未 product_verified（归 06）；基线 `gitea/main@5fb13a8c`。

## 已验证

`-k research_diagnostics` 74 passed（D1–D5 回归均先红后绿）；全量 9614 passed / 77 skipped（干净树 @8db4bbd9）；ruff 0；QC 第三轮探针 D5 actual=unknown / 双向补全 issue·context；归档探针 D3/D4/S4 组复跑不回归。收据见 `…/04/PROGRESS.md`。

## 未验证 / 已知边界

- 存量台账无 coverage / 版本链 / 曝光日志：真实用户会大面积 unknown，是数据现状不是 bug；补齐责任见 `…/04/BLOCKED.md`。
- 01 合同夹具按 01 规格手写，01 定稿后需对齐。

## 下一步

06 用 `adapters.load_legacy_inputs` 起步，按 BLOCKED 清单逐类补收据；合并 main 等用户确认。

## 踩过的坑

- `git commit -- <paths> -m` 把 `-m` 当 pathspec；用 `-F 文件 -- <paths>`。
- 真实写入者用 `checkpoints._now` 盖 `ts`，测试不钉时钟会被 cutoff 过滤掉派生行。
- 时间缺口的裁决要防两条绕过：优先级顺序（D4）与提前返回（D5）——修一条漏一条等于没修。
- 上轮口径「13 项已修复」实为「原固定反例集转绿」；`docs/superpowers/summaries/2026-09-13-*.md` 从未落盘。
