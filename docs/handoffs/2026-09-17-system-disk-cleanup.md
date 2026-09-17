# 2026-09-17 整盘低风险清理与工作树回收

## 背景与授权
上一轮保守清盘已在 `3f259337` 留痕，可用空间由约 5.4 升至 28.3 GiB。本轮用户要求查看整盘，盘点后授权「你按照最优路径推进，不要错删」。选用可再生成缓存优先、工作树逐项证明可恢复的路径；不以最大释放量为目标。

独立审查树：`docs/qc-8792-readiness-0917`。原始证据目录：
`~/.finance-runtime/reviews/disk-cleanup-system-20260917/`。
本文是本轮执行结果；上一轮记录 `2026-09-17-disk-cleanup.md` 不覆写。

## 整盘盘点及排除项
目录占用与可释放物理空间不同，以下不加总：
- Cursor 图形端与 CLI 大量占用来自会话库、聊天、代码快照；不是普通缓存。主状态库约 6.45 GiB、CLI 聊天约 13.1 GiB 均保留。
- 金融项目 348 棵注册 worktree；107 棵位于 `/tmp`。其中 8 棵有未提交内容，部分 `git status` 干净的树仍有被忽略的用户数据库。拒绝按目录年龄批量删除。
- `finhot` 两树 `node_modules` 约 12.8 GiB；即便无打开文件也不证明没有使用者，整套已安装依赖保留，只做原生包缓存清理。
- 废纸篓有旧行情库，Cursor staging 有大代码快照，回滚目录有认证/状态库。恢复用途未证明可放弃，全部保留。
- Devin、Grok 的 ShipIt 载荷是比当前安装版更新的待安装版本，进程仍活跃；保留。
- HuggingFace 检索模型被代码引用，保留。swap、系统更新快照不手动动；Data 卷无本地 APFS 快照。
- WorkBuddy/Jarvis/CC Switch 等旧备份不在本轮执行范围。Homebrew 仅预览，无实际清理动作。

## 按执行顺序
### 1. 固定基线与文件级白名单
保存 8792 health、五容器状态/挂载/启动时间、工作树注册清单和文件系统空间。逐项检查 lsof、进程参数、软链及启动器引用，校验文件身份和 SHA256；不持久化无关进程完整参数，避免泄露凭证。

完成 **20 个文件/目录目标**：
- 9 个 `codex-runtime-install-*/node-runtime.tar.xz` 残留包，payload 均为空；只删包，不删 `codex-primary-runtime`。
- 7 个 Electron 下载 ZIP；已安装的 Electron 不动。
- Cursor Agent 最旧两版 `2026.08.11-e8db854`、`2026.08.31-4057e58`；当前 `2026.09.08-6caf4ff` 和上一版 `2026.09.02-c22c1a3` 保留，前后可执行文件 SHA256 一致。
- `Downloads/Claude.dmg`、`Grok_Bot_0.51.0.dmg`：确认 `/Applications` 已安装同身份且更高版本，检查挂载无进程占用后正常 `hdiutil detach`，不 force eject，再删镜像。

证据：`file-cleanup-receipt.json`。执行器 `cleanup-low-risk.py` 是一次性证据附件，不是通用删除工具。

### 2. Docker 明确的闲置构建产物
使用本地 Alpine 镜像，在无网络、只读根文件系统、drop capabilities 下只读挂载两个待审卷。实际结构确认：`sub2api-gomod-cache` 是模块下载/源码缓存，`sub2api-gobuild-cache` 是 Go 编译缓存。

复查无任何容器引用后，精确 `docker volume rm` 两卷；另删无容器依赖的 `golang:1.27.0-alpine`。不执行 `system prune`、不清其他匿名/具名卷、不重启 Docker、不强制 trim。

Docker 内部约 3.038 GB 缓存加 0.36 GB 镜像空间可回收，但宿主回收异步，不能把内部逻辑量视为即时释放量。证据 `docker-cleanup-receipt.json`。

### 3. 包管理器原生整理
- `uv cache prune --offline --no-config`：移除 22,851 文件，工具报告 1.7 GiB；没有 `--force`。
- `npm cache verify`：回收 63,583,281 字节无效缓存；保留 npx 环境。
- pnpm 10 `store prune`：移除 13,286 文件/294 包。
- pnpm 11 `store prune`：核对全局虚拟存储项目引用，移除 1 个未引用全局包及 128,523 文件/3,092 包，工具报告 2.77 GB。

首次进程守卫见 `npm run start -p 3000` 就安全中止，0 清理操作。核实是已经运行十天的原服务器，只豁免该精确 PID/命令后续跑；没有终止服务或关闭安装并发检查。

证据：`package-prune-receipt.json`（首次中止）、`package-prune-receipt-resumed.json` 和 `prune-*.log`。工具报告不是独立物理回收量，pnpm/APFS 共享内容不能与目录大小简单相加。

### 4. 逐项证明可恢复的旧验收 worktree
107 棵临时工作树先做 status（包含未跟踪文件）、ignored 完整清单、提交祖先、进程/启动器引用盘点。最终只取 **29 棵**：
- detached HEAD，无命名分支，无锁；根目录超过 72 小时；无最近代码改写。
- HEAD 及 reflog 的所有 old/new 提交都已被固定 `gitea/main@0a1cb8c4` 包含。
- tracked/untracked 均干净，无 assume-unchanged/skip-worktree、无 submodule；每个 tracked 文件逐字节算 Git blob 哈希与 index 核对。
- ignored 只有 Python 字节码、pytest/ruff 缓存，无用户数据或额外产物。
- 无打开文件、cwd、进程参数及启动器引用。

第一遍安全闸因 29 棵 Git 私有日志均在当日 10:05:25 重写而跳过，**没有删除**。进一步逐条读取日志中的实际 Git 事件时间：全都超过 72 小时，内容仍只有已合提交。改用实际事件时间和 old/new 提交可达性判活动，只有这两种已审日志路径免除文件修改时间判据；其他近期写入仍拒绝。没有把不明日志修改原因编造成事实。

删除前归档每棵私有 Git 元数据及 pytest/ruff 缓存，并保存精确 revision、tracked 文件校验与恢复命令。之后 `git worktree remove <路径>`，**不带 `--force`**。其他工作树和分支均不动。

证据：`worktree-removal-receipt-v2.json`、`worktree-metadata/`。旧 `worktree-removal-receipt.json`/attempt1 表示安全跳过历史，不是最终状态。

## 验证及实际空间
- 本轮开始 **28.31 GiB**，最终三次间隔 5 秒读数均约 **36.67 GiB**，净增加约 **8.36 GiB**；`df` 使用率约 **94% → 92%**。
- 这是整机可用空间净变化，不排除并发写入、swap 波动、APFS 共享及 Docker 异步回收。中途曾见 37.2 GiB，不能用最高瞬间读数代替最终值，也不能累加各工具报告冒充归因测量。
- 工作树注册 **348 → 319**；差集恰为批准执行的 29 棵，所有剩余注册项逐字段不变。29 个 revision 对象和元数据归档哈希仍可验证。
- 实际抽一棵 revision `2d16a7f76382dd0aecf9b7f46bb05cbbe9f89529` 重建 detached 工作树，3,969 个受控文件、status 干净；随后正常移除测试恢复树。见 `worktree-restore-smoke.json`。一次抽验不冒称 29 棵全部恢复演练。
- 8792 healthy，revision `bf662e9310ff751a4c31763815ee78fb7d6d5122`，source_dirty=false、code_matches_repo=true。
- sub2api/PostgreSQL/Redis 健康、rsshub 运行；wechat2rss 原先退出状态保持。五容器的镜像、挂载、启动时间均未改变。
- 金融 venv 依赖 import 通过；finhot 的 TypeScript/Vite/Next/Electron 安装路径可解析；3000 npm 服务仍在。仅冒烟检查，不是重跑全仓测试或真实模型验收。
- 生产库、用户数据、聊天/会话、Cursor 快照及回滚、检索模型、已安装 node_modules、上一轮留下的五份 Gitea 备份均未列入本轮删除操作。

最终凭据：`final-verification.json`、`df-final.txt`、`docker-df-final.txt`、`worktrees-final.txt`。

## 后续与被否方案
| 方案 | 结论 |
|---|---|
| 可再生成缓存先清，纯代码工作树逐项证据后移除 | 采用；降低空间压力且保留恢复路径 |
| 因缓存路径/同名/旧日期而直接整删 | 否；缓存根也能承载运行时，Git ignored 也能藏用户库 |
| 全删聊天或 Cursor staging、清空废纸篓 | 否；用户强调不误删，未证明可放弃历史/恢复点 |
| 为凑释放数字重启服务、清 swap 或强制回收 Docker VM | 否；无必要且会影响正在使用的服务 |
| 只看 reflog 文件 mtime 判活跃 | 否；文件重写时间与实际 Git 操作时间不同，应查事件与提交可达性 |

到此停止削减。此次一次性脚本与完整白名单留在持久审计目录，不能作为通用 prune 脚本直接重跑；没有安装定时清理、改变长期保留策略或扩大到其他人的在途树。代码质检 F1/F2/F3、行情新鲜度和真人验收边界仍未解决，见原 8792 质检报告。
