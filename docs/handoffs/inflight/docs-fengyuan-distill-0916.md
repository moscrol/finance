# docs/fengyuan-distill-0916

## 这个分支做什么
把风远94 对账台账（`docs/learning/knevo-distill/fengyuan94-corpus-dedup-2026-09-16.md`）判「新增」与「部分·
建议进闭环」的卡走 `perspective-distill` 闭环进 `fengyuan` 画像。画像、原料、卡片、patch 全在 gitignore 的
用户空间；进 git 的只有本交接、`evolution/backtest-queue.md` Q-002 #12–#30、skill 第 0 步过期段修正。

## 当前状态（2026-09-16 17:30 前后，全部收口；用户已先后授权「按最优方案推进」与「你来做分析判断，我不复核」）
四篇 article（快照日为 date）：优先8卡 `pa-516facf90296`、新增第二批14卡 `pa-e0178691c647`、B侧11条
`pa-403ebdafaf79`（2026-08-08）、「部分」组15卡 `pa-fbb827444720`。全部候选引文逐字核验通过。

| 批 | patch 批 | patch 拒 | 人工写入 |
|---|---|---|---|
| 优先8卡 | 5（R61/R12/R65/R28/R29） | 3（R35/R27/R30 数字） | 3（其剥离版） |
| 第二批14卡 | 10（含 R60） | 5（R13/R26/R50/同义/R59 数字） | 3（剥离版） |
| B侧11条 | 11 | 6（数字或与 #6 重复） | 4（剥离版） |
| 「部分」15卡 | 9 | 3（R42 数字/环节版/同义） | 4（R11/R23/R39/R42 剥离版） |

- **裁决已按用户授权落地**：边界第 1 条收窄（原文存 known_gaps；例外句允许报表科目作涨价/订单/定价权兑现
  验证信号）；R29/R60 批；R27/R30/R59 与其余带数候选一律「拒 patch + 剥离版人工写入」，数字全部进 Q-002。
- 累计：approved patch 105 条 + 人工条目 14 条。用户授权 agent 终审后已复核：同义扫描（4-gram Jaccard>0.30）零命中、事件性残留零命中、数字审计仅保留 1 处思想实验量级（反弹20%判别器）；known_gaps 已改记终审结论；每批评审后考卷 3/3
  （边题「核报表质量」在边界收窄后仍弃权）；8792 可见 fengyuan 24 篇。
- 评审判据与逐批结果：job 目录 `~/.local/share/finance-workbench/private-distillation/fengyuan-20260916/
  review-policy{,-batch2,-batch3,-batch4}.md` + `plan.json`。
- 抽取全程走 `start-finance-workbench-glm-canary` 的智谱直连（8080 网关上游自 14:50 起全 503）。

## 未吸收（有意，非缺口）
- ~~7 张策展字段卡~~ 已在用户授权终审后手编完成（全部追加式：ML1 扩产判别轴、ML3 四阶段+第三层双面、ML4 三维充分性、ML5 同构两用、RP6 场景分叉、新增 RP21 涨价端/纯量端配对；数字进 Q-002 #24/#27–#30；exam 3/3）。
- R17（避免第二份梯子）、R32（七层带持仓动作，触只读红线）：台账明说不吸收。
- R09 定性句被 R12 批准条目覆盖；R38/R46 未产出候选（事件性强/原文缺失），数字已进队列。

## 下一步
1. Q-002 #12–#30 按各行数据源前提逐条标定（#28/#29 本仓可回放，优先）。
2. ~~生产 smoke 待网关~~ 已完成：用户拍板「切回 glm 当写手」。路径=先 BYOK 试跑（PUT /api/llm/config，remember=false）→ 单视角完整冒烟 completed、零降级、答案用上本日蒸馏内容（B型出清+三维检查）→ 备份启动器（bak-20260916-pre-glm-writer）改 FORESIGHT_BUILTIN_* 三行为智谱直连 glm-5.2（coding 端点）→ launchctl kickstart 重启（新 pid、同 rev 0758a423、deps 全绿）→ 内置链再冒烟 completed。同晚按用户指示升级 glm-5.3-flash（官方直连就有，无需 fomo；三形状探针全 200；注意它每答先思考约500 token，max_tokens<1024 会得到空正文——运行时合成默认 3000 不受影响）；完整冒烟 ~1 分钟完稿、答案带证据层声明与三维检查。备份链：bak-20260916-pre-glm-writer（kimi 版）→ bak-20260916-glm52-writer（5.2 版）。接线前按三种报文形状（plain/tools:[]/real tools）各探一次全 200。LLM_MODEL=gpt-5.6-sol@8080 保留作第二 provider，网关恢复即自愈；sidecar 8796 未动。
3. 用户随时可翻案：known_gaps 与四份 policy 文件保有全部溯源，说一声即撤任意条目。

## 踩过的坑
- 用户空间与 user 真值都在启动器现查；skill 第 0 步已改。启动器 PYTHONPATH 指 runtime 树，只 eval 需要的行。
- 网关探活只信 `chat/completions` 的 `choices`；glm-5.2 小 max_tokens 会被思考吃空，探针给 ~200。
- 边界收窄的安全做法：首分句逐字保留（考卷取针按「不适用」类标记分句、按顿号出针），例外句避开标记词，
  改完必重跑 exam——本次边题仍守住。
