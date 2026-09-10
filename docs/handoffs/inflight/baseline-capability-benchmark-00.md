# baseline/capability-benchmark-00

## 这个分支做什么
能力升级任务包 00 号单「用真实工作衡量能力增长」：30 道真实研究工作题（10 类 × 2 公开 + 1 密封）、评分规则、走 Workbench 真实对话门的 runner、匿名配对评审包与汇总（含反向验证）。合同在 `codex/docs-capability-upgrade-plan@b80decbd` 的 `docs/superpowers/plans/2026-09-09-capability-upgrade/00-*.md`；进度 `progress/00.md`，阻塞 `blocked/00.md`（同目录，本分支）。

## 当前状态（2026-09-10 19:1x）——基线已收口，等人工评审
**终件已产、已拷仓、评审包已出、验收文已写**：`intelligence/eval/runs/20260910T105119Z-cb00-baseline-372d047c0b0f.json` = 28 completed + 2 engine_missing（chain-01/02，B7 路由缺陷）+ 0 tainted + 0 skipped + 0 判官真坏（质量闸门 rc=0）。评审包 `~/.finance-runtime/capability-benchmark-00/review-pack-20260910/`（30 匿名 sheet、6 题双评、calc-01 配真错版 decoy）。验收文 `docs/verification/2026-09-09-capability-benchmark-00-baseline.md`。**剩下只有人工活**：评审填分（≥20% 双评，名单在 pack.json）→ `aggregate`（decoy 胜则 rc=3）→ 单臂基线无胜负表，待升级后对比臂重跑同题集。

## 关键事实（接手先看）
- sidecar 8813 在 `cdb16985`、出口已切回 Cockpit 57244（备份 launcher，key 走 keychain；B8）。臂标签 `baseline-372d047c0b0f` 不变（372d047c→cdb16985 只动评测侧）。编排脚本已停，不要再起（它固化 8080 env）。判官 override `~/.grok/bin/grok`+`SANDBOX=off`（偏离生产两点，验收文已注明）。
- 数据形态：25 题走 8080（09-09 晚）+ 5 题走 57244（09-10 白天）——混合出口，同被测 revision，served_models 逐 turn 可溯源。
- method-01 七轮才干净：六轮全死终局 LLM 出口故障（503/429/400/Timeout），B4 机制（探针拦截+烧穿打标+resume 只搬干净题）保证零污染。
- decoy 教训：第一版「错得不够」（单季数全对=正确参照），重造为「中报−2025一季报」张冠李戴版才入包——decoy 必须独立核算后再用。

## 未验证 / 边界
- 人工评审未进行；aggregate 未跑（等评分）。
- chain/continue 类公开题覆盖受 B7 压缩（chain 仅 h1 有效）。
- 单跑不做显著性宣称；无同题 Knevo 样本不报竞品胜负。
- B5 遗留：生产 8792 判官二进制仍坏（launcher 钉的 grok-1.0.5 被清），本单不代改。
