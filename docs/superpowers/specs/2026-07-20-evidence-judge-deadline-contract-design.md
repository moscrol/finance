# Evidence Judge 截止时间契约修复设计

## 背景与根因

生产 API 会通过 `llm_refine.provider_override()` 注入内置 GLM，因此
`ASK_EVIDENCE_JUDGE=auto` 会真正执行语义相关性闸门。当前
`evidence_judge.judge_relevance()` 把 `deadline` 关键字继续传给
`llm_refine.complete()`，但后者的公共签名只接受 `timeout`，导致题材研究的
`company_mapping` 阶段抛出：

```text
TypeError: complete() got an unexpected keyword argument 'deadline'
```

没有配置 LLM 的测试和离线调用会跳过语义闸门，因此此前未覆盖这条生产路径。

## 方案选择

采用调用方适配，不扩张 `llm_refine.complete()` 的公共接口：

1. `judge_relevance()` 保留可选绝对截止时间，用它计算本次调用的有效剩余秒数；
2. 向 `complete()` 只传其正式支持的 `timeout` 与 `temperature`；
3. 绝对截止时间已经耗尽时直接返回 `None`，保持语义闸门 fail-open；
4. 保留独立 judge provider 的覆盖逻辑。

不选择给 `complete()` 重新增加 `deadline` 参数，因为只有语义闸门需要这层适配，
而 `complete()` 内部已经按 `timeout` 创建自己的绝对截止时间。扩大底层接口会增加
所有调用方的契约面，也容易形成两套截止时间谁优先的歧义。

不选择关闭语义闸门，因为那会以牺牲幻觉防线来掩盖接口错误。

## 数据流与边界

```text
ResearchDeadline
  -> evidence_providers 计算 stage_timeout
  -> judge_relevance 取 min(stage_timeout, Deadline.remaining)
  -> llm_refine.complete(timeout=effective_timeout)
  -> complete 内部建立单次 LLM Deadline
```

控制面仍记录研究总截止时间；展示面只接收 judge 的保留/丢弃结果或 fail-open，
不会暴露异常参数、内部路径或 provider 凭据。

## 测试与验收

先写失败回归，再实现：

- 用真实 `llm_refine.complete` 签名的 spy 验证不再传 `deadline`；
- 验证有效 `timeout` 不超过绝对截止时间剩余值；
- 验证已耗尽截止时间时不调用 LLM 且返回 `None`；
- 运行 evidence judge、semantic gate、research owner 与核心测试集；
- 部署后通过 HTTP 重跑“光模块题材深挖”，要求 `company_mapping` 不再失败，
  形成引用与公司映射，运行结束后 readiness 与常驻 RAG worker 仍为 ready。

随后继续执行个股、新闻、观察清单端到端验收。内部异常为零是日常可用的硬门槛；
数据缺口可以诚实降级，但不得伪装成完整研究。
