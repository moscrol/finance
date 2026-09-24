已核对全部封存原件。以下为最终中文 Spec 报告。

---

# Spec 组最终报告（PR #894 / Workorder #85）

- **revision**: `62777a76d7812bf5eebe070892e5977b2aa93003`
- **baseline**: `c9dd71dfd678855b61662100ec74625b92ad1f1b`
- **本会话纪律**：只读已封存证据（inputs/claims.md、explore-spec/REPORT.md、execute-spec/REPORT.md、execute-spec/execution.json 及 execute 阶段 commands 原始日志），未运行任何命令/测试/子代理，未读 quality 组与作者报告。所有读数均与原件复核一致：`007-bash` → `23 passed in 1.91s`, exit 0；`008-bash` → 阳性对照 `1 failed`, exit 1；`009-bash`/`010-bash` → 作者测试收集期 `PermissionError`（`TREE/.agents`），exit 4，0 用例执行；`execution.json` → STAGE_COMPLETE。

## Claims 逐项判定

| ID | 判定 | 依据 |
|---|---|---|
| **C1** | **verified** | 静态：`market_feature_store/hithink_client.py:252`（HTTP 状态先于解析）、`:265`（业务码 429）、`:147-178`（Retry-After 秒数/HTTP-date，86400→60s 封顶，非正值归零回落）、`:41/:267`（次数常数界）、`:204-205,:214,:273`（monotonic 时间界）、`:130-143`（预算校验有限非负）、`:214,:222,:273`（准入制非强杀在途读）。探针（execute 007-bash 8 项 C1 用例全过）：非 JSON 429 正文退避、秒数+date 双形态采纳、Retry-After=0/过期 date/负值回落有界指数且 calls=1+MAX、预算 0.001 时 calls==1 且 sleeps==[]、wait 越 deadline 立即耗尽、重发 timeout 收紧 ≤ 剩余预算。 |
| **C2** | **verified** | 静态：对照 `inputs/baseline_hithink_client.py:128,:161-165`，4001 语义同构；`hithink_client.py:278-285` 错误消息反而移除基线 `:165` 携带的 `payload.message`（向更安全方向偏离）；耗尽消息仅含 path/budget/retries。探针（5 项全过）：retries=4→4 次尝试退避 [0.8,1.6,3.2]、retries=2→exact-`HithinkAPIError`、code=500 单次调用无 `probe-UPSTREAM-SECRET`、非 JSON 200 不重分类无 `probe-BODY-SECRET`、429 后 4001 不重分类（5 次调用，退避 [0.8,0.8,1.6,3.2]）。 |
| **C3** | **verified** | 静态：`sync/sync_hithink_research.py:236-242`（uuid+原始 scope 审计）、`:264-269`（empty/partial 行级分账）、`:301-309`（失败档只留 error_type 防泄密）、`:312-330`（仅吞限流耗尽，余者重抛熔断）、`:417-433`（missing kind/request_id + partial）。探针（临时 DuckDB 4 项全过）：valuation 限流耗尽→`partial`+missing（带 request_id）且热度继续、审计行 `failed/HithinkRateLimitError/payload_json=None/params 含 600519.SH`、空 anomaly→`complete_with_gaps` 且 missing==[]、普通错→`HithinkCaptureError` 熔断第二股票不请求、混合场景限流可忍→后续普通错 kind=valuation/rate_limited=False 熔断且两类审计行分账。 |
| **C4** | **verified** | 静态：`sync_hithink_research.py:40`（退出码 3）、`market_feature_store/cli.py:1298-1318`、`skills/daily-full-review/scripts/run_review_sync.py:189-203,:382-388`（注册 partial 映射）、`:568-585`（原地重试优先→notify+runlog(false)+return 1）、`sync/sync_daily_full.py:154-166,:331`。探针（3 项全过）：注册步骤 3→partial／未注册 3→fail 语义不变、单体 partial→`HithinkResearchError`、CLI partial→3/ok→0（模块经 `_from_tree` 断言来自候选 TREE，0 skipped）。 |
| **C5** | **verified** | 静态：`sync_hithink_research.py:354-363`（上海当日限制）、`:399-415`（历史仅 heat_trend）、`:350-353`（直写生产拒绝）、`scripts/recover_local_review.py:120-123`（历史回补排除 latest-only，静态）、`write_path.py:98-115,:118-129`、`intelligence/services/finance_query.py:1369,:1391,:1410,:2235-2238,:2287`（只读数据集登记+read_only 连接）、`consumption_registry.yaml:274-277,:97-104`。探针（3 项全过）：非当日零请求即拒、history_only 只发 heat_trend、samestat 硬链接识破+FileNotFound 容错+`production_write_blocked`、编排层在任何请求前拒绝直写生产。 |
| **C6** | **verified**（含覆盖限制） | 静态：source.diff 18 个文件全部范围内，无部署/出站工具/生产根变更；`scripts/audit_hithink_runtime.py` 无网络调用痕迹；`hithink_client.py:12-15` docstring 明示约七分钟窗口不承诺默认 300s 预算覆盖。环境佐证：execute 会话全部探针在禁网沙箱内以假 urllib 响应+临时 DuckDB 运行，无真实外呼；负面清单项不可穷举（见 limits）。 |

## 验证结果分账

- **独立审查者探针** `work/spec/probes/test_spec.py`：execute 会话原件 007-bash → **23 passed / 0 failed / 0 error / 0 skipped**，exit 0，零返工、未删断言，模块均断言来自候选 TREE。
- **作者测试**（`tests/test_hithink_stock_daily.py`、`tests/test_hithink_research.py`、`tests/test_review_sync_hithink_wiring.py`，含 since-last-review.diff 新增 4 条回归）：两组命令（009/010-bash 原件）均在收集期被宿主沙箱 `PermissionError: TREE/.agents` 阻断，exit 4，**0 用例执行** → 记 **blocked**（环境拒绝，非断言失败）；未改沙箱、未加忽略钩子、未搬移。**作者测试绿否本组不作任何主张，不洗作 PASS 证据**。
- **阳性对照** `test_positive_control.py`：008-bash 原件 exit 1，`1 failed (assert 1 == 2)`，分类 **probe_bug（intentional）**，未修正、原件保留、不计入正常探针统计——证明失败信号可到达报告。

## 最终判定：**PASS_WITH_LIMITS**

C1–C6 全部为 verified（23 项独立探针 + 静态行号对照），无产品断言失败、无 provider 故障（execution.json 7 次请求均 200，STAGE_COMPLETE）。不能给 PASS 的原因：作者测试 0 执行且被环境阻断未被洗白、explore 越阶段规程偏差、部分证据为静态/环境佐证而非可穷举运行验证。

```json
{
  "stage": "report",
  "group": "spec",
  "complete": true,
  "revision": "62777a76d7812bf5eebe070892e5977b2aa93003",
  "baseline": "c9dd71dfd678855b61662100ec74625b92ad1f1b",
  "verdict": "PASS_WITH_LIMITS",
  "claims": [
    {"id": "C1", "status": "verified", "static_evidence": "market_feature_store/hithink_client.py:41,130-143,147-178,204-205,214,222,252,265,267,271-273", "probe_evidence": "007-bash原件23 passed中C1八项全过:非JSON正文429/业务码429双形态0.8基准指数退避、Retry-After秒数+HTTP-date采纳且86400封顶60s、0值/过期date/负值回落有界且calls=1+MAX、预算0.001→calls==1且sleeps==[]、wait越deadline立即耗尽、重发timeout收紧≤剩余预算(准入制非强杀)"},
    {"id": "C2", "status": "verified", "static_evidence": "hithink_client.py:252,259-260,265,278-285对照inputs/baseline_hithink_client.py:128,161-165同构,且候选错误消息去除基线:165携带的payload.message", "probe_evidence": "007-bash中C2五项全过:4001 retries=4→4次尝试退避[0.8,1.6,3.2]、retries=2→exact-HithinkAPIError(code=4001)、code=500单次无probe-UPSTREAM-SECRET、非JSON200不重分类无probe-BODY-SECRET、429后4001不重分类5次调用退避[0.8,0.8,1.6,3.2]"},
    {"id": "C3", "status": "verified", "static_evidence": "sync/sync_hithink_research.py:236-242,264-269,301-309,312-330,417-433", "probe_evidence": "临时DuckDB四项全过:valuation限流耗尽→partial+missing带request_id且热度继续、审计行failed/HithinkRateLimitError/payload_json=None/params含600519.SH、空anomaly→complete_with_gaps且missing==[]、普通错→HithinkCaptureError熔断、混合场景限流可忍→kind=valuation/rate_limited=False熔断且两类审计行分账"},
    {"id": "C4", "status": "verified", "static_evidence": "sync_hithink_research.py:40、market_feature_store/cli.py:1298-1318、skills/daily-full-review/scripts/run_review_sync.py:189-203,382-388,568-585、sync/sync_daily_full.py:154-166,331", "probe_evidence": "三项全过:run_step注册partial_exit_codes=(3,)→partial/未注册3→fail、单体partial→HithinkResearchError、CLI partial→3/ok→0,模块经_from_tree断言来自TREE,0 skipped"},
    {"id": "C5", "status": "verified", "static_evidence": "sync_hithink_research.py:354-363,399-415,350-353、scripts/recover_local_review.py:120-123(静态)、write_path.py:98-115,118-129、intelligence/services/finance_query.py:1369,1391,1410,2235-2238,2287、consumption_registry.yaml:274-277,97-104", "probe_evidence": "三项全过:非上海当日零请求即拒HithinkResearchError、history_only只发heat_trend、write_path samestat硬链接识破+FileNotFound容错+production_write_blocked、编排层在任何请求前拒绝直写生产"},
    {"id": "C6", "status": "verified", "static_evidence": "source.diff 18文件全部范围内无部署/出站工具/生产根变更、scripts/audit_hithink_runtime.py无网络调用、hithink_client.py:12-15 docstring明示不承诺默认300s覆盖约七分钟窗口", "probe_evidence": "环境佐证:execute会话全部探针在禁网沙箱内用假urllib响应+临时DuckDB,无真实外呼;负面清单项不可穷举见limits"}
  ],
  "reviewer_probes": {"passed": 23, "failed": 0, "error": 0, "skipped": 0, "runs": 1, "source": "execute-spec/commands/007-bash原件(23 passed in 1.91s, exit 0)", "rework": "无,零返工,未删产品断言"},
  "author_tests": {"passed": 0, "failed": 0, "error": 0, "executed": 0, "blocked": true, "source": "execute-spec/commands/009-bash与010-bash原件均exit 4:收集期PermissionError [Errno 1] on TREE/.agents(tree内ls同样Operation not permitted),0用例执行;环境拒绝非断言失败,未改沙箱/未加忽略钩子/未搬移;作者测试(含since-last-review.diff新增4条回归)绿否本组不作主张"},
  "positive_control": {"classification": "probe_bug", "intentional": true, "observed_exit": 1, "observed": "execute-spec/commands/008-bash原件:1 failed in 0.06s, assert 1==2 'intentional probe_bug: evidence that failures reach the report',未修正原件保留,不计入正常探针统计"},
  "findings": [],
  "limits": [
    "作者测试3文件(含since-last-review.diff新增4条回归)全程0执行被宿生沙箱阻断,其通过与否未验证,未被计入任何PASS证据——此类未跑项不构成C1-C6的verified依据,verified仅来自独立探针+静态对照",
    "规程偏差(已披露):explore阶段曾违反'不跑测试'纪律提前运行探针,020-bash原始证据留存;最终统计只取独立execute会话的23/0/0/0一轮,两轮读数未加总、未重复计数",
    "C1-C5静态行号与C6 diff清单/脚本证据由explore阶段读取,execute会话未逐行重读但复核diff无实现变化后以此为基础接受;本报告会话仅复核封存报告与日志原件",
    "finance_query引擎只读强制仅静态确认read_only=True连接与数据集登记,未逆向引擎内部;recover_local_review.py:120-123历史排除为静态证据,脚本未运行",
    "C6负面清单项(无部署/无出站工具/无真实外呼)无法穷举所有执行路径,依赖diff文件清单+禁网沙箱环境证据",
    "阳性对照probe_bug为宿主刻意设计(assert 1==2退出码1),非产品缺陷,原件保留"
  ]
}
```
