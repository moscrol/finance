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

状态：**已完成并提交**（`330c2094`；撰写本行时原文误标「待提交」，已合入本分支）。

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

## 2026-09-10 · I2 收口：材料身份超窗恢复 + 表格跨界验收钉（`3bcf9841`）

### 3. 材料身份超出最近完整消息窗口后的处置分层（spec I2 新增验收）

状态：**已完成并提交**（`3bcf9841`）。

- `user_task.conversation_context_material_unrecoverable`：按 `ConversationContext.to_prompt_block`
  自带的「（前 N 字符已省略…）」如实自述标记，区分「对话里确实没有材料」与「材料正文
  被截出窗口」——两者此前同判成 MISSING_MATERIAL，现在分开。
- `task_frame.build_task_frame`：题面引用材料 + 对话块已知被截断 → 新歧义
  `MATERIAL_OUT_OF_WINDOW_AMBIGUITY` + 专属澄清 `MATERIAL_OUT_OF_WINDOW_CLARIFICATION`
  （提示重贴原文或给材料 id），不编身份、不靠无限扩大窗口达标；澄清回答沿用
  `resolve_task_frame_clarification` 的材料合并车道。
- `user_task.rebind_material_from_text` / `detect_reposted_material_gap`：本轮重贴原文
  时按内容哈希重建同一 `material_id`（与窗口内轮次得到的 id 逐位相同，无持久化）。
- `episode_factory.assemble_input_understanding_context`：截断 + 重贴场景身份表如实标注
  「按本条消息重贴内容重建…（对话块已截断，与此前同一内容的材料 id 相同）」。
- 测试 +4（红→绿）：不编身份 / 专属澄清措辞与缺材料车道分开 / 重贴重建同 id /
  身份表溯源标注。

### 4. 跨旧截断边界的表格实例验收（spec I2「先复用现有分段机制」）

状态：**验收通过，现有机制覆盖，不改投影、不放宽 240 上限。**

- `test_table_crossing_truncation_boundary_delivers_header_and_units_to_model`：
  12 行表格必跨 240 字模型可见边界，断言每片表头带单位列（元/吨、亿元）、
  关键行（762 / 1570）完整送达——02 深读的「按行分片 + 每片带表头」机制成立。
- `test_table_slice_truncated_overwide_row_is_flagged_not_silent`：锁「超宽行截尾
  必带省略号、不静默丢列」这一判官可见口径。
- web_fetch 发布主体/文档类型口径：02 已在证据标题与观察值首句带出
  （`classify_web_source`，progress/02 §实施）；注册表契约文案归 04 合入后的
  注册表负责人（blocked/02 B-2），本单不动注册表。

### 5. graph_lookup mode 真实对话验收（Workbench 8820）

状态：**网关阻塞，未跑；命令与条件已就位。**

- 8820 实例在跑本树代码（`source_revision=330c2094`，未含本刀——本刀不影响
  graph_lookup 路径，无需为这次 live 重载），env 指向 8080 / sol，判官已修
  （`LLM_JUDGE_GROK_SANDBOX=off`）。
- 探针（2026-09-10 11:52–12:09，按踢醒「两条都探、2×200 才发题」）：
  8080 502/503 upstream（Plus-first 已生效但上游仍不可用）；cockpit 57244
  503 `auth_unavailable` / 超时。**两侧连续 4 轮均不可用，按「5xx/429 就等，
  不连打」未发题。**
- 恢复条件与命令：8080 或 57244 任一连续 2×200（间隔 20s）后，经
  `POST /api/conversations/{id}/messages` 真实对话门跑「关系包追到原页」案例
  （KB `/Users/a77/kb-wt-cap03-runtime` 只读，不许产生 access_log 写入），
  需 `continuous-episode.json` 为证。8080 先恢复则 8820 不用动；仅 57244 恢复时
  按踢醒用 `WORKBENCH_LAUNCHER=…bak-20260909-pre-mirasim8080` 重启本票 sidecar。

### 读数

- 全量 intelligence/tests：**7697 passed, 15 skipped, 1 xfailed**（收据
  `20260910T040601Z-330c2094`）；ruff 全绿；pre-commit 11 道全过。



## 待办 / 未做

- graph_lookup mode 真实对话验收（spec I2「由关系包追到原页并用其中条件完成研究」）：
  网关阻塞中（见 §5 恢复条件与命令）。
- `service.md` 之后 06 主接调度——本单只交付工具合同。

## 命令

```bash
cd /Users/a77/fwp-wt-capability-i2
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider \
  intelligence/tests/test_graph_research_map_modes.py \
  intelligence/tests/test_p1b_runtime.py::AgentGraphToolsTests::test_loop_forwards_mode_arg_to_graph_lookup_runner
```
