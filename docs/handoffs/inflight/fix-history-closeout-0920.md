# fix/history-closeout-0920

## 这个分支做什么
从固定 `c9bd82ff` 收尾两项历史债：同根扩窗链的窗口预占误拒，以及 `daily-full` 结构图查询漏召回。

## 决策与被否方案
| 选定 | 否掉 | 理由 |
|---|---|---|
| 预占键=`root_query_id/root_sample_id/ranking_start/ranking_end` | 直接父件 `source_start/end`、显示文本猜窗 | 父件窗会随合法 trace 扩展；根排名窗才是稳定选择，逐边校验仍由既有解析/读取门负责 |
| 原词后最多一次 `-`→`_` CRG 查询，按 path+symbol 去重，总上限20 | PATH-only、硬编码 market_feature_store、普通词多派发 | 保留原查询，有限补 Python 符号召回，不伪造命中 |
| `uvx_missing` 显式 `structure=unavailable` | 吞异常成正常零命中 | 后端不可用与合法 `missing` 不能混同 |

展开见 `docs/handoffs/2026-09-20-history-closeout-fixes.md`。

## 当前状态
- 已提交：`dca7c27e`（窗口稳定身份）、`7e5f2ccd`（代码地图别名/不可用语义）。
- clean e0f2a5c7通过独立Spec→Quality，已推gitea；PR #800以feat/history-market-anatomy为底。本次只回写状态，未合main或部署。
- 原件读取与窗口绑定在 `c9bd82ff` 已有，本枝没有按旧交接重复施工。

## 已验证
- 历史设计探针副本：同根 stock 经扩窗 trace 原件由 conflict 转 success；原件/副本 SHA 已留外部证据。
- 回退稳定键变异：新增 3 条链式/并发断言红；恢复后绿。
- `test_history_window_binding.py + test_history_market_anatomy.py + test_history_live_seams.py`：78 passed。
- `test_code_map.py`：42 passed, 3 skipped；实际 `uvx` 全量 build 后图 `ready n=30246 @7e5f2cc`。
- 原始 `test_structure_probe_daily_full` 独立真实执行：1 passed；Ruff 四个改动文件通过。
- 收据/日志：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-closeout-fix/`。
- 独立Spec四组行为及必要12P；Quality另7P/0F/0S，均固定e0f2a5c7，证据在同根history-closeout-review/spec、quality。分母不合计。Spec量具校准/全局收据误写已单独留档。

## 未验证 / 已知边界
- 未跑整仓/前端/真实模型/生产写入；旧真实四题失败属于 `fbd8f2a6`，本枝未重跑，不能称当前通过。
- #791 成员并集/相似排名正文忠实、独立启动对照组不在本实施片；窗口测试不能关闭它们。

## 下一步
主协调处理原PR783后续合流及验收。与main4ace5ec2预演无文本冲突，但未跑合流全叶；原自然四题、#791仍独立待验。本枝禁止直接合main。

## 踩过的坑
`pytest | tee` 若未启用 pipefail，shell exit 不能代表 pytest；以收据 counts/exit_status 为准。外部探针副本只改 `SOURCE`，勿覆盖旧证据原件。
