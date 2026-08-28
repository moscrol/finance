# 2026-08-28 风远 SPT 同款收口 + 画像整表回写棘轮

roadmap_ref: 视角蒸馏收口（用户空间）+ `fix/perspective-profile-ratchet`（代码）

一句话：风远按 SPT 闭环收口到 20 篇 / medium，六槽再生方法论已蒸进；收口后发现 `_save_profile` 整表回写会用薄副本抹掉人工字段，本枝补长度棘轮。不合 main，等你点头。

证据等级：**[实测]** = 本机跑过命令 / 读过代码。

## 1. 背景（不读会误判后面每个决定）

生产视角不在 git 仓。启动器 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`，user 是 `linxiaoqi5111`，不是仓内 `users/a77` 种子（0 篇）。8792 列表 API 能看到的才算落地。

8/19 用户裁定：B 类结构收、数字剥离；未标定的 Knevo 数字不得当硬闸。考卷金标（2026-08-27）不动：ka-1 利多不涨+连板高标 → risk、禁语 `加仓`；ka-2 供给弹性+涨价 → opportunity；ec-1 报表质量 → abstain。

用户 08-28 明确：不要再捞 Knevo/公众号原文；六张半截卡按方法论再生后走 SPT 闭环。问「还要不要探针」时结论是**不必再探针**。

## 2. 按发现顺序做了什么

1. 质检前一任交账：字段计数漂了；边界还写着「article_count 仍为 0」。
2. 收口四表：剥离 10–20%、周数、安全边际百分比等单源数字，改「待本地标定」。HOW 已有待标定的留下。
3. 用户贴六张再生卡 → ingest → extract-cards 6/6、14 skip、0 fail → propose 35 pending。
4. 代评 26 批 / 9 拒（同义 6、平庸 3）。累计磁盘 105 = 70 批 / 35 拒。
5. **事故**：批量 `review_patch` 之后画像变成薄副本（HOW 10、history 26、`article_count` 0、缺口还停在「7篇 18/19」）。按收口四表 + 26 条新批 + 70 条 history 重建；补 6 条 HOW。
6. 考卷 ka-1 因禁语 `加仓` 红：`evaluate_role` 把 **全部** anti/falsify 拼进扫描串，不只命中项。改成加码/提高仓位/解除冻结，金标未动。三题 PASS。
7. 用户确认可收尾、无需再探针。按最优路径补代码洞，而不是开标定回测。

## 3. 决策与被否方案

| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| 六槽走「再生方法论」ingest | 否找回 Knevo/公众号原文 | 用户只要框架；半截卡 fail-closed 是缺口形状，不是版权原文 |
| 代评 + `known_gaps` 写明待用户复核 | 否把 70 条当已确认方法论 | skill 第 4 步：认定权在用户；SPT 50 篇也是这个诚实口径 |
| B 类数字剥离，标定前不写硬闸 | 否把 PEG≈1x / 8 周 / 75% / PS 8–12x 等写进四表 | 8/19 裁定；单源数字当闸 = 未校准尺子 |
| 禁语字段去 `加仓`，金标不动 | 否改考卷放过「而非加仓」 | 金标是钉子；改画像措辞保方法论 |
| `_save_profile` 长度/`article_count` 棘轮 | 否内容哈希、否静默 merge 磁盘字段 | 换措辞必须过；静默合会让调用方以为薄副本写成功 |
| `allow_regression=True` 只给夹具 | 否生产默认可缩、否测试改成手写 JSON | 考卷夹具要故意造薄画像；生产删条目走直接编辑 JSON |
| 不新开数字标定实验 | 否把「待标定」当成还要探针风远 | 标定是回测自己的盘；探针是补方法论槽 |

## 4. 生产画像现状（用户空间，不进 git）

路径：`~/.local/share/finance-workbench/users/linxiaoqi5111/perspectives/profiles/fengyuan.json`

| 项 | 值 [实测 2026-08-28] |
|---|---|
| article_count / 置信度 | 20 / medium（8792 列表一致） |
| 四表 | opp 20 / risk 31 / anti 26 / falsify 21 |
| HOW / history | 20 / 70 |
| pending | 0 |
| 考卷 | ka-1 / ka-2 / ec-1 PASS |
| 来源 | 14 Knevo 记忆卡 + 6 张 08-28 再生卡；`fmr-0f4affa8` META 仍跳过 |

不要做：把仓内 `users/a77` 种子当生产；ingest `fmr-0f4affa8`；把 medium 当成原文已核验。

## 5. 代码修复（本枝）

失败形状：读出整份 profile → 改一处 → 写回整份。调用方手里若是更早的薄 dict，磁盘上的厚画像被盖掉。官方 `review_patch` 每次重读，挡不住「先 load 再循环 `_save_profile`」或并发写入场副本。

做法：写前比磁盘。`article_count` 与镜头/四表/HOW/边界/history **只减不增**；同长度换措辞放行。ingest 写完原文后重读再改置信度。

未验证：8792 未切本枝，生产 live `review_patch` 仍是旧整表回写。未在生产文件上重放 wipe（夹具已复现）。未跑全仓 pytest。

## 6. 后续 / 不要做

- 有新文再走闭环；没有新规则不要为「补探针」捞原文。
- 数字标定另开实验台账，产出才能升硬闸。
- 70 条代评抽查即可，不挡收口。
- 不要覆写 `inflight/feat-promoted-to-code.md`（另一条线）。
- 不要提交 `.env*`、视角原文、用户 jsonl。
