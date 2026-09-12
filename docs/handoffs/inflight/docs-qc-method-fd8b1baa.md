# PR #738 · fd8b1baa 质检

## 这个分支做什么
独立审第五轮/跨会话修复汇报；只写审查文档，不改实现或生产。

## 决策与被否方案
- 固定 PR 头 fd8b1baa，不把作者树未提交续修计入验收：中间状态可能是变异试验。
- 暂不放行；不以旧提交全绿、单测重跑绿覆盖当前组合全量红及确定性缺陷。
- 保留旧 CLI 兼容，但 help 失败不能冒充能力不存在。
- 详情与证据见 `docs/handoffs/2026-09-12-method-closed-loop-fd8b1baa-review.md`。

## 当前状态
远端 PR 头两次核实为 fd8b1baa；比 607f53a6 仅增交接文字，代码未变。作者树有他人在途续修，未碰；本枝只含两份质检文档，不推送/合并。

## 未验证 / 已知边界
- P1：active.json=[] → CLI 崩溃 rc1 → 夜跑调用默认 daily，无告警（本轮再现）。目录/悬空链误判 unset 的前轮问题仍在。
- P2 新证实：receipts._fsync_dir 吞目录 os.open 的任意 OSError。注入 EIO，首次/重试/竞态输家均无异常返回，目录 fsync 未执行。
- P2：help 失败仍当无 active 能力，调用默认且无告警（本轮再现）。
- P2：证伪目录内 [] 文件被静默跳过，report rc0 宣称空库；0字节/非UTF8场景已修。
- 前轮坏 protocol 导致 active 两种输出模式判定不一致、迁移命令缺参/非可执行脚本直跑/编号问题均未改。
- 未跑全量、真实夜跑、生产迁移/写库；故障注入不等于证明断电已丢数据。

## 已验证
冻结树定向 3P/84 deselected，收据 `~/.finance-runtime/test-receipts/20260912T101041Z-fd8b1baa.json`；相关 Ruff/zsh 语法通过。原 fsync 失败后重试探针通过。
作者干净全量收据核实：22c60030=9435P/0F；607f53a6=9436P/1F；同一失败用例其后连跑三次各1P。不能据此认证全量绿或负载为唯一原因。
旧快照2efdff46的 active --help 本轮再测rc2，不是0。
证据 `/tmp/method-qc-fd8b1baa-evidence/`，真实 Shell 只替换 daily/通知为spy。

## 下一步
唯一收口人提交续修，补目录open/fsync分点、坏结构、help失败及真实Shell行为测试；修迁移命令，压缩原inflight（23023字节）。固定新头复验后再跑安静全量，不抢跑、不停别人的进程。

## 踩过的坑
三份1P收据是同一用例三次，不是三个不同失败项。目录helper被调用≠目录已同步。Bash spy避免宿主zshenv污染隔离用户根；被测Shell仍为zsh。本轮只审，未将临时探针落地为实现回归门。
