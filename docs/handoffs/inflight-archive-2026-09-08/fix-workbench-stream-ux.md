# fix/workbench-stream-ux

## 这个分支做什么

8792 Workbench 的三个体感问题**全部收口**：排版一大坨（A）、38 秒只看到一行字
（B）、非流式一股脑输出（C）。

活代码树：`~/fwp-wt-stream-ux`，**已 rebase 到 `gitea/main@8688545b`**（零冲突）。
六个 commit。未推、未合。

## Live 实测（已验证，n=3）

对照 `:8792`（= `main@8688545b`）vs `:8801`（本分支）。同一问题「明天你怎么看」。

| | 8792（main） | 本分支 3 轮 |
|---|---|---|
| text.delta 条数 | 1 | 424 / 663 / 777 |
| 最大分片 | 1117 字（整段） | 10 / 4 / 3 字 |
| 整段推送次数 | 1 | **0 / 0 / 0** |
| 文字比完成早出现 | 0s（同刻） | 25.8s / 34.1s / 44.9s |
| 列表项 | 0 | 3 / 3 / 3 |
| 加粗 | 0 | 6 / 11 / 7 |

**首字绝对秒数不要引用**（16.7～57.2s 波动），它跟着检索阶段长短走。可引用的是
「文字比完成早出现多久」和「分片数/最大分片」——那两个由架构决定。

补证轮（`repair_goal` → `repair_reentry`）同样会流：3 轮里有 2 轮走了补证，
分片数照常。曾一度怀疑补证路径不流式，是错判，见下面「踩过的坑」。

进度条（seam 修好后，`run_20260824_000543_048856`）：

```
 0.5s  已完成问题理解与任务对齐。
11.1s  正在查盘面快照。   / 已取得盘面快照。
11.1s  正在查主线结构。   / 已取得主线结构。
40.3s  研究回答已形成，正在完成最终核验。
81.7s  已完成回答与证据的绑定核对。
```

同轮流式 956 条 delta / 最大分片 4 字 / 整段推送 0 次；正文 1429 字、3 列表项、
5 处加粗。**A/B/C 四项指标同轮全中。**

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

- intelligence 全量：**5554 passed / 11 skipped / 0 failed**（`-p no:randomly`）。
  基线 `3ac070a2` 是 5483，本分支净增 71 条测试。
  注意：旧 handoff 提到的 main 存量 4 红在 `3ac070a2` 上已不复现。
- webapp：typecheck + eslint 干净，vitest **67 passed**（新增 2 条回归）。
- ruff `intelligence/` 全绿；`layer_audit.py` ERROR 0；pre-commit 9 道全过。
- **拿真实 payload 回放**过 projector（不只是单测夹具）：同一轮里
  `market_data` → 「正在查盘面快照。」、`mainline_context` → 「正在查主线结构。」，
  改动前两句都是「正在核对计划所需资料。」。
- **拿真实 content 回放**过解码器：那次 run 模型吐的 1808 字符信封，按逐字节 /
  随机 1-40 / 整块三种切法，解出的 1156 字与 `json.loads(...)["draft"]` 完全一致。
- 整链验收（`test_draft_stream_end_to_end.py`）：假 SSE → `chat_with_tools` →
  `GLMModelClient` → `run_store`，客户端拼接结果 == 模型正文，覆盖
  1/3/11/64/4096 五种分片尺寸。
- `pnpm build` 通过，产物已随 B 提交（`intelligence/api/static/` 是入库的，
  按 `faa8041b`/`64222cf0` 的既有惯例并进功能 commit，不单独开一条）。
  C 不需要动前端：`streamEvents.ts` 本来就支持 `text.delta` 增量拼接。

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
- **重复正文是这条链最贵的失败形状，两道闸缺一不可**：传输层按「首个 delta
  之前/之后」分抛两种异常（之后那种连 provider 链都不许再走）；编排层查
  stream log 而不是穿一个 flag 下来——日志本身就是「有没有东西过到客户端」的
  答案，还能扛住重连重放。捕获与发射要拆开：`text_chunks` 仍要写（它是崩溃
  兜底正文），只抑制重复推送那一半。
- **sink 必须按每次 model turn 重置解码器**。第一轮的 PLAN JSON 会吃掉信封
  前缀预算（4096），共用一个解码器的话正好在终稿要用时 disarm。
- **不传 `on_content_delta` 就一行流式代码都不走**。测试双桩多是固定参数
  `lambda`，无条件加 kwarg 会把它们全打断——这也是 `_stream_kwargs` 存在的
  唯一理由。
- `draft_publisher` 与 `episode_progress` 是**两个 owner，契约相反**：后者禁止
  模型 prose 过 seam，前者专门运模型 prose。不要合并成一个模块的两个分支，
  否则「模型文本能不能过这条缝」只能靠读 event kind 来回答，下一个人必错。

## 未做 / 下一步

**唯一没做的是合并**：合 `main` 与推送按红线需用户点头。分支已 rebase 到
`8688545b`、零冲突、全绿、live 已验证。

B 曾在 live 里没生效（三轮全是通用句），真因是 `_public_trace_step` 丢掉
output_summary 按 stage 重合成，已在 `6fd1c2c7` 修掉并 live 复验通过。

**已知张力（设计上接受了，不是遗漏）**：语义核验在 draft 完成后才跑（30→38s
那 8 秒），所以流式期间用户看到的是**未过核验**的文字。架构本来就预留了位置
——`answer.snapshot` rev1(`verified_draft`)/rev2(final) 两阶段，前端
`MessageBubble` 已有「可核验草稿 · 模型精修中」文案。且实测那轮 **rev1 与 rev2
逐字符完全相同**（1218==1218，`identical: True`），核验改文字是少数情况。
真出现核验改稿时，用户会看到正文被替换一次——这是有意的取舍。

**`sdk_glm` / `sdk_gpt` 后端没接流式**：`OpenAIAgentsRuntime` 的流式语义还没
对齐，`app.py` 里显式只在 `selection.name == "continuous_glm"` 上挂 sink。
生产默认就是 continuous_glm，但换后端时这条会静默退回非流式。

**一键回退**：`WORKBENCH_DRAFT_STREAM=off` 关掉流式，不用改代码、不用重新部署。
这是三条改动里唯一动了模型传输层的，留了闸。

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
- **`RunStore` 的第一个位置参数是 `user_id`，不是根路径。** 写成
  `RunStore(tmp_path)` 会得到一句「非法 user_id」，正确写法是
  `RunStore("xxx", root=tmp_path / "runs")`。
- 流式下 `usage` 只在最后一个 chunk 出现，且必须显式开
  `stream_options.include_usage`。忘了它 episode 的 token 账会静默归零——
  行数、覆盖率都正常，只有数值是空的。
- 分片重组里 `name` 只能覆盖不能拼接：有的网关每片都重发 name，拼接会得到
  `market_datamarket_data`，然后工具静默不执行。已加回归测试。
- **「端口有人 listen」≠「我的服务起来了」。** 本会话在这上面栽了一次：8797 被
  另一棵树（`fwp-wt-event-calendar-serving`）抢先占住，我的 uvicorn 日志里明明
  写着 `address already in use` 就退了，而我只看了 `lsof -t` 有 PID 就开测，
  连打三轮、还据此写下「rebase 引入了回归」。**起服务后必须核对监听进程的 cwd
  是不是自己那棵树**：
  `lsof -a -p $(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t) -d cwd -Fn`
- **同理，B 那次「没生效」也不是玄学**：`_public_trace_step` 丢掉 output_summary
  按 stage 重合成。单测和历史 payload 回放都在**产出侧**验的，全绿；真正的验收点
  在**消费侧**。新字段要在被消费的那一层断言，不是产出的那一层。
