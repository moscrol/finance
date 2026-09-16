# 02 · 阻塞与跨轨诉求

本轨 engineering_complete 不受下列项阻塞；它们是接线与定稿依赖，列出责任单与续跑步骤。

## 1. P12「01 真输出」目前是在途版本（责任：01 / 02 续跑）

- 现状：`/Users/a77/fwp-wt-judgment-maintenance-01`（分支 `feat/judgment-maintenance-01`，代码基线 5fb13a8c，`judgment_maintenance/` 目录**未提交**且仍在编辑）。2026-09-13 06:40Z 用其 `assess()` 跑自带合成夹具 `fixtures/research_evolution/01/complete/input.json`，产物零改动通过 02 适配与排序，已冻结为 `intelligence/tests/fixtures/research_evolution/02/from_01_inflight_assess_report_synthetic.json`（含 01 六个文件的 sha256 前缀）。
- 未满足的部分：01 尚无最终 SHA；输入是合成的（field 效果不可据此宣称）。
- 续跑步骤（01 定稿后，任何人可做）：
  ```bash
  W=<01 最终树>; PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
  cd $W && PYTHONPATH=$W $PY -B -c "import json; from intelligence.services.judgment_maintenance import assess; d=json.load(open('intelligence/tests/fixtures/research_evolution/01/complete/input.json')); r=assess(**{k:d[k] for k in ('owner_user_id','as_of','knowledge_cutoff','bindings','evidence_versions','condition_observations','policy')}, generated_at='<UTC>'); json.dump(r.to_dict(), open('/tmp/jm.json','w'), ensure_ascii=False, indent=2)"
  ```
  然后把 `/tmp/jm.json` 放进夹具的 `report` 键、更新 `_provenance`（最终 SHA），重跑 `pytest -k research_priority`。若 01 改了 `change_type/reason_code/status` 枚举或 `object_ref/EvidenceVersion` 键名，`test_p12_real_01_assess_output_flows_through_unchanged` 会红——那是真差异，改 02 适配表（PROGRESS §1）而不是改测试期望。

## 2. 06 接线（责任：06）

- 端点 `GET /api/conversations/{id}/research-evolution` 的 `priority` 段：调用 `adapt_candidates` + `prioritize` + `render_view`；`evaluation_at` 取服务端可信 UTC；owner 来自部署允许的用户上下文，不信请求正文。
- 来源读取归 06：01 报告、`research_project.load_project(...)`、`research_queue.load_research_queue(...)`、`data_requests.build_requests(...)` + `check_requests` 状态；02 只接对象。
- `effort_estimates` 与 `request_bindings` 目前没有生产来源：前者待 05 的观测耗时或用户估时，后者待 06 的 DependencyBinding 建立后按 request_id 映射。缺它们时任务 `effort=unknown`、补数请求 `legacy_unbound`——这是如实状态，不是缺陷。
- 用户点击/完成的存储与 05 事件归 06；02 不因点击改任何判定。

## 3. 05 关联（责任：05）

- 事件按 `task_id` + `policy_version`（当前 `research-priority-policy/v1`）关联；02 未产出任何「预期收益 / 概率」，05 评价「同等质量下完成时间/漏检/无效执行」时按版本分列。

## 4. 无

- 无公共源模块修改诉求；无白名单外写入；未复制任何旧模块。
