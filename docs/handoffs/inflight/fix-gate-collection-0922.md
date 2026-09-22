# 全树门禁收集中断（分支 `fix/gate-collection-0922`，未合）

一句话：**文档规定的门禁命令 `pytest -q` 在 origin/main 上从 2026-08-20 起必停在
`Interrupted: 1 error during collection`，一条测试都跑不到；本分支把误归档的活测试移回收集面，
并让收据记下「跑的是多大一片」，修后全树 12442 passed / 0 failed。**

- 工作树 `~/fwp-wt-financial-comparison-0922`（与 `fix/financial-comparison-0922` 同树切分支，磁盘只剩 2.2G，不再开新树）
- base `f783f19c8`（= origin/main），两个提交：`999c1b1fb` 修收集面、`661811b8a` 收据记收集面
- 证据目录 `~/.finance-runtime/reviews/gate-collection-20260922/`
- 授权边界：有界离线核查；**未** push、未合 main、未部署、未跑付费模型审查

## 断在哪

`a41e86dfc`（2026-08-20，「24 个全仓零引用的孤儿脚本移入 scripts/archive/」）把
`scripts/test_kb_freshness_fix.py` 一并扫走了。它不是孤儿：

- 被测对象 `scripts/check_kb_freshness.py` 是活脚本（`skills/daily-full-review/scripts/nightly_full_review.sh` 在调，
  `intelligence/services/evidence_freshness.py` 与它对口径）；
- 该测试用 `sys.path.insert(0, Path(__file__).parent)` 定位被测脚本——文件一挪，`import check_kb_freshness` 即断；
- `pytest.ini` 的 `norecursedirs` 不含 archive，所以 `scripts/archive/` 仍在收集面内 →
  **收集期直接 Interrupted，全树一条测试都不跑**。

复现（两棵不同的树、`env -i` 干净环境与继承环境都一样）：
`/tmp/repro-collect` 最小复现 + 另一 agent 的 `~/fwp-wt-8792-financial-r6-repair` 上同样中断。
把导入修好后该测试本身是绿的（3 passed）——被扫掉的是**真实覆盖**，不是死代码。

## 为什么 33 天没人发现（这句话的精确边界）

- 「等价 CI」那条叶子 `.gitea/workflows/workbench-check.yml:37` 跑的正是 `python -m pytest -q`，
  但本机 Gitea **不跑 Actions**，所以红不出来。
- 收据库里 08-20 之后有 **187 张「≥10000 passed / 0 error / exit 0」**的收据，看着像全量绿。
  逐个回查它们的 revision：**176 个 revision 全部带着那个坏文件**（`audit_receipts.py` / `receipt-audit.json`）。
  带着它就不可能跑出未收窄的全树绿 → 这些「全量绿」**都是收窄过的读数**。
- 但收据看不出收窄：`target` 只记 pytest 的**位置参数**，182 张的 target 就是仓根绝对路径。
  `--ignore` / `-k` / `-m` / `--deselect` 一个都不入账。书面佐证：
  `docs/verification/re06-0c275716/REVIEW.md`、`re06-957e83f4/REVIEW.md` 两份复核只能从交接正文里
  找回「命令含 `--ignore=test_codex_sandbox.py`」，并因此声明不当作自己的全量结论。

所以准确说法是：**文档那条命令坏了 33 天**；期间流通的全量数字都带着**无法从收据审计的收窄**。
我没有证据说清每一张具体收窄了什么——收据没记，这正是第二个提交要补的。

## 改了什么

### 1. `999c1b1fb` 收集面

- `scripts/archive/test_kb_freshness_fix.py` → `tests/test_kb_freshness_fix.py`，`sys.path` 改指 `repo/scripts`
  （与 `tests/test_code_map.py` 同惯例；`scripts/` 下现无任何 `test_*.py`，放回去才是孤例）。
- 删掉原件手写的 `main()` 跑器：它 catch 住 `AssertionError` 后打印「✅ 所有测试通过」——
  正是这文件本身要防的假绿形状，判据以 pytest 为准。
- **判据扩一句，而不是加实例清单**：`tests/test_scripts_module_references.py` 的 docstring 已记载
  同一「零引用」误判复发三轮（#453 / #472 / 本单前身），但前几条只量「活代码 → 归档模块」的断链，
  看不见第四类变体：**被归档的就是 pytest 的收集物**。新增
  `test_archive_holds_nothing_pytest_would_collect()`（归档区不得含 `test_*.py` / `*_test.py` / `conftest.py`）
  与反向锁 `test_archive_scan_actually_looks_somewhere()`（扫描面失效即红）。

### 2. `661811b8a` 收据记收集面

- `conftest._collection_scope()`：`ignore` / `ignore_glob` / `deselect` / `-k` / `-m` / `maxfail` / `--lf`
  与实收数 `collected` 一并写进收据；
- `counts` 补 `xfailed` / `xpassed`——不补的话 `collected` 与读数天然对不平，
  「收 12000 跑 6000」这种截断就永远解释得通、也就永远查不出来；
- `scripts/check_test_receipt.py` 读它：默认**只报不拦**（验子集读数是正当用法，见既有 `--require-target`），
  `--require-full-scope` 才升成拦截项，旧格式收据按 fail closed 拒；另加收执对账，
  `exit 0` 却没跑完收集物的收据直接判红。

## 撤保护验证（不红的守卫等于没有）

| 变异 | 结果 |
|---|---|
| 把 `test_probe_guard.py` 放回 `scripts/archive/` | 归档守卫红 |
| 把 `rglob("archive")` 改成 `archive-typo` | 反向锁红（扫描面失效被抓） |
| M1 收据里不写 `scope`（接线被摘） | 红 |
| M2 `counts` 不记 xfailed/xpassed | 红 |
| M3 `_collection_scope` 漏记 `deselect` | 红 |
| M4 校验器无视收窄旋钮 | 红 |
| M5 收执对账永远判平 | 红 |
| M6 `--require-full-scope` 不接进 blockers | 红 |

`mutation-receipt-scope.json`（6/6 killed）。端到端那条测试是特意加的：单测只能证明
`_collection_scope` 算得对、校验器读得对，**若有人把 `"scope": _collection_scope(session)` 一行删掉两边仍全绿**——
门覆盖不到「有没有接上」。它真起一次 pytest，从输出里的收据路径把收据读回来。

## 读数

| 命令 | 结果 | 证据 |
|---|---|---|
| `.venv-workbench/bin/python -m pytest -q`（无任何 --ignore，@`f783f19c8`+改动） | **12442 passed / 85 skipped / 2 xfailed / 0 failed**，26m13s，exit 0 | `full-gate.log`、`receipt-full-gate.json`（dirty=true，脏的即本改动） |
| 同上（干净树 @ `661811b8a`） | **12462 passed / 85 skipped / 2 xfailed / 0 failed**，38m31s，exit 0 | `full-gate-2.log`、`receipt-full-gate-2.json`（dirty=false，`scope` 全空、`collected=12549` 与读数合计对平）、`receipt-verify.log`（`--require-full-scope` 判「可采信」） |
| `ruff check .` 全树 | All checks passed | `ruff.log` |

## 明确没做到的（别当成已解决）

- **没有 push、没有合 main**。两个提交都只在本地 `fix/gate-collection-0922`。
- **没修 CI 不跑这件事**：Gitea 不执行 Actions，`workbench-check.yml` 仍然是一张纸。
  真要门禁生效，得有人跑 runner 或改成本机钩子——本轮未动。
- **没有回溯清算那 187 张收据各自收窄了什么**：收据没记，事后无法还原；只能证明「它们不可能是未收窄的全树」。
- **同树另一分支 `fix/financial-comparison-0922` 的 13352P 是绕开坏文件得出的**（当时用 `--ignore`）。
  本分支合入后，那条分支应 rebase 到含本修复的 main 再重跑，才能给出未收窄的数字。
- 归档守卫只管 `**/archive*` / `**/deprecated*` 目录，**不**声称全树收集无错——那件事只有真跑 `pytest -q` 能证，
  所以本单的结论靠上面那张读数表，不靠守卫。
