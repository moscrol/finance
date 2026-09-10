# baseline/capability-benchmark-00

## 这个分支做什么
能力升级 00 号单「用真实工作衡量能力增长」：30 题（10 类 × 2 公开 + 1 密封）+ 评分规则 + 走真实对话门的 runner + 评审包。合同见 `…/2026-09-09-capability-upgrade/00-*.md`；进度/阻塞见同包 `progress/00.md`、`blocked/00.md`。

## 当前状态（2026-09-11 00:1x）——终件在手，但**模型出口与判官同时断**，resume 与重出评审包都得等

**终件** `intelligence/eval/runs/20260910T105119Z-cb00-baseline-372d047c0b0f.json` 经 I1 重审：**clean 13 / recovered 10 / unavailable_final 5 / engine_missing 2**。material-01/02、calc-01、continue-01/02 是「事件链全 502 + 无有效终稿」的假干净；`review-pack-20260910/` 已 HOLD，**不要开评**（decoy 配的 calc-01 本尊就是无效降级答案，反向验证在包内不成立）。

**前置双断（B9，00:0x 实测）**：① 被测出口 Cockpit 57244 sol/terra 429 `model_cooldown`，周窗余量 3%、**reset 09-16 00:38**；② 判官 grok Build **402 余额耗尽**（18:53 终件时还好的）。判官离线的读数不是生产形状（B5 已认过），**不许硬跑**，也不许拿同族 `gpt-5.6-sol` 顶判官。两项都要用户处置（充值/换出口），二选一见 B9。

**开跑姿势**：先 `bash ~/.finance-runtime/capability-benchmark-00/preflight-00.sh`：出口/判官/sidecar 臂标签/续跑计划四查，NO-GO 退 1；GO 后 `run --resume` 且 **`--case` 只点必需题**（离线现算会重跑 7 题 = 5 隔离 + chain-01/02）。新包出新目录。

## 关键事实（接手先看）
- sidecar 8813 在 `cdb16985`、出口 Cockpit 57244（备份 launcher + keychain；B8）；臂标签 `baseline-372d047c0b0f` 不变（372d047c→cdb16985 只动评测侧）。编排脚本已修（B9「两个哑雷」）：探针改跟 sidecar 出口、每 attempt 过 preflight、续跑起点取较新件。判官 override `~/.grok/bin/grok`+`SANDBOX=off`（偏离生产两点，验收文已注明）。
- 数据形态：25 题走 8080 + 5 题走 57244——混合出口、同被测 revision，served_models 逐 turn 可溯源；再换一次出口仍属此例（B8/B9）。
- 另两条教训见 B8：method-01 七轮才干净；decoy 第一版「错得不够」重造后才入包。

## 未验证 / 边界
- 人工评审未进行；aggregate 未跑；after 臂未起跑。
- chain/continue 类公开题覆盖受 B7 压缩（chain 仅 h1 有效）。
- 单跑不做显著性宣称；无同题 Knevo 样本不报竞品胜负。
- B5 遗留：生产 8792 判官二进制仍坏（钉的 grok-1.0.5 被清），本单不代改；判官账号现又 402 欠费，生产同受影响。
- 「I1 合入 main 才能统一两臂口径」不成立：main 上没有 `capability_benchmark.py`（harness 从未上 main）。两臂共用 I1 树这一棵量具即可（`--base` 各指自己的 sidecar）；合车道分支是独立 PR，不在 after 臂前置链上。
