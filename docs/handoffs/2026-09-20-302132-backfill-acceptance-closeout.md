# 302132 回填验收收口（2026-09-20）

## 背景

冻结候选 `3736d5bfa9978dfa0a264bb2e44795c4bc29b27d` 的执行实现把目标股固定为 `CODE = "302132.SZ"`，数据检查中的 SQL 也直接使用这个常量。独立验收对父收据、嵌入 child、外部 child 与 apply/verify 两轮 spec 做了深比较，但 `spec.code` 只检查股票代码格式。这留下一个授权对象错位：两轮父子材料可一起写成 `000001.SZ`，37 项检查仍全部通过，而验收实际查询的仍是 302132。

同一 schema 的数值判定直接执行 `math.isfinite(v)`。Python 会把整数隐式转成浮点；`10**400` 超出浮点范围时抛 `OverflowError`，导致 CLI rc=1 且不生成结构化验收 JSON。它破坏了 fail closed 合同：坏 schema 应明确 FAIL rc=2，并跳过依赖该 schema 的数据计算。

## 发现顺序

1. 从固定提交建立独占树，构建代码地图后定位 `_validate_receipt`、`_is_num` 与既有 E2E fixture。
2. 原样运行外部 `probe.py`：control rc0/PASS/37；两轮同步伪 code 仍 rc0/PASS/37；超大整数 rc1、无 JSON。
3. 先加真实 CLI 反例：仅 apply 错、仅 verify 错、两轮同步错；三类既有数值入口分别注入超大整数；另加 bool、NaN/Inf、正负超大整数和普通有限数的函数级对照。修前 8 项失败，红灯同时覆盖错误通过与裸异常。
4. 最小修复后，独立 probe 的控制组保持 37P；两个反例都变为结构化 FAIL rc2，且 `data_checks_executed` 明确失败表示跳过。
5. 两次定向 mutation 分别撤掉代码绑定和溢出保护，新增断言重新失败；恢复后同输入转绿。
6. 提交代码冻结 `be3f29306739ff55ac7f40adbbc9f55503c26abf`，在干净 SHA 上重跑完整模块、Ruff 和原 probe。

## 方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 只保留 `_CODE_RE` 格式校验 | 能挡畸形字符串，挡不住另一只合法股票 | 否决 |
| 只依赖 child/parent/跨轮一致 | 同源材料可同步造假，无法绑定 SQL 对象 | 否决 |
| 将所有 SQL 改读 `spec.code` | 会让伪授权材料改变查询对象，扩大本片语义与风险 | 否决 |
| 每轮 schema 绑定 `spec.code == CODE` | 明确声明本专用验收器的授权对象，保留全部深比较 | 采用 |
| 最外层捕获所有 Exception | 可能把编程错误伪装成普通 schema 失败 | 否决 |
| `_is_num` 只捕获 `OverflowError` | 数值谓词成为总函数，普通 int/float 语义不变 | 采用 |

## 验证与收据

- 完整相关模块：104 passed，等于原 89 项（65 验收 + 24 其余）加 15 项新反例。
- Ruff：两目标文件 all checks passed。
- 原 probe 在代码冻结上：control rc0/PASS/37；`spec_other_code` rc2/FAIL/22；`huge_numeric_pin` rc2/FAIL/22。
- CODE mutation：3 failed / 101 deselected；overflow mutation：5 failed / 7 passed / 92 deselected；恢复后 15 passed / 89 deselected。
- 证据根：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/backfill-acceptance-fix/`。
- `manifest.json` 列出固定源、代码冻结、原 probe SHA、源码 SHA、结果摘要及 114 个证据文件的 SHA256；`manifest.sha256` 签 manifest 自身。
- 所有 pytest/probe 进程使用 `env -i` 白名单：HOME/PATH/LANG/TMPDIR、`FWP_TEST_RECEIPT=0`、`PYTHONDONTWRITEBYTECODE=1`、必要的 PYTHONPATH；pytest 禁用 cacheprovider。

## 后续与边界

- 交给 root 依次做 Spec→Quality；本实现代理不创建 PR、不合 main。
- probe 使用全新 tiny 30 日 fixture；child 写入与独立验收是真实路径，但 parent 收据由 fixture 组装，因此不能声称生产全父链演练。
- 没有读取或复制生产/旧大演练 DuckDB/parquet，没有跑生产回填、真实模型或 API。
- 历史 49/49 和 9706P 是 `00d64e37` 的旧收据，不移签到本提交。
- 未跑无关全仓 Python/前端；范围外门禁由 root 的冻结候选流程另行管理。
