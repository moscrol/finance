### 原文片段选择试验接续收口（不请求合并或部署）

<!-- arena-excerpt-closeout-20260929-26c77304 -->

已从原件追回 f37629829 的前三次首发，仅补第四次 OFF-transmission，没有重抽前三题。四次顺序为 OFF-news → ON-news → ON-transmission → OFF-transmission，实际模型均 glm-5.3、600秒/40步、单次75秒/修复40秒、0工具；同题TaskFrame/canonical材料hash、system hash一致，作者格式实际为v1/v2/v2/v1。

第四次 `run_20260929_181219_876777` 未交付实质答案：多句claim、JSON错误后流式输出失败，终态failed/repair_model_unavailable。失败原样保留；中断数小时后续完，且控制臂失败，不作稳定性、性能或财务非劣性结论。

**候选不满足原门槛，已在本机隔离接续分支撤回v2实现。** 候选news的“量产采购订单仍为无”将D0否定延伸到D3，摘要把预计60天写硬；不能判八问全可用。财务仍有已给CFO后笼统要求非现金/营运资本调整的口径问题。

隔离上下文自动代码审查无可证明阻塞项（有范围限制，非人工）；前三份匿名内容自动评审都给usable，但漏掉上述明确源文限制，原件和分歧保留、不增抽判卷；第四份单次评审unusable。机械身份/hash检查不替代语义验收。

撤回提交 **26c77304ba48f098159dfc0cdac1a4e332255a8c**，分支 `fix/8792-harness-takeover-0929`；运行时文件与957dc51e2逐字节相同。试验代码/测试留patch归档，新增6项退役保护测试。该干净提交34文件定向复测 **1029P/4S（20.16秒）+ Ruff通过**；不是全仓/前端/E2E门禁，不为本PR整个head签合格。收据 `20260929T103240Z-26c77304-dee6f476821c.json`。

本机报告 `docs/verification/2026-09-29-arena-harness-final.md`，证据 `docs/verification/material-source-excerpts-final-2026-09-29/`。原始补齐/自动审查记录在 `~/.finance-runtime/reviews/8792-answer-capability-20260928/arena-finalization-0929/`。

仅同步状态：接续提交尚未push，不改本PR head，不关闭或合并本PR，回答能力主线继续WIP。验收进程/临时检出已清理；8792仍62fad1d0d986、代码匹配，DuckDB大小和mtime未变。未切生产、未重启8792/8798。
