# 连板日历首次点击的状态同步修复

**Goal:** 页面初次显示即可选择日期和梯队，父组件回传同一天不清掉用户刚选的筛选；真正外部换日仍清筛选。

**Architecture:** `LimitUpDashboard` 在提交界面后、浏览器能与之交互前同步外部日期，沿用现有 handledFocus 去重。只将该同步由 useEffect 改为 useLayoutEffect，加载数据仍用 useEffect。

**Tech Stack:** React 19、TypeScript、Vitest 与 Testing Library；无需新增依赖。

## 复现与选择

GitHub PR32 前端失败与本机稳定探针都在点击后得到 aria-pressed=false。MutationObserver 在首次可见单元格出现时立即点击，随后回传父日期；日志显示 click(09-23) 后旧 passive effect(09-24) 才执行，把筛选和日期改回旧值。原单项15次、整文件10次均通过，说明通常的等待会隐藏该时序。

选择布局阶段同步：工作仅是比较日期和设置本地状态，适合在可交互前完成。增加 pending-selection 状态会引入额外确认/撤销协议；测试里额外等候或重跑 CI 不修复真实竞态，均不采用。不改数据端点、请求预算或用户可选日期。

## 执行与验收

- [x] 在 OriginalWorkbench.test.tsx 写稳定回归：观察首次可见 gridcell 并原生点击，回传选择日期后仍选中5板；再外部换回原日，全部梯队重新选中。旧代码明确失败。
- [x] LimitUpDashboard.tsx 仅把 focusDate/data/loading 同步 effect 改为 useLayoutEffect；保留 load 的普通 effect。
- [x] 同一回归转绿，整文件及 lint/typecheck 通过；去掉全部临时 DEBUG 日志。
- [ ] 独立 Spec/Standards 审查，再将补丁纳入 PR32 的门禁修复提交；候选固定新 SHA 后跑本机完整与前端/E2E/GitHub。FINANCEWORKS-8 内容质量仍独立验收。

原日志保留在私有 runtime 的 ladder-repro-56d0131b/。这只是发布阻塞项修复，不证明模型回答更好。
