# 9 月 30 日行情恢复记录

截至 2026-09-30 21:23（UTC+8）。代码候选为 `65ab05505cd9fc32da917629b28efc7df91cf3d1`，PR https://github.com/moscrol/finance/pull/9 。此记录描述当时已经发生的动作；后续运行结果以收据和服务读数为准。

## 背景与发现顺序

用户将回答、模型及 harness 优化交给 Claude，本任务负责 GitHub/Gitea 环境和 8792 的运行准备。PR #5 已在全量检查通过后按既有授权合入，main 为 `94628fbe8`。

18:30 的 local 计划在同花顺板块 K 线请求中 TLS EOF 失败，S7 正确保留 09-29 的生产库。19:30 使用既有暂存库恢复，两次直接 `RemoteDisconnected` 绕过客户端的 `URLError` 捕获，整批失败。旧实现的新回归 15 项全红，因此缩小到标准库 GET 请求的异常边界修复。

两轴审查发现 HTTPError 的正文读取也会在 except 内断线。修复后 HTTPError 响应与普通响应共用读取边界，已知 429 只用状态和响应头，保持独立预算。响应被正确关闭后，重复失败的测试夹具改为每次创建新响应。

第一次候选真实续跑到约 550 个板块后持续 TLS EOF，有限次数耗尽，未发布。该模块到整批结束才提交这批少量增量，因此改用它已有的 `--resume --limit 200` 分块入口，不改数据代码。5 个分块、一次不限量完成检查、从 limit-pools 开始的完整剩余编排均成功。Mac 在 20:17–21:03 合盖睡眠，墙钟时长包含暂停。

21:15 同日门、跨日门和 09-29/09-30 独立数值审计均通过；核对生产文件身份及时间未变，先留 APFS 克隆和 SHA-256 收据，再用既有原子换库函数发布。8792 的 health/readiness 均 HTTP 200，数据库与快照同为 09-30，关键缺项为空。服务代码仍是干净的 `2c3949786568`，未部署回答候选或修改模型配置。

20:40 的 finalize 在 Mac 短暂唤醒时遇到恢复锁，以 75 退出。21:15 已用原 LaunchAgent 补启动，随后卡在读取网盘客户端登录库。进程采样及 TCC 日志确认 macOS App 数据授权等待，已向用户请求处理；截至此记录未宣称 L2/报告完成。

## 方案与理由

| 方案 | 评价 | 结果 |
|---|---|---|
| 扩展已有有限 GET 重试 | 能恢复瞬时传输故障，持续失败仍显式退出 | 采用 |
| 无限重试或提高到巨大次数 | 隐藏持续故障，也不能保存整批中间进度 | 否决 |
| 原生分块 resume | 成功块由原模块保存，避免网络中断丢整批 | 本次恢复采用 |
| 手改 SQL、跳过门或直接覆生产 | 无法证明语义、完整性和并发安全 | 否决 |
| 发布未合并代码为永久服务根 | 超出本次恢复且缺少合入/部署确认 | 未做 |
| 换进程绕开 macOS 隐私提示 | 不能替代系统权限授权 | 未做 |

## 验证与收据

任务输出根：`/Users/a77/Documents/Codex/2026-09-30/8-75693271-3d2b1ba99-github-agent-https/work/readiness-0930/`。

- `transport-red.log`、`http-error-red.log`：两次缺陷的红测试。
- `transport-final-v2.log`：126 项邻近回归通过；当时是最终夹具内容、提交前，不能冒充最终干净提交收据。
- `review-results.json`：标准/规格两轴；最初 HTTPError 的 P2 已修复。
- `gate-65ab05505/`：本机完整检查，Python 18745 passed、1 failed、78 skipped、2 xfailed；其他叶子通过。
- `gate-65ab05505-map-refreshed/`：刷新地图后同一探针仍失败。`code-map-sanitized-query.json` 证明测试启动器 PATH 缺 uvx；交互环境同一探针通过。保留失败，不改测试或删地图绕过。补全启动器后的结果单独记收据。
- GitHub 65ab05505：python、frontend、e2e、registry-check、workbench-check 均 success。
- `chunked-result.json`、`downstream-sync.log`：原生分块及后续编排完成。
- `publish-result.json`、`value-audit.json`、`after-publication.json`：三道门通过、备份/原子替换、服务实际 ready。
- `finalize-l2-process.sample.txt`：L2 在 SQLite open 等待 OS 授权；未包含登录值。

测试解释器为本任务 `work/finance-answer-quality/.venv-workbench/bin/python`（锁定依赖）；数据恢复使用现有夜跑解释器 `~/finance-workspace-private/.venv-workbench/bin/python`。后者 httpx 版本漂移未在共享环境中擅自升级。

09-29 申万 31 行业前收链问题随原生 20 日历史刷新修复，两日审计 FAIL=0、WARN=2。两个 warning 属于 09-29 的强势股数量和 turnover 空值率；09-30 的 300980.SZ 两源前收冲突保留缺口，不伪造补齐。

21:17 GitHub 代码及 9 张 PR 元数据完成新备份，GitHub/Gitea 的 main 同为 94628fbe8，候选分支同为 65ab05505。保留已删除 GitHub 分支的备份，但不推回 GitHub。

## 后续与工具沉淀

先处理真实系统授权、核对 finalize 的实际结果；检查最终本机全量收据，再等待用户对 #9 的合入决定。定时同步代码仍在旧快照，永久启用重试需独立按部署流程切换。不要重开 Claude 的内容实验，不要把 ready 或工程全绿等同于财务回答验收。

这次可复用的能力已进入客户端及回归；分块、锁、值审计、克隆备份和换库均复用仓库现有入口。任务目录的脚本绑定日期、文件身份和原故障库，只作为操作证据，不安装成另一套通用写库链。单次网络恢复不能推出性能改善趋势。
