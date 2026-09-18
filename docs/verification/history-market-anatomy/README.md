# history-market-anatomy 验证收据

## 当前工程节点：ba281381（2026-09-18）

[接力状态与限定条件返修验证](ba281381/acceptance.md)：状态、实际观察日数与“未成熟非失败”同卡；新v1.1原件显式日期，旧v1只读保存日历；审核最小引用和恢复均有真实接缝回归，数学不变。固定四叶通过（Python11566P/81S/2X），接力7项＋诊断4项内存变异均抓住，完整旧第三题原件只读复核、SHA未改。**没有重跑真实四题，最近业务裁决仍为fbd8失败**。32份归档及开发期同秒收据覆盖如实披露；见[决策快照](../../handoffs/2026-09-18-history-succession-delivery.md)。未合并、未部署，仍是WIP。

## 前一工程节点：58b78542（2026-09-18）

[参数诊断返修验证](58b78542/acceptance.md)：可信程序诊断与事实分型，市场漏类型给具体修正提示，不暗中改对象。固定四叶通过（Python11531P/81S/2X），四个进程内变异被抓住；保留前一a05b3483全量两条失败及修正过程。脚本Episode证明反馈→改参→实查询，**没有重跑真实四题，最近业务裁决仍为下方fbd8失败**。决策见 [返修快照](../../handoffs/2026-09-18-history-diagnostic-repair.md)，未合并、未部署。

## 最近真实四题节点：fbd8f2a6（2026-09-18）

[固定代码复验与真实四题裁决](fbd8f2a6/acceptance.md)：工程四叶通过（Python 11501P / 81S / 2X）；第二实现独立算术复核已支持rank/trace/新特征，仍保留partial/unsupported。**真模型同会话四题已执行，整组失败，未合并、未部署。** 原答、调用/引用manifest、原件哈希和新收据在 `fbd8f2a6/`，不覆盖旧失败或旧读数；这是作者侧验证，不是独立人员QC/真实浏览器验收/方法认证。最新决策见 [09-18快照](../../handoffs/2026-09-18-history-market-anatomy-live.md)。

## 初版历史收据：506e1e23（以下段落仅描述该节点）

被测代码：`506e1e237ad0c8f7a61d2a94b4df9ff40c7d0b49`，基线 `0a1cb8c4`。这是**作者侧验证**，不是独立QC、方法认证或生产真实模型验收。决策与被否方案见 [日期快照](../../handoffs/2026-09-17-history-market-anatomy.md)。

## 文件

| 文件 | 能证明什么 / 不能证明什么 |
|---|---|
| `ci-receipt.json` | 固定代码的四叶读数与日志哈希；不是合流后main收据 |
| `python-receipt.json` | 正确解释器、依赖、干净代码树、11464通过；17警告、81跳过与2预期失败未隐藏 |
| `python.txt` / `frontend.txt` / `e2e.txt` / `registry.txt` | 各叶原始终端输出；frontend=107通过，浏览器=34通过/2跳过，registry=5项通过（反向台账98条存量warning） |
| `queries.json` | 显式研究窗口和实体参数；排名后的代码由作者选入，不是模型自选轨迹 |
| `read-only-receipt.json` | 7次真库只读查询的query_id、源代码/原件哈希、全集/缺数及实际模型投影原子省略数；完整输入与每日路径留artifact_root，不由摘要代替 |
| `mutations.json` | 三个内存替换式及原失败输出，目标断言确实拦住；不是独立审计或全缺陷覆盖 |

首次未提交工作区全量11463通过不是最终收据；固定506e1e23再跑为11464通过。变异进程产生的失败pytest收据是故意破坏的反向证据，不能当正常代码回归失败；以本目录固定代码收据为准。

## 重跑只读查询

在候选代码根执行；`OUT` 必须是未存在的新目录：

```bash
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
DB="$HOME/finance-workspace-private/db/market_feature_store.duckdb"
OUT="$HOME/.finance-runtime/history-anatomy-replay-$(date +%Y%m%dT%H%M%S)"
"$PY" scripts/probe_history_queries.py --db "$DB" \
  --recipe docs/verification/history-market-anatomy/queries.json --output "$OUT"
```

不联网、不调用模型、不改市场库或用户台账。输入库若补数/改源，指纹与query_id变化是预期，不要把旧原件当当前水位。脚本检查模型投影的 `projection_status`，**NAV采样是有声明的展示选择，不是整条日线路径全都投递给模型**。

## 自动化路径边界

`tests/test_history_market_anatomy.py` 覆盖手算、字段来源实际投影、未来数据不改变前缀信号/类比、名单时点、缺失分母、越界/取消/只读/行数上限、原件分页和研究finish。真实Episode用的是脚本模型；Workbench run_turn探针主动停在controller；既有Playwright用隔离夹具和空模型密钥。三者都**不能替代生产真模型整组问答**。

在506e1e23节点，独立原件验算器对market/trace/rank明确unsupported，没有把格式/哈希正确当成算术通过。09-18扩展后的实际支持/跳过与复算读数见上方新节点，不用旧说明描述当前实现。所有结果仍保持研究用途，不能证明策略可用、因果资金迁移或完整SPT/风远方法。

## 四叶复验方式

Python使用上面的`PY`，干净环境（保留PATH/HOME/KNOWLEDGE_WIKI）、umask 022：`-m ruff check .` 与 `-m pytest -q`。前端在 `intelligence/webapp/` 执行 `pnpm install --frozen-lockfile`，再 lint/typecheck/test/build。

浏览器回归：`WORKBENCH_PYTHON="$PY" WORKBENCH_E2E_PORT=18891 RE06_E2E_PORT=18894 RE06_E2E_URL=http://127.0.0.1:18894 pnpm test:e2e`（先确认端口空闲；环境同样清理，测试服务由Playwright管理）。registry检查按 `.github/workflows/registry-check.yml` 五项执行。不要因前一叶失败就不跑后一叶。
