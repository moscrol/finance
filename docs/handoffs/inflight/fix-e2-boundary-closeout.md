# fix/e2-boundary-closeout

## 这个分支做什么
按 v10 分片收口 E2 材料边界；开发树 `fwp-wt-e2-boundary-closeout`，主树不动。

## 当前状态
应用 P3e 修复已在 `0b83e14f` 提交，P3e 独立 QC 已通过并完成仓内归档；当前仅有产品门、作者收据说明、独立报告/证据归档与本交接的未提交文档改动，尚未推送、合并或部署。正式 T2→T3/Knevo 暂不运行。

## 决策与被否方案
- P3e 只判 `QueryResolver` 词典早读闸门；不把 41P/347P 外推成完整 P3，避免局部证据伪装成全链安全。
- 保留首次启动器误拒 41 次及日志；不以修正版收据覆盖失败历史，保证审查器自身故障可追溯。
- 独立报告、失败/修正版收据、启动器、补针和哈希入仓；不只在 `/tmp` 留证，避免临时证据丢失。
- 归档后再决定下一片；不直接进入正式 T2→T3/Knevo，也不把 controller 前 history/context 与 P3e 合并处理。

## 已验证
独立审查固定 `0b83e14f`：focused 作者测试+独立补针 41P、修正版禁止 IO 尝试0；相关八文件回归347P、禁止 IO 尝试0；改动 Python 文件 Ruff 通过。首次 focused 36 errors/5 failed，原因是 `/tmp` 与 `/private/tmp` 路径比较错误，原件已保留。报告见 `docs/verification/e2-boundary-closeout/p3e-query-resolver-20260915-independent-qc-20260915/`。产品门和作者 README 已更新为“独立 QC 完成、仅限本片”。

## 未验证 / 已知边界
P3 仍未完成：controller 前 history/context、静态路由/简称/日历先验、预取前歧义与不可恢复基底澄清、注入式 resolver、可信继承、四组九类来源过滤、恢复/压缩/子研究/非工具事实、确定性/legacy 回落及交付后读取。local_only 原题号槽和更多 runner、P4–P7、前端/E2E/完整 registry-check 未完成。不得将本片声明扩展到 `understand_query` 零 IO、真实入口隔离或产品验收。

## 下一步
1. 核对归档目录、哈希、产品门、作者 README 和本文件的 diff；仅按 pathspec 提交文档。
2. 提交后再决定下一片；若继续，先冻结 controller 前 history/context 与 QueryResolver 交界的小片，作者验证后独立 QC。
3. 合并/部署及正式 T2→T3/Knevo 均等待用户另行授权。

## 踩过的坑
每条 shell 显式 `cd`；pytest/ruff 使用 `.venv-workbench/bin/python`。审查器路径必须对临时根 `resolve()` 后比较；Python audit hook 不是 OS 沙箱，native IO 需另拦。相关回归 347P 不能替代完整 453P 隔离结论；各组收据不相加。
