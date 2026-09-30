# 全局盘点更正：GitHub 云端与跨机交接 · 2026-09-30

接替 `2026-09-30-project-wide-closeout-plan.md` 中测试隔离的过时状态，并补覆盖范围。用户指出云端已经完成实现，本次从 origin 实际取回并核对，纠偏已写项目学习层。

## 已查明并完成

- GitHub origin 实际是公开仓 `https://github.com/moscrol/finance`，不能沿用旧私有仓名或默认私有。Gitea 与 origin 的 main 均为 `7569327143a9a40ff44da32d723865b062d856e6`，生产仍 `2c3949786568`，主干之间无需补合或重新部署。
- 同步前 origin 591 条分支、Gitea 590 条，590 条同名分支全部同 SHA；唯一缺项是 `claude/test-isolation-tmpdir-hw7e8h`。本次已取回其两个提交并复制到 Gitea，双端读回均为 `4129bdad96d55c9e1b5da8bc281247cabbff6335`。
- `12ec68c11a184dc6908f10c2154bb40b0a1bad5b` 修改嵌套 gate 的 TMPDIR；`4129bdad` 修改根 conftest 的全局 autouse fixture，对所有使用 tmp_path 的测试增加目录权限收尾。应写“实现完成，验收未完成”，不再派人重写，不称小范围测试改动。云端两份全量仍需完成收据，未合主干、无需部署。
- GitHub 三条 claude 分支已覆盖：legacy-worktree-cleanup 是 main 祖先；hithink 同名修复在 main `659ce1a1e`，后续由 Gitea #894 接替，列历史清理候选。GitHub 草稿 #3 与 Gitea #956/#966 分属不同编号空间。
- Mac 原测试位于 `.claude/worktrees/unclosed-session-stats-838ac4`，仍有一份未提交差分。已保全到 `/Users/a77/.finance-runtime/reviews/remote-consistency-20260930/mac-uncommitted-main-gate-test.patch`（2135 bytes）。它额外断言伪共享临时根不被修改；云端版本未逐字包含该断言，故暂未删除。
- 本机脏 main 未覆盖。新增干净文档树 `/Users/a77/.codex/worktrees/remote-sync-handoff-0930/finance-workspace-private`，分支 `codex/dual-remote-handoff-0930`，只放协作规则、AGENTS 入口和可公开的共享交接。

## 发布边界

完整本机审计及本分支历史只归档到 Gitea，不把内部路径/运行原件所在的整枝推至公开 origin。共享版在文档分支的 `docs/handoffs/2026-09-30-project-wide-closeout-shareable.md`，供 GitHub / 云端 / 手机读取；其链接以推送后的固定提交回读为准。双远程协作规则见同枝 `docs/workflows/dual-remote-collaboration.md`。

本次可共享分支保持两端同 SHA，私有归档分支是明确例外。不是用强推或全量镜像消除差异。

## 尚未完成

1. 云端候选与 main 基线的全量完成收据及独立验收；根 conftest 的测试生命周期改动要按实际影响面审。
2. Mac 补充断言是否被候选证据充分覆盖；确认前保留原树和备份。
3. 旧 garbage-* 一次性清理。修复只预防新累积；仍需确认原作者清理命令、点名目标和并发进程状态，本次没有猜命令或删除目录。
4. 本机 doctor 发现 httpx=0.25.2、锁文件=0.28.1，未改共享环境；云端与 Mac 不能只凭相同代码 SHA 互签测试环境一致。
5. 文档分支尚未合主干，不能声称所有 agent 已自动加载新规则；GitHub 主干保护还须单独落实既有 AGENTS 的公开仓要求。

远程 heads 原始清单保留在 `/Users/a77/.finance-runtime/reviews/remote-consistency-20260930/remote-heads-before.json`。没有新模型调用、测试重写、主干合并或生产切换。
