# FinArena 邀请试运行

## 范围与隔离

入口是 `intelligence.arena.app:create_app`，不是现有 Workbench API。前端为 `intelligence/webapp/arena.html`；单独构建到 `dist-arena`。默认只监听本机，不修改 8792 服务，不访问生产 DuckDB 或投研用户目录。

本版实现研究结果的匿名对比、一次性邀请评审、投票账本、观测胜率、用户题目队列、运营调用两个 Agent、审核发布及撤销。策略只做事前登记，不做成交、净值或收益结算。不是完整的金融能力认证，也不是公开互联网部署。

采用 FastAPI（Python HTTP 服务）和 SQLite（单机事务数据库），复用已有 React、Vite 和 lucide-react。SQLite 适合低并发邀请试运行；多实例部署、账户恢复和高并发运营前应迁移到 PostgreSQL 与正式身份系统。此库不与现有 Workbench SQLite 混用。

## 本地运行

从仓库根目录执行。独立 worktree 可让 `PY` 指向主树解释器；不要使用缺依赖的宿主 Python。

```bash
export PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
pnpm --dir intelligence/webapp arena:build
$PY -m uvicorn intelligence.arena.app:create_app --factory --host 127.0.0.1 --port 8816
```

浏览器：`http://127.0.0.1:8816/`。端口占用时另选端口，不终止其他服务。

默认数据：`~/.local/share/finance-arena/arena.sqlite3`。可设置 `ARENA_DATA_DIR` 为独立目录；API 与运营命令必须使用同一目录。数据库、邀请码和运行材料不提交 Git。备份使用 SQLite backup API 或停机后备份，运行中不要只拷贝主文件而忽略 WAL。

首屏有四套明确标记为人工编写的虚构教学题。正式榜初始为空；启动不会生成正式票或虚构 Agent 成绩。访客的会话存在 HttpOnly Cookie 中，30 天过期；清除浏览器数据后不能恢复身份和原记录。

## 用户参与

- 游客可查看共同材料、比较两份回答，选择 A/B 更好、同样好、都不够好或跳过。手机提供回答切换页签。
- 正式票要求先兑换一次性邀请码。邀请码由运营方签发，不要求上传姓名、账户或机构资料。
- 正式对战也允许游客试评，但游客票永远不转为正式票。
- 投票后揭晓参赛身份与内容指纹；同一会话对同一场不能重复计票或改票。
- 用户可提交无隐私或保密信息的题目，经审核后用于公开匿名评测；此动作不触发付费调用。
- “我的评测”保存当前会话的投票与题目状态；题目发布后可直接进入该题评测。
- 举报只进入运营复核队列，不自动改分。现阶段没有自动裁决或完整申诉系统。

签发邀请码：

```bash
$PY -m intelligence.arena invite --label first-reviewer --days 7
```

邀请码只在命令输出中显示，数据库保存哈希。不要在公开文档、版本库或运行截图中发布邀请码。一个邀请码不等于一个经实名认证的自然人；邀请方仍须控制签发、披露关联关系并人工检查串票。

## 运营闭环

```bash
$PY -m intelligence.arena queue
$PY -m intelligence.arena run --agents /private/agents.json --task /private/task.json --question-id QUEUED_QUESTION_ID
$PY -m intelligence.arena runs
$PY -m intelligence.arena publish --match run-RUN_ID --reviewed-for-identity-and-data-rights
$PY -m intelligence.arena reports
$PY -m intelligence.arena invalidate --match run-RUN_ID --reason '发现身份泄露，撤销本场并保留回执'
```

自建题目省略 `--question-id`。用户队列题的 `question` 与 `category` 必须完全匹配；运行预占在外部调用前提交，已执行题目不允许重复发起以挑选结果。状态为 `pending -> running -> review -> published`，失败为 `failed`，撤销为 `withdrawn`。失败重试需新的明确运营决策及新的任务记录；没有自动重试。

`run` 并行调用两个参赛版本，成功与失败都留记录。终端输出运行编号不代表成功，须用 `runs` 核查状态。输出未经运营审核不可见。`publish` 自动检测正文中的登记名称，但只能作为辅助检查：别名、自报供应商、引用网址、题目和材料泄露仍须人工审核。运营还需确认材料、模型输出和产品评测的授权。

### 参赛配置

```json
[
  {
    "participant": {"id": "alpha", "name": "Alpha Agent", "version": "2026-09-v1", "kind": "agent"},
    "protocol": "arena-v1",
    "endpoint": "https://alpha.example/arena",
    "api_key_env": "ARENA_ALPHA_KEY"
  },
  {
    "participant": {"id": "baseline", "name": "Reference Model", "version": "pinned-version", "kind": "model"},
    "protocol": "openai",
    "endpoint": "https://provider.example/v1",
    "api_key_env": "ARENA_BASELINE_KEY",
    "model": "pinned-model-id"
  }
]
```

这里只是协议示例，不是已接入的产品。配置必须恰好两个不同版本；OpenAI 兼容接口是模型对照，不标成完整 Agent。密钥从环境变量读取，不写入运行记录。地址由运营配置，不允许访客指定任意 URL。

默认仅允许 HTTPS 与解析到公网的地址，不跟随重定向、不使用环境代理。`--allow-local-endpoints` 只为受控本机测试放行 loopback；它不是对私网任意访问的许可。应用层 DNS 检查不能代替网络出口隔离，公网部署需防 DNS 重绑定并限制出口。

### 任务

```json
{
  "question": "利润增长与经营现金流下降并存时，应如何核实盈利质量？",
  "category": "financial",
  "as_of": "2026-09-18T15:00:00+08:00",
  "evidence": [
    {"title": "经授权的材料标题", "content": "完整可公开的材料正文。", "source": "可追溯来源与发布时间"}
  ]
}
```

`category` 为 `financial / industry / event / strategy`。双方收到同一任务与材料。`as_of` 是任务声明，并不证明远程 Agent 未用未来数据。本版没有沙箱工具轨迹审计，正式结果应理解为“远程接口可追溯”，不是“隔离环境可核验”。

### arena-v1 服务契约

平台向参赛服务发 `POST /runs`：

```json
{
  "request_id": "平台运行编号加参赛版本指纹",
  "task": {"question": "问题", "category": "financial", "as_of": "截止时间", "evidence": []},
  "limits": {"timeout_seconds": 120, "deadline": "带时区的绝对时刻"},
  "anonymous": true
}
```

立即返回 `{"run_id":"remote-id","status":"running"}`，或带完整答案的 `completed`。随后平台每秒 `GET /runs/{run_id}`，终态为 `completed / failed / cancelled`。完成格式：

```json
{"run_id":"remote-id","status":"completed","answer":{"content":"原始 Markdown 研究正文，至少 20 字符。"}}
```

超时会尽力 `POST /runs/{run_id}/cancel`；远程取消成功与否不作保证。默认总执行时限 120 秒，可通过 `--timeout` 设为 1 到 600 秒；取消请求最多额外等待 2 秒。响应预算 250KB，答案上限 40000 字符。不索取私有思维链；本版也未实现附件、结构化引用、完整 token/费用核算或多轮会话协议。材料和原始答案保存在本地运行账本，公众只得到经过白名单清洗后的正文。

## 胜率口径

观测胜率 = 胜 / (胜 + 负)。平局、双差单列；演示、游客、跳过、撤销对战不进入正式统计。撤销保留原票与回执，但立即移出统计。同一问题仍可能存在不同参赛组合，本版不提供对手难度校正或重复题聚类估计。

题目覆盖按问题、类别、截止时间与材料的联合指纹去重，不把重复运行算作新题。少于 30 个胜负票、10 位评审或 5 道有票的去重题目，标记“样本积累中”；超过门槛也只叫“描述统计”，不是显著性证明。按名称排列，不据此宣布实力排名。没有 Bradley-Terry、置信区间、评委独立性校正或机构专家认证。用户偏好不等于事实准确率，更不等于投资收益。

## 策略登记

运营命令为 `$PY -m intelligence.arena register-strategy --file /private/strategy.json`，字段以 `intelligence/arena/models.py::Strategy` 为准：证券代码与目标权重、基准、带时区的起止时刻、规则、参赛版本和来源运行。

登记必须早于生效时刻，同一 ID 不可覆盖；总权重不超过 100%，不允许重复证券或无效数值，身份必须属于已完成的来源运行。**这是运营登记，尚未自动验证策略字段与原始答案一致。** 股票池边界、信息截止、调仓规则、成本假设需要运营在规则正文中明确；没有机器可执行的完整策略合同。

本版不计算 T+1、涨跌停、停牌、费用、容量、成交或收益；列表收益始终为空。下一阶段应建立统一成交账本和滚动前向观察，再接入策略榜。不能用手工补历史收益绕过这一边界。

## 验证

```bash
$PY -m ruff check intelligence/arena intelligence/tests/test_arena.py intelligence/webapp/arena_e2e/serve.py
$PY -m pytest intelligence/tests/test_arena.py -q
pnpm --dir intelligence/webapp lint
pnpm --dir intelligence/webapp test
pnpm --dir intelligence/webapp arena:build
WORKBENCH_PYTHON="$PY" pnpm --dir intelligence/webapp arena:e2e
```

浏览器测试使用独立临时库和 8826 端口，里面的参赛结果是固定测试夹具，绝不能用于正式服务。截图与失败轨迹在 `intelligence/webapp/test-results/`。启动实际服务后可用 `node intelligence/webapp/arena_e2e/smoke.mjs` 做七档宽度与素材检查；该脚本不投票。证据缩略图为本地生成的虚构材料封面，可用 `node intelligence/webapp/arena_e2e/make-evidence.mjs` 重建。

公网开放前还需独立域名、HTTPS、反向代理限流与请求体限制、网络出口隔离、账户与恢复、数据留存/删除政策、独立评审治理、真实 Agent 授权及适配验收、备份恢复和负载测试。设置 `ARENA_ALLOWED_HOSTS`、`ARENA_PUBLIC_ORIGIN` 后仍不等于这些要求已满足。不得直接把现有 Workbench 生产服务暴露给访客。
