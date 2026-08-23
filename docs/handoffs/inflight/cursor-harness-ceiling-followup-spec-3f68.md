# cursor/harness-ceiling-followup-spec-3f68

## 这个分支做什么
Harness 后续规格（GitHub PR #3）。只改文档。纲领：增加输入必要就加，限制输出只做减法。

## 当前状态
D0/D1 已结。D2：W2 confirmed，W1 仍欠 `marker_loss>0`。
#349 D3 与 #350 D4 第 1 步已合入 `gitea/main@4dd96f6f`。#343 仍开。本树只改文档。未切 8792/8796。

## 未验证 / 已知边界
合 main ≠ 生产生效。同 SHA / 切端口未做。不要按审查开条件放稿门。W1 自然样本未到。

## 下一步
切端口等用户。同 SHA 是 `R-20260824-09`。#343 另点头。W1 等真 `marker_loss>0`。

## 踩过的坑
超集树 `2bac3633` 一次改了 30+ 已在 main 且已漂的文件，整树当解耦版会三向。`1c52e19f` 的 `agent_episode.py` 已与 main 相同，不要再拆。
云端子代理 ID（会腐烂）：`079a3f4b-6c91-40ce-969b-22381bcc58ce`。失效重读 spec §0.3。

## 已验证
#349/#350 合入后本机全量 6252 passed / 13 skipped。开关板在 `gitea/main`，serving 仍不 import `capability_switchboard`。
