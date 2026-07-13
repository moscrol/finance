# Workbench Runtime Probe Freshness Design

## Goal

修复目标公司提示文本的非目标路径保真、运行时 DuckDB 探针缓存的新鲜度与挂起恢复，以及真实 smoke 中 readiness 到 terminal cutoff 的单调性校验。

## Design

`preserve_required_system_notices` 先判断 `AnswerSpec.system_notices` 是否要求目标公司提示。不要求时直接返回原始 `answer`，不做字符串转换、裁剪或换行规范化；要求时才去重并把提示置于正文之前。

运行时探针以 canonical 输入路径作为稳定键。DuckDB 文件指纹包含规范路径、device、inode、`mtime_ns` 和 size；成功 cutoff 缓存同时记录指纹，只有当前 stat 成功且指纹完全一致时才能命中。探针失败或返回 `None` 不写 30 秒正缓存。inflight 记录 Future、启动时间和 generation；租约到期可启动新代，旧代只能完成自己的 Future，只有仍是当前代的 worker 才能更新缓存和删除 inflight。每次请求清理过期缓存和超租约 inflight，限制路径变化产生的陈旧状态。

smoke 同时保留 readiness 与 terminal DuckDB cutoff。completed 且 readiness 使用 DuckDB 时，terminal cutoff 必须存在且不早于 readiness；相等或更新日期合法。摘要分别报告两者，不把 readiness 值伪装成运行结果。

## Failure Handling

- DuckDB stat/fingerprint 获取失败：不命中旧成功缓存，仍允许真实 probe；该次失败不正缓存。
- probe 瞬时异常：当前调用返回无 cutoff，下一请求立即可重试。
- probe 永久挂起：调用仍受 100ms 等待上限约束；租约到期后新 generation 可接管。
- 旧 generation 迟到：只 resolve 旧 Future，不改新 generation 的 inflight 或 cache。
- terminal cutoff 缺失、非法或早于 readiness：smoke 以 `run_metadata`、exit 2 失败关闭。

## Verification

先补失败测试覆盖 exact equality、文件版本更新、瞬时恢复、挂起租约接管、旧慢/新快竞争，以及 cutoff older/equal/later；再实现最小修复，运行相关后端、前端、静态检查和 pre-commit。
