# fix/workbench-stream-ux

## 这个分支做什么

8792 Workbench 的三个体感问题里，本单收口两个：**排版一大坨**（A）和
**38 秒只看到一行字**（B）。第三个「真流式」没做，见下面「未做/下一步」。

活代码树：`~/fwp-wt-stream-ux`，基线 `gitea/main@3ac070a2`。
两个 commit：`4f6d6e6c`（A）、`9e7989cb`（B）。未推、未合。

## 诊断依据（实测，不是推断）

全部来自一次真实 run：`run_20260823_221135_424228`（用户 linxiaoqi5111，
问「明天你怎么看」）。复放 `stream.jsonl` 与 `continuous-episode.json` 得到：

| 时刻 | 事件 |
|---|---|
| 0.0s | task / prefetch |
| 6.0s | model_turn #1 返回（36 tokens，只决定调哪些工具） |
| 6.1s | market_data + mainline_context 执行完（已预取，各 0.001s） |
| **6.1→30.0s** | **model_turn #2：生成正文，23.9s / 1038 tokens** |
| 30→38s | 证据绑定 + 语义核验 |
| 38.00s | answer.snapshot rev1(1218字) + text.delta(**1218字一整块**) + rev2 + message.complete **同一秒全到** |

三个根因互不相同：

1. **非流式**断在三处：① 全仓只有 `llm_refine.py` 一处 `"stream": True`，且它
   是不带工具的合成调用；带工具的 `chat_with_tools` 走非流式。② 终稿是 JSON
   字段 `{"status":...,"draft":"…"}`，逐 token 吐出来是转义序列。③
   `conversation_orchestrator.emit_text_delta` 传的是整段 draft，而真正接 token
   的 `stream_text_delta=capture_safe_text` 只入 buffer 不 emit。
   **前端 `streamEvents.ts` 早就支持增量拼接，是后端没喂。**
2. **无 reasoning** 是刻意边界，不是 bug：`episode_progress` 模块 docstring 写死
   「Episode ledger 的值一个都不许过 Run/SSE seam」，projector 注释是
   「ignoring every event payload value」。
3. **排版**不是 CSS：`MarkdownView` 是 marked+GFM，`styles.css` 对
   h1-h3/ul/ol/table/pre 都有样式。是正文里没有 markdown 结构——prompt 里四条
   全是否定式约束，没有一条正面要求可读性。

## 已验证

- intelligence 全量：**5483 passed / 11 skipped / 0 failed**（`-p no:randomly`）。
  注意：旧 handoff 提到的 main 存量 4 红在 `3ac070a2` 上已不复现。
- webapp：typecheck + eslint 干净，vitest **67 passed**（新增 2 条回归）。
- ruff `intelligence/` 全绿；`layer_audit.py` ERROR 0；pre-commit 9 道全过。
- **拿真实 payload 回放**过 projector（不只是单测夹具）：同一轮里
  `market_data` → 「正在查盘面快照。」、`mainline_context` → 「正在查主线结构。」，
  改动前两句都是「正在核对计划所需资料。」。
- `pnpm build` 通过，产物已随 B 提交（`intelligence/api/static/` 是入库的，
  按 `faa8041b`/`64222cf0` 的既有惯例并进功能 commit，不单独开一条）。

## 关键设计（别退回去）

- **工具名当枚举键，不是当内容透出**。`_TOOL_LABELS` 的键必须 ⊆
  `_DEFAULT_TOOL_METADATA`（12 个），跨 seam 的是我们写死的中文标签。查不到就
  退回通用句 —— 认不出来就 fail closed。已加一致性测试锁两边：少一个会**静默**
  退回通用句（不报错、不刷屏，只是那个工具永远看不见），多一个说明工具已删或改名。
- **限定语排在被限定内容之前**。新增的排版约束写成「禁的是按固定小标题填空，
  **不是**禁止排版」，顺序反过来模型会把「禁止固定标题」泛化成「禁止一切结构」
  ——那正是改动前发生的事。
- `_CONTRACT_FINGERPRINT` 是**故意**要变红的门禁。这次显式更新
  `a6f450a1…` → `af870456…` 并在 commit 里写清改了哪一条。不要靠回退让它变绿。
- `tool_request` 的工具名在 `name` 键，`tool_result`/`tool_error` 在 `tool` 键，
  两个都试，别赌某一个运行时的写法。

## 未做 / 下一步

**C：真流式**（未开工，建议单独开单）。收益最大——生成占 23.9/38 秒，做完首字
从 38s 提到 ~6s。路径：

1. `glm_agent_runtime` 终稿轮开 `stream=True`（现在走
   `llm_refine.chat_with_tools`，非流式）
2. 写增量 JSON 字符串字段扫描器，只提 `"draft":"` 之后的内容，处理
   `\"` `\n` `\uXXXX`
3. delta 接到 `emit_text_delta`（前端已就绪）
4. **必须照抄 `llm_refine.py` 那道闸**：流式已吐字后失败禁止回退非流式，否则
   用户看到重复正文（注释里记了 inc-4258 那次工具双执行的文本版）

**已知张力**：语义核验在 draft 完成后才跑（那 8 秒），流式意味着先展示未过核验
的文字。架构其实预留了位置——`answer.snapshot` rev1(`verified_draft`)/rev2(final)
两阶段，前端 `MessageBubble` 已有「可核验草稿 · 模型精修中」文案。且实测本轮
**rev1 与 rev2 逐字符完全相同**（1218==1218，`identical: True`），核验改文字是
少数情况。

**A 的效果尚未 live 验证**：prompt 改动要真跑一次问答才看得到排版变化，本会话
没重启 8792（那是用户正在用的进程）。重启命令见下。

## 怎么起来看

8792 上跑的是主树的旧代码。要看新版：

```bash
cd ~/fwp-wt-stream-ux
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m uvicorn \
  intelligence.api.app:app --host 127.0.0.1 --port 8793
```

换个端口起，8792 不用停，可以并排对比。前端产物已 build 进
`intelligence/api/static/`，不用另跑 vite。

## 踩过的坑

- **`episode_progress.py` 在 `intelligence/services/`，不在 `runtime/`**。主树那棵
  脏分支把它挪去了 runtime，照着改会找不到文件。
- 排版的真正位置是 `episode_protocol.py`（continuous episode 路径），不是
  `answer_quality.py`。后者是 ask/synthesis 路径（Engine B）。用户那句「明天你
  怎么看」走的是前者。两处都改了，但只改 `answer_quality` 不会有任何效果。
- `compact_for("market_forecast")` 落到 `else` 分支，`prompt_profile` 不是
  `"full"`——所以 `answer_quality.py:90` 那个 `full` 分支里的写作要求对市场题
  **根本没生效**。新增的排版约束因此放在 base lines，不放分支里。
- 这棵树没有自己的 `.venv`，用主树的
  `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
