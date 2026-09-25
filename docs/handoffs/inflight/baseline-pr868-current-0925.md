## 这个分支做什么
把 #868/#910/#911 组合前向到固定 main fe9，交付新鲜离线证据；不合 main、不部署 8792。

## 决策与被否方案
| 选择 / 否掉 | 理由 |
| --- | --- |
| 新树重跑 / 继承旧收据 | main 改五个 HTTP 调用点；收据须绑新 SHA |
| 修探针及读数 / 改产品异常 | observer 接口与最终预算槽理解错误不等于产品缺陷 |
| 保存旧日志 / 修剪换绿 | 封存字节不可改，格式红也不豁免 |
| 新补审提案 / 借旧预算 | 授权、候选与逐轴证据均不可转移 |
展开：`docs/handoffs/2026-09-25-pr868-current-base-offline.md`。

## 当前状态
受测代码已提交：`fb41cebdaa6a186c14bd402f0f2dd83705f64421`，基座 `fe9fdbfd70a637efc5bcf0cfecf74080a8d6a90c`，合入旧组合23536。代码树验时干净。后续 docs-only 交付不继承完整收据。进程已结束，专用19981/19984无监听。

## 已验证
Python 16243P/0F/75S/2X，collected16320；Ruff、registry五项、前端123P、E2E34P/2S均通过。完整scope/身份/解释器/依赖收据校验exit0；固定解释器 `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`。
C3作者及时/迟到2例及启用compat的五调用点12例通过；内层两轴各C3 3P/C7 66P原件已保存，不重复计数。
仓内证据 `docs/verification/2026-09-25-pr868-current-offline/`；原根 `/Users/a77/.finance-runtime/reviews/pr868-current-20260925/attempt02/`。

## 未验证 / 已知边界
fb41无独审、无L6。并行owner旧f261 C3 spec获有限采信；其跨旧批spec汇总不是当前双轴闭合，旧quality/C7限制不可抹去。其333/354不是本轮余额。
缺真库57等共75S、2个既有xfail；真实金融来源/自主研究/反证修订/live identity未验。代码diff-check有8份继承封存文件空白；新增归档另4份原始日志带空白，docs-only检查也exit2，均未豁免。
main验中前进到4db9a42b6，仅两份文档变化，未重绑本收据。

## 下一步
owner选定最终候选后，另批新根双轴独审：提案每轴39、总78，无自动重试/增额。不得直接运行历史generator。其后另批L6、当时revision门禁、main合入及可回滚部署。本轮新增付费请求0。

## 踩过的坑
observer需 `(event, **fields)`；最终零预算槽exc_class=None不代表实际请求没超时，要读last_dispatched_failure。第一轮错误断言日志保留。pytest会截短tmp目录名，内层证据按布局找。controller完成不是语义PASS。
