# Chat-first Skill Workbench 本地私有站点运行说明

## 定位与边界

当前 Workbench 面向单机或受控私网研究环境。它已有用户目录校验、写入脱敏、
协作式取消和 Skill 超时，但**尚未提供生产级认证与服务端身份绑定**。因此：

- 只监听 `127.0.0.1`，或置于已有身份认证和网络访问控制之后；
- 不把端口、临时隧道或反向代理直接暴露到公网；
- 不将当前页面描述为公共 SaaS 或公开站点；
- 完成本文末尾全部安全门之前，不使用 `0.0.0.0`。

## 运行环境

- Python 3.10+；CI 使用 Python 3.12。
- Node.js 22。
- pnpm 10.12.1（仓库 `packageManager` 固定版本）。
- 推荐 Linux/macOS；命令以 POSIX shell 为例。

在仓库根目录准备 Python 环境：

```bash
python3 -m venv .venv-workbench
source .venv-workbench/bin/activate
python -m pip install -r intelligence/api/requirements.txt PyYAML "duckdb==1.4.3"
```

## 构建前端

Vite 将 React 构建结果写入 `intelligence/api/static/`，FastAPI 随后从同一端口
提供页面和 API。

```bash
cd intelligence/webapp
corepack enable
corepack prepare pnpm@10.12.1 --activate
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
cd ../..
```

开发前端时可在第二个终端运行 `pnpm dev`；Vite 会把 `/api` 代理到
`http://127.0.0.1:8788`。日常私有使用优先选择生产构建加单个 FastAPI 进程，
路径更短，也与验收环境一致。

## 数据与环境变量

### 用户运行时数据

推荐把 `FORESIGHT_USERS_DIR` 指向仓库外、权限为 `0700` 的绝对路径。每个用户
的持久数据位于该目录下：

```text
<FORESIGHT_USERS_DIR>/<user_id>/conversations/
<FORESIGHT_USERS_DIR>/<user_id>/runs/
```

未配置时默认写入 `intelligence/users/<user_id>/`；该目录已被 Git 忽略，但仓库外
目录更适合备份、权限隔离和避免误操作。`FORESIGHT_USER` 只设置本地默认用户，
不是认证机制。

### 研究数据

- 默认仓库根目录由应用源码位置推导。
- Daily Review / Daily Agent 仅读取
  `market_feature_store/exports/` 中的 canonical Markdown / JSON。
- `WORKBENCH_REPO_ROOT` 仅用于显式切换研究数据根目录，例如隔离测试 fixture。
- 不把会话、Run、DuckDB、凭据或真实用户数据提交到 Git。

### LLM 配置

不设置 LLM key 时，Workbench 会保留真实检索与 Skill 结果，并用确定性模板表达；
UI 会明确显示“未配置 LLM”。产品默认使用服务端托管的 GLM，可由 secret manager
注入以下变量，文档不提供任何值：

- `FORESIGHT_BUILTIN_LLM_API_KEY`：默认模型的 GLM Coding Plan 服务端密钥；
  也兼容既有
  `ZHIPU_API_KEY` / `GLM_API_KEY`。
- `FORESIGHT_BUILTIN_LLM_MODEL`：可选，默认 `glm-5.2`。
- `FORESIGHT_BUILTIN_LLM_BASE_URL`：可选；托管密钥默认使用
  `https://open.bigmodel.cn/api/coding/paas/v4`，兼容 key 默认使用普通
  OpenAI-compatible endpoint。

默认模型未配置时，继续兼容原有服务端 provider 自动探测：

- Provider key：`DEEPSEEK_API_KEY`、`MOONSHOT_API_KEY`、`KIMI_API_KEY`、
  `DASHSCOPE_API_KEY`、`QWEN_API_KEY`、`ZHIPU_API_KEY`、`GLM_API_KEY`、
  `OPENAI_API_KEY`。
- 通用 OpenAI-compatible gateway：`LLM_API_KEY`。
- 可选配置：`LLM_BASE_URL`、`OPENAI_BASE_URL`、`LLM_MODEL`、`LLM_TIMEOUT`、
  `LLM_THINKING`。

通用 `LLM_API_KEY` 的优先级高于 provider key；provider key 按应用代码中的固定
顺序选择。生产环境应只配置预期 provider，密钥只能存在于服务端 secret manager
或进程环境，不能写入仓库、日志、浏览器变量或前端构建产物。

“模型连接”面板还支持会话级 BYOK。用户密钥只保存在当前服务进程的内存中，
按用户隔离，不进入磁盘、Conversation、Run、日志或响应；服务重启后自动清除。
首版只开放固定的 HTTPS provider endpoint，不接受任意 Base URL，避免把 BYOK
接口变成访问内网地址的 SSRF 入口。

## 启动

先配置所需的非敏感目录变量和可选的服务端 LLM secret，再从仓库根目录执行：

```bash
python -m uvicorn intelligence.api.app:app \
  --host 127.0.0.1 \
  --port 8788
```

打开 `http://127.0.0.1:8788`。本地首版使用进程内 worker；不要启动多个 Uvicorn
worker 共享同一用户目录，否则当前单进程锁和取消信号无法提供跨进程保证。

## 健康检查

页面和 Skill Registry 都返回成功，才视为可用：

```bash
curl --fail --silent --output /dev/null http://127.0.0.1:8788/
curl --fail --silent http://127.0.0.1:8788/api/skills | python -m json.tool
```

第二条应返回包含 `daily-review` 与 `daily-agent` 的 JSON 数组。若根路径返回
`503`，先在 `intelligence/webapp` 运行 `pnpm build`。

## Self-use 真实运行 smoke

服务启动后，用 smoke 脚本创建一个 Conversation、发送 hybrid mode 问题、消费并
按 cursor 重放 SSE、检查终态与结构化 report：

```bash
python scripts/smoke_workbench_self_use.py \
  --base-url http://127.0.0.1:8788 \
  --user linxiaoqi5111 \
  --question "今天市场怎么样" \
  --timeout 180 \
  --output /tmp/workbench-self-use-smoke.json
```

输出 JSON 只保存聚合状态、Run ID、事件计数、report/model 元数据和 secret scan
结果；不保存问题正文、回答正文、完整 citation、Authorization header、API key
或用户私有路径。secret scan 仅扫描 RunStore/ConversationStore 已脱敏后的响应
字符串，命中时只记录字段位置和 marker 类型，不回显原值。summary 使用同目录
临时文件、`fsync` 和原子替换写入。

退出码：

- `0`：Run completed，包含显式 degraded completed；
- `1`：Run failed 或 cancelled；
- `2`：HTTP/SSE/report 协议异常，或 secret scan 命中。

## 公开部署前的安全门

以下项目必须全部设计、实现、测试并经过安全评审；当前代码中的路径校验和脱敏
只是纵深防御，不能替代这些边界：

1. **认证与会话**：接入 OIDC/OAuth2 或受信反向代理，使用安全 cookie、CSRF
   防护、TLS、短会话和撤销机制；所有 API 与 SSE 都必须鉴权。
2. **服务端推导用户**：`user_id` 必须来自已验证 token/session 的不可变 claim；
   忽略并拒绝客户端 query/body 中自报的 `user`，同时校验会话、Run 和 artifact
   的所有权。
3. **用户隔离**：为每个租户设置独立 namespace、文件权限和备份边界；增加跨用户
   IDOR 测试，禁止通过路径、ID、SSE cursor 或 artifact 下载越权。
4. **限流与费用控制**：按用户和组织限制请求速率、并发 Run、输入长度、输出
   token、每轮 Skill 数和日/月预算；provider 调用前后记录可结算用量并设置熔断。
5. **队列、取消与超时**：将进程内线程池替换为可恢复的持久任务队列；加入幂等
   key、并发上限、重试/死信策略，并把取消和超时传播到 Skill、检索和 LLM 网络。
6. **服务端密钥**：使用 secret manager 注入、最小权限、轮换和 provider 出站
   allowlist；禁止将密钥放入 `VITE_` 变量、响应、trace、artifact 或错误详情。
7. **审计、脱敏与保留**：记录身份、操作、资源、结果和费用但不记录 secret；
   对 prompt、引用、错误、SSE、日志和下载统一脱敏，并定义保留、导出、删除和
   安全事件告警流程。
8. **网络与运行隔离**：使用 TLS、安全响应头、可信代理列表、CORS allowlist、
   容器/系统用户最小权限，以及按租户控制的存储和备份加密。

只有安全门全部通过后，才可评估公网域名和多用户部署；在此之前，本服务保持
“本地/私有站点”定位。
