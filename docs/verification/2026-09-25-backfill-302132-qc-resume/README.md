# #813 限定独审续跑原件

状态：`BLOCKED_SCHEMA_AND_UNSUPPORTED_CLAIMS`。没有有效的独审通过结论。模型原始稿自称 PASS_WITH_LIMITS，但枚举错误且含未执行的通过陈述，执行器和宿主对账均拒收，原稿没有被改写。

- 固定候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59` / base `4cc15e703f81bce8abadee00f68caacdb0c72b4d`；封存 main `03352758cf9b31e3f5d179b517be48cb89588679`，当前组合未验。
- 本轮42请求：K3-02预检1超时；GLM-01预检4+探索7，目录合同不符阻塞；GLM-02预检4+探索8+执行17+报告1。
- 独立探针七例实际3P/4F，另两次语法收集错误。4F为探针/夹具问题，但修正未复验；作者重跑0、execute故意红对照未跑、Quality未启动，不能宣称无发现。
- 490原件、4,347,005字节；`manifest.json` 记录原路径、存储路径、原字节/存储字节SHA256。日志及空白敏感文件用可逆Base64，其余逐字保存；脚本以 `.txt` 归档。`archive-verification.json` 是落盘原字节核验，Git提交内核验在PR发布前另做。
- 排除候选检出树、运行时凭据存储、临时数据库/用户目录与符号链接。K3旧11请求批仍在09-24的qc-01归档，本包不改它。

优先入口：

1. `raw/pr813-glm-qc-20260924-02/host-evidence-audit.json`：哪些陈述被原始日志否定、有效通过用例及合同遗漏。
2. 同目录 `report.json`：宿主封存记录（不是独立判官报告）。
3. 同目录 `spec/report/parsed.json` / `spec/report.controller.json`：模型原始无效稿及门禁拒收。
4. 同目录 `spec/execute/commands/015-bash/output.log.b64`：3P/4F原始pytest输出；其它工具请求保存被替换的探针版本。
5. `../../handoffs/2026-09-25-backfill-302132-scoped-qc-resume.md`：背景、决策与下一步。

未改产品代码、未合main、未写生产或动8792。所有自有审查进程已退出。
