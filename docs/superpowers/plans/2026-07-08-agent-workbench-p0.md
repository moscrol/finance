# Agent Workbench P0 实施计划（评审修订版）

日期：2026-07-08
状态：第 0 步已完成（Run/Artifact/Trace 协议 + run_store + golden 样例）；第 1 步待开工
关联：`2026-07-08-run-protocol.md`（协议正文）

## 与原设计稿的差异（评审结论落地）

1. **起点修正**：仓库已有 `intelligence/server.py`（stdlib JSON API）+
   `intelligence/web/`（猜你想问 SPA）+ `ask_chat.py`（多轮追问第一版）。
   Workbench 不是从零建 Web 层，而是**新增 FastAPI 服务与前端，档 A 保留不动**，
   等协议稳定后再评估是否合并。
2. **选型修正**：Next.js → **Vite + React SPA**（本地单用户工作台用不上 SSR，
   构建产物由 FastAPI 静态托管，少一个 Node 运行时）；后端 **直接 import
   `intelligence.services.*`**，不 subprocess 包 CLI。SSE 推送 step 流维持不变。
   > 教学：选前端框架先问"要不要服务端渲染"；不需要 SSR 时 Vite SPA 是 React
   > 生态默认答案，Next.js 是"React + 服务端"的答案。
3. **协议修正**：Run schema 增加 `session_id`（会话归组，ask_chat 已是此模型）、
   `parent_run_id` 提前到 P0、status 扩成五态状态机、`degrades[]` 一等字段、
   `manifest_ref` 引用（不复制）现有复盘 manifest；所有 UI 可见字段写入前脱敏。
4. **git 策略**：runs 落用户态 `intelligence/users/<id>/runs/`（已 gitignore，
   已登记台账地图）；协议 + 脱敏 golden 样例入库做回归。

## 实施顺序与验收

### 第 0 步（本分支，已完成）
- [x] 协议文档 `2026-07-08-run-protocol.md`
- [x] `intelligence/services/run_store.py`（单写入者、append-only trace、脱敏、原子写）
- [x] golden run 样例（脱敏）+ 协议回归测试（8 个用例全绿）
- [x] 台账地图登记 + .gitignore

### 第 1 步：包一条 ask 流
- FastAPI 服务（新增 `intelligence/api/`），`POST /api/runs` 创建 run，
  in-process 任务注册表（ThreadPoolExecutor 起步，不上 Celery），
  `GET /api/runs/{id}/events` SSE 推 trace step。
- service 层接线：`ask.answer_query` 执行中经 run_store 落 run/trace/artifact，
  CLI 直跑同样产 run（`--no-run` 可关）。
- 验收：前端（可先用最小静态页）输入问题 → 回答 + answer.md 产物卡片 +
  trace 时间线；**关掉 LLM key 全链路优雅降级**；浏览器刷新后凭 run_id 重放。

### 第 2 步：foresight 追问卡片（parent_run_id 已就绪）
### 第 3 步：theme-radar 接入 + 题材深拆模板
### 第 4 步：daily / verdict（run.manifest_ref 引用现有台账）
### 第 5 步：视觉打磨（消息级免责横幅、状态徽章、"思考了 N 秒"、行内可操作表格块）

## P0 不做（维持原稿）
登录/权限/云部署/实时行情/自动下单/重构知识库/重写老 HTML。

## 安全边界
不构成投资建议（消息级横幅）；不接下单；trace/run 所有可见字段写入前 `redact()`；
runs 目录不入 git。
