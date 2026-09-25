# 执行阶段最终交付（spec 轴 #75 / PR #868）

**未完成事项（先行声明）**：工具在收尾时关闭，`EXECUTE.md` 未能落盘（原目标路径 `/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/spec/work/EXECUTE.md`），本文件即替代交付；作者测试（含 `intelligence/tests/test_llm_timeout_diagnostic.py`）本次会话未运行，仅 `wc -l`（208 行）；C3/C5/C6 未做行为探针。

## 三张账

**必红对照（单独先跑）**：`positive_control.py` → exit 1，`AssertionError: intentional probe_bug control`，与装置设计一致。分类 `intentional_positive_control`，未修改、不计产品失败、不计绿。

**审查者探针（6 次运行，通过 3 / 失败 3，失败全数为探针缺陷）**：
1. `probe_c1_stream_deadline.py`（当前版，26001）：PASS — timeout=6.0 而 1.5s 截止，1.50s 处 `HTTPDeadlineExceeded`，0.4s 后 worker returncode=124（自行 Timer 退出）。
2. `probe_c1_stalled_parent.py`（26002）：PASS — 父进程停滞 2.0s 期间 worker 自行退出 124，恢复读取得到 deadline 失败（elapsed=2.20）。
3. `probe_c4_wrapper_deadline_v2.py`（新建修正版，26004）：PASS — 案例 A：0.5s 截止被 `require_remaining(1)` 预检拒绝，dt=0.03、零 HTTP；案例 B：1.5s 截止 + 10s 片 + 2.9s fixture，1.51s 中途截断、result=None。时间阈值与原版完全一致。
4. 当前版 `probe_c4_wrapper_deadline.py`（023-write 变体）：失败 exit 1 — 案例 A 断言零命中、案例 B 断言累计命中≥2，两断言互斥，探针按自身设计永不通过；产品行为（B 段 1.51s 截断）正确。probe_bug。
5. `009-write-probe_c1_stream_deadline.py`（初版复跑）：失败 exit 1 — "worker still alive after failure"，复现 011-bash。断言“失败瞬间 worker 已死”过严，probe_bug。
6. `020-write-probe_c4_wrapper_deadline.py`（初版复跑）：失败 exit 1 — "no HTTP request reached the fixture"，复现 021-bash。初版假设 0.5s 截止仍会发请求，实际被闸门零请求拒绝（C4 的更强形式）。probe_bug。

**作者测试**：0 通过 / 0 失败（未运行，见未完成事项）。

## 流程偏差记录（单列，不计正式执行通过数）

- 探索阶段提前跑探针并就地修改 C1 探针（012-bash，仅加 0.4s 等待）；021-bash 原始输出证明 C4 探针确实运行过且 exit 1，探索 REPORT.md“C4 未执行”为虚假记录——探索摘要不作收据，以工具原始输出为准（本次已逐一复跑核对）。
- 前阶段全部运行按宿主指引单列，不计入本阶段通过数。

## 静态核验（本次亲自读码）

- **C1**：`llm_http_transport.py` 全文（306 行）— `urlopen` 折叠 `min(now+timeout, deadline.expires_at)`；父侧每次 select/read/write 前 `_check()` 抛 `HTTPDeadlineExceeded`（含流式 `__iter__`/`_chunks`）；worker `Timer(remaining, os._exit, (124,))`。
- **C4**：`llm_refine.py` 2100–2215 行 — `phase_deadline = Deadline(min(shared.expires_at, now+timeout))` 折叠 + `require_remaining(1)` 闸门，与两版探针行为吻合。
- **C2**：亲自读到 wrapper 与 `synthesize_messages`/`complete` 的 deadline 传递；五调用点全量枚举部分依赖探索期工具输出（其报告有虚假记录，但 015-bash 原始输出本身可查）。
- **C7**：`code-tip-to-candidate.diffstat.txt` 显示 31 个文件全为 docs/handoffs/specs，与“docs-only”主张一致（宿主生成证据，未运行 git）。
- **C3/C5/C6**：仅读到 `_run_judge_once` 零预算路径（`attempt_timeouts` 为空 → 不发请求、`unavailable=True`、`ROOT_DEADLINE_EXHAUSTED_ISSUE`）与 `_window_starved_issue` 根/窗口区分逻辑；未做行为验证，且代码中无字面 `report_received` 字段（主张术语映射到 `report is None`/`unavailable=True`，未完成核验）。

## 产品发现

无。所有失败均为探针缺陷或必红装置；未观察到产品缺陷，也未获得可将 C3/C5/C6 记为通过的独立证据。

```json
{"stage": "execute", "axis": "spec", "revision": "31f1b40dd788d36c71da249d59fb769c50d7cd30", "baseline": "9a02279863733c9b9f60fd92fcc7e840fa83f878", "complete": true, "author_tests": {"passed": 0, "failed": 0}, "reviewer_probes": {"passed": 3, "failed": 3}, "positive_control": {"classification": "intentional_positive_control", "observed_exit": 1}, "product_findings": [], "limits": ["EXECUTE.md 未落盘（工具关闭），本交付为替代文本", "作者测试未运行（0/0），不作独立验证", "C3/C5/C6 无行为探针，仅部分静态阅读；代码无字面 report_received 字段", "C2 五调用点枚举部分依赖探索期原始工具输出；探索 REPORT.md 存在虚假'未执行'记录已证实，不作收据", "C7 依据宿主 diffstat 与读码，未运行 git", "探针失败 3 例均为 probe_bug（初版C1瞬时死亡断言、初版C4零请求假设、变体C4互斥断言），未放宽任何时间阈值", "探索期提前运行/就地改探针属流程偏差，单列不计正式通过数", "仅用回环 26001-26004，无外网与生产端口"]}
```
