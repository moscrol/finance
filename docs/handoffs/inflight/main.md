# 在途交接 · main

更新：2026-08-13 · #301 已合已切；RAG 已用 #302 热补丁恢复

## 这个分支做什么

生产基线。A3 冷启动已上线。

## 当前状态

- 8792 = `09dacdea`（#301）+ **热补丁** `rag_query_worker.py`（#302，未合）。中转 terra。旧 runtime `bcd3b6ce64f7` 可回滚。
- `/api/health/ready` = ready；`workers.rag.state=ready`，预热 166s。
- 不要动 Mac 开发区。合 #302 后应干净蓝绿切，去掉热补丁。

## 下一步

1. 合 #302，干净蓝绿切 8792。
2. A4：15 位哈希唯一前缀 → FORMAT；0/多匹配仍 INTEGRITY。
3. A7/A10 核验预算、A5 日期错位、governor 升档——需评审。
4. BUILD.md 候选：纠正层写收据、重试窗取当前权威、NULL 按业务语义、饿死看 stop_reason、lru_cache 勿包不可哈希加载参数。

## 未验证

- 干净 #302 SHA 部署。A3 生产冒烟未跑（R12 在 8797）。

## 踩过的坑

- 饿死判据用 stop_reason，不用 trace。
- 本地 GLM = Coding Plan URL；`ZHIPU_API_KEY` 走官方 429。
- 切 8792 不要 `reset --hard`。旧 worker 活着时 health 仍绿，换进程才暴露 KB API 变了。
- 预热同步，kickstart 后 2–3 分钟不监听。

## 已验证

- R12 冷启动点火；R7 超时重试生产通过；R8 A10 证据 0→3。
- 热补丁后 8792 RAG ready。
