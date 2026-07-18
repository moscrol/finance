# Workbench P1 Retrieval, Data Producer and Followups Plan

**目标：** 消除 BGE-m3 重复冷加载，把 AkShare 从 API 环境拆成独立数据生产者，并升级 followup 展示/执行契约。

## Task 1：Followups v2（先行、低耦合）

- `Followup` 新增 `label`（最多 20 个中文字符）和 `full_prompt`（完整用户口吻）。
- 保留 `question` 作为一个版本的兼容 alias；API 同时输出三字段。
- LLM schema 改为生成 label/full_prompt，parser 兼容旧 question。
- React 按钮显示 label，点击提交 full_prompt。
- Python、组件与 E2E 测试验证“短展示、长执行”。

## Task 2：Persistent Hybrid RAG worker

- 新建独立 worker 协议：`health`、`query`、`shutdown`；请求/响应均带 schema version、request id、deadline。
- worker 进程启动时加载索引/BGE-m3，后续 query 复用；客户端超时或协议错误时降级现有 CLI。
- 使用 loopback HTTP/Unix socket 二选一：本机优先 Unix socket（不开放网络端口），测试用内存/loopback transport。
- readiness 暴露 worker 状态、模型加载次数、index revision；worker 崩溃可重启，满足 P0.5 的硬进程边界。
- 验收：连续两次 query 只有一次模型加载，热查询延迟显著低于冷查询，故障注入可降级 CLI。

## Task 3：AkShare 独立 data-source 环境

- 新建幂等 bootstrap/run 脚本，环境位于 runtime data-source venv，不安装进 Workbench API venv。
- provider chain：canonical producer > AkShare complete fallback > 保留旧 complete；partial 只写降级状态，不覆盖 complete。
- LaunchAgent 模板只生成到 repo 文档/模板，不自动安装；安装和启用属于 canonical 部署步骤。
- 代理失败记录 provider/error/attempt，不伪报 fresh/ready。

## Task 4：验证

- 全仓 Python、前端 lint/typecheck/unit/build、三尺寸 E2E。
- 冷/热 RAG benchmark、worker crash/restart、CLI fallback。
- AkShare complete/partial/failed/provider precedence 与 dry-run LaunchAgent。

本计划按 1 → 2 → 3 顺序执行；每个 task 独立提交。
