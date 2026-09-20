# 同花顺采集版本 · 作者验证证据

测试代码固定于 `c85d01017fa239aa3b2101b1585e8f5c07e005b3`。这份归档不修改运行代码；不是独立 QC（质量复核）通过证明，不是生产切源验收。背景、决定、各收据适用范围见 [日期快照](../../handoffs/2026-09-15-hithink-sector-capture-audit.md)。

## 证据索引

| 证据 | 落点 | 结论与限制 |
|---|---|---|
| 环境与范围 | `environment-and-scope.json` | macOS / Python3.12.13 / Node26 / pnpm10.12.1；不是工作流 Ubuntu/Node22 的同环境运行 |
| 固定版全量 | `hithink-capture-full-c85d0101.output.json`、同名 `.exit`、`20260915T072124Z-c85d0101.json` | 干净树9739P/79S/2X、exit0；收据不含xfailed计数，原输出含2X |
| Ruff与收据核验 | `hithink-capture-ruff-c85d0101.output.json`、`hithink-capture-receipt-*-c85d0101.output.json` | 全仓Ruff通过，固定SHA/解释器/依赖/干净条件核验通过 |
| 前端与浏览器 | `hithink-capture-frontend-*.output.json`、`hithink-capture-e2e-c85d0101.output.json` 及各 `.exit` | lint/typecheck/build通过，Vitest76P，Playwright三视口15P；只用隔离夹具/本机服务 |
| 作者变异 | `hithink-capture-mutation-{limit,manifest,terminal,time,exit,fallback}.output.json`、`.patch.output.json`、`.exit` | 每次只改一个保护、独立恢复，六次exit1。父SHA相同但dirty=true，不能当该提交正常失败收据 |
| 恢复后 | `hithink-capture-mutation-restored.output.json`、`20260915T080851Z-c85d0101.json` | 隔离树恢复干净，六个定向文件141P、exit0；不冒充全量或独立QC |
| 开发中反例与推进 | `hithink-capture-audit-*.output.json`、`20260915T06*-fdbe5dad.json`、`20260915T07*-fdbe5dad.json` | 均是父SHA下未提交第三片代码的dirty收据；初始27F、边界2F/48P保留 |
| 注册表 | `hithink-capture-registry-{crossrepo,single}-c85d0101.output.json` | 五条命令逐条留EXIT；单仓全0，跨仓check为1（KB七处指纹），其余0；96条反向warning未升级 |
| 图谱 | `hithink-capture-graph-{before,after}.output.json` | 路径/符号断言检查，不是运行验证；包含他仓脏树，归档明确revision/dirty |
| 地图 | `hithink-capture-code-map-final-*.output.json` | build/query exit0但vault unavailable、structure missing，不是完整召回 |
| 提交门禁 | `hithink-capture-commit.output.json` | 代码提交hooks通过；dataset空表内容检查未提供DB而跳过 |
| 独立QC失败 | `qc-dcee18f2-*.output.json`、`qc-c85d0101-*.output.json` | 前两片Codex额度失败/Claude503；本片组合复核Codex额度失败。没有实际复核报告，不得从错误JSON的subtype=success推通过 |

## 无损格式与核验

`*.output.json` 保存 `original_path`、`raw_sha256`、`encoding` 和保留原换行的 `lines`。包括日志、变异补丁、QC请求和错误输出，不是经过润色的摘要。重建原件：

```python
raw = ''.join(payload['lines']).encode(payload['encoding'])
assert hashlib.sha256(raw).hexdigest() == payload['raw_sha256']
```

收据JSON与原 `.exit` 文件按字节复制。目录内 `shasum -a 256 -c SHA256SUMS` 核对归档文件，清单不包含自身。指纹只证明归档未变，不证明算法正确、供应商完整、独立复核完成或生产就绪。没有归档临时DuckDB、浏览器缓存/二进制trace或任何密钥。
