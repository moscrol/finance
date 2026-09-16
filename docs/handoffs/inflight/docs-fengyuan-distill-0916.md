# docs/fengyuan-distill-0916

## 这个分支做什么
把风远94 对账台账（`docs/learning/knevo-distill/fengyuan94-corpus-dedup-2026-09-16.md` §5）判为「新增」的卡
走 `perspective-distill` 闭环进 `fengyuan` 画像。画像、原料、卡片、patch 全在 gitignore 的用户空间；
进 git 的只有本交接、`evolution/backtest-queue.md` Q-002 #12–#15、skill 第 0 步过期段修正。

## 当前状态（2026-09-16 17:00 前后，优先批已收口）
- **优先 8 卡闭环完成**（article `pa-516facf90296`，GLM 直连抽取，8 候选全部引文核验通过）：
  **4 批**（R61 一致预期锚 / R12 纸面产能 / R65 比率口径 / R28 数据现查通用句，均进 anti_patterns 或对应字段）、
  **1 拒**（R35：value 写死「1-2季度」违 08-28 剥数纪律；剥离版在 review-policy「待用户手编」段）、
  **3 pending 待用户**（R27/R29/R30 与画像边界第 1 条「不做报表核查」冲突，推荐采纳+边界收窄，见 review-policy）。
- 考卷批后重跑 3/3 通过（边题「核报表质量」仍弃权）；8792（gitea/main=0758a423）可见 fengyuan 22 篇。
- known_gaps 已更新：74 条 approved 均 agent 起草待用户复核 + 本批 4A/1R/3P 一行。
- 第二批 14 卡已 ingest（`pa-e0178691c647`）**未抽取**——等自己的评审策略再走 extract。
- 模型网关 8080 自 14:50 起上游（Mirasim 账号组）全 503，恢复未确认；本批经
  `~/.local/bin/start-finance-workbench-glm-canary` 的智谱直连（glm-5.2, coding 端点）完成，用户在会话中指路。

## 下一步
1. 用户三裁决：① R27/R29/R30 批否 + 边界第 1 条是否收窄；② R35 剥离版手编与否；③ 复核 4 条已批。
2. 第二批 14 卡：写 review policy（台账 §5 已示警 R59/R60 边界、R13/R19 剥案例、R38 查重 q17 Q6）→ extract
   `--article-id pa-e0178691c647` → propose → review。之后「部分」22 卡与 B 侧（08-08 快照，`--date 2026-08-08`）。
3. 抽取用网关（恢复后）或 glm-canary 直连均可；LLM_API_KEY 未设时链条取 FORESIGHT_BUILTIN_*。

## 踩过的坑
- 用户空间与 user 真值都在启动器现查（本次 `FORESIGHT_USERS_DIR=~/.local/share/finance-workbench/users`、
  `FORESIGHT_USER=linxiaoqi5111`）；skill 第 0 步已改为现查。
- 启动器 `PYTHONPATH` 指向 runtime 树，整份 eval 会加载别的代码；只 eval 需要的 export。
- 网关探活只信 `chat/completions` 里的 `choices`；`/health`、`/v1/models` 全程是绿的。

## 未验证
- 生产 Workbench 单视角 smoke（选 fengyuan 问行情题）未跑——网关不可用，Workbench 自身模型也走它。
- 4 条已批与 3 条 pending 的最终认定权在用户。
