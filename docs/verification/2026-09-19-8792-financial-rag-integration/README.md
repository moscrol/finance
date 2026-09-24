# R6×RAG分帧：固定组合收据

业务提交：**`d8d6196baebdb1108a81ae01466e9df6397dc4fc`**。
基底：文档f70b9399/业务d06dc1e8；仅接20939b18读取片，保金融代码身份与私有pycache换代。
详细决定、红灯顺序和边界见 [日期交接](../../handoffs/2026-09-19-8792-financial-rag-integration.md)。
外置原件：`~/.finance-runtime/reviews/8792-financial-rag-integration-20260919/`。

## 可以签什么

- 固定干净d8 Python **12220P/86S/2X**，Ruff0，前端115P及lint/typecheck/build0，E2E34P/2S。
- pytest收据由本次日志精确指向 `20260918T181016Z-d8d6196b.json`，八项条件通过；不从同SHA/最新文件猜覆盖。
- 固定金融d8＋KB91725ea9＋site9f60bef五项原生registry/crosswalk全0，前后身份不变。
- 新RAG九组撤保护及原financial-delivery/R6/research-delivery/extraction四套各自完成；发布另有一次预先限定的串行完整八组完成。均逐项恢复、最终恢复绿，无收集错误，各分母不相加。
- RAG修复正向探针exit0、反向期待exit1；旧R6原件12个hash不变，回放连接0，临时登记0/0/0/1。

## 不能抹掉的限制

**不签无保留全绿或可直接合入。**

1. 原发布并发执行baseline触及180秒上限，`publication-incomplete.json.complete=false`、runs为空，runner未保存原中间stdout/XML/栈。实际执行数未知，不能称零执行、断言失败或资源争用已证。
2. 同树单次诊断150P/51.19秒；再按 `publication-serial-protocol.json` 做一次限定串行对照，基线/恢复150P，八组红→绿。没有改代码、增加时限、循环重试；**后续绿不解释或修复第一次超时**。原总套件汇总仍有publication exit1。
3. 宿主 `engineering.json.all_passed=false`，registry exit1因旧KB声明不一致；固定三仓通过另列，不scan倒退登记。
4. 无本候选新自然模型/独立QC；旧R6/R3仍0/4 not_passed。F2报告取回未修，整枝答案保留/runtime/资金历史未合，未push/合main/部署，8792未切。

## 撤保护失败口径

| 套件 | 组数 | 基线/恢复执行数 | 分类 |
|---|---:|---:|---|
| rag-transport | 9 | 78/78 | 6组含断言、2组期待异常未抛、1组仅测试体异常 |
| publication（串行） | 8 | 150/150 | 每组含断言，另有一条ValueError |
| financial-delivery | 6 | 20/20 | 每组含断言 |
| financial-r6 | 13 | 91/91 | 每组含断言 |
| research-delivery | 13 | 107/107 | 每组含断言 |
| extraction | 35 | 165/165 | 28组含断言，7组仅KeyError/UnicodeDecodeError |

JUnit `<failure>`不等于AssertionError。`mutation-failure-classification.json`逐条分类，`DID NOT RAISE`单列，未知拒绝；原XML与变异diff均在manifest外置指纹内。开发首红6F与78P/196P3S未提交读数只做开发轨迹，不冒充固定收据。

## 原件与副本

- JSON逐字节复制；`.txt`只是展示副本，最多去行尾空白和EOF多余空行，原日志不改。
- `manifest.json`记每份原件/副本SHA256、字节数与转换，并列外置原件指纹；没有递归临时数据、用户目录、worktree或软链。
- `SHA256SUMS`覆盖包内除自身外的全部文件；manifest不自哈希。后续确认另写新文件，不修改封存原件。
- 秘密扫描只有私钥/GitHub token/API key/Bearer有限形状，零命中不代表通用秘密认证。
- refs exit0仍有26行数漂移/8未解析/1未核数；graph0仅证路径/符号；vault lint前后20E/17W、exit1未改判。
- 自建固定finance/site及原超时诊断树已正常移除，复用KB树未动；检查进程已退出，8931/8934无listener。关闭的是本轮检查，不是生产服务。
