# 同花顺个股标准化预演 · 作者验证证据

测试代码固定于 `40317d780d71de03ca6884c4c437b9accece0b49`。这份归档不修改运行代码；不是独立 QC（质量复核）通过证明，不是生产切源验收，也不包含本片未运行的全量 / 删保护变异 / 前端·E2E / registry 结果——那些对 c85d0101 成立的结论不借给本片。背景、决定、各收据适用范围见 [日期快照](../../handoffs/2026-09-15-hithink-stock-preview.md)。

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

## 无损格式与核验

`*.output.json` 保存 `original_path`、`raw_sha256`、`encoding` 和保留原换行的 `lines`，包括失败日志与门禁输出，不是经过润色的摘要。重建原件：

```python
raw = ''.join(payload['lines']).encode(payload['encoding'])
assert hashlib.sha256(raw).hexdigest() == payload['raw_sha256']
```

收据 JSON 按字节复制。目录内 `shasum -a 256 -c SHA256SUMS` 核对归档文件，清单不包含自身。指纹只证明归档未变，不证明算法正确、供应商量额关系真实、覆盖完整、独立复核完成或生产就绪。没有归档临时 DuckDB、真实行情或任何密钥；所有数据库验证均为合成数据和隔离库。
