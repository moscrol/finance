# T-C 派单：FINAL_JSON 判据与生效解析器对齐（**验收工具层**）

- 日期：2026-08-17 ｜ 索引：`2026-08-17-dispatch-00-index.md`
- **层：验收工具**——既不是产品通用底座，也不是领域 Harness。它是**我们量东西的那把尺**。
- **dsh 接缝：无**（尺子不进产品）。
- 信源路由：本仓账本与实测。不需要外部信源。

## 0. 一句话

判据说「`json.loads` 成功才算写出了答案」，生效解析器比它宽松。
**照判据判 repair 轮，会把明明出了稿的 run 记成空稿。**

## 1. 现场（自包含）

基准 run：`run_20260817_094617_943922`
产物根：`/Users/a77/.local/share/finance-workbench/users/verify-r22-r23-0817/runs/<run_id>/`
文件：`continuous-episode.json`

| 事件 | 内容 | `json.loads` | 去向 |
|---|---|---|---|
| seq14 `model_turn` | 1404 字符，keys=`[bindings,draft,gaps,status]`，`draft`=**732** 字符 | ✅ **成功** | 被 seq16 first finish 结转：`carried_draft_chars=732` |
| seq19 `model_turn`（repair） | 1299 字符 | ❌ **失败**：`Expecting ',' delimiter: line 1 column 54` | 生效解析器**捞了出来**，成为 `outcome.draft`（612 字符）与最终 `answer.md` |

失败原因：`draft` 字符串里 `"AI算力"`、`"7月中旬即为高点…"` 的双引号**未转义**。

## 2. 危害

`docs/handoffs/2026-08-17-r22-r23-carry-draft.md` §3 写的判定标准是：

> 某条 `model_turn.content` 能 `json.loads` 出 `draft`，且紧随 first finish `carried_draft_chars>0`

R-20260817-01 这类**结转型预测全靠这个判据结案**。照它判 seq19，会判成「无 FINAL_JSON」，
而产品实际出了稿并交给了用户。**尺子比被测物严，会在真绿的地方报红。**

⚠ 反方向同样危险：如果直接把判据放宽到「解析器能捞出来就算」，
就再也测不出「模型输出格式坏了」这件事本身。

## 3. 任务（二选一，不要两边各改一半）

**方案 1（改生成侧）**：让 draft 正确转义，`json.loads` 恒成立。
判据不动，尺子保持严格。代价：要动生成侧的序列化。

**方案 2（改判据）**：判据放宽到与生效解析器同口径，**并把宽松那一段写明**——
写清「用的是哪个解析器、它能容忍什么」，且**另立一条独立断言**盯「模型输出格式是否合法」，
不让格式退化被静默吸收。

推荐**方案 1**：尺子该比被测物严，不该反过来迁就。但若生成侧代价大，方案 2 可接受，
前提是那条独立断言必须同时落地。

## 4. 完成定义

- 离线夹具：拿 seq19 的**原始 content** 作输入，断言判据与生效解析器给出**同一个结论**。
- **变异测试**：把转义修复（或判据放宽）那一行抽掉，夹具必须转红。没被变异证伪过的门禁是假门禁。
- 若走方案 2：另有一条断言专盯「content 是否合法 JSON」，且它与「是否算写出答案」**分开计数**。
- 回写 `docs/handoffs/2026-08-17-r22-r23-carry-draft.md` §3 与账本里引用该判据的行。

## 5. 已知不受影响

**2026-08-17 T1 的 hit 结论不依赖 seq19**——它只用 seq14 + seq16，两者都过严判据。
本轨无论怎么改，都不动那条结论。见 PR #128。

## 6. 边界

- 不动产品降级文案（T-B）、不动兜底开关（T-A）、不动预算（T-D）。
- 不切 8792。
- 改判据须同步改账本里所有引用它的行，**不要留第二份口径**。

## 7. 环境

- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（宿主 `python3` 缺依赖）
- Gitea PR：`git credential fill` + `http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls`
- 合 main 必须等用户确认
- ⚠ 不要从 `/Users/a77/finance-workspace-private` 工作树提交（落后 main 293 提交，
  其 `docs/prediction-ledger.md` 相对 main 是 -573/+159 的旧版本）
