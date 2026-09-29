# 在途交接 · feat/mutation-check-tool

## 这个分支做什么

`scripts/mutation_check.py`：spec 驱动的变异自检（锚点恰 1 处 → 基线 → 逐个拆门 → 点名测试须全红 → 原字节还原并核 HEAD）。#961 交接「下一步 3」。PR #965。

## 决策与被否方案

- 新建，不扩 `review_probes/run_extraction_mutations.py`：那条是证据级（冻结 revision + 临时树），判据「有红就算」。
- 原地改 + 原字节写回 + 写前 / 还原前核对文件；否 `git checkout --`（吞未提交实现）、否临时 worktree（慢、缺本地文件）。
- `.pyc` 三处删；否 `PYTHONPYCACHEPREFIX` 全隔离（每轮重编 stdlib / 三方包）。
- 注入 pytest 插件读结果；否解析 `FAILED` 行（参数化 id 能带空格）。
- 拒父目录符号链接与硬链接目标（独立审查补，702481725 / 040a4a261）；否只查末级 `is_symlink`（同字节仓外替身能过 status + blob）。

全表：`docs/handoffs/2026-09-29-mutation-check-tool.md`

## 当前状态

- 已推送：a7e159684 → 460ffe388 → f4eaad043 →（审查补丁）702481725 → 040a4a261 → 本提交（自检 spec 补 M31/M32、测试 docstring 读数、本交接）。PR #965 open，没加 guard。
- 全仓 Python：审查会话在五 PR 联合预览 83e88fb8433c（含 #965@040a4a261）上跑；040a4a261 之后本分支只动 yaml / 测试 docstring / docs。读数见 PR 评论。合入 main 待用户确认。

## 已验证

- @040a4a261：定向 25 passed（venv），ruff 通过；自检 32/32 KILLED，日志在 `~/.finance-runtime/reviews/mutation-check-tool-0929/`。

## 未验证 / 已知边界

- 信号屏蔽、还原后核验失败两层没有确定性用例（纵深防御）。
- `imported=false` 只是提示：子进程 / xdist worker 里的 import 看不到。
- 原地改树：同一棵树上的其他进程会短暂看到变异体。

## 下一步

1. 联合预览全量绿 + 用户确认 → 合入；红了先看是不是本 PR 的测试。
2. 合入后经用户同意：harness-reference 开分支改 `TOOLKIT.md` 三处 + vault 镜像（`check_refs.py` 读 finance `gitea/main`，必须先合）。

## 踩过的坑

- 别人会往本 PR 分支推修补：续作前 `git fetch` 比对远端，ff，不覆盖。
- pytest 默认转义非 ASCII 参数化 id，spec 点名不了 → 显式 ASCII ids。
- YAML `|-` 块按首行剥缩进：多行锚点从首个非空白字符写起。
