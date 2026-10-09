# Pi 原生 + Knevo Skill 层（验证臂）

这一入口在 Pi CLI 挂载常驻 `finance-mode` 和四个按需读取的专项，数据走与 8792 同源的工具注册表。
它是隔离验证入口，不改 8792、不写生产库、不持久化个人记忆。接入生产及质量放行另验。

设计：`docs/superpowers/specs/2026-10-09-knevo-skill-layer-design.md`。
当前读数：`docs/handoffs/inflight/fix-knevo-pi-runtime-1010.md`。

## 首答

先提交源码，选择新的树外产物目录。用工作区事实报告的 Python 解释器运行：

```bash
python integrations/pi/run_native.py prepare \
  --root <新产物目录> --db <源库.duckdb> \
  --question-file <问题.txt> --as-of 2026-09-30 \
  --today 2026-10-09 --rag-bindings <受管代际绑定.json>
python integrations/pi/run_native.py run --root <产物目录> --dry-run
python integrations/pi/run_native.py run --root <产物目录>
```

`prepare` 固定提交号、runner/kit/skill 哈希、APFS 只读克隆、问题、截止日、模型与调用上限，复制 RAG 绑定并固定端点摘要。
`run` 前后校验源码仍干净且这些输入未变；已经启动的目录不能重跑。真实验证使用受管 RAG 绑定，`off` 仅用于离线测试。
凭证从现有启动器的 export 行读取，不执行启动器、不落盘密钥。

默认只验证方法论层。`prepare --second-look` 另开一次自检续写，`--subagents` 另开研究派单；它们是独立实验变量，按需分批验证。
子任务共享根模型/工具调用上限及绝对截止日，带相同工具参数说明，只能读取自身挂载的专项，不再派单。
失败、取消、长度截断、没有终稿的子任务都不作为成功结论；局部失败在主线程可见。

## 验证与产物

```bash
python -m pytest -q tests/test_pi_native_runner.py tests/test_pi_finance_extension.py \
  intelligence/tests/test_knevo_skill_layer.py
```

Pi 子进程测试只连本机模拟接口，不调用付费模型。没有 Pi CLI 的环境会明确跳过子进程测试，不能把跳过算作已验证。
测试覆盖工具真实可见性与调用、skill 读取、自检停止、子任务参数传递和错误传播、读路径限制、冻结校验及完整 runner/bridge 往返。

产物包括 `plan.json`、`pi/answer.md`、`pi/events.jsonl`、工具与脱敏模型请求/响应、`RESULT.json` 和哈希清单。
`RESULT.status=completed` 只说明完整终稿、模型身份和执行完整性成立，`quality=UNREVIEWED` 仍需全文核验。
`skill_reads` 只计成功读取，调用尝试不冒充已读取；空答案、错误停止、型号不符和输入变化会非零退出并保留现场。

内容验收检查：全集边界、量价与资金的区别、指数贡献依据、反证可观测性、缺口声明。
字数和调用数不代替质量。同题对照还要固定代码、模型参数、数据库、截止日和工具上限；n=1 不签总体胜率，失败不重抽补绿。

## 边界

- 验证入口使用独立 Pi 配置目录，显式工具白名单，不加载全局扩展或项目资源。
- 子进程仍运行在当前用户权限下，继承模型传输所需环境；这是可信本机验证，不是操作系统沙箱。
- `--offline` 停止 Pi 的自动目录联网，不会阻止模型请求。
- 本入口使用隔离的新用户空间，不据此宣称个人记忆召回或跨轮 report/track 已验证。
- Pi JSON 模式可能在模型报错时退出 0，必须同时核对停止原因；一次自检的状态按用户输入重置。
