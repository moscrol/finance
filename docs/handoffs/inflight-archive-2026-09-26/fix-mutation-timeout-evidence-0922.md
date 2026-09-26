# 变异量具超时留证｜2026-09-22

## 这个分支做什么
让 `scripts/review_probes/run_extraction_mutations.py` 在超时/中断/启动失败时留下现场：输出直接落盘、卡住转储线程栈、进程状态独立成收据、results.json 逐步持久化。180 秒帽、变异定义、唯一锚点与还原校验都不变。只改评审量具与新增测试，不碰任何产品代码。

## 起因（不翻旧案）
2026-09-18 R6 发布套件 baseline 在并发下 180 秒超时。旧 runner 用 `subprocess.run(capture_output=True)`，只在子进程返回后写日志——超时抛 `TimeoutExpired` 时 stdout/XML/栈全部丢失，`results.json` 只剩 `complete=false, runs=[]`。**那次现场已不可补造，本分支不解释、不翻案，只让下一次可归因。**

## 决策与被否方案
| 选择 | 被否方案 | 理由 |
|---|---|---|
| Popen + 输出直接写日志文件 | 加长超时或重试到绿 | 不解决可观测性，还会掩盖首红 |
| `start_new_session` + `killpg` 只收自己的组 | 按名字 pkill pytest | 会误杀并发会话——本机实测同时有两个其他会话在跑全量 |
| 缺 JUnit 记 `missing_or_invalid` / `executed=None` | 记 `executed=0` | 0 是「证明了零执行」；超时只能说「没有完成记录」 |
| `check_result` 增加进程状态与 JUnit 门 | 只看 exit code | 超时进程 exit=-9 且无 XML，旧断言会误判或 TypeError |
| 本批撤保护探针放证据目录 | 用正式量具验它自己 | 循环论证：正式量具正是被测对象 |

## 当前状态
分支 `fix/mutation-timeout-evidence-0922`，提交 `e9e3361adb27af0466613b1b2d1f49fdd7cfa84c`，基座 main `a2c8d1f90773`。源码树 clean。**未 push、未提 PR、未合 main、未部署、未动 8792。**
证据根：`~/.finance-runtime/reviews/mutation-timeout-evidence-20260922/`。

## 已验证（本树、精确 SHA）
- 定向 23P；全量 **12534P / 85S / 2X**、Ruff 全仓 0。精确收据 `20260922T111226Z-e9e3361a.json`，`check_test_receipt.py --expect-revision` exit 0（revision / 解释器 / python 版本 / 依赖指纹 / 干净树 / 依赖门禁均对上）。
- 前端 lint+typecheck+**110P**+build exit 0；E2E **34P/2S** exit 0；registry 五项（parseability / check / backfill-tables / generate-views / crosswalk）exit 0。
- 撤保护 **11 组**：每组红都有具名证人、还原后绿、前后字节指纹一致，`results.json complete=true`、最终树 clean。
- pre-commit 9 项通过，2 项因无相关文件跳过。

## 未验证 / 已知边界
- **不归因 09-18 那次超时**。本轮只证明「以后超时会留证」，没有证明那次的原因；观察到本机并发全量是常态，但那是旁证不是结论。
- 没有重跑 R6/#835 的 publication 套件本身，本分支不改变它的任何成绩。
- `save_json` 的原子替换没有独立证人（无并发写场景断言）。
- E2E 两个旋钮不联动（配置读 `RE06_E2E_PORT`、用例读 `RE06_E2E_URL`），只设端口会让用例打到旧地址。现存尖角，本轮未修。
- 本轮零新自然模型验收、零独立 QC；R6 线的真实验收不因此前进。

## 下一步
1. 要归因发布超时：在 #835 固定 SHA 上重跑 publication 套件；若再超时，读 `<label>.log` 尾部线程栈与 `<label>.process.json`，不要重试挑绿。
2. 合 main 需用户确认；合入前按四叶重验（本树读数只对 `e9e3361a` 成立）。
3. R6 线真正的收口仍缺独立 QC 与真实验收，且 R6 已被 #835 财务前向候选接替，不要在旧树上重复推进。

## 踩过的坑
- 我提交时加了 `-c core.hooksPath=.githooks`，该目录不存在 = **静默跳过全部 pre-commit**。事后补跑 9 道确认没掩盖失败。要跳过钩子必须显式 `--no-verify` 并说明；指错 hooksPath 不会报错。
- `pgrep -f pytest` 会匹配到**别的会话**的全量运行，被误读成自己的任务还没结束。判断自己的进程要用自己的 PID。
- E2E 在新 worktree 找不到 `.venv-workbench`，会静默回落宿主 python3 并报 `No module named uvicorn`；用 `WORKBENCH_PYTHON` 显式指定。
