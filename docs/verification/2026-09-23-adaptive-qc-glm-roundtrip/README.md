# #75 / PR #868 GLM 准入往返失败

宿主状态：**BLOCKED_GATEWAY_TOOL_ROUNDTRIP**。没有新的独立 Spec / Quality verdict，不能合入或部署。

## 身份与结果

- 固定候选 `31f1b40dd788d36c71da249d59fb769c50d7cd30`，baseline `9a02279863733c9b9f60fd92fcc7e840fa83f878`，候选干净只读。
- 新私有根 `/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1830/`；旧 K3 / GLM 原件未改，不续签。
- 实际模型 `glm-5.3`，现有智谱官方直连，私有 shim 19899；请求显式传 `reasoning_effort=low`，不声称服务端关闭 thinking。
- 真实请求 4：小载荷 1、pi 往返 3；全部完成，传输失败 0、自动重试 0。此处 completed 只指传输完成，不是任务成功，也不是计费收据。
- 正式 Spec / Quality 请求均 0；作者测试 0、审查产品探针 0、自然金融题 0。离线工装自检另账，不算产品验证。

## 失败证据

1. `gateway-observations.json`：首个 pi 响应同时提交 read 和 write，write 参数已经写入猜测字符串，尚未观察 read 返回。
2. `spec/gateway/commands/001-read/` 与 `002-write/`：读取随机 fixture 成功，首次写入内容与其不同。
3. `003-write/`：下一轮试图改写正确内容，create-only 文件工具以 `FileExistsError` 拒绝；错误原件未覆盖。
4. `spec/gateway/REPORT.md`：模型最终回显正确 fixture，也承认首次猜测错误。终端文本正确不能替代落盘副本正确。
5. `spec/gateway/receipt.json`：exit 0、无超时，但 tool_executions=3、written_copy_matches=false；准入失败后停止，未启动后阶段。

## 工装检查与缺口

两轴沙箱、假上游适配、结构化提交 mock 自检通过，真实模型请求为 0。检查包含外网/生产/凭据访问拒绝、限定回环端口、失败退出码保留、阶段预算及重复提交拒绝。

复核发现 **run_stage.py 的 `--tools read,bash,write` 未包含 `deliver_stage`**。pi SDK 的 `allowedToolNames` 会据此过滤扩展工具；直接调用工具的 mock 没有覆盖实际 CLI 菜单。这不是本次 gateway 失败原因，但会阻塞尚未运行的正式终稿链路。工装只作证据快照，不推广为可用生产 runner。后续须在新输入快照里修复允许名单，并以真实 pi 启动、零模型请求的工具菜单检查验证。

后续准入还应由工具状态机强制“读到结果后才开放写入”，不能只靠提示词要求顺序；保留本次失败，不覆盖原件重判。

## 合入边界

`merge-check.json`：分支 `da8ab92325e5a1ba72aef2e22d07dffeff3ed869` 对最新 `gitea/main=b59d6eed0356ae093b52bd291ab328628de8790e` 的 `merge-tree` exit 0，无文本冲突。只检查合并形状，未跑联合树测试，也未实际合并。

全量工程收据仍只属 `7ad61a0d3`，45P 仍只属 `2f4b5f089` / `2c61ff825`。L6 仍 **NOT_PASSED，实际 1/1/0**。当前 head 完整门禁、联合树测试和最终独审仍缺失。

167 份原件归档逐字节一致，`archive-manifest.json` 可复核；密钥扫描无命中。模型思考正文只留私有原始流，未复制进仓库。私有进程退出，19899 已释放；本批未改产品或生产配置。
