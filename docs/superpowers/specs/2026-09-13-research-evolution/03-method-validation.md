# 03 · 方法验证与真实前向概率实验 v1

状态：待执行设计；本次只写 spec。基线 `gitea/main@5fb13a8c`，2026-09-13 实测。03 独立实施，06 接入产品。

## 1. 目标与边界

交付：同一冻结案例的删轨消融，以及事前概率的到期评分。消融只测指定方法使用新增信息的效果，不证明数据轨普遍有效。

独立服务复用既有统计，首版采用人工概率/确定性规则；LLM 概率只作历史演练。不做自动训练、框架改写、晋升、荐股、抓取、恢复旧夜跑或修改情景树。平均 Brier 差仅描述。

## 2. 现状与增量

以下路径以 `intelligence/` 为根，除注明者外：

| 当前源码 | 已有能力/本次复用 |
|---|---|
| `services/methodology_backtest/stats.py` | Wilson、`four_state`、`DependenceReadout`、`block_bootstrap_readout`、`combined_verdict`；布尔统计直接复用 |
| `services/methodology_backtest/{compiler,runner,lifecycle,receipts}.py` | 同宇宙/同事件日基准、跨窗 purge、版本认证；沿用规则与结果语义，不造第二条晋升链 |
| `services/method_validation/{protocol,study,store,flywheel}.py` | 固定双红三组对照、当天冻结、到期回检、不可覆盖记录；其 writer 只接固定协议，本轨只引用旧收据 |
| `eval/replay_engine.py` | 已有 `confidence_probability/pit_grade/memory_bucket/arm`；eval adapter 导入旧结果，service 不反向 import eval |
| `scripts/dual_blind_forecast.py::_calibration_metrics`（仓根） | 已有 Brier/AUC/五桶误差；对齐数学口径，不启动退役脚本，不对舍入数继续统计 |

相关测试 **117 passed / 24.56s**：`test_methodology_dependence.py`、`test_method_validation.py`、`test_replay_engine.py`、`test_dual_blind_forecast.py`（均在 intelligence/tests）。代码地图 empty，结论来自源码。

增量：通用实验身份、冻结概率/基准、配对评分、窗口使用记录与统一收据。

## 3. 白名单与任务 0

独占：`intelligence/services/research_validation/**`、`intelligence/eval/research_validation/**`、`intelligence/tests/test_research_validation_*.py`、`intelligence/tests/fixtures/research_evolution/03/**`；进度只写 `docs/superpowers/plans/2026-09-13-research-evolution/03/{PROGRESS,BLOCKED}.md`。

v1 不改既有文件。api/app.py、cli、userspace、ledger-map、注册表与 UI 归 06。既有统计若有问题，先交最小复现、符号与拟改路径给 06 协调；受影响结果 eligible=false，不绕开重造统计平台。

任务0：确认树/base/总合同，重跑四组测试，登记源码与签名映射。实测 block_bootstrap_readout 把 ±0.1 都 bool 成命中，本轨必须验证真正 bool。映射、类型保护及反例齐全即完成任务0，不等生产数据。

## 4. 对象合同

owner 来自06认证上下文，visibility=private。UTC时戳、冻结交易日历；JSON禁非有限数。语义SHA-256作id，生成时间不参与身份；重试返回首次原件。改义产生新id并supersedes旧对象；冻结后同 `(study_id,case_id,arm_id)` 只允许同payload幂等。改p/基准/时间/recipe不得加入原study确认集合，v1拒绝修订预测；需另开study并继承曝光史。唯一键预占与原件发布必须原子，禁止先检查再写入的竞态。

```text
StudyProtocol
  schema_version="research-study/v1", id, owner_user_id, visibility
  study_id, lineage_id, parent_study_id?, created_at, frozen_at
  question, event_spec, universe_ref/hash, forward_start, evaluation_end
  discovery_window, validation_window?, holdout_window?
  arms[], baseline_spec, comparisons[], primary_comparison_id
  analysis_policy, source_hashes, version_hashes, exposure_receipt_refs[]
  status: draft|frozen|closed|invalid
ProbabilityForecast
  schema_version="probability-forecast/v1", id, owner_user_id
  study_id, case_id, arm_id, forecast_at, registered_at, as_of
  knowledge_cutoff, outcome_due, p, p_baseline
  origin: human_manual|deterministic|historical_llm
  mode: forward|historical_rule|historical_llm
  projection_hash, input_refs/hashes, model_id?, model_version?, prompt_hash?
  framework_hash, probability_recipe_hash, baseline_hash
  pit_grade, memory_bucket, outcome_spec_hash, calendar_hash
  capture_receipt_ref, supersedes_id?
OutcomeObservation
  forecast_id, observed_at, available_at, due, source_refs/hashes
  value: 0|1|null, status: settled|pending|missing|invalid
MethodValidationReceipt
  schema_version="method-validation-receipt/v1", id, owner_user_id
  visibility="private", study_id, lineage_id, protocol_hash, generated_at
  source_hashes, version_hashes, mode, empirical_status, eligible
  pending_gaps[], excluded_counts, sample_manifest_hash
  comparison_readouts[], outcome_receipt_refs[]
  decision_eligible=false, promotion_eligible=false
```

eligible 仅指可用于**声明的实验比较**；不是晋升/荐股资格。empirical_status：`pending|descriptive|insufficient|not_distinguishable|supported|refuted|invalid`。supported/refuted 仅指 `claim_kind=paired_date_win_rate`；平均差单列 `mean_brier_difference_descriptive`，不得继承支持结论。

gap 为 `{code,object_refs,retryable,next_check_at?}`，至少区分 future_not_due、outcome_missing、baseline_unavailable、arm_missing、unverified_pit、holdout_exposed、version_mismatch；非法输入报错/invalid。

case_id 由 `(entity_id,as_of,event_spec_hash,outcome_due,universe_hash)` 派生，各臂共享，不含预测结果。首版限板块 history_outcomes.fwd_return 布尔谓词；复用 rules 白名单，horizon须在metadata存在，默认D+1起5个交易日。散文不作真值。

## 5. 登记、基准、结算

服务公开 freeze_study/register_forecasts/settle_outcomes/evaluate_study/read_receipt/record_exposure，显式接受owner、repository、now。06供可信时钟/userspace根/台账；客户端不传now。登记前只用临时根。record_exposure 接受同owner的底层结果身份/区间和访问来源，由本轨原子写入；练习揭示和原件访问只登记客观曝光，是否影响实验由本轨判定。

协议在 forward_start 前冻结；真实前向登记限 D0 当天盘后、第一结果窗开始前，as_of=D0，forecast_at≤registered_at=可信 now。首次登记时间不可回填。输入通过已有 PIT（当时可知）收据校验；晚于 cutoff 拒收，只有 hash 而无原件/验证收据不能升 strict。概率为 [0,1] 有限非 bool 数字；high/medium/low 不换算成概率。人工概率只归人工，确定性概率绑定 recipe，LLM 历史概率永不改 mode 为 forward。

基准：同事件同宇宙的发现窗，各日先算比例再日期等权。冻结源行/分母/版本/purge/p_baseline；结果期跨窗样本剔除。无有效样本→baseline_unavailable，不填0.5；改基准新study。

结算要求 now≥D+h收盘、available_at≤now、日历/源版本一致。未到期pending（库有未来值也一样），到期缺值missing。修订追加Observation；旧结论保留，重算为correction_replay。

## 6. 消融首例与输入隔离

固定 task、case 全集、期限、基准、算法版本及预算，声明 base（盘面）、full（加一条输入轨）、minus_track；相同臂可合并。每 study 只有一个确认性主比较，其余探索。

eval 离线 runner 读取冻结 manifest、每臂允许字段及代码白名单上的纯 `predict_fn(projection)->p`；service 不动态加载代码。首个可跑 adapter 为规则二桶概率：每臂一条现有可编译规则，发现窗分条件真/假两桶；桶内各日计算结果比例，n=有样本的日期数，k=这些日比例之和，p=(k+1)/(n+2)。这是固定平滑 recipe，不把加权数称独立样本量；n=0 返回 gap。未知标签不能转 false。规则/训练结果冻结；臂间规则差仅为移除轨对应谓词，完整记录差分。测量对象明确为“规则＋信息配置”，不冒充纯因果效应。

删轨同时删除依赖该轨的派生量。runner 保存每臂实际 projection/hash；残留信息或输入隔离无法验证时 eligible=false。人工先看 full 再填删轨概率可能记得答案，仅 descriptive。

按case配对，一臂缺失整对退出主比较；保留原全集、原因、覆盖率。缺轨写gap，不判无效。

## 7. 评分、相关性、经验结论

Brier=(p-y)²，越低越好。完整配对案例日内等权，再日期等权；delta_d=mean(Brier_base−Brier_candidate)，总差=mean(delta_d)。计算不舍入，mode/horizon/版本/PIT分列。(.9,1),(.8,1),(.2,0),(.1,0)的Brier=0.025。

校准五桶 `[0,.2),…,[.8,1]` 报计数、平均预测与实际频率；稀疏桶沿用checkpoints.DEFAULT_CALIBRATION_MIN_N，只报不足。Brier 累计是描述，不用任意阈值宣布已校准。

主检验：一天一个胜出bool（delta_d>0）。平局保留总N；v1含平局→insufficient/ties_test_not_defined，不删掉或当输。全平局只写未观察到增量，平均差照报。

无平局时复用 `four_state/wilson` 与 `block_bootstrap_readout`，再 `combined_verdict`。零假设 p0=0.5 指对称胜负，不是市场上涨率；不能虚造 baseline_n=2/k=1 喂 readout。min_n取rules.DEFAULT_MIN_N，其他取stats.DEFAULT_MIN_BLOCKS/DEFAULT_BLOCK_BOOT/DEFAULT_BLOCK_SEED并冻结，不能为支持而降低；块长至少为最大 outcome horizon。保留前后半段。日期块沿唯一事件日取样的近似、n_dates/n_blocks/n_clusters、完整交易日 span 均入收据，不把簇数称精确有效 N。

evaluation_end到达才作一次确认检验，此前只报pending数/单项，累计评分封存。supported/refuted只指胜出日期频率；不等平均差显著、收益或未来保证。依赖不足不得被Wilson绕过，探索比较不冒充已控制连续试验。

## 8. 谱系与 Holdout 防复用

Holdout 是最后验证的未查看样本。三段窗口事前冻结且严格递进，按日历 purge 跨界结果；既有 lifecycle 只读参考，本轨不晋升。

读取验证结果前，repository 原子预占并追加 `ExposureReceipt(owner_user_id,lineage_id,window,case_manifest_hash,outcome_identities,stage,accessed_at,actor,reason)`。隔离范围是同owner全局，不能只查lineage：按真实实体与底层结果区间匹配已暴露事实，case改名、改谓词阈值、换study_id/lineage_id均不能洗白。同意图重试返回原件；改方法再用已暴露事实为holdout_exposed。首次预占后若崩溃可按原操作id恢复，另一操作不能趁未写完重占。外部人工或actor曝光未知→exploratory且eligible=false，不能靠声明新谱系证明未见。

失败也留尝试。崩溃同意图返回原exposure，看过结果改方法是新尝试。eligible由冻结身份与暴露记录派生，不接受调用方自填true。

## 9. 接线与验收

06供认证/时钟/目录台账/产品入口，03供合同/原子记录/评分。拒跨owner、越界/非法软链。历史adapter只读可验证replay原件，保留pit_grade/memory_bucket/arm/model。

测试须覆盖：

1. 同输入幂等/同意图并发收敛；改 p、基准、版本、cutoff 不复用旧身份；不同意图冲突。
2. D0 登记零 outcomes；库中预塞未来值仍 pending；到期缺值不当失败；概率 bool/NaN/越界拒收。
3. 手算 Brier 一致；“多数天略赢、少数天大亏”的正胜出率与负平均差并列，不写全面改善。
4. 复制同日 case 不增证据；增加板块不增加日期块；连续差不能进入 bool 统计；依赖不足不支持/证伪；平局不丢分母。
5. 删轨后衍生量残留被拦；少答难题的覆盖率损失不可隐去；unknown 不变 false。
6. 跨窗 outcome、错版本、缺 PIT 原件、late 注册分别拒绝/降级；历史演练与前向不混。
7. 同study/case/arm改p或并发填不同p被拦；换study_id、lineage_id、case别名重用已暴露holdout均被拦；未知外部曝光不eligible。崩溃恢复幂等、只留赢家/覆盖原件/跨owner均失败。
8. 临时真实文件两次结算→06 消费收据；未来未到/块不足也能完整返回 pending/insufficient，不伪造长期样本。

未来实现后的验收命令（当前尚无新测试，不把空收集写成通过）：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest --collect-only -q intelligence/tests -k research_validation
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests -k research_validation
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_methodology_dependence.py intelligence/tests/test_method_validation.py intelligence/tests/test_replay_engine.py intelligence/tests/test_dual_blind_forecast.py
```

collect-only须exit 0且选中测试数>0；测试须覆盖上列反例，不能只有常量/形状断言。生产源码读取和fixture均不得启动旧双盲脚本。

顺序：任务0→合同/repository→登记结算→评分/消融→谱系→06联调。每步更新 PROGRESS；依赖缺失在 BLOCKED 写证据、完成范围、责任轨、解锁条件与恢复入口，只改本轨。

06接线后以有效D0输入冻结首例人工概率；非交易日/源不鲜则预建下个合格日协议、保持pending。写next_check_at和恢复入口，不回填过去冒充前向。

**双完成：** engineering_complete 要求白名单、反例、既有相关回归通过，服务可调用且有pending真例；empirical_complete 要求预注册期末已到、源与结果可核、无验证污染并生成读数。后者允许 insufficient/not_distinguishable/refuted，不能以得到支持为完成条件。两状态分别交06展示，工程完成不等于证明有效。

依据：统一终局spec §4–§7；[上一轮压力测试](/Users/a77/agent-memory/00_inbox/2026-09-13-time-river-epistemic-review.md)。本稿未新增外部事实承诺。
