# capability-integration · 进度（换会话先读这里）

整包集成的接线工作树 `/Users/a77/fwp-wt-capability-i2`（分支 `feat/capability-i2`）。
本文记录 I2 的接线动作，不重复整张 spec（见 `../2026-09-09-capability-upgrade` 各单 progress）。

## 2026-09-09 · 本工作树已做两刀

### 1. B05-1 · turn_controller 把对话块传给 build_task_frame

状态：**已完成并提交**（`b2b6e619`）。

- `intelligence/services/turn_controller.py`：`decide_turn` 调 `build_task_frame` 时传
  `conversation_context=context if context else None`——空串保持旧调用方语义（未知，
  不追问）；真实入口空历史块带「（无历史消息）」字样，非空，走「已知为空」车道。
- `intelligence/runtime/turn_control_core.py`：`control` 在 `_frame_for` 引入 `context`，
  `_frame_from_decision` / `_frame_from_intent` 透传 `conversation_context`。
- 红→绿 3 例：`decide_turn` 绑材料引用、`decide_turn` 已知空上下文确定性追问
  （且旧语义不变）、`control` 绑材料引用。
- 读数：规则层 Q07 / C3#1 / C3#2 / R5 之前卡在这行（`../2026-09-09-capability-upgrade/progress/05.md`），
  接上后预期 12/12。
- 已有测试基线：`test_turn_controller.py` + `test_turn_control_core.py` + `test_task_frame.py`
  + `test_conversation_orchestrator.py` 437 passed。

### 2. 03 graph_lookup 适配 · mode 路由 + 结构化返回

状态：**代码与测试就绪，待提交**（本工作树未提交改动）。

- `intelligence/services/agent_research.py`：`build_graph_tools` 的 `graph_lookup` 支持
  `mode` 路由（`package/view/trace/compare/scope/legacy`）；`legacy` 是原行为（概念匹配+
  公司暴露，source=「本地知识图谱」）逐字节不变，默认保留；其它 mode 走知识库研究地图
  只读 Python API（`build_theme_package` 现算不落盘、`views.serve(auto_refresh=False)`
  不写库、trace/compare/scope 全只读），因此**不触发 CLI `package` 追加
  `access_log.jsonl` 的写副作用**（已双向实测：CLI package 增 1 行，import API 行数不变）。
- 研究地图命中的条目 source=「本地知识图谱·研究地图」，`internal_locator` 带页级定位。
  判官三条口径随之携带：关联≠兑现（`realization=unknown` 只转述）、unknown≠0
  （compare 的 unknown 格 value=null）、陈旧要声明（`recent.stale` / `view.status`）。
- KB 根从 `knowledge.resolved_wiki_root`（wiki 目录）推导到 `skills/lib`，用
  `importlib.util.spec_from_file_location` 按文件加载，绕开 KB 的 `rag/__init__` 重依赖。
- `_run_tool` 扩展 `mode` kwarg（只对声明 `mode` 参数的 runner 注入），主循环从模型
  args 提取 `mode`；`_TOOL_DESCRIPTIONS` 的 graph_lookup 描述补了 `mode` 说明。
- 只读红线：`/Users/a77/kb-wt-cap03-runtime` 的 `wiki/relations/access_log.jsonl` 全程
  行数不变，`research_map.db` 未创建。

### 测试

- 新增 `intelligence/tests/test_graph_research_map_modes.py`（13 例）：无 KB 桩 legacy
  不变、mode 注入不破坏、五种模式结构化返回、view 不写库、package 不追加 access_log、
  compare unknown 不输出 0、scope 返回读取范围。
- 新增 `test_p1b_runtime.py::test_loop_forwards_mode_arg_to_graph_lookup_runner`：模型
  JSON args 的 `mode` 透传到 runner。
- 全量 intelligence/tests：**7684 passed, 15 skipped, 1 xfailed**（收据
  `20260909T160649Z-b2b6e619.json`）；ruff 全树 0。

## 待办 / 未做

- 本工作树未提交改动（`agent_research.py` / `test_p1b_runtime.py` / 新测试文件）待提交，
  不擅自合 main。
- workbench 真实对话验收 graph_lookup mode 路由（spec I2「由关系包追到原页并用其中条件
  完成研究」）与应用级消费（`episode_tools` / RAG 主链已覆盖）未做：本刀只到工具与单测层。
- `service.md` 之后 06 主接调度——本单只交付工具合同。

## 命令

```bash
cd /Users/a77/fwp-wt-capability-i2
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider \
  intelligence/tests/test_graph_research_map_modes.py \
  intelligence/tests/test_p1b_runtime.py::AgentGraphToolsTests::test_loop_forwards_mode_arg_to_graph_lookup_runner
```
