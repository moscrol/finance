# cursor/harness-ceiling-followup-spec-3f68

## 这个分支做什么
Harness 后续规格（GitHub PR #3）。只改文档。纲领：增加输入必要就加，限制输出只做减法。

## 当前状态
D0/D1 已结。D2：W2 `R-20260821-08` confirmed；W1 `R-20260821-07` 仍欠 `marker_loss>0`。正文 `docs/verification/2026-08-24-d2-w1-w2-natural-sample.md`。
D3 已提交 `5b599223`（Gitea #349）。D4 第 1 步已提交 `a478ad55`（Gitea #350）。本树只改文档。

## 未验证 / 已知边界
W1 自然样本未到。D3/D4 未合。同 SHA / 合 main / 切端口等用户。不要按审查开条件放稿门。

## 下一步
合 #349 / #350 / #343 等用户。同 SHA 是 `R-20260824-09`。W1 等真 `marker_loss>0` 再结，别把结构水印当删格。

## 踩过的坑
超集树 `2bac3633` 一次改了 30+ 已在 main 且已漂的文件，整树当解耦版会三向。`1c52e19f` 的 `agent_episode.py` 已与 main 相同，不要再拆。
云端子代理 ID（会腐烂）：`079a3f4b-6c91-40ce-969b-22381bcc58ce`。失效重读 spec §0.3。

## 已验证
R-05 / W1 / W2 在 main。开关板模块仍不在 `gitea/main`。serving 不 import `capability_switchboard`。
