# 在途交接 · main

更新：2026-08-12 · Cursor Cloud（经 exec 隧道操作本机）

## 这个分支做什么

上一份交接的根因已修并合并：#287 快照↔DuckDB 对账门禁、#288 词表三方审计、#289 措辞词表注入。今天 daily-full 主链已跑通。

## 当前状态

- **main=b89df3e2 已推送（#287–293 七个 PR 全合并），Mac 主树停在 5b7464be——合并≠部署，隧道 530 断连挡住了 pull+deploy**。恢复后跑 `git pull && ./scripts/deploy_workbench_runtime.sh`。
- daily-full 08-12 三道门全绿、日报已出、audit_coverage 今日全表覆盖；快照↔DuckDB 对账 PASS。iCloud 导出已废弃（correction 已落，SKILL.md 已改）。
- A 组冒烟（5b7464be，backend=continuous_glm，run=20260812T131457Z）：**证据链已通（7/10 绑定 3–15 条）**，真值仍 0/7，12 条失败全在 fact 层（数字没进正文）→ #293 修此；#292 修 gap 答案中间档。
- knevo 对照：BaseFinanceMode/closed_loop_retrieval 只在引擎 B，**引擎 A 被 cutover 孤儿化**；#292/#293 是接线第一批。

## 下一步

1. 隧道恢复后：Mac pull + deploy（目标 revision b89df3e2）。
2. 重跑 A 组对照：fact 层 12 条红是否下降 = #292/#293 的直接判决。
3. A3 个股深挖 terminal failed（证据=0）待翻 trace 归因。
4. 后续接线：suggest_options 缺口镜像、report→track 接力（knevo Top5 第 4/5）。

## 踩过的坑

- exec 隧道有 CF ~100s 响应上限：长命令 nohup 到日志再轮询（scripts/rexec.py）。
- 非交互 shell 的 python3=系统 3.9（import 即崩）；.venv-workbench 无 akshare（第 4 步才暴露，白跑 7 分钟）。日常解释器 /opt/homebrew/bin/python3。→ #291 预检。
- 变异还原禁用 `git checkout <file>`（吞未提交改动）；同长度变异+同秒还原会命中 .pyc 旧字节码，先清 __pycache__。

## 已验证

- #287 门禁真数据正确 FAIL（快照 08-12 超前库 08-11 的活漂移现场）。
- #289 分支 .venv-workbench 全量 4571 passed / 4 failed，4 条均 main 固有或负载偶发。
