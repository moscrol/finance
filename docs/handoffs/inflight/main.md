# 在途交接 · main

更新：2026-08-12 · Cursor Cloud（经 exec 隧道操作本机）

## 这个分支做什么

上一份交接的根因已修并合并：#287 快照↔DuckDB 对账门禁、#288 词表三方审计、#289 措辞词表注入。今天 daily-full 主链已跑通。

## 当前状态

- main=bc669725 已推送，Mac 主树已 pull。**生产 8792 仍跑旧快照——合并≠部署**，要 `scripts/deploy_workbench_runtime.sh`。
- 未合并：#290 标注残片剥离、#291 daily-full 预检+逐步计时。
- daily-full 08-12 第三轮跑收据中（/tmp/daily-full-20260812.log）。跨日门抓到的两个窟窿已补：08-11 limit-heat、08-12 period_rank（写方 scripts/compute_features.py，不在 daily-full 内）。
- 08-01 验收产物复盘：15 FAIL = 6 题被 fulfillment gap 模板吞（C5 绑了 24 条证据仍被吞）+ ~9 题缺正典词/字段；无 stale/deadline 签名。**08-01 测的是引擎 B，08-12「证据不足」是引擎 A——两次验收不同引擎**。
- knevo 对照：五元素/缺数三档/闭环检索早已建成（BaseFinanceMode、closed_loop_retrieval），但**只在引擎 B；引擎 A（生产默认）零引用，被 08-08 cutover 孤儿化**。checklist 验收 4 条未勾。

## 下一步

1. deploy_workbench_runtime.sh 部署 + 重启 8792，health 对 source_revision。
2. 重跑 28 题验收：按 evidence_bound=0 分桶；run 产物记录 engine/backend（现在没有这字段）。
3. skill 收尾：audit_coverage.py + db_delta_export 到 iCloud。
4. 决定 #290/#291；设计题：BaseFinanceMode 质量层接进引擎 A。

## 踩过的坑

- exec 隧道有 CF ~100s 响应上限：长命令 nohup 到日志再轮询（scripts/rexec.py）。
- 非交互 shell 的 python3=系统 3.9（import 即崩）；.venv-workbench 无 akshare（第 4 步才暴露，白跑 7 分钟）。日常解释器 /opt/homebrew/bin/python3。→ #291 预检。
- 变异还原禁用 `git checkout <file>`（吞未提交改动）；同长度变异+同秒还原会命中 .pyc 旧字节码，先清 __pycache__。

## 已验证

- #287 门禁真数据正确 FAIL（快照 08-12 超前库 08-11 的活漂移现场）。
- #289 分支 .venv-workbench 全量 4571 passed / 4 failed，4 条均 main 固有或负载偶发。
