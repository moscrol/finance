# `/api/runs` 真实消费者盘点（W3 交付）

> 范围：谁在 **POST** `/api/runs`（引擎 B / `_run_ask`），以及谁只 **GET** 会话 run 的旁路。
> 检索：`rg "/api/runs" --glob '!**/static/**'` @ `gitea/main` 同源树。
> **不合并引擎。** UI 生产路径是 `POST /api/conversations`（引擎 A）。

## POST `/api/runs`（创建 ask 引擎 run）

| 消费者 | 路径 | 还在用吗 |
|---|---|---|
| **live_probe** | `intelligence/eval/live_probe.py` `post_ask`；wrapper `scripts/live_probe.py` | **是**。验收探针的 ask 车道。 |
| **webapp `createRun`** | `intelligence/webapp/src/api.ts` | **客户端还在，UI 不调。** `App.tsx` 只走 `createConversation` + `createConversationMessage`。构建产物里 POST `/api/runs` 是死代码（见 `docs/layered-rebuild-roadmap.md`）。 |
| **pytest** | `intelligence/tests/test_workbench_api.py` 等 | 是，测引擎 B 与 SSE/artifact 契约。 |

## 不 POST `/api/runs`（易误判）

| 名字 | 实际入口 |
|---|---|
| **smoke_workbench_self_use** | `POST /api/conversations` + `/messages`；再 GET `/api/runs/{id}/events\|report\|trace` |
| **eval acceptance** | `POST /api/conversations/{id}/messages`；再 GET `/api/runs/{id}/context\|trace` |
| **followups** | 会话路径写入 `followups.json`；`GET /api/runs/{id}/followups` 是读口。Ask 路径 `_run_ask` 也会写 followups。 |
| **checkpoint-recheck** | 夜间核对判断/foresight，**不打 Workbench HTTP**。 |
| **webapp 主界面** | 对话 API；随后 GET `/api/runs/{id}` / events / report / artifacts / followups / cancel。 |

## 结论（给后续「要不要留引擎 B」）

今天 **生产 UI 不创建 ask run**。还活着的 POST 消费者是：live_probe（marker 车道）、以及回归测试。删入口会砸探针与一批 API 测试，不会砸聊天 UI。
