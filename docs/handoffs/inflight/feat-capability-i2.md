# feat/capability-i2 · 在途交接（2026-09-10 覆写）

> 工作树 `/Users/a77/fwp-wt-capability-i2`，分支 `feat/capability-i2`。
> 任务来源：能力升级整包集成 spec
> （`docs/superpowers/specs/2026-09-09-capability-integration-and-live-research-design.md`，
> 本树承担 I2 接线）。**换会话先读**
> `docs/superpowers/plans/2026-09-09-capability-integration/PROGRESS.md`。

## 已交付（本分支四个提交，全部绿）

| 提交 | 内容 | 读数 |
|---|---|---|
| `b2b6e619` | B05-1：turn_controller/control 把对话块传进 `build_task_frame` | 437 基线 + 3 新例 |
| `330c2094` | 03 graph_lookup mode 路由（package/view/trace/compare/scope/legacy，全只读，KB 不写） | 7684 passed |
| `3bcf9841` | 材料身份超窗恢复分层 + 跨 240 字表格边界验收钉 | **7697 passed**, 15 skipped, 1 xfailed（收据 20260910T040601Z） |

材料身份超窗：`conversation_context_material_unrecoverable`（按对话块自带的截断自述标记）
区分「没材料」与「材料超窗」；后者走专属澄清（提示重贴），用户重贴原文时
`rebind_material_from_text` 按内容哈希重建同一 material_id，身份表如实标注重建来源。
不改对话块预算、不放宽 240 字模型可见上限。

## 唯一在途项：graph_lookup mode 真实对话验收

- **阻塞原因**：双网关均不可用（2026-09-10 11:52–12:09 共 4 轮探针）：
  8080 502/503 upstream（Plus-first 已生效但上游未恢复）；cockpit 57244 503
  `auth_unavailable` / 25s 超时。按踢醒（/tmp/k3-wrap-common.md）「5xx/429 就等，不连打」。
- **恢复条件**：任一出口连续 2×200（间隔 20s）。8080 先恢复则 8820 实例
  （pid 2091，已在跑本树 `330c2094`，graph_lookup 路径与本刀无关、无需重载）直接用；
  仅 57244 恢复才按踢醒用 `WORKBENCH_LAUNCHER=$HOME/.local/bin/start-finance-workbench.bak-20260909-pre-mirasim8080`
  重启本票 sidecar（8820；**禁止动 8792/8793/8795/8799/8801/8813**）。
- **验收命令**：`POST /api/conversations/{id}/messages` 真实对话门跑
  「由关系包追到原页并用其中条件完成研究」案例；KB `/Users/a77/kb-wt-cap03-runtime`
  **只读**（验收前后核 `wiki/relations/access_log.jsonl` 行数不变）；需
  `continuous-episode.json` 为证。降级模板 / 160 字 / `model_error` 不当能力失败，记原件。
- 解释器一律 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；
  凭证 `eval "$(grep '^export ' ~/.local/bin/start-finance-workbench)"`，cockpit key 走 keychain。

## 边界

- 不合 main、不动生产、不另开树。02 注册表契约文案归 04 合入后的注册表负责人
  （blocked/02 B-2），本单不动 `research_tool_registry.py`。
- spec 其余项（I1/I3/I4/I5、J1–J3、00 对照）各有负责人，不在本树范围。
