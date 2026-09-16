# docs/teaching-card-judgment-draft

## 这个分支做什么
为 `docs/learning/teaching-framework/01-daily-card-outline.md` 的 15 处判读句留白起草 v0（`02-daily-card-judgment-draft-v0.md`）：只用创始人原话拼句、每格带出处与覆盖度，等创始人逐句「对 / 改 / 删」。不改 01，留白原样。

## 决策与被否方案
- 来源只认三处（00 骨架转录的口述 / 07-03 问卷第八、九层与答疑澄清 / UL Relationships）；否了 `reading-rules-inventory-2026-08-19.md`（外部 KOL 规则），否了问卷第一至七层（只给指针，Q8 待拍）——保住「这是创始人自己的方法」这条链。
- 09-08 口述（第十七至二十一段）一并收入并标日期；否了直接排除——同一文件同一格式逐句转录，排除等于替创始人选（Q1）。
- 原话里后续走向预测的半句（「要开始向下继续调整」「基本都是回落」等）不收；阶段定义里的走势描述词（下穿 / 反弹到周均线 / 抗跌）保留。判据 = 合规门实测 + 任务红线，取舍线摆给创始人（Q6）。
- 「大概率」「买」两处用「……」省略；否了保留原话——前者在 `E_PROBABILITY` 禁表，后者是动作词（Q5 / Q10）。
- 平台命名对象（承接 / 资金板块 / 宽度 / 承接盘反复）不用来顶替原话，对应情形明写留空（Q9 / Q13）。

## 当前状态
已提交 f25f851f（草稿）+ 本交接（独立提交）。未推送、未开 PR、未合入。15 格覆盖度：full 4（1.1 / 1.2 / 1.6 / 1.8）· partial 10 · none 1（5.1 资金面）。文末 13 条疑问全部两段并列摆出，没替创始人选。

## 已验证
15 条草稿行逐条过 `guided_reading.lint_output`（`compliance_gate` 观察剧本六类 + 「策略」）与 `E_FORWARD_CALL`：零命中；全文 `E_STOCK_SCOPE` 零命中。pre-commit 全过。工作树 @ gitea/main 727b2611。

## 未验证 / 已知边界
- 引文逐字性靠人工比对原文，没有脚本核对；发现有差以 00 骨架原文为准。
- 没跑全量 pytest / ruff（纯文档，未动代码）。出处只到「段 / 条」，没到行号。

## 下一步
创始人逐格填「对 / 改 / 删」→ agent 把「对」的句子回填 01 各格并升版本（卡片判读段句末带 `[§n vX]` 追溯号）。回填前先拍 Q13（1.8 标签用「高位震荡」还是保留平台名）与 Q3（二次探底 / 缩量右底是否合成一格），这两条决定 01 的格子数。

## 踩过的坑
- 平台阶段名「承接盘反复」含子串「接盘」，在 `compliance_gate._DIRECTION_TERMS` 上——含它的草稿行过不了门；运行时靠 `stage_rules.REFERENCE_STAGE_ALIASES` 印「高位震荡」才过。母本 / 词表里凡要上卡片的名字，先过一遍 `lint_output`，别只肉眼核词表。
- 主检出树是别人的脏树（detached HEAD），本任务全程在工作树 `/Users/a77/fwp-wt-teaching-card-draft` 做，解释器用主树 `.venv-workbench/bin/python` + `PYTHONPATH=` 工作树根。
