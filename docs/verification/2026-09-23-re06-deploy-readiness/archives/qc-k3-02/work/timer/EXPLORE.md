# K3 explore · group=timer · C7–C10

- revision: `8eac9b3b55c563b1eb3be58686fcc0918464f69a`
- baseline: `b59d6eed0356ae093b52bd291ab328628de8790e`
- 候选（只读）: `/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/candidate/finance-workspace-private`
- 解释器: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
- 本场只静态检查 + 写探针；**未执行任何 pytest / 前端测试；UI 未动态验证**。完成 ≠ PASS。
- C1–C6 属另一独立组，本场不审、不签字。

## 交付物

| 文件 | 用途 |
|---|---|
| `work/timer/probes/test_reviewer.py` | 自造 pytest 探针，15 条用例，覆盖 C8/C9/C10（tmp_path 造台账，不碰生产/真实 LLM） |
| `work/timer/probes/test_positive_control.py` | 含 `assert 1 == 2`，供下一会话单独运行，记为 expected_positive_control/probe_bug |
| `work/timer/probes/activity-reviewer.test.tsx` | 自造 React 生命周期探针（C7），6 场景，经 tsc 静态解析（仅 jest-dom 匹配器类型提示，运行时由 setup.ts 提供） |
| `work/timer/EXPLORE.md` | 本文件 |

## 静态证据（精确到行，均在候选树 `intelligence/` 下）

### C8 纯计时不表达测量意愿；空/部分/混合不错误回落默认 — 静态一致
- `services/product_value/consent.py:35-57` `measurement_scopes`：纯 `{activity-timer}` 返回 `None`（55-56 行）；空集返回 `frozenset()` 而非 None（43→57 行）；混合 scope 返回 `scopes - {activity-timer}`（57 行），部分授权得以保留。
- 写侧 `services/research_evolution/run_observer.py:138-175` `_measurement_consented`：`measurement_scopes is None` 的记录被跳过（169-171 行），不翻掉自用默认；`entries` 非空时才要求 `covers_measurement(scopes_at(...))`（174-175 行）。空集授权会产生 entry（空 frozenset）→ 不会错误回落 `True`。
- 读侧 `services/product_value/measure.py:146-166` `_consent_timeline` 同样跳过 None；`_scopes_at`（169-174）区分「无记录=None」与「空集」；759-763 行用量 None→`consent_unknown` limitation，不错误放行。

### C9 旧 v1 仅完整自用形状对称兼容 — 静态一致
- `consent.py:44-54` 转换条件八项齐全：`consent_version=="workbench-activity-v1"`（45）、scopes==REQUIRED（46）、`source_channel==frontend`（47）、`protocol_version=="workbench-self-use/v1"`（48）、`pilot_id` 前缀 `workbench:`（49）、`participant_id==owner_user_id` 且 owner 非空（50-51）、`task_id is None`（52）。不满足任一即不转换（53-54 才赋值）。
- 转换不读 `action`，授予/撤回对称（探针 `test_c9_legacy_conversion_symmetric_grant_and_withdraw` 覆盖）。

### C10 真撤回不被重启计时覆盖；计时不授权试点；不改写原记录/摘要 — 静态一致
- 折叠 `consent.py:64-85 scopes_at`：计时授权映射为 None 后不进 entries，无法撤销既有的 research+logging withdraw；读/写两侧共用此一份折叠（run_observer.py:143-145 注释与调用一致）。
- 前端区间事件 `task_id: null`：`webapp/src/components/ResearchActivityControl.tsx:96`（`{ ...event, task_id: null, participant_id: user }`），不把计时绑到试点任务。
- `measurement_scopes` 只读 event，不 mutate（探针 `test_c10_measurement_scopes_does_not_mutate_raw_event` 深比较断言，含 content_hash 字段）。
- 内容摘要确为哈希而非自然语言：`services/product_value/events.py:454` 校验期算 `content_hash(normalized, drop_keys=_CONTENT_DROP_KEYS)`；`services/product_value/summarize.py:997` `source_event_hash` 由 `event_id:content_hash` 派生；`measure.py:898` `input_hash` 同源。兼容读取路径（consent.py）不触碰上述任何一处。

### C7 计时控件生命周期用 activity-timer/v2 — 源码与已提交产物一致
- 源码 `ResearchActivityControl.tsx:35-46` consent 构造器：`consent_version:"workbench-activity-v2"`、`scopes:["activity-timer"]`、`effective_at==event_at`（撤回取 `max(now, lastEnd+1)`，37 行注释+实现）；停止 56-70、开始 72-108、pagehide 监听 109、卸载清理 110-114（`disposed=true` 后仍 `stop()`）、切会话因 effect 依赖 `[conversationId, user]`（116 行）走同一 stop。
- 发布物核对（非源码替代）：`api/static/index.html:9` 引用 `/assets/index-BobixB9S.js`，该文件存在于 `api/static/assets/`（411,798 B）。窄查产物：`workbench-activity-v2` 命中、`activity-timer` 1 处、`pagehide` 2 处、`workbench-activity-v1` **0 处**；窗口摘录显示产物内 consent 载荷为 `payload:{consent_version:"workbench-activity-v2",scopes:["activity-timer"],effective_at:Be,action:he,...}` 且撤回分支 `he==="withdraw"?C+1:0`，与源码逐点对应；TERMS 文案「计时同意独立于研究测量同意。」亦在产物中。

## 疑点（suspected issues，均为低严重度/待动态确认）

1. `consent.py:43`：`payload.scopes` 若为字符串（脏数据），`frozenset(str(s) for s in ...)` 会拆成字符集，产出「垃圾意愿」记录而非 None/报错。台账已过校验时不可达，未验证校验器是否拒绝非列表 scopes。
2. `consent.py:48`：`event["source_version"]` 若非 mapping（如字符串），`.get("protocol_version")` 会 AttributeError。同样依赖上游校验。
3. `consent.py:49`：`pilot_id` 恰为 `"workbench:"`（空前缀后无内容）也算匹配，边界宽松。
4. `run_observer.py:153-159`：台账读取异常时同意门**放行**（fail-open，留 stderr）。文档声明为有意设计（门不阻断被测 run），但与 C10「撤回优先」的精神存在张力：瞬时读故障期间测量事件仍会落盘。列为设计风险而非代码缺陷。
5. UI 授权被拒后的尽力补撤回（`ResearchActivityControl.tsx:101-103`）失败时仅 `.catch(() => {})`：服务端可能残留一条 activity-timer grant。因 `measurement_scopes` 将其映射为 None，对测量门/读数无影响，属台账整洁性观察。

## 未验证边界（limits）

- 未运行任何测试：Python 探针仅 `ast.parse` 通过；TSX 仅 tsc 解析通过（报 3 条 jest-dom `toBeEnabled` 类型提示，属 setup 类型未加载，非语法/解析错误）。UI 未动态验证。
- 写侧探针用镜像复现 `run_observer.py:155-175` 的调用序列（真实 `ObservingRunStore` 构造依赖重）；若候选改序列，镜像保真度失效。读侧已有一条用真实 `measure._consent_timeline/_scopes_at` 的探针（importorskip 保底）。
- 产物与源码的「构建同源」仅凭 token 级比对，未重新构建验证；无法排除手工编辑 bundle。
- 服务端给前端 consent 事件补 `source_channel` 等字段的接线未核（对 v2/activity-timer 结论无影响，因 55 行先于来源判断）。
- content_hash 管线仅核到 events.py:454 / summarize.py:997 / measure.py:898 三处用法，未全量审 _CONTENT_DROP_KEYS 组成。
- C1–C6 未审； baseline↔revision 差异未逐行 diff（候选非 git 工作树，仅快照）。

## 下一场命令

```bash
CAND=/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/candidate/finance-workspace-private
WORK=/Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/work/timer
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python

# 作者测试（C8/C9/C10 直接相关；fold_shared/toctou/i11 属他组主张，可参考不签字）
cd $CAND && $PY -m pytest intelligence/tests/test_re06_activity_consent_gate_effect.py -v

# 本组自造探针
cd $WORK/probes && $PY -m pytest test_reviewer.py -v
# positive control（必须 FAILED，记 expected_positive_control/probe_bug）
$PY -m pytest test_positive_control.py -v

# UI（宿主已备锁定依赖；缓存指向 work；--configLoader native）
cd $CAND/intelligence/webapp
REVIEW_UI_KIND=author npx vitest run --configLoader native --config $WORK/../../inputs/ui.vitest.config.mjs
REVIEW_UI_PROBE=$WORK/probes/activity-reviewer.test.tsx npx vitest run --configLoader native --config /Users/a77/.finance-runtime/reviews/re06-deploy-readiness-20260923-01/qc-k3-02/inputs/ui.vitest.config.mjs
```
