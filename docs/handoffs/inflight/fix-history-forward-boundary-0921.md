# fix/history-forward-boundary-0921 在途

## 现状
整体仍 **CHANGES_REQUIRED / 未验收**。本轮只补「#814 正式门禁收据」这一个缺口，且结论**只对新候选 `42784d27e` 成立**。

候选 = `442476f7d`（历史修复）+ #814 四文件**原样移植**（`a092a021c` 的 `conftest.py`/`scripts/run_main_gate.sh`/`scripts/main_gate_receipt.py`/`tests/test_main_gate_receipt.py`，patch-id 与源侧一致）。**零产品代码改动**，不另建第二套门禁。候选与证据都在树外隔离目录 `~/.finance-runtime/reviews/research-tail-formal-gate-20260922/`（见其 `summary.json`），未推送；本分支 tip 只多这份文档，**#845 head 仍是 `442476f7d`**。

## 本轮已验
- **Python 正式门禁**：`scripts/run_main_gate.sh` exit 0，981s，**12861P / 85S / 2X，failed=0**；收据 `gates/python/receipts/gate-LeUjPpuc/pytest.json` 绑定 revision + 解释器 + `dirty=false`，写在树外。
- **收据独立复核**：`main_gate_receipt.py` 对该收据 exit 0；负向控制两条——换 revision → exit 4、谎报 pytest exit=1 → exit 4。
- **前端叶**（同 commit 的**另一个检出**）：install/lint/typecheck/`110P`/build/E2E `34P 2S 0 重试` 全 exit 0；build 产物与仓内静态资源逐字节一致（`dirty=false`、首尾身份稳定）。
- **registry 叶**：四条 `--check` + 台账对账 exit 0（反向 98 行仍是既存 warning）。

## 与 06 轮逐 ID 对账
新增 **50 个 ID 全部来自** `tests/test_main_gate_receipt.py`；**消失 0 个**；4 条状态变化全在 `tests/test_code_map.py`——`.code-review-graph/graph.db` 被 gitignore，新检出无图，那对互斥测试整体换边（3 条空图用例由 skip 转 pass，结构探针转 skip）。
**覆盖差（不要含糊）**：`test_code_map.py::test_structure_probe_daily_full` 本轮未跑（CI 同样不跑）；06 轮那次通过用的是 `b6de1a38` 建的陈旧图——两边都没把它绑到本候选。

## 未验，别外推
独立模型终审（三领域）、历史原四自然题、runtime/financial 两线、与当前 `main`（`a2c8d1f9`，领先 9 个 merge）的联合树；CI 用 node22 而本机 node26。**未合并、未推送、未部署、未回填**。06 轮证据未重跑、未复用、未重发。

## 坑
- 收据目录必须用 `FWP_TEST_RECEIPT_DIR` 指到树外，否则污染共享 `latest.json`。
- 前端 build 会写 `intelligence/api/static`（tracked），**必须另开检出**，否则 Python 叶的首尾身份校验被污染。
- 一轮 basetemp 3.4GB / 5816 项，且含测试造的只读夹具，删前要 `chmod -R u+w`（清单留在 `basetemp-inventory.json`）；本机磁盘长期 97%。

## 下一步
按授权逐项走：① 独立终审（同 thread / 串行 / 容量失败即停）；② 原四自然题单独验收，不得用单个工具或登记测试代签；③ 最后才做联合树 + 新 main 组合验收。合并与部署始终另行确认。
