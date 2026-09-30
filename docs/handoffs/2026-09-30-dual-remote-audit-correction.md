# 全局盘点更正：GitHub 云端与跨机交接 · 2026-09-30

接替 `2026-09-30-project-wide-closeout-plan.md` 中测试隔离的过时状态，并补覆盖范围。用户指出云端已经完成实现，本次从 origin 实际取回并核对，纠偏已写项目学习层。

**本轮后续更正优先**：最终 fetch 查到云端已推进 bca700858 / 3d2b1ba99，但现有强制镜像将远端退回4129。两提交已从本地远程跟踪日志保全，并用普通快进恢复双端到 `3d2b1ba99af6f8ca180de2524ebf58f5dd8d62ea`；Mac 原补充测试已经纳入，函数语法树一致，原树仍保留。收据为本次证据目录 `cloud-recovery.json`，bundle 为 `cloud-test-3d2b1ba99-preserved.bundle`。因此下文4129/测试尚未纳入是较早阶段状态，不能用于当前派工。最新共享交接在文档树本地77763c433，Gitea #991 正文已补恢复事实；为了避免继续触发回退，文档最后补丁暂未推，停用强制镜像确认项待用户答复。

## 已查明并完成

- GitHub origin 实际是公开仓 `https://github.com/moscrol/finance`，不能沿用旧私有仓名或默认私有。Gitea 与 origin 的 main 均为 `7569327143a9a40ff44da32d723865b062d856e6`，生产仍 `2c3949786568`，主干之间无需补合或重新部署。
- 同步前 origin 591 条分支、Gitea 590 条，590 条同名分支全部同 SHA；唯一缺项是 `claude/test-isolation-tmpdir-hw7e8h`。本次已取回其两个提交并复制到 Gitea，双端读回均为 `4129bdad96d55c9e1b5da8bc281247cabbff6335`。
- `12ec68c11a184dc6908f10c2154bb40b0a1bad5b` 修改嵌套 gate 的 TMPDIR；`4129bdad` 修改根 conftest 的全局 autouse fixture，对所有使用 tmp_path 的测试增加目录权限收尾。应写“实现完成，验收未完成”，不再派人重写，不称小范围测试改动。云端两份全量仍需完成收据，未合主干、无需部署。
- GitHub 三条 claude 分支已覆盖：legacy-worktree-cleanup 是 main 祖先；hithink 同名修复在 main `659ce1a1e`，后续由 Gitea #894 接替，列历史清理候选。GitHub 草稿 #3 与 Gitea #956/#966 分属不同编号空间。
- Mac 原测试位于 `.claude/worktrees/unclosed-session-stats-838ac4`，仍有一份未提交差分。已保全到 `/Users/a77/.finance-runtime/reviews/remote-consistency-20260930/mac-uncommitted-main-gate-test.patch`（2135 bytes）。它额外断言伪共享临时根不被修改；云端版本未逐字包含该断言，故暂未删除。
- 本机脏 main 未覆盖。新增干净文档树 `/Users/a77/.codex/worktrees/remote-sync-handoff-0930/finance-workspace-private`，分支 `codex/dual-remote-handoff-0930`，只放协作规则、AGENTS 入口和可公开的共享交接。

## 发布边界

后续实查推翻了“只推私有 Gitea 可保密”的初始判断：该仓已有面向公开 origin 的 push mirror，提交触发开启、周期 8 小时。本分支 d45671f2e 曾因此短暂出现在 GitHub，确认双端仍为自己的原提交后，已依次撤下本轮新建的 Gitea / GitHub 引用。本地分支与工作树保留，取消了本分支 upstream；不要再把此枝推入这个带公开镜像的 Gitea 仓库。

保全 bundle：`/Users/a77/.finance-runtime/reviews/remote-consistency-20260930/private-review-preserved.bundle`，已通过 `git bundle verify`，包含 d45671f2e，依赖主干已有的 4de44009af6de4619573a3e35984d3477228a9df。读回证据在同目录 `remote-heads-contained.json`：双端各 592 条分支、无差异。引用移除不代表公开对象/缓存已清除；没有重写远程历史或修改镜像设置。

共享版在 `codex/dual-remote-handoff-0930` 的 `docs/handoffs/2026-09-30-project-wide-closeout-shareable.md`，镜像处置另见同枝 `2026-09-30-remote-mirror-boundary.md`。该枝适合公开且双端同步；完整原件保持本地。最终可读链接以最新提交回读为准。

## 尚未完成

1. 云端候选与 main 基线的全量完成收据及独立验收；根 conftest 的测试生命周期改动要按实际影响面审。
2. Mac 补充断言是否被候选证据充分覆盖；确认前保留原树和备份。
3. 旧 garbage-* 一次性清理。修复只预防新累积；仍需确认原作者清理命令、点名目标和并发进程状态，本次没有猜命令或删除目录。
4. 本机 doctor 发现 httpx=0.25.2、锁文件=0.28.1，未改共享环境；云端与 Mac 不能只凭相同代码 SHA 互签测试环境一致。
5. 文档分支尚未合主干，不能声称所有 agent 已自动加载新规则；GitHub 主干保护还须单独落实既有 AGENTS 的公开仓要求。

远程 heads 原始清单保留在 `/Users/a77/.finance-runtime/reviews/remote-consistency-20260930/remote-heads-before.json`。没有新模型调用、测试重写、主干合并或生产切换。
