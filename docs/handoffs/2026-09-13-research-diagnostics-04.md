# 2026-09-13 · 研究进化 04 · 个人研究流程诊断：决策快照

分支 `feat/research-diagnostics-04`，代码提交 `fea6ef98`，基线 `gitea/main@5fb13a8c`。
inflight 压缩表在 `docs/handoffs/inflight/feat-research-diagnostics-04.md`，进度与收据在
`docs/superpowers/plans/2026-09-13-research-evolution/04/PROGRESS.md`。本文不限长，记背景、被否方案与理由。

## 背景（不读会误判后面每个决定）

- 六份规格由 `docs/river-next-specs` 分支（`194241dd`）交付，本轨 cherry-pick 携入。04 与 01 并行：01 的
  `judgment-maintenance/v1` 报告在 04 里只是**输入**，04 用自己维护的合成夹具，不等 01 实现。
- 04 的产品语义是「给用户定责的流程诊断」，与现有校准（`checkpoints.calibrate` / `observation_script.enters_calibration`）
  方向相反：校准是**准入**（判不出就不准进），诊断是**归责**（判不出就不能说你错）。很多决定都从这一点推出来。
- 存量台账（`checkpoints.jsonl` 等）没有版本链、曝光日志、覆盖声明。任务 0 核对后确认：五类检查里只有观察剧本
  的迟登能在存量数据上真正判出 issue / context，其余大面积 unknown 是数据现状。

## 按发现顺序做了什么

1. 找规格：主树没有 04 文件，`git log --all` 定位到 `194241dd`，独立树 `fwp-wt-river-next-specs-0913`。
2. 建树 `fwp-wt-research-diagnostics-04`（gitea/main@5fb13a8c），cherry-pick 规格提交（交接要求「携入这组规格」）。
3. 任务 0：读 `checkpoints.py / judgments.py / scenario_trees.py` 全文与 `observation_script.py` 的 late 判定；
   发现 `is_late` 判不出登记时刻按 late 处理——这在 04 里必须反过来（见决策 1）。
4. 写合同层 → 时钟 → 分组 → 五类规则 → 分母 → 选题 → 报告 → 适配器；先用空输入跑通 id 稳定性。
5. 写复合夹具并**先跑真实输出再写断言**，避免把预期编码成期望。
6. 三条失败修正：三倍重复输入导致 `observed` 文本里 verdict id 列表膨胀（改为输入按 id 去重 + 排序集合）；
   真实写入者用 `checkpoints._now` 盖 `ts`，派生 checkpoint 落在 cutoff 之后被过滤（测试里 `mock.patch.object` 钉时钟）；
   `git commit -- <paths> -m` 把 `-m` 当 pathspec（改 `-F`）。

## 决策与方案对比

| # | 决策 | 备选 | 评价 | 结果 |
|---|---|---|---|---|
| 1 | 迟登缺登记时刻 / 只有日期 → unknown | 复用 `is_late` 的 fail-closed（判不出=late） | 校准准入可以从严；归责从严等于用缺记录定罪，违反规格「缺记录不等于事实为假」 | unknown + `recorded_at_unknown` / `recorded_at_date_only` |
| 2 | 到期机会落在派生 checkpoint 行，原剧本 `due=None` | A 两边都算；B 只算剧本行 | A 同一原对象双计，违反「多源不增加样本」；B 的 verdict 挂在 checkpoint id 上，剧本行永远「无回检」 | 适配器写 `derived_from`；规则跳过有派生行的原对象 |
| 3 | 过期沿用的「当时已知失效」按失效事实记录时间 ≤ 使用时刻 | 强制要求曝光收据才可判 issue | 存量与近期都无曝光日志，强制曝光让本检查永久 unknown；规格的「可知性」是按行为当时 cutoff，不是按看没看 | 曝光收据进证据与分组，不作 issue 门槛；仅 hash 变仍 unknown |
| 4 | 策略无该对象类型规则 → excluded；有规则但当时不在效 → unknown | 两者统一 unknown | 统一 unknown 会把 memo 判断塞进迟登分母，unknown 数字失真 | `not_ex_ante` / `not_applicable` 排除；`rule_not_in_effect` unknown |
| 5 | 未到期作 `not_due_yet` 显式排除 | 当 out_of_range 丢弃 | 规格 §5 要求「未到期 excluded 并列原因」可见 | 保留在 exclusions 与分母 excluded 列 |
| 6 | 同 key 合并取 issue > context > unknown；输入按 id 去重 | 取第一条 / 取最保守（unknown） | 重复扫描不该把已判出的事实降回 unknown；也不该让重复膨胀 observed 文本 | 三倍输入 → 同 finding id、同分母 |
| 7 | 存量作者只看写下的字段 | 按 category / 文本相似猜作者 | 规格明禁文本相似证明看过；未知来源不算独立用户能力 | `unknown_legacy` / `promotion` → unknown_origin |
| 8 | 回检责任：剧本 / 树 / 方法观察 → system；其余按 metric | 一律 user | 这三类由系统钩子逐日解析，缺回检是系统失败 | non_attributable `system_recheck_missing` |
| 9 | 无时区时刻按只到日 | 假定 +08:00 | 写入者三种时钟（UTC / +08:00 / naive）混用；猜错会把及时判成迟登 | granularity=date，不判精确迟登 |
| 10 | 选题按 issue 类别字典序第一类，池内按 sha256(owner,finding,case) 取最小，优先未见 | 随机 / 按最新 issue | 需可复现；规格「不将结果选题说成随机」 | 同输入同题；重复题仍交付但标 seen_or_repeated |

## 验证与收据

见 PROGRESS §收据。要点：50 测试全绿绑定 `fea6ef98`；旧读取器 78 + 相邻模块 60 回归绿；pre-commit 11 道过；
适配器测试用真实写入者造五本台账，前后 sha256 相等。

**不成立的结论**：
- 夹具全部 synthetic，不证明任何用户效果或方法有效性。
- 复合场景里的 issue 数量是夹具设计出来的，不是任何真实用户的读数。
- 全仓 `pytest -q` 未在本树跑；合并前按 AGENTS.md 跑等价 CI。

## 后续要做

- 06：按 `…/04/BLOCKED.md` 清单注入收据；先 `adapters.load_legacy_inputs` 看 `gaps`。
- 01：定稿后对齐 `maintenance_report_01.json` 夹具与 `parse_maintenance_reports`。

## 不要做

- 不要把 unknown 折进 evaluated 或算成 0 issue——`denominators.check_identities` 会报 `denominator_identity_broken`，那是实现 bug 的信号，不是要抹掉的 gap。
- 不要在 04 里加 LLM 评分或语义判定；散文理由走 `manual_review`，规格 §6 明确无模型。
- 不要为存量 checkpoint 补造 `declared_deadline`；要判它们迟登，先在登记时写下截止或在 policy 定义确定性截止规则。
- 不要让 `generated_at` 进 `content_dict()`；报告 id 稳定性依赖它被排除。
