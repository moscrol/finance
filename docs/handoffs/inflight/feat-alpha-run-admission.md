# feat/alpha-run-admission

树 `/Users/a77/fwp-wt-alpha-run-admission`，基座 `gitea/main`=`94f5daae`（干净树）。**未提交、未合 main、8792 未动。**

## 这个分支做什么
Alpha 内测（3–10 可信用户）前的三块基础：① `RunSupervisor` 准入与排队；② 用户数据异地备份（Mac→VPS，launchd）；③ VPS 外部拨测。运行手册 `docs/workbench/hosted-alpha-gate.md` 增补 §1.4/§2.5/§6/§7。

## 决策与被否方案
- 排队不计时：`_submit` 只入队标 `queued`，`_execute` 在 worker 线程才写 deadline/起 Timer/标 `running` / 否提交即计时 / 满载时排队吞掉执行预算
- 准入预检在配额前 + `_submit` 锁内原子复核 + 竞态输了退配额（`RunQuota.release`）/ 否只预检 / 两请求同过预检会双双入队
- 恢复路径 `admitted=True` 绕过准入 / 否一律过 / 同用户两个在途 run 会丢一个
- 三条 env 默认=历史行为（2 worker/不限/无界）/ 否改默认 / `test_workbench_api:1708` 钉 capacity==2
- 备份=每日快照+`--link-dest`+`latest`+保留 14 天 / 否 `--delete` 镜像 / 镜像把写坏的数据盖到唯一副本
- `latest` 用 `ln -sfn` / 否 `mv -f` / mv 会把新链移进旧目录（测试抓到）
- 拨测阈值 3 次、翻转才通知 / 否每次都发 / 刷屏
- owner 免每用户上限（复用 `WORKBENCH_QUOTA_EXEMPT_USERS`）/ 否新增 env / 自用脚本会连发；队列上限不豁免
- 向导改序：Access 应用先于 DNS/ingress / 否原顺序 / 原顺序在主机名生效到 Access 建好之间 8792 无认证裸奔；cloudflared 在用户域，去掉 sudo/system

## 当前状态
改 5 文件 + 新 5 文件。`_run_ask`/`_run_conversation_turn` 签名未变；前端 `RunStatus` 早含 `queued`，不用重建 bundle。

## 已验证（本树、`.venv-workbench` 解释器）
- 新增测试 18 例（admission 9 / quota 1 / backup 4 / probe 4）；相关既有套件 284 绿；`bash -n` 向导
- pre-commit 10 道 Passed（forbidden-files 无匹配 Skipped）；ruff check 绿；新文件已 format
- 备份脚本对真实 `users/`（151 目录 472MB）本地全量 8s，`latest`/`last-success.txt` 正确
- 全量 pytest @本树 **7563P/5F/15S/1x** 386s；5 红全在 `test_dream_mine.py`，`gitea/main` 干净临时树同样 5 红 → 存量

## 未验证 / 已知边界
- 远端 ssh 备份没真机试（VPS 地址未知）；`Target.parse` 两形态有单测
- 未部署快照、未跑向导、未改启动器、未 kickstart——真人步骤见手册 §7
- 准入与配额互斥范围仍单进程（手册 §4.2）；SSE 每连接占一线程未改（≤10 人可接受）

## 下一步
1. 提交（pathspec）→ PR → 合入 gitea/main（用户已确认）
2. 手册 §7 六步接线；§3 九条验收
3. 阶段 C：拆 Research Worker、队列持久化、Postgres 共享状态

## 踩过的坑
- 按文件加载含 dataclass 的脚本要先登记 `sys.modules` 再 `exec_module`
- `ruff format` 对三个既有文件的整文件重排是存量（基线同样不过），只修自己那处空行
