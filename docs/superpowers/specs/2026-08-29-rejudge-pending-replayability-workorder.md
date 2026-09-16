# 2026-08-29 rejudge pending 行可重放性修复工单（占位）

> 来源：2026-08-29 rejudge 积压清账（97 行，sol 判官离线重放，汇总
> `intelligence/eval/runs/20260829T140500Z-rejudge-drain-sol.json`）。
> 状态：**已修复（同日收口，台账行 `R-20260829-04`，分支
> `fix/rejudge-pending-replayability`）**。修法=方向 A+B：行内内联
> judge_request+published_answer（行即夹具，工件删除后仍可离线重放）、
> episode_task_id 从 artifact 自带的 contract 免费取（adapter 调用点零改
> 动）；`replayable_pending_rows()` 分（可重放, stale）两组不改写索引；
> CLI `--export-fixtures` 固化清账准备步（stale 行拒绝导出）。既有 49 条
> 旧式行如实归 stale。

现象：97 行积压里只有 44 条可清账——`append_pending_from_artifact` 落行时
`run_id`/`artifact_path` 双双为 None（adapter 调用点不传；私有 artifact 里
也没有 run_id 键），judge_request 又不随行存储。工件一旦被清理或搬家，
积压行就只剩 sha 指纹，**永远重放不了**（本次 49/93 唯一 sha 即此形状）。

修法方向（认领者定）：
- A. 落行时内联存 `judge_request`（压缩后 KB 级，索引在家目录不进仓）；
- B. adapter 调用点补传 run_id 与 artifact_path（run 目录路径它拿得到）；
- 倾向 A+B 都做：A 保证独立可重放，B 保留可溯源。

判据：新产生的 pending 行在工件删除后仍可离线重放；`has_judge_request`
字段语义改为「行内自带请求」；既有 49 条不可重放行如实标注 stale 不硬清。

红线：索引仍在家目录（gitignore），不进仓；不改已发布答案。
