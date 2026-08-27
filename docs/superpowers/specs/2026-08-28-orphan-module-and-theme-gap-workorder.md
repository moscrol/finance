# 工单：归档孤儿模块第三次复发 + 题材预取静默空手（2026-08-28）

- 状态：**待认领**。两件独立可拆，P0 先行。
- 来源：用户要求对 08-27/08-28 两日 30 个已合 PR 做独立质检，两处实测缺陷。
- 基座：`gitea/main@f9976cbb`，干净树 `/Users/a77/fwp-wt-qc-0828`。
- 台账：**预注册 `R-20260828-04`，行与本单同提交**（crosswalk 正向门要求）。
- 质检读数（全量，`/tmp/qc-main` @ `1813acd3`）：`1 failed, 6875 passed, 12 skipped`，
  ruff `All checks passed`。唯一红是 `test_installed_codex_sandbox_denies_network_and_unix_socket`
  ——**与本单两件事都无关**，见 §3：`/tmp` 工作树专属，三条网络腿全 denied，
  红只出在文件系统腿；非本批 PR 引入。

---

## 0. 一句话

P0：**两个**模块于 08-20 被当作「零引用孤儿」归档，但它们是**被字符串引用的
`-m` 子进程模块**，静态搜不到——`sync_akshare_market_snapshot`（AkShare 兜底
provider）与 `forecast_learning_loop`（每日双盲的学习上下文注入）
**已死 8 天**，且死得无声。
P1：`_theme_sector_snapshot_items` 的缺口声明挂在 `elif items:` 上，
**板块行不存在时连缺口都不声明**，返回空元组——与该函数自己写的 fail-closed 契约相反。

---

## 1. P0 · 归档孤儿模块：同一个洞的第三次复发

### 1.1 实测证据

```
$ cd /Users/a77/finance-workspace-runtime      # 生产 code_root
$ /Users/a77/.local/share/finance-workbench/akshare-venv/bin/python \
    -c "import importlib.util as u; print(u.find_spec('scripts.sync_akshare_market_snapshot'))"
find_spec -> None
```

调用点 `intelligence/services/market_snapshot_sync.py:369`：

```python
subprocess.run([str(python), "-m", "scripts.sync_akshare_market_snapshot", ...],
               cwd=code_root, ...)
```

生产可达链路（非死代码）：
`scripts/run_market_snapshot.sh` → `--akshare-python` + `--code-root`
→ `sync_market_snapshot(...)` → `_subprocess_akshare_runner` → 上面那行。

文件现位置：`scripts/archive/sync_akshare_market_snapshot.py`，
归档提交 `a41e86df`（2026-08-20，「24 个全仓零引用的孤儿脚本移入 scripts/archive/」）。

第三处引用点 `scripts/run_akshare_snapshot.sh` 由 §1.5b 的判据测试扫出来
（人工逐个反查时漏了它）——这本身就是「判据优于清单」的一次实证。

### 1.2 第二个：`forecast_learning_loop`（本单判据测试扫出）

`scripts/dual_blind_auto.sh` — launchd **工作日 09:10** 自动跑
（`intelligence/dream/com.financeworkspace.dual-blind-forecast.plist`）：

```sh
/usr/bin/python3 -m scripts.forecast_learning_loop sync-reflections   >> ... || true
/usr/bin/python3 -m scripts.forecast_learning_loop sync-annotations   >> ... || true
LEARNING_CONTEXT=$(/usr/bin/python3 -m scripts.forecast_learning_loop prompt --limit 5)
```

前两处 `|| true` 吞掉失败；**第三处没有 `|| true`**，但脚本是 `set -uo pipefail`
（无 `-e`），命令替换失败只让 `LEARNING_CONTEXT=""` 然后继续。
净效果：**每日双盲答卷静默地不再注入已批准的 lessons/rules**——
§8 那套「批注→审批→注入」的学习闭环 8 天来一直在空转。

归档的 `forecast_learning_loop.py` 恰好提供 `sync-reflections` /
`sync-annotations` / `prompt` 三个子命令，与三处调用一一对应，确系同一模块。

### 1.3 为什么两处都静默

- AkShare：`runner()` 的非零退出不抛异常，下游 `validate_market_snapshot_root`
  在空临时目录上判定不 PASS，于是 `akshare_exact` 记为失败、**继续走下一个
  provider**。「兜底 provider 永远失败」被表达成「今天 AkShare 没取到」，
  与真实网络失败在读数上不可分辨。
- 双盲：见上，空串继续跑。

**共同形状：能力静默丢失，指标上看不出来。** 这正是本仓反复钉的那类反模式。

### 1.4 这是第三次复发，前两次就在本批 PR 里

| 轮次 | PR | 移回的脚本 | 抓到的方式 |
|---|---|---|---|
| 1 | #453 | 5 个（`audit_marker_vocabulary` 等） | main 测试收集炸 |
| 2 | #472 | `theme_radar_quality_rules` | 两处生产引用 |
| 3 | **本单** | `sync_akshare_market_snapshot` + `forecast_learning_loop` | 质检反查 + §1.5b 判据测试 |

三轮都是同一个 08-20 sweep 的残留。**前两轮修的是实例，没修判据**——
`#253`/`a41e86df` 的「零引用」判据只认静态 import，
不认 `-m "scripts.X"` 这类**字符串形式的模块引用**，所以每次只能靠下一次事故发现。

### 1.5 修法

**a. 移回**（P0）：`sync_akshare_market_snapshot.py` 与 `forecast_learning_loop.py`
从 `scripts/archive/` 移回 `scripts/`。用 `git mv` 保历史。

**b. 判据补洞**（P0，防第四次）：`tests/test_scripts_module_references.py`——
扫描全仓活代码，断言被引用的 `scripts/<name>.py` 真实存在。只认两种**无歧义**
形式：(1) `-m` 后跟的模块名，跨 `.py` 字符串字面量与 `.sh` 命令行同一条正则；
(2) 真 import 语句，经 **AST** 取而非正则。

AST 而非正则是关键：`test_rag_worker.py` 把 `from scripts.rag_freshness import ...`
写在一个**字符串**里喂给临时目录（模拟知识库仓），正则会误报，AST 看到的是
`Constant` 不是 `Import`。第三条测试就是钉这个反向锁。

这条测试是**判据**，不是实例清单——对未来任何一次归档 sweep 一律生效。

> ⚠ 不采用「把 archive/ 从收集面排除」之类的绕法：问题不在测试收集，
> 在**归档判据本身漏认一整类引用形式**。排除只会让第四次复发更晚被发现。

### 1.6 验收

1. 上面那条 `find_spec` 在生产 code_root 下返回非 None。
2. 新增测试在移回前必红、移回后转绿（变异验证：把文件挪回 archive/ 应立刻复红）。
3. `scripts/archive/` 剩余 15 个脚本全部通过同一条判据（已实测：无第三个漏网）。

---

## 2. P1 · 题材预取：解析成功却静默空手

### 2.1 实测证据

`intelligence/services/asof_prefetch.py::_theme_sector_snapshot_items`
（#484 引入，`R-20260828-02`）。离线复现（本单实跑）：

```
Case A（as_of 早于该板块首行）        : 0 items -> []
Case B（exclude_sector 命中 + 当日无成员行）: 0 items -> []
```

### 2.2 形状

函数自述写着「解析不到 → 单条 fail-closed 提示项，不臆配」，
但 fail-closed 只覆盖了 `sector is None` 这一条路。缺口声明写成：

```python
    elif items:                     # ← 缺口声明挂在「板块行已产出」上
        items.append(... "成员行缺失" ...)
    return tuple(items)
```

于是 `items` 为空的两条路都静默返回 `()`：

- **A**：`row is None`（板块在表里有行，但全在 `as_of` 之后）。
  `resolve_prefetch_sector` 经 `load_theme_daily_rows` 判存在性，
  而后者**不带日期过滤**——所以「板块存在」与「as_of 当天有行」是两件事。
  本仓明确支持回溯问句（`requested_information_cutoff`，#473 刚修过区间起点），
  问一个板块诞生前的日期即命中。
- **B**：`exclude_sector` 命中（发酵分支已交付时间轴）且当日无成员行。
  **缺口声明恰好在发酵分支活跃时被抑制**——而成员映射正是该分支不提供、
  本函数存在的理由。

两条路的后果一致：模型拿不到数，**也不知道自己没拿到**——
正是本 PR 立项要治的「判据要的供数永远缺席」。

### 2.3 修法

把缺口声明从 `elif items:` 解绑，按两个维度各自独立声明：

- `row is None` → 声明「板块行缺失」（点名 `fact_sector_daily` 与 as_of，
  提示不得用其他日期冒充）。
- `member_rows` 为空 → 声明「成员行缺失」，**不再看 `items` 是否非空**。

净效果：`sector` 解析成功时函数**永不返回空元组**——要么给数，要么给缺口。

> 边界：`sector is None` 那条既有路径不变（已 fail-closed）。
> `exclude_sector` 抑制的只是**板块行**，缺口声明不受它影响。

### 2.4 验收

1. 上面 Case A / Case B 各转为「返回恰好 1 条缺口项」，标题点名缺的是哪一层。
2. 既有三条测试（`test_exact_name_in_question_beats_broadened_subject` /
   `test_unresolved_subject_fails_closed_with_note` /
   `test_ferment_sector_exclusion_keeps_members`）逐字节保持绿。
3. 变异验证：把新守卫改回 `elif items:`，新增两条必红。

---

## 3. 附：全量质检结论（不立单，仅留档）

- **唯一红非本批引入，且不是 App 漂移——是「质检树放在哪」决定的**
  （`test_installed_codex_sandbox_denies_network_and_unix_socket`）。
  实测对照，同一二进制、同一提交、同一解释器，只换工作树位置：

  | 工作树 | public_tcp | loopback | unix_socket | **live_root_read** | status |
  |---|---|---|---|---|---|
  | `/private/tmp/qc-main` | denied | denied | denied | **unexpected_success** | `unproven` ❌ |
  | `/Users/a77/fwp-wt-qc-0828` | denied | denied | denied | denied | `proven` ✅ |

  **三条网络腿在两处都 denied**——测试名点的「network and unix socket」根本没坏。
  红全部来自文件系统腿：`probe_sealed_isolation` 用
  `Path(__file__).resolve().parents[2] / "AGENTS.md"` 当 live_root，
  断言沙箱**读不到**它；而 codex `:minimal` 读权限**放行 /tmp**，
  于是仓库一旦位于 `/tmp` 下，这条断言必然 `unexpected_success`。
  `/tmp` 下重复 2/2 红、`/Users` 下重复 3/3 绿，非 flaky。

  → **这是一颗埋在质检流程里的地雷**：AGENTS.md §7 让质检开干净 worktree，
  路径由人随手定；开在 `/tmp` 就会对一个与改动无关的题目报红。
  与本仓 `pytest.ini` 注释记的那次事故同形状——「文档里的验收命令」与
  「实际能跑的命令」按路径分叉，两周无人知。

  **本单不改它**，因为两种修法的取舍是判断题，改错方向就把真门禁变成假门禁
  （本仓明令禁止）：(a) 让 live_root 取一个必然在沙箱可读集之外的锚点，
  使断言与仓库位置无关；(b) 保持断言，改为在仓库位于 `/tmp` 下时显式
  skip 并说明理由（**不是** xfail——xfail 会把真失败也吞掉）。
  倾向 (a)：它修的是判据本身；(b) 只是让地雷不响，仓库真放 /tmp 时隔离
  确实没被证明。**建议单独立单**，附上上表作为证据。
- **30 个 PR 的其余部分未发现缺陷**。抽查深读了 #481 / #473 / #465 / #484 /
  #482 / #470 / #480 / #461 的全部非文档 diff：证据链、fail-closed 方向、
  变异验证、生产 run 号引用均到位。#481 的取号器本单实跑取到 `R-20260828-04`，
  双源仲裁与自述四项工作正常。
- **流程观察（非缺陷）**：`#453`→`#472`→本单是同一 sweep 的三轮残留，
  每轮都靠事故发现。本单 §1.5b 的判据测试是第一次修「判据」而非「实例」。
