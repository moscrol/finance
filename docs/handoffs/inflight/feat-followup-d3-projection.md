# feat/followup-d3-projection

## 这个分支做什么

followup-angle-composer spec（2026-08-17 §5/§8 P1）质检发现的最后一块缺口：
ask s03 已换 compose 心脏，但 D3 结构（P0 强势替代 / P2 瓶颈词）没接进投影——
B 槽在 ask 路径退化成 subject 级模板，点不了下一跳名字。本分支把 D3 结构对象
从构建处直通到选角，不从 Markdown 反解析。

## 改动

- `ask_blocks.py`：新增 `D3Structure` + `second_derivative_queue_for_llm`（文本+结构同源产出）；
  `_alternative_queue_pairs` 拆出 `(name, note)` 对，`name+note` 与原展示行逐字节一致；
  旧名 `_second_derivative_queue_block_for_llm` 保留为兼容包装。
- `ask_types.py`：`AskResult` 载 `d3_alternatives` / `d3_bottlenecks`（默认空）。
- `ask.py`：D3 消费点改用新函数，结构写回 result。
- `followups.py`：`project_ask_state` / `generate_followups` 增 `alternatives`/`bottlenecks` 参数，
  投影为 `AlternativeItem(source="d3_p0")` + `listed_names`。
- `api/app.py`：s03 把 `result.d3_*` 传入 `generate_followups`。

## 已验证

- 定向 65 + 触及面 183 passed（`test_ask_compose` / `test_workbench_api` / `test_live_probe` /
  `test_followups`，收据 `20260819T153814Z-72b99d99.json`）。
- 新测试 3 条：结构与文本同源（DB 夹具 + 无库回退）、投影进 B 槽点名下一跳、无 D3 时行为不变。

## 边界

- 未 live 验证（合并后由 8792 部署带出；行为差异只在 followup 卡 B 槽文案）。
- 未合未推（等用户确认合并）。
