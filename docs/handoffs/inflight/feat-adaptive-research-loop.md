# feat/adaptive-research-loop 在途

## 这个分支做什么

修研究回路计划、取证、修订与公开保真；工程边界已修，09-22单次自然验收内容失败。

## 决策与被否方案

local_only四只读能力冻结，不开derived_calculation；根T900、单帽75、每次核验内部共享窗150不变。不重跑挑样本，不改旧答案。
空集仅本次未命中，未查/失败只能尚未查证；历史回退不认证退出；gap不是收据，直接零值可引用。拒正则一律删否定句。
详见 `docs/handoffs/2026-09-22-adaptive-absence-live.md`；旧非命中/均值背景见09-21同目录快照。

## 当前状态

树 `/Users/a77/finance-worktrees/adaptive-research-loop`。业务81ff5e7da，live加载干净a1da0c98e；本轮只改交接，不移签live到文档tip。未push/PR/合main/部署/fetch，未请求/重启8792；隔离8797已退出。
新run `run_20260922_002223_310816` 原件 `~/.finance-runtime/adaptive-absence-live-20260922/`。584.26秒，9写手/15工具/4判官调用；transport completed，内容partial，judge unavailable。

## 已验证

唯一一次off臂K3真实消息；3次参数错误后纠正、无外部研究工具。backfill1+semantic-gap repair1均无工具且自报completed；新稿重新送核、stale=false，但两次核验均不可用。末次实际失败TimeoutError有脱敏收据，0秒拒发与实际调用分开。
只读claim-audit确认9月14行：个股-3.0766%、申万综合-2.3047%、芯片+0.5615%、氟-3.5973%、FP综合-4.2820%。除个股外正文累计全错，氟强弱方向反；±1.6%概括漏9/7的+3.70%。审计前后库/股票行一致。
探针25P；旧a1da0c98e定向709P及81ff5e7da六+五变异为各自版本工程证据，不签本轮内容。解释器主树 `.venv-workbench/bin/python`。

## 未验证 / 已知边界

无PLAN、无均值选择/均值陈述、无finance成功空集、无直接零值/历史回退自然验收。无工具自报partial终局格仍待。本次未见私有诊断泄漏但非独立审查。
独立判官未裁决；修订由程序预检推动。两次核验合计4发，不是全回合共享150秒；timeout_asked不是耗时。9/19以后未查，单次旧新闻片段不证整个库无同期证据。
旧run_20260921_203845_282895仍partial，均值错和无据否定不改判。判官失联可交未审错误，发布提示不保证内容正确。

## 下一步

先离线复现窗口收益计算/相对强弱错误，论证复用只读聚合；核查判官超时归属，禁止为刷绿加live。后续真实样本另预注册。
前向基线、完整Python/前端/E2E/registry及独立Spec/Quality另签；不自动推进生产。

## 踩过的坑

独占basetemp先建父目录；limit_up是零值指标。ok=true可包parse_error，不能当空集。绑定通过不证数学正确；判官轮数、调用数、拒发数须分开。
