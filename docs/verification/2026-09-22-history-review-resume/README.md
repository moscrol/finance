# #841 读取恢复后的独立审查尝试

## 结论

用户要求继续推进。本轮固定 `43511e3f15bd18bfd49868dfbac5b1d3774fd0bc`，先恢复只读工具入口，再各启动一次独立 Spec / Quality 静态审查。两条均实际读取源码，但在产出终稿前遇到 Codex 订阅用量限制，exit 1；状态均为 `BLOCKED_USAGE_LIMIT_NO_FINAL_REPORT`，不是 PASS，也不是代码 CHANGES_REQUIRED。作者不得代填独立结论。

| 轴 | 耗时 | 进程时限 | 退出 | 日志 exec 标记 | CLI 显示 tokens used | 终稿 |
| --- | --- | --- | --- | --- | --- | --- |
| Spec | 395.184s | 600s | 1，用量限制 | 35 | 92622 | 未产生 |
| Quality | 421.208s | 600s | 1，用量限制 | 17 | 201067 | 未产生 |

exec 标记是文本日志中的调用段计数，不代表成功检查数；CLI token 显示不等于收费 token 或实际价格。两条均未到外部时限，不能记为超时。错误原文提示 `try again at 5:04 AM`，只保存服务当时提示，不保证额度届时一定恢复。本轮不重试、不加购、不转付费提供商，不重开旧 K3。

## 工具恢复

原 `/Users/a77/.local/bin/codex` 是指向应用可执行文件的软链接，但同目录无配套宿主。本轮实际新增个人工具入口：

`/Users/a77/.local/bin/codex-code-mode-host` -> `/Applications/ChatGPT.app/Contents/Resources/codex-code-mode-host`

没有修改 `~/.codex/config.toml`、权限策略或服务配置。虽然是个人目录，这个入口会被该用户的其他命令行会话看到，不能描述为完全无全局影响。启动采用应用内 Codex 绝对路径，继续 `--ephemeral --sandbox read-only`；最小模型探针已通过 git 命令和源码读取确认完整 SHA 及 `RunStore.read_history_artifact` 签名。它仅证明传输与读取可用，不算审查通过。直接调用应用路径与补链接未做单变量对照，不声称已排除所有宿主解析原因。

此前一次将 `--ask-for-approval` 放在 exec 子命令后的命令在参数解析阶段 exit 2，未调用模型；修正后的最小探针成功。该初次错误及成功探针完整控制台输出仅在会话工具返回中，保存的是成功探针最终消息，不补造原日志。Codex 另报现存配置字段和 hooks 配置解析 warning，本轮未修共享配置。

## 证据

- `spec/quality-prompt.txt`：事先固定的范围、只读限制和终稿要求，两者不共享发现。
- `spec/quality-execution.json`：复用旧 `run_check.py` 得到的完整执行记录。进程前后均 SHA 全等、status 为空，`identity_stable=true`；环境仅继承 HOME/PATH，umask 022。
- `transport-probe.txt`：读取探针终稿。
- `summary.json`：机械提取的身份、退出状态、耗时、token 显示、磁盘采样及终稿不存在检查，不是 reviewer 报告。
- `EXTERNAL-SHA256SUMS`：绑定运行目录下完整 `spec.log`、`quality.log`，保留调用命令、源代码输出和用量错误；不将大日志重复塞进 Git。外置原件仍需另行备份，Git 哈希不是原件备份。
- `run_check.py.txt`：当时实际执行的旧记录器副本。其历史 docstring 写着 no network/model，描述旧用途，不能套给本轮 Codex 子进程；本轮确有一个读取探针与两次代码审查模型任务。
- `seal_resume.py.txt`：一次性版本绑定的归档工装，不是通用审查工具或应用新能力。

外部根：`~/.finance-runtime/reviews/react-trace-integration-20260921/history-review-resume-43511/`。没有 `spec-report.md` / `quality-report.md`，不创建冒名终稿。日志里的公开叙述只有开工说明，没有明确缺陷陈述或完成判断。源码输出证明发生过读取，不证明审查覆盖完整。Quality 的发现阶段列出了相邻树的 AGENTS 路径，故不声称文件系统读取范围完全隔离；本轮没有有效独立签字。

## 范围与尚欠

本轮新 pytest 执行 0、新金融应用探针 0。之前 599P 仍只属于 `64b0b48f`，f73 全量仍只属于 f73；43511 与 f73 的非 docs 差异为空也不移签收据。只读子进程采样最低 4253126656 bytes；检查前已低于原全量 6 GiB 停止线，未重跑全量、未安装依赖、未起服务或删缓存。共享磁盘变化不归因本次审查。

自然金融仍 not_passed：225/25 及有效分母理解、正文数字引用、判官实际消费未验。#793/#794、#833/#845联合组合不接管，不合 main/#832、不部署8792、不写生产、不关闭 PR。

## 后续预算核对

作者仅静态核对后续入口：`scripts/workbench_probe.py --timeout` 限制客户端轮询，不取消服务端 run；不要把它当硬停止。`intelligence/api/app.py::_continuous_turn_timeout_seconds` 读取服务端墙钟预算；`_deployment_execution_policy` 只会按档位提高 profile 的 max_llm_calls，不能假定任意 env 能向下设限。`conversation_orchestrator.py:1824` 建共享 LLMCallLedger，`llm_refine.py::try_reserve/_reserve_llm_call` 在实际请求前预占，重试/回退逐次计入。真实执行前仍须明确题目、模型、尝试硬上限及服务停止方案，并验证确实传到下游；本轮没有授权/实施新自然模型预算。

下一次独立审查须先确认额度和磁盘，再固定范围发起新任务；不能用本次中断日志补签，也不无限自动重试。旧六包和失败原件保持不变。
