# K3 独立复核报告 — PR #809 冻结候选

- 审查者：K3（独立代码复核，非作者，单会话，不冒称互盲双审）
- 候选 cwd：`/Users/a77/fwp-q-react-trace-0921`
- 固定 SHA：`dda5895aafc88e5fa20632cf4aaefea973940164`（首、尾两次 `git rev-parse HEAD` 一致）
- 基线：`728f327160bbd2485cb635e7ef09d040d718d7b5`，差异文件恰 11 个（5 源码 + 1 文档 + 5 测试，600+/11-）
- 首尾 `git status --porcelain`：均为空（首：空；尾：空）
- 沙箱：候选树只读未改；探针/日志/报告仅写 `.../independent/k3/`；未读凭据/生产库/其他审查报告；未做记忆回写与 handoff

## Spec 结论：PASS

### S1 引用序号只在分析副本移除 — PASS
- `strip_evidence_ordinals`（episode_protocol.py:694-699）复用既有引用文法 `_PROSE_EVIDENCE_REF_RE`（E/e + 1~999，前后边界断言），替换为空格防粘连；不改公开稿。
- 两处消费均为分析副本：`_novel_numeric_condition_indexes`（episode_semantic_verifier.py:4213，只算 index，原句 `sentence=text` 仍参与支持判定与引用校验）与 `_bound_evidence_quantities`（:4633，仅证据语料视图）。
- 自跑探针 `probe_s1_refs.py`：E27 不授权数量 27；真实 27% 阈值与 +12.6% 仍绑定；`cited_evidence_ordinals("根据E99得出结论")` 仍返回 `("E99",)`（未知引用门未动）；E1000/E0/PE27 不误剥；`增长E27倍` 不粘连成 `增长倍`；含未支持 31.5% 的条件句仍被拒（index 0），有证据支持时不误删。

### S2 参数校验反馈受控 — PASS
- `validation_diagnostic`（finance_query.py:1788-1811）= 7 个已知前缀（标识符经 `_diagnostic_identifier` 闸门 `[a-z][a-z0-9_]{0,63}`，违规显式占位 `[invalid identifier omitted]`）+ 11 条精确白名单消息，其余一律「查询参数未通过校验」；`validation_retry_hint` 的 dataset/字段插值同样过闸门（:1859,1864）。
- 执行异常在 :2213-2216 只包异常**类型名**为 `FinanceQueryExecutionError`，非 ValidationError 子类；`_finance_query_failure_result`（episode_tools.py:1973-2013）对 timeout/cancelled/limit/其他各给固定文案，不伪装成可纠参数错误，且 `evidence=()`（诊断非市场证据）。
- 自跑探针 `probe_s2_diag.py`：`unknown dataset: ../../etc/passwd`、伪造 IOException 散文、近 miss 白名单串（后缀追加 DROP TABLE）均被遮蔽；合法 `pe_ttm` 不被过度遮蔽；执行/超时/取消分类与文案正确，无异常回显。

### S3 复用原反馈链 — PASS
- episode_tools.py 差异仅 observation 字符串替换（3 行），无新增重试机制/预算/取消绕过；hunger 钩子 `record_finance_query_rejected` 为既有内部遥测，不变。
- 新测试 `test_finance_query_repair_feedback.py` 首行自述「Offline feedback delivery, not an autonomous model-quality acceptance test」，脚本模型 + tmp_path 临时真实 DuckDB，未声称自然模型必然纠正。

### S4 JSON 投影边界复制 Mapping — PASS
- `_mapping_for_json`（research_progress.py:62-70）仅 `isinstance(Mapping)` 转 `dict`，经 `json.dumps(default=...)` 递归生效；tuple 由 JSON 自身处理；未知对象抛 `TypeError`，无 `default=str` 吞错。
- 崩溃链确认：`agent_episode.py:657/704/726` 在 rejected/error/timeout 路径以 `call.arguments`（ModelToolCall 递归只读 Mapping）构造 `ToolCallDigest` → `__post_init__` → `normalize_query`；修复前 `json.dumps(mappingproxy)` 抛 TypeError 会沿 `consume` 上溢（探针 2 对照复现该 TypeError），修复后不再整轮崩。
- 自跑探针 `probe_s4_frozen.py`：递归 mappingproxy（含 tuple 嵌套）记账成功且原对象不变；set/bytes/object 仍 TypeError；普通 dict 输出与基线 `json.dumps` 完全一致（无回归）；`query` 快路径与空 Mapping 行为不变；tracker `close_batch` 保留 rejected 调用。

### S5 文档准确 — PASS
- `docs/agent-product-door.md` 新增段与代码一致：只复制不改冻结原对象、未知对象仍拒绝、错误反馈进原 Episode、证据保留；并显式否认「自动纠参/保证自然模型重试/修复整轮异常后的汇总用量与事件日志不一致」。未越界声称。

## Quality 结论：PASS

- 自跑测试：`pytest -p no:cacheprovider -q` 5 个相关文件（test_agent_episode_progress / test_episode_numeric_citations / test_episode_protocol / test_finance_query_repair_feedback / test_research_progress），**116 passed / 116，rc=0，4.78s**。
- 探针 3 组（区别于新增 tests 的自造反例 + 正常对照）全绿，留存于 `k3/probes/`，日志 `k3/logs/probes.log`。
- 代码质量：注释准确标注意图与边界；白名单/闸门方向为安全侧（过遮蔽而非泄露）。

## 发现（均非阻塞）

1. **低 / 提示** finance_query.py:1793-1811：部分合法校验消息不在白名单（如 `at least one metric or dimension is required`、`limit must be an integer between 1 and 1000`、`unknown query argument: ...`），反馈退化为通用「查询参数未通过校验」。方向安全、retry_hint 仍附着，仅反馈具体性略降。
2. **低 / 提示** finance_query.py:1779-1784：标识符闸门只收小写 snake，含大写的合法标识符会被占位符遮蔽（过遮蔽，安全方向）。
3. 探针首跑两处期望错误（序号带 `E` 前缀、数量保留 `+` 号），系探针自身修正，非候选缺陷；修正后全绿。

## 自跑命令与分母

- `git rev-parse HEAD` / `git status --porcelain` / `git diff 728f327..HEAD`（首尾各一次，一致）
- `PYTHONPATH=/Users/a77/fwp-q-react-trace-0921 $PY probes/probe_s{1,2,4}_*.py`（`$PY`=.venv-workbench python；import 均核 `__file__` 指向候选树）：S1 约 15 断言、S2 约 20 断言、S4 约 14 断言，rc 全 0
- pytest 上述 5 文件：116/116 passed

## 边界与未验

- 未跑全仓 25 分钟套件与前端；未触真实行情/模型/API。
- 未验自然模型真实纠参（S3 仅证反馈可达且可取回，作者与本文均不声称必然纠正）。
- 跨仓 registry-check 基线漂移按提示不属本 PR。
- 金融质量：公开稿删条件后「满足两条」、ranking_intent=false、225/25 与 12.6/16.5 未绑定未送核验视图——仍 **not_passed**，本代码审查不替代、不放行。
- 工程结论仅针对冻结候选 dda5895：Spec PASS / Quality PASS；不给 main/部署/金融质量放行。
