# 在途交接 · main

更新：2026-08-13 · 夜间循环：#301 已上线；#302 RAG 热补；A4 PR 待合

## 这个分支做什么

生产基线。夜间按 part 修 bug，早上验收。

## 当前状态

- 8792 = `09dacdea`（#301）+ RAG 热补丁（#302 未合）。中转 terra。
- A4 在 `cursor/hash-prefix-format-d7ac`（`truncated_hash` → FORMAT）。
- 不要动 Mac 开发区。

## 下一步

1. 合 #302，干净蓝绿切（去掉热补丁）。
2. 合 A4。
3. A5 日期错位定因；A7/A10 核验预算仅修明确 bug。

## 未验证

- 干净 #302 部署。A3/A4 生产冒烟未跑。

## 踩过的坑

- 切 8792 不要 `reset --hard`。旧 worker 活着时 health 仍绿。
- 预热同步，kickstart 后 2–3 分钟不监听。
- 哈希截断口子只认少 1 位唯一前缀。

## 已验证

- R12 冷启动；R7 超时重试；R8 A10；热补丁后 RAG ready。
