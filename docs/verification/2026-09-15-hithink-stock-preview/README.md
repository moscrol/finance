# 同花顺个股标准化预演 · 作者验证证据

测试代码固定于 `40317d780d71de03ca6884c4c437b9accece0b49`。这份归档不修改运行代码；不是生产切源验收——那些对 c85d0101 成立的结论不借给本片。背景、决定、各收据适用范围见 [日期快照](../../handoffs/2026-09-15-hithink-stock-preview.md)。

归档分三批：第一批（交接时）只有定向 277P；第二批（同日续跑）补齐全量、12 项删保护变异、全仓 Ruff、前端四叶与 registry 只读检查。全量跑在 `2ad19f35`（`40317d78` + 纯文档归档提交，`git diff 40317d78..2ad19f35 -- ':!docs'` 为空，代码等同）。第三批（同日，QC P3 修复）：修复提交 `728ecf82`（stock/sector CLI 失败 fallback 补 `contract_version`、sector 片新增 `hithink-sector-preview-v1` 进成功报告、文档写明 2026 日历边界、`row=None` 防御性重置），3 项删保护变异见红 + 全量复跑 9834P 零回归。

## 证据索引

| 证据 | 落点 | 结论与限制 |
|---|---|---|
| 环境与范围 | `environment-and-scope.json` | macOS / Python3.12.13 / 依赖指纹 3328bed61f3e21ea；含日志→收据映射、逐收据计数与归档时工作区状态。本片无前端/E2E 运行，Node 版本不适用 |
| 干净固定定向 | `hithink-stock-preview-clean-40317d78.output.json`、`20260915T094612Z-40317d78.json`、`hithink-stock-preview-receipt-check-40317d78.output.json` | 干净 40317d78 十文件 277P/9.90s、exit0；收据七项条件核验「可采信」。只覆盖定向十文件，不是全量，两次耗时不是性能结论 |
| 开发中反例与推进 | `hithink-stock-preview-{before,before-r2,unit,unit-r2,edges-before,regression,regression-r2}.output.json` 与七份 `*-3bba5b4e.json` 收据 | 父 SHA 下未提交本片代码的 dirty 收据：5F/74E（夹具 DDL 按分号截断，测试夹具错误）→79F（模块/CLI 未实现）→78F/1P（正则缺括号，实现错误）→79P→3F/90P（整数股约束与 Decimal 上下文隔离）→275P→277P。dirty 结果不能当父提交干净状态 |
| Ruff 与交接检查 | `hithink-stock-preview-ruff-40317d78.output.json`、`hithink-stock-preview-ruff-handoff.output.json` | 三文件 Ruff 与交接文档检查通过；未宣称全仓 Ruff |
| 提交门禁 | `hithink-stock-preview-code-commit.output.json` | 40317d78 提交 hooks 全过（含层级审计、字段/路径门）；dataset 空表内容检查未提供可读 DB 而跳过 |
| 地图 | `hithink-stock-preview-map-{build,query}.output.json` | build exit0（26384 节点 @3bba5b4e）但 query status=stale、vault unavailable、structure 无命中；定位依赖直接源码与测试，未拿空图下架构结论 |
| 图谱 | `hithink-stock-preview-graph-{before,after}.output.json` | graph_audit 回写前后各一次 exit0；审计对象含主检出/KB 脏树，是路径/符号断言，不是运行或合流验收 |
| 全量（第二批） | `hithink-stock-preview-full-2ad19f35.output.json`、同名 `.exit`、`20260915T103043Z-2ad19f35.json`、`hithink-stock-preview-receipt-check-full-2ad19f35.output.json` | 干净 2ad19f35 全量 9834P/79S/2X、642s、exit0；收据七项条件核验通过。2ad19f35 与 40317d78 代码等同（只差文档归档提交） |
| 全仓 Ruff（第二批） | `hithink-stock-preview-ruff-full-2ad19f35.output.json`、`.exit` | 全仓 All checks passed、exit0 |
| 删保护变异（第二批） | `hithink-stock-preview-mutations.{json,output.json}`、`hithink-stock-mutation-driver.py.output.json`、14 份 `20260915T1031/2/3*-40317d78.json` 收据 | 隔离树 `fwp-wt-hithink-stock-mutation-40317d78`。基线 95P 干净 → 12 个变异逐一落盘（读回核验）、逐一见红（1–56F，红的是语义对应测试）→ 还原后 95P 干净。每轮清 `__pycache__` 且 `PYTHONDONTWRITEBYTECODE=1`。12 份变异收据刻意 dirty=true，不是固定提交失败 |
| 前端四叶（第二批） | `hithink-stock-preview-frontend-{lint,typecheck,test,build}.output.json`、各 `.exit` | 本片零前端文件改动；lint/typecheck/build exit0，Vitest 76P。跑在本机 Node26/macOS，不等于工作流 Node22/Linux；未跑 Playwright E2E |
| registry（第二批） | `hithink-stock-preview-registry-{crossrepo-check,crossrepo-check-parseability,generate-views}.output.json`、各 `.exit` | check-parseability 60/60 与 generate-views（跑后树仍干净）exit0；跨仓 check exit1，7 处漂移全在 kb/ 侧、finance 侧零漂移，与前一片记录一致，是他仓既存问题不是本片新增。backfill-tables 会写姊妹仓，未跑 |
| QC 配额探针（第二批） | `hithink-stock-preview-qc-probe.output.json`、`.exit` | codex 网关最小探针 exit0（此前两片卡额度/503 的门已通）；后按用户指示独立 QC 改用 k3，codex 正式复核已中止（其部分 session 存 `qc-40317d78-codex-aborted-session-log.output.json`，不作复核证据） |
| 独立 QC（第二批，k3） | `qc-40317d78-{request-md,report-md,k3-session-log,k3-exit-code,probes-py,author-tests-*,qc_probes_output-*}.output.json`、四份收据 `20260915T10{3556,4513,4732,5745}Z-40317d78.json` | k3（pi/provider mirasim-kimi）隔离树复核 exit0：**无 P0/P1/P2**；155 项独立探针+CLI/类型边界全过；QC 自跑全量 9836P/0F/77S（作者侧 9834P/79S：两侧总数同为 9913、均 0 失败，差异是 2 项在作者壳下 skip、在 QC 壳下执行并通过）。两条 P3（CLI 失败路径缺 contract_version、文档缺 2026 年份边界说明）与两条观察项见报告 §3。复核后作者树/分支 ref/QC 树零污染由作者独立核验，vault 变动归因为其他并发会话 |

### 第三批（QC P3 修复，728ecf82）

| 证据 | 落点 | 结论与限制 |
|---|---|---|
| 修复后定向 | `20260915T113143Z-a8616d74.json`（dirty，提交前首跑）、`20260915T113340Z-728ecf82.json`（干净基线复跑） | 两个 preview 测试文件 139P（含 5 条新增 `contract_version` 断言，测试函数数不变）。`20260915T113400Z-728ecf82.json` 是一次含不存在文件名的误跑（no tests ran），不作证据 |
| 删保护变异（3/3 红） | `p3fix-mutations.json`、收据 `20260915T1133{04,17,34}Z-728ecf82.json` | 三个新增 `contract_version` 落点（stock CLI fallback / sector CLI fallback / sector 成功报告）逐一删除，红的是语义对应测试（2F/1F/2F），还原后 139P 干净。`row=None` 重置无行为差异、无对应变异，如实记录为防御性改动 |
| 兄弟 hithink 测试 | `20260915T113421Z-728ecf82.json` | 九个既有 hithink 测试文件 132P，sector 成功报告加字段未破任何消费者断言 |
| QC 复现命令重放 | `p3fix-p3-stock-invalid-options{,.exit}.output.json`、`p3fix-p3-{stock,sector}-fallback{,.exit}.output.json` | QC P3-1 的字面复现命令（`--trade-date 2026-10-01`，空隔离库）现输出 `contract_version=hithink-stock-preview-v1` + `invalid-preview-options`；库不可达路径两片同带各自版本，均 exit2 且未创建库目录。指纹仍不补——失败时范围未验证、输入未读到 |
| 全量复跑 | `p3fix-full-728ecf82.output.json`、`p3fix-full-728ecf82.exit`、`20260915T114624Z-728ecf82.json` | 干净 728ecf82 全量 9834P/79S/2X、698s、exit0，计数与第二批基线一致（零回归）；收据七项条件核验「可采信」。全仓 Ruff 同轮通过（未另存输出件） |

## 无损格式与核验

`*.output.json` 保存 `original_path`、`raw_sha256`、`encoding` 和保留原换行的 `lines`，包括失败日志与门禁输出，不是经过润色的摘要。重建原件：

```python
raw = ''.join(payload['lines']).encode(payload['encoding'])
assert hashlib.sha256(raw).hexdigest() == payload['raw_sha256']
```

收据 JSON 按字节复制。目录内 `shasum -a 256 -c SHA256SUMS` 核对归档文件，清单不包含自身。指纹只证明归档未变，不证明算法正确、供应商量额关系真实、覆盖完整、独立复核完成或生产就绪。没有归档临时 DuckDB、真实行情或任何密钥；所有数据库验证均为合成数据和隔离库。
