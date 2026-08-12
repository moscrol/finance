# 在途交接 · main

更新：2026-08-13 · 夜间循环三 PR 待合；无下一只已钉死的 harness bug

## 这个分支做什么

生产基线。夜间按 part 修 bug。

## 当前状态

- 8792 = `09dacdea`（#301）+ RAG 热补丁（#302 未合）。中转 terra。
- 待合：#302 RAG worker、#303 A4 截断哈希、本轮 A1-R2 冷启动。
- 不要动 Mac 开发区。

## 下一步

1. 合 #302/#303/A1-R2，一次干净蓝绿切（去掉热补丁）。
2. A5 日期错位：knevo 对照笔记，非本仓日期过滤 bug；无收据不改。
3. A7/A10 核验预算、governor 升档——设计，不是 bug。

## 未验证

- 三 PR 生产冒烟。

## 踩过的坑

- 切 8792 不要 `reset --hard`。预热同步，kickstart 后 2–3 分钟不监听。
- 饿死看 stop_reason，不看 trace；`model_finish` 不是饿死。

## 已验证

- R12 冷启动；R7 超时重试；R8 A10；热补丁后 RAG ready。
