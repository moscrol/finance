# #832 前向合流验收（2026-09-21）

固定候选 `a14005fc9a9d671d178da6fc91be9cb69ae67e77`：把开跑时 main
`f2c3e9e1a24f42ae9b1d5a8cb9e501ababd1330a`（#830）合入 #832；不改 #809 原头。
**工程通过；独立审查超时未完成；自然金融质量未通过；无合并/部署授权。**

## 精确收据

- Python 全量 12596 passed / 87 skipped / 2 xfailed / 17 warnings，1480.30 秒，exit 0。
  `python-final-execution.json` 首尾同 SHA、全树 clean；`receipt-a140.json` 经
  `receipt-check-a140.log.txt` 校验 exit 0。JUnit 完整文件由外部哈希清单绑定。
- 相比 ec246761 全量多42条；89项 skip/xfail 的名称和原因完全相同，见 `junit-comparison.json`。
- 前端六步 exit 0，单测110P、E2E 34P/2S；`frontend/frontend.json` 首尾同 SHA/clean，
  每份日志字节数与 SHA256 已核对。
- Ruff / registry parseability / check / backfill-tables --check / generate-views --check /
  ledger crosswalk 六命令 exit 0，见 `checks.json`。
- 真实旧答离线回放删除索引14、15，计数悬空消失，其他句子逐字不变；源工件未改。
  `condition-artifact-replay-a140.json` 与脚本是作者离线诊断，模型调用0。

## 唯一新增 K3 会话

09:55:14.623130Z 开始，10:05:17.542856Z 收尾；外层600秒帽触发 SIGTERM，exit143。
使用既有订阅 `mirasim-kimi/kimi-k3`，只读源码沙箱，只有本轮证据目录可写。
导入预检通过，确认模块来自固定候选；首尾 SHA/clean 不变。

21次工具调用（20 bash、1 write），仅写下 `REPORT-IN_PROGRESS.md` 草稿并阅读源码，
**没有运行 pytest/自造行为探针，没有 Spec/Quality 结论或独立签字**。
原草稿 pending 不由作者补填。配置关闭自动重试；记录里 auto_retry_start=0，
这不认证不可见上游的重试行为。没有自动新开会话、没有另换模型求绿。

`k3/events-selected.jsonl` 只保留原事件中的 session / agent_start / turn_start /
tool_execution_start / tool_execution_end / turn_end / auto_retry_start / auto_retry_end /
agent_end；不改这些事件内容。message_update 等高频增量留在外部原件，
`EXTERNAL-SHA256SUMS` 绑定完整4.7MB事件和settings文件。筛选日志不是完整模型思考记录。

## 不得外推

本收据不移签后续 docs-only tip，更不覆盖测试期间又前进的 main。
自然金融会话0；225/25、候选数值显式引用、语义审核消费、板块排序与按需展开未据此完成。
历史来源修复在独立 `feat/history-evidence-integration-0921`（代码f90fd3dc3），
不混进 #832；不因历史片有测试就关闭 #793/#794。
原 ec246/a412 的失败和成功记录仍见 `../2026-09-21-react-trace-qc/`，未覆盖。

## 校验

`SHA256SUMS` 绑定本目录其他归档文件（不含自身），`EXTERNAL-SHA256SUMS` 绑定大原件。
完整执行根：`~/.finance-runtime/reviews/react-trace-integration-20260921/`。
