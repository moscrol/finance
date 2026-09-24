# fix/re06-visibility-timing

## 这个分支做什么
I14会话可见性计时竖切，基于06候选c5359120；不是冻结任务配对测量完成。

## 当前状态
代码已提交a4ace074；树/主树隔离，未合未推未部署。作者后续3add63d5仅文档/探针，应用代码无新增差异。本树无其他人的改动。

## 决策与被否方案
- 默认关，显式同意回包后计时；停止/切会话/pagehide补末段+撤回。
- 只记workbench:<会话>自用，task_id=null；否了拿02候选冒充05冻结任务。
- 隐藏pause/tab_hidden保留区间，不推断外部查阅或任务完成；单调时钟量时长。
- keepalive立即发末段，不排慢请求队列；失败如实缺口，不保证异常退出送达。
- 背景/被否方案/收据详见 `docs/handoffs/2026-09-14-re06-visibility-timing.md`。

## 未验证 / 已知边界
I14尚缺可信冻结任务身份→模型等待→完成→不可变收据同链验收；三视口仅合成visibilitychange，非OS真人后台。多窗口授权、全局撤回、崩溃送达未验。没有真人试点/真实前向、Knevo配对、合并候选或生产部署结论。独立QC未完成。

## 下一步
1. 独立审a4ace074同意/生命周期/失败边界，勿用作者绿代替。
2. 通过服务端解析05冻结分配后补任务级I14；不要前端编实验身份。
3. 合并候选另基最新main重验；I13/I15等用户授权。
4. E2在另一树fwp-wt-e2-boundary-closeout@1a7363c4；独立QC工具故障，P2仍不放行。

## 已验证
a4ace074 dirty=false：全仓pytest **10146/79skip/2xfail**、Ruff绿；RE全部+原Y1/Y2+05计时 **152绿**；前端lint/typecheck/build/101单测绿；全套浏览器 **34/2skip**；registry/提交钩子绿。79skip逐项解释见日期快照与-rs日志，未新增绕行。
证据 `~/.finance-runtime/verification/re06-visibility-a4ace074/manifest.json`；全量收据 `~/.finance-runtime/test-receipts/20260914T093239Z-a4ace074.json`。

## 踩过的坑
每条shell显式cd；Python用主树.venv-workbench。隔离端口8891/8894且同时设RE06_E2E_URL=http://127.0.0.1:8894，否则旧binding测试仍找8794。build改跟踪的api/static；已随源代码提交，未部署。05按event_at看同意，撤回须晚于最后区间，避免同毫秒误排。
