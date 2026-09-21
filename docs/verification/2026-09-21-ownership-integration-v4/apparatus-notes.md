# 本轮设施错误与边界

以下都发生在记录/核查工具，不是候选代码失败；原脚本与失败输出保留。

1. `assemble_candidate.initial.py` 在任何 merge-tree、ref 创建、worktree 创建前，错误地期待 `git show-ref --verify <不存在ref>` 返回 1；本机无 `--quiet` 返回 128，断言失败。观察缺失 branch/worktree 后，仅加 `--quiet`（缺 ref 返回 1），成功组装。工具返回的原 traceback 没有另存 stdout 文件；保留原脚本、错误文本与复核退出码于 `assembly-preflight-error.json`，不声称这份 JSON 是原始终端输出。
2. `check_inputs.initial.py` 错把六代 manifest 都当 `entries`；旧五代实际用 `files`，于是首个 archive 读取 `KeyError`，完整 stderr 保留 `input-check.log`。按实际 schema 兼容两种成员键后，`input-check-corrected.log` 记录成功；六代成员/大小/哈希/旧提交字节/候选副本全部一致。
3. 主检出没有 `scripts/run_frontend_gate.py`；最初探读返回 ENOENT。没有据此判项目无该能力；后续从冻结 v3 和本轮实际 v4 候选读取并执行存在的正式入口。

候选是 `git merge-tree` 的真实三方合并结果（每步 exit 0），随后以四个精确父提交生成新提交。该方式不触碰三张来源 PR 的索引；未声称经过普通 git commit hook。已在固定新候选上显式运行 `pre_commit run --from-ref <base> --to-ref <candidate>`，适用检查通过、源码不变，原日志保留。

工程门禁运行器仅为本轮有限记录器，不安装调度任务。Python 命令上限 3600 秒，frontend 1800 秒，registry/hook 每命令 300 秒；无自动重试。frontend 的第六步就是 E2E。运行器可在超时终止自己拥有的进程组，不是 OS 沙箱或文件访问隔离保证。
