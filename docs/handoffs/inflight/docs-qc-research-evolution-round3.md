# 研究进化四轨返修 · 第三轮审查

## 这个分支做什么
独立审 01 `7c50645a` / 02 `556efa2a` / 04 `fce5132c` / 05 `19e6176f` 的八项修复；不改候选、不审签 03/06。详报 `docs/handoffs/2026-09-13-research-evolution-round3-qc.md`。

## 决策与被否方案
- 固定 SHA 独立树测，否了在原树改测试；主检出有他人改动。
- 原八例与新边界分开计；否了“原例绿=缺陷族已关闭”。
- 不代修/合并：用户只要求审查。合成输入压测，不是真人事故证据。

## 当前状态
审查产物归本地 `docs/qc-research-evolution-round3`，无 push/合并/部署。结论暂不签收：新边界 **5 项（3 P1、2 P2）**。
- 01 J4[P1]：时区字符串顺序让较新的更正版先退休，旧 hash 复活，open=0。
- 01 J5[P2]：同时间不同 hash 被排序兜底误作先后，抹掉 ambiguous_version_order；本轮新回归。
- 04 D5[P2]：used_is_current 提前返回盖过 time_unknown，后来的同 hash 恢复把 unknown 洗为 context。
- 05 PV6[P1]：只有放弃终态、无时间/run/费用，收据并入让成本 unknown→known，缺口2→0、金额仍0.46。
- 05 PV7[P1]：task_started 推导成熟资格仍被未来窗剥夺，分母6→3、unknown→pass。
其余四项修前也错，本轮未完整封堵。02 无新增实现发现。

## 已验证
固定干净树模块 99+65+72+110 = **346 passed**；各模块 Ruff 通过。原八项反例符合修复预期；新增独立安全断言 **5 failed**，逐项修前对照。证据 `~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/manifest.json`。原/临时候选树仍干净。

## 未验证 / 已知边界
未重跑全仓、前端/端到端/注册表或四轨组合。05 的9650P收据确实存在但为父 SHA `7c7c388b`+两文件 dirty，不是最终候选干净树门禁。04交接“最新已推”与本地远端跟踪 ref/用户本次口述不一致。

## 下一步
01修J4/J5；04修D5；05修PV6/PV7。新SHA重跑原8例+新5例+合法路径对照；06最终组合另跑集成门禁。报告与探针在本分支，不能只交口头描述。

## 踩过的坑
- 探针 `docs/verification/research-evolution-round3/`，默认读 `/tmp/research-evolution-round3-qc/{01,04,05}`；可设 RESEARCH_EVOLUTION_QC_ROOT。刻意红灯，不属于产品回归集。
- 原归档脚本锁旧 SHA；本轮仅改路径/锁SHA执行副本，未覆盖旧证据。
- 通用知识点是表示不变性、追加无效证据不核销缺口、成熟资格不倒退；业务夹具留本仓，未动脏 harness-reference。
