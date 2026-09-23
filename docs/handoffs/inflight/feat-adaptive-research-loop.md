# feat/adaptive-research-loop 在途

## 这个分支做什么

研究回路取证、窗口收益、公开保真及 LLM 传输层绝对截止；工单 #72 / PR #868。验收与 #76/#75 条件卡：`docs/verification/2026-09-22-adaptive-deadline/README.md`。

## 决策与被否方案

- 代码前向后重跑四叶，否了沿用旧树收据；测试冲突同时保留 main 的 complete 参数化和本枝传输层 mock。背景：`docs/handoffs/2026-09-23-adaptive-deadline-forward.md`。
- 后续 main@9a0227986 仅文档，前向得 a663ec524；QUEUE 保留两侧所有候选。代码尖到该提交只有 docs，不伪称新 head 跑过全量；详情见 README 后续文档前向节。
- 共享 deadline 转发变异由 c582d6755 用例杀死；is_cancelled 转发变异存活，留后续补停顿期用例，不改已验代码尖。
- 工程绿不等于合入授权，保留 WIP。

## 当前状态

9c9c0c0a1 已推送，后续仅 docs；用户已批准 L6 候选先验顺序、三题预算及只读副本，并要求核对判官开关。差异已查明，尚未发模型请求或冻结数据。PR 保留 WIP；未部署、未碰生产 8792。

## 已验证

7ad61a0d3 加锁隔离树：九项 exit 0，pytest 14921P/85S/2X/0F；前端单测 120P、E2E 34P/2S；ruff、registry×4+crosswalk；严格探针 0 越窗；定向回归 63P。收据根 `~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`。收据再次校验通过（含 full-scope；collected=15008）；a663ec524 对冻结 main@9a0227986 conflict-check clean。收据不属于后续文档 head。

## 未验证 / 已知边界

#76 L6 未跑，#75 未终审。协议及判官对照见 `docs/verification/2026-09-23-adaptive-l6-preflight/README.md`：授权已获，启动收尾控制/失败阳性对照未齐；旧 compare 端口禁用。off 仍可规则删句和写手改稿，但判官迟到自然路径为 NOT_EXERCISED；adaptive_arm=off 不是关判官。113 项离线回归过，收据绑定 9c9c0c0a1。absence 内容、is_cancelled 停顿期阳性守护及 5 处 timeout 来源未收口。

## 下一步

1. 用户确认前保持 WIP，不合 main。
2. 合前重新 fetch、冻结双方 SHA、核冲突及代码差异；新增代码需新合流树四叶，不套用本次收据。
3. 不重复索要已有授权；固定候选 31f1b40dd 和两个判官模式，补齐阳性对照及启动收尾控制，再执行三题。用户未明令改 off，不擅加开关双组调用。L6 后推进 #75。

## 踩过的坑

全量 pytest 用主树 venv、独占 basetemp；并发高负载与磁盘不足会伪红。QUEUE 两侧各建文件会 add/add，按候选行合并。测试树已加锁，审查者另建树，不清理它。
