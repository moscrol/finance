# 2026-08-29 LLM transport 符合性套件工单（占位）

> 来源：`docs/verification/2026-08-29-conformance-seam-census.md`（缝普查 P1 #1，
> 分支 `test/conformance-seam-census`）。机制复用三件结构（参数表 × 能力声明表 ×
> 棘轮 baseline），参照 `intelligence/tests/conformance/`（运行时缝）与
> `intelligence/tests/conformance_tools/`（工具缝）。
>
> 状态：**已完成合并**（2026-08-29，PR #513 @`5be00c4f`）。套件
> `intelligence/tests/conformance_transport/`，读数 **21 passed**、baseline 空。
> 两路已声明偏差钉成显式契约（CLI 类名承载故障种类、`max(1.0,·)` 超时地板）。
> 交接：`docs/handoffs/inflight/test-llm-transport-conformance.md`。
> **缝普查 P1 三张（#12/#13/#14）至此全部收官。**

缝：`llm_refine.complete()`（L788）的返回契约 `(content, provider, reason)` ×
两个独立演化的传输实现——HTTP OpenAI-compatible（`_post_chat`）与 CLI judge
（`grok_cli_judge.complete_grok_cli`，provider `transport="cli"`，构造点
`llm_refine.py:273`）。两路的错误分类、超时、重试语义已分叉。不变量草案：
返回三元组形状与错误词表、超时不越窗、cancelled 传播、凭证不入 trace。
**按 transport 参数化，禁止按厂商名参数化**（`_PROVIDERS` 8 槽是共用 HTTP
路径的配置，不是实现——普查已定性，别重新发现）。零网络：HTTP 路打假
transport 函数，CLI 路打假子进程（抄 `test_grok_cli_judge.py` 现成替身）。

验收：两 transport × 全部不变量参数化跑通；existing 散装断言
（`test_llm_provider_fallback.py` / `test_grok_cli_judge.py`）不重复不删除；
分支独立、pathspec 提交、不合 main。
