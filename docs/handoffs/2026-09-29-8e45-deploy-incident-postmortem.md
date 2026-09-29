# 2026-09-29 · 8e45 运行树被旧版部署脚本镜像覆盖 — 事故复盘

> 执笔：Arena agent 会话（exec-a77 默认端点），2026-09-29 16:00 HKT。
> 性质：生产事故复盘 + 已落地修复记录。证据全部来自本机一手日志。

## 一句话结论

9/29 00:01–00:04，一个夜间 agent 会话在 runtime 软链指向 8e45 worktree（PR #952
验收树）的状态下，经 remote_exec 隧道执行了主工作区里的 09-08 旧版
`scripts/deploy_workbench_runtime.sh`。旧版「脏源只警告 + 无 git 树目标闸门」，
`rsync -a --delete` 把停在 09-08 的脏主工作区 `intelligence/`（约 300 个未提交
改动）整树盖上 8e45，造成 763 处变更、**−204,670 行**（≈ 09-08→09-28 的 main
进展被回滚），并触发服务崩溃循环。**事故链，非人为破坏。**

## 时间线（HKT，证据可回放）

| 时间 | 事件 | 证据源 |
|---|---|---|
| 9/28 12:13 | 8e45 worktree 创建（PR #952 merge head），之后 runtime 软链指向它 | 目录 birth；`workbench.err.log` 崩溃堆栈路径 |
| 9/28 23:06–23:57 | 夜间会话（arena.ai agent，默认 profile 桥）做 closeout/git 考古（#955/#958 线），期间模型实测 gpt-6-sol / super-nova-ext 交替 | `.arena-bridge/desktop.log`（写入/执行/模型检测全留痕） |
| 9/29 00:01–00:04 | **rsync 镜像覆盖**：`/api/exec` POST 密集（00 时 67 次）| `/tmp/cc_exec_server.log` |
| 00:02:05 | 客户端 3 次超时断开（BrokenPipe），服务端命令继续跑 = 长命令指纹 | exec 日志 traceback |
| 00:02:32 / 00:04:01 | rsync 进程两次（超时→重试）PID 49548/49549、50135/50136 | 统一日志 `log show` |
| 00:05:43 | `start-finance-workbench` 启动器被创建，与 exec 调用**秒级对齐** | 文件 birth vs exec 日志 |
| 00:0x | kickstart → 崩溃循环：8e45 时代 Run 记录带 `maintenance_launch` 字段，09-08 代码 `Run.__init__` 拒收 → TypeError | `workbench.err.log`（50197→…→55590 重启链） |
| 00:07:44 | 夜间会话最后一次隧道调用 | exec 日志 |
| 00:55:47 | PR #958（docs，worktree_closeout 回执）由 a77 合入——与覆盖**无因果**（纯时间巧合） | gitea merge commit `180df3b15` |
| 11:02–11:06 | 晨间恢复：launcher 修改 → 新 worktree 62fad + 软链新建 → deploy-probe 验证 | 文件 mtime/birth；`workbench.log` |
| 13:0x–13:47 | 前一会话取证时误删 6 棵 worktree（含活树 62fad）→ 次生事故；13:47:30 重建恢复 | exec 日志；62fad birth |

## 根因链（五个条件叠加，缺一即不发生）

1. runtime 软链指向了 git worktree（应为 standalone 快照）；
2. 主工作区停在 09-08 且脏（rsync 源=工作树当前内容）；
3. 磁盘上的部署脚本是 09-08 旧版（无闸门；main 版已有双闸）；
4. 夜间会话在 1+2+3 同时成立的窗口执行了它；
5. zsh/rsync 不在 run_command 白名单 → 部署只能走 remote_exec 隧道（该路径
   客户端有超时重试，放大了伤害窗口并掩盖了错误回执）。

## 已落地修复（本会话，均有验证记录）

1. **闸门回植**：主工作区 `scripts/deploy_workbench_runtime.sh` 补两道闸——
   闸门A `$SNAP/.git` 存在即拒绝（只许写 standalone 快照）；闸门B 脏源默认拒绝
   （需显式 `WORKBENCH_ALLOW_DIRTY_SOURCE=1`）。T1/T2/T3 实测通过（假目标 +
   假服务标签，生产零接触），`zsh -n` 通过。原版备份：本地 `archive-8e45/`。
2. **8e45 重置**：7 项独有未跟踪文件先归档（`/Users/a77/incident-archive-20260929/`
   tar，sha256 `ed447474…cd6d319`；py 源码另有副本），随后 reset+clean，
   验证 0 脏条目、HEAD `8e45e299a`、曾删文件全部复活。PR #952 本体仅 8 文件
   +508/−99，且已是 main 历史，无丢失。
3. **服务恢复验证**：8792/8796 healthy，`source_dirty=false`，
   `code_matches_repo=true`（R-06 达标）。

## 次生事故与教训（前一会话，已修复）

删除 6 棵 worktree 前未查引用，误删软链目标 62fad → 8792/sidecar 等服务
SIGTERM。**教训：删任何 `.finance-runtime/` 下的树之前，必须先 grep 软链、
launchd、脚本引用。** 修复后 worktree 注册表无残留（41 条全对齐）。

## 遗留事项

- **remote_exec 令牌回归**：10:47 启动的默认桥实例 env 缺令牌（12:37 版 main.cjs
  已加文件回退 `remote-exec-token`，14:48 该文件已就位）——旧实例重启后自愈。
- **夜间会话身份**：证据指向默认 profile 的 arena.ai 会话（closeout 主题，
  gpt-6-sol 为主），remote_exec 不落 desktop.log 属设计行为，最终命令文本不可
  复原；残余可能性：远端 rx.py 持令牌客户端（服务器日志不记客户端身份）。
- **8e45 验收**：树已还原干净，但原始验收协议随夜间会话计划丢失——建议先定义
  验收清单再跑，勿盲目执行。
- **RAG 索引建在脏源上**（source_dirty=true，41 个未提交文件未入索引）——
  既有状态，另行处理。

## 证据索引

`/tmp/cc_exec_server.log`（5.5 万行隧道调用）·
`~/.local/share/finance-workbench/workbench.{log,err.log}` ·
`~/.arena-bridge/desktop*.log`（逐条写入/执行/模型检测）·
统一日志 rsync PID 记录 · `/Users/a77/incident-archive-20260929/`
