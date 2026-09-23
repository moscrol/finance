# feat/adaptive-research-loop 在途

## 这个分支做什么

研究回路取证、窗口收益、公开保真及 LLM 传输层绝对截止；工单 #72 / PR #868。验收与 #76/#75 条件卡：`docs/verification/2026-09-22-adaptive-deadline/README.md`。

## 决策与被否方案

- 代码前向后重跑四叶，否了沿用旧树收据；测试冲突同时保留 main 的 complete 参数化和本枝传输层 mock。背景：`docs/handoffs/2026-09-23-adaptive-deadline-forward.md`。
- 后续 main@9a0227986 仅文档，前向得 a663ec524；QUEUE 保留两侧所有候选。代码尖到该提交只有 docs，不伪称新 head 跑过全量；详情见 README 后续文档前向节。
- 共享 deadline 转发变异由 c582d6755 用例杀死；is_cancelled 转发变异存活，留后续补停顿期用例，不改已验代码尖。
- 工程绿不等于合入授权，保留 WIP。

## 当前状态

文档合流 a663ec524 已推送功能分支；纳入 main@9a0227986。PR 描述 C2 已改为 5 处调用，C7 明确收据绑定 7ad61a0d3；标题 WIP、open、未合入。本文件及 README/INDEX 收尾只改 docs，精确 head 以 Git/PR 回读为准。未部署、未碰生产 8792。

## 已验证

7ad61a0d3 加锁隔离树：九项 exit 0，pytest 14921P/85S/2X/0F；前端单测 120P、E2E 34P/2S；ruff、registry×4+crosswalk；严格探针 0 越窗；定向回归 63P。收据根 `~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`。收据再次校验通过（含 full-scope；collected=15008）；a663ec524 对冻结 main@9a0227986 conflict-check clean。收据不属于后续文档 head。

## 未验证 / 已知边界

#76 L6 未跑，#75 终审未完成。新离线预检与待授权协议见 `docs/verification/2026-09-23-adaptive-l6-preflight/README.md`：四旧记录提取、9 测试通过；顺序成环（L6 要合后 main、终审要合前、#72 要先 L6），候选实测的顺序修订及模型/数据授权均待确认；旧 compare 端口落在 #76 禁用区，不可直接开跑。absence-live 内容问题、is_cancelled 停顿期阳性守护及 5 处 timeout 的 Deadline.slice 来源仍未收口。

## 下一步

1. 用户确认前保持 WIP，不合 main。
2. 合前重新 fetch、冻结双方 SHA、核冲突及代码差异；新增代码需新合流树四叶，不套用本次收据。
3. 请用户批准 L6 候选实测顺序与三题预算/数据冻结；再补判定器阳性对照和启动收尾控制。未批准不发模型请求。L6 后才推进 #75。

## 踩过的坑

全量 pytest 用主树 venv、独占 basetemp；并发高负载与磁盘不足会伪红。QUEUE 两侧各建文件会 add/add，按候选行合并。测试树已加锁，审查者另建树，不清理它。
