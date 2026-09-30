# 嵌套门禁测试的环境隔离 · 2026-09-30

分支 `claude/test-isolation-tmpdir-hw7e8h`（GitHub origin）。代码头 `3d2b1ba99af6`，四个代码提交：
`12ec68c1` TMPDIR 隔离 → `4129bdad` conftest 只读目录收尾 → `bca70085` 并入 Mac 原会话测试 → `3d2b1ba9` 剥 GATE_*。
另有 runbook 与本交接两个文档提交。

## 背景

09-30 门禁跑 #988 时，`tests/test_main_gate_receipt.py::test_gate_without_basetemp_flag_touches_nothing`
超出 `run_gate()` 的 40 s subprocess 超时；同树单跑整文件 66/66、20 s。这条用例专测「不带 `--basetemp`」，
而 `gate_env()` 只覆盖 `HOME` / `PYTHONDONTWRITEBYTECODE` / `FWP_TEST_RECEIPT_DIR`，`TMPDIR` 继承外部，
于是嵌套 pytest 落到全机共享的 `$TMPDIR/pytest-of-<user>/`：与并发会话共用编号与清理；Mac 上那里积着
2 个删不掉的 `garbage-*`（实测 14045 条目、202 个只读子目录），pytest 每次建 basetemp 都去重试清理。

`garbage-*` 的来历：pytest 删旧编号目录时，`rm_rf` 的权限修复只向上修**文件**的父目录；只读的**子目录**
删不动，整个目录被改名成 `garbage-<uuid>` 留下，此后每次启动重扫。只读目录来自导出 / 冻结 / 封存类
产品代码（这正是它们要测的行为）。

原会话在 Mac 树 `fix/main-gate-tmpdir-isolation` 留下一条未提交测试后额度耗尽；本会话（云端，推 GitHub）接手。

## 按发现顺序

1. 先写位置断言测试（嵌套 pytest 回报 `tempfile.gettempdir()` 与 `tmp_path`），修前红（temproot=`/tmp`）。
2. `gate_env()` 设 `TMPDIR=<tmp_path>/sys-tmp` 并 **先 mkdir**。去掉 mkdir 的变异同样红——
   `gettempdir()` 对不存在的 TMPDIR 静默退回 `/tmp`，只设变量等于没修。
3. 共享根预埋 `garbage-*`：修前嵌套 gate 建了 `pytest-0/1` 并把它清掉，修后原样不动。
4. 基线全量（未改 main，basetemp 放 scratch）扫只读目录：21 个用例实例留 114 个只读目录，20 个测试函数
   分布在 `test_ceiling_instruction_export` / `test_ceiling_pit_fixture` / `test_build_agent_runtime_ceiling_fixture`
   / `test_run_agent_runtime_benchmark` / `test_repair_backfill_stock_history`。→ 根 conftest 收尾夹具。
5. 经隧道读 Mac 树原会话的测试：它断言的私有目录名恰好也是 `sys-tmp`，并额外压「继承的 TMPDIR 带残留、
   假根一个字节不许动」——正对完成标准。在本实现上绿、去掉 TMPDIR 红，原样并入。
6. 容器门禁带 `GATE_KEEP_BASETEMP=1`（为事后扫 basetemp）跑全量，`test_green_gate_removes_explicit_basetemp`
   只在本分支红：外层开关经 `gate_env` 漏进嵌套 gate，绿了也不删 basetemp。直接跑 pytest 时看不出。
   → 剥 `GATE_*`，并把 `monkeypatch.setenv("GATE_KEEP_BASETEMP","1")` 写进该用例本身。
7. Mac 门禁第一轮也带着该开关，停掉重来；第二轮经隧道起，exec 服务 PATH 无 node → 18 条假红 + 1 条
   锁竞争时序红（见下）；第三轮用登录 shell 的 PATH，全绿。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| gate_env 设 TMPDIR（先 mkdir） | 覆盖所有 tempfile 用户；可被 extra_env 覆盖 | 采用 |
| 设 `PYTEST_DEBUG_TEMPROOT` | 只管 pytest；名字是调试用途；gate_env 本就剥 `PYTEST_*` | 否 |
| 证明：TMPDIR 指不可写目录，等用例失败 | gettempdir 静默退回 /tmp，用例照过；容器里 root 无视权限 | 否 |
| 证明：断言嵌套 pytest 实际临时根 + 假根带残留不被碰 | 直接测「在哪」，不依赖副作用 | 采用（两条） |
| 只读目录：逐条补 `finally: chmod` | 20 条 / 5 个文件，改动面大，新增用例会漏 | 否 |
| 只读目录：`pytest_sessionfinish` 扫整个 basetemp | 要私有 API `config._tmp_path_factory`；强建 basetemp 会触发共享根清理 | 否 |
| 只读目录：根 conftest autouse，仅对用 tmp_path 的用例收尾补 u+rwx | 一处生效、自动覆盖新增；软链不跟、文件不动、出错不变红 | 采用 |
| 另写一条残留测试 | 与原会话重复 | 否，原样并入原会话那条 |
| gate_env 剥 `GATE_*` | 与 TMPDIR 同类；需要的用例本就经 extra_env 传 | 采用 |

## 验证与收据

- **Mac 全量门禁（权威）**：`3d2b1ba99af6` 18709P / 0F / 75S / 2X，collected 18786 对平（= #988 的 18782 + 本分支 4 条新测试），
  `check_test_receipt.py --require-full-scope` exit 0。收据 `~/.finance-runtime/test-receipts/gate-Hu4e6NDk/pytest.json`。
- 红收据留作证据：`gate-NvV3Nzb6`（第一轮，带 GATE_KEEP_BASETEMP，86% 手动中止）；`gate-rwtmuYYX`（exec PATH 无 node，
  18 条 node 假红 + 1 条锁竞争）。同树登录 PATH 下 `tests/test_pi_review_repair.py` 75P，锁竞争单跑 3/3 绿。
- 容器（Python 3.12.3、无 macOS 设施）：未改 main 基线 61F / 18513P；最终提交 60F / 18518P，**60 条全部同见于基线**，零新增。
  前端 lint/typecheck/test/build 绿；e2e 34P/2S（需把 playwright 期望的 `chromium_headless_shell-1179` 别名到预装 1194，只在 scratch 做）；registry 五项绿。
- 变异 7 种均被抓：去 TMPDIR、去 mkdir、去收尾调用、lstat→stat、只修根目录、去 GATE_ 前缀（先改测试后改实现）、Mac 测试在去 TMPDIR 时红。
- 只读目录：修后 Mac 全量 basetemp 0/8892、容器全量 0。
- 不成立的结论：容器读数不能当全量绿；锁竞争那条的「负载相关」只有两次历史红 + 3 次单跑绿，n 小，未定根因。

## 后续

- 合入：Mac 上 `git fetch origin claude/test-isolation-tmpdir-hw7e8h` → 推 Gitea → 开 PR → 用户确认后合。
- 收口 Mac 树 `.claude/worktrees/unclosed-session-stats-838ac4`（目录名与分支名对不上，别认错）。
- `test_http_correction_lock_contention_is_bounded_and_cannot_write_later` 负载下 busy≠cancelled，另开单查。
- Mac 共享临时根本轮已清 `garbage-*`（2 个），并把 09-29 的 `pytest-4818` / `pytest-4821` 里只读目录改可写，交还 pytest 自清。

## 不要做

- 别把 `sys_tmp.mkdir` 当冗余删掉：删了嵌套 pytest 会静默回到全机 /tmp，只有位置断言能抓住。
- 别为「更快」把收尾夹具改成 sessionfinish 扫全 basetemp：见上表，会强建 basetemp 并触发共享根清理。
- 别用「指向不可写目录」的思路给别处写隔离测试：Python 的 tempfile 不会失败，只会悄悄换目录。
