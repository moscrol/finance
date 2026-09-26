## 范围

#833 的 H-01 局部返修，base=`fix/history-forward-0921@7edfe24e76afbd5c365fbf97dd2414847b086f88`，head=`d91aff9d8437fe903f3e643b65d4805aa4cf243c`。仅叠放比较，不合 main，不替换旧冻结版本。

历史意图、通用追问继承与截止投影复用顶层来源分区。引用/围栏不授历史权限；原文仍供分析。明确范围续问保窗口、截止及本地读取上限。产品门文档随源码更新。

## 实测

- 固定干净提交上定向三组共530 passed（168+169+193，其中已含新41例）。全仓 Ruff与diff-check通过。
- 五处进程内撤保护：24/15/6/1/4个断言失败，零夹具错误，运行前后源码哈希一致。工具 `scripts/probe_history_control_boundary.py` 可复跑。
- controller -> TaskFrame -> control -> Episode合同/工具登记；H-01夹具禁并计数网络及DuckDB连接尝试，离线模型/知识替身，不执行历史工具。

## 仍需修改，禁止整体放行

正常版相邻反例H-02：`那它们见顶后谁接力？`、`以前有没有类似，失败案例也看看` 合法继承历史但 material_contract=None，授权出现web_search/web_fetch；期望local_only的2断言仍红。该编号仅本轮发现编号，不是新工单。H-01局部绿不能覆盖此权限缺口。

未跑本revision完整Python/前端/E2E/registry全部合入门禁、未重跑旧四自然题、无新独立Spec/Quality。整体历史仍CHANGES_REQUIRED。旧#833作者全量不移签，原两次capacity无report不翻案；runtime/财务未重启审核。未合并、部署、回填或删除工作树。

## 证据

集中于#838文档分支的新包 `docs/verification/2026-09-21-research-tail-forward/history-boundary-repair-01/`，旧三包不动；本机原件 `~/.finance-runtime/reviews/research-tail-integration-20260921/history-boundary-repair-01/`。以后续归档评论的Git blob核验为准。
