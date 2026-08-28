# feat/capability-switchboard

## 这个分支做什么
从 `gitea/main` 抽出开关板 + 谓词缝（不搬旧超集树 `76ee1e89` 已漂文件）。

## 当前状态（2026-08-26 15:40 二次更新）
- **#350 已合 main**（`4dd96f6f`）；**#415 扩容批已合**（operator/pack/probe 12 行登记 + pointers，`ef2d8427`）；**#414（判读基线 r3）已合**——`predicate.reading-baseline` 转 active/exists 并进臂。**本单闭环**。
- **8796 当日二切**：`76ee1e89`（超集树）→ `6c47450e` → **`ef2d8427`**（含 dream-mine/判读基线/板扩容三合并）。health 全绿（dirty=false、deps 7/7），判读基线自此回到 8796，超集树彻底退役（目录保留可回退）。8792 未动（`fbdbbfd2`），**切流另开窗口**（r3 交接红线：今晚夜跑保持单变量，主检出不 pull）。
- 回退路径：旧快照目录**未删**；改回 `~/.local/bin/start-finance-workbench-capability-sidecar` 的 `runtime_tree=` 行 + `launchctl kickstart -k gui/$UID/com.a77.finance-workbench-capability-sidecar`。
- 切换验证：`test_capability_switchboard.py` 20 绿 + `test_asof_prefetch_dual_red.py` 合计 28 绿；runner `scripts/run_capability_switchboard.py` 在新快照可用。

## 未验证 / 已知边界
- ~~判读基线暂离 8796~~ **已解决**：#414（r3）合入 main，`ef2d8427` 快照已含，行已 active/exists 进臂。
- ⚠ **2026-08-26 15:50 全臂离线扫描（`ef2d8427` 快照，`--all-arms`，收据 /tmp/switchboard-ablation-demo.json）：66 条记录，27 过 / 8 败，败因分两类**：
  1. **`predicate.reading-baseline` 三题全败**（组件侧）——off 后 `reading_baseline_guidance` schema_delta 均空。可能：①臂题不触发判读注入 ②faces 接线未到 runner 观测面（#350 只接 dual_red_counts 最小面）③真 bug。**记给 r3 线核对**；在此之前「进臂」名不副实（arm-eligible ≠ arm-passing）。
  2. **`current-mainline` 单题连败 6 颗**（题侧）——finance_query / evidence_search / news_search（offered_schemas）、semantic-verifier（judge_status）、noop-prompt（prompt_segment_delivered）在这道题上正控全空、底盘均跑完。同批原子在 weekly-market-cause 上全过 → 疑该 case 在新底上没跑到 offer/judge/prompt 阶段（frame 解算或夹具漂移），**先修题再谈原子**。
  另：5 条 mandatory 拒关属正确行为（合同不可满足 ≠ 关得动）。
- ~~新架构组件无 board 行~~ **已解决**：#415 落 12 行登记 + pointers；但登记行 `positive_control` 均留空=不进臂，runner 的 operator/pack/probe 差量支持是下一批。
- `predicate.evidence-layers` 仍 `canonical=contested`，被 default-v1 排除，正典工单未了。

## 质量层消融首轮读数（2026-08-26 18:54，收据 `fwp-wt-capability-switchboard-main/intelligence/eval/runs/20260826T101858Z-quality-ablation.json`）

harness=`scripts/run_quality_ablation.py`（PR #416），6 题 × 双臂 × 真 LLM × 五维盲评（满分 20）。**样本小（单 judge、单次采样、4-5 题可用），是首个信号不是结论**：

| 组件 | 边际贡献 | 逐题要点 |
|---|---|---|
| evidence-judge | **+2.8** | 估值题 -6 / 复盘题 -5 / 主线题 -3（关掉后）——最值钱，别关 |
| kb-rag | **+1.5** | 全靠知识型题（瑞华泰估值 -8）；纯盘面题 Δ0（靠 DuckDB 不靠 KB） |
| **reading-baseline** | **-0.4（负）** | 估值题 +2，但复盘/主线题各 -2；伤在 truth_boundary(-0.4)——判读规则让模型更敢下判断也更易越数据边界 |

⚠ **判读基线负读数记给 r3 线**：r3 交接「总开关 A/B 零数据」——本轮即第一份 A/B 数据，方向为负。建议：换 judge + 加题复跑一轮确认；若确认，考虑默认关或按题型门控（估值/个股题开、复盘/主线题关）。
已知缺口：theme-liquid-cooling 题基线盲评失败 → 全组件失去该题；kb-rag 另失 index-rebound-space（该题走 1 秒确定性短路，对组件不敏感）。

**首轮读数的推进（2026-08-26 19:10，按「先确认再动刀」纪律）**：
- 盲评重试修复 → PR #422（open）；**确认轮**（reading-baseline + kb-rag × 6 题，seed 20260827 独立采样）基于该分支后台进行中，收据将落 `fwp-wt-capability-switchboard-main/intelligence/eval/runs/`。负信号确认前**不动生产代码**（题型门控是候选方案，不是已决定）。
- 实验副产品立单：**#423** CLI ask 缺全链绝对 deadline（实测单次 71 分钟，违反「deadline 传绝对时刻」已确立原则）；**#424** kb_search（Engine A 主 KB 通道）不过证据裁判语义闸（该闸 Engine B 实测 +2.8 分，Engine A 零引用=覆盖缺口）。

## 下一步
1. 板扩容小批次：operators / 四袋 / 探针登记成原子行（带 seam + close_via + positive_control，走设计稿第 0-1 步纪律），顺手落实替补探针预留 id。
2. #343 合入 main 后刷 8796 快照，恢复 reading-baseline 臂。
3. （可选）种子表加三行「指针行」：数据块（开关在 `AskOptions.enabled_providers`）、视角注入（开关在 Workbench UI）、引擎 A/B（开关在 `ASK_CONTINUOUS_RUNTIME` env），防止「不在板上」被误判成「没有开关」。

## 踩过的坑
- 旧坑仍有效：不要 `git checkout 76ee1e89 --` 已漂路径；不要复用 `/Users/a77/fwp-wt-capability-switchboard`（那是 `1c52e19f` 的 docs 树）。
- 新坑（2026-08-26）：`align/switchboard-p0` 超集树在 handoff 里长期挂着「解耦树，不合 main」，容易让人以为重切工作还没发生——实际 #350 已合。**判断「X 有没有进 main」用 `git log --grep` / 文件存在性，别只读交接文档**（本文件此前就写着「未合」）。

## 已验证
8796 切换后 `/api/health`：status=healthy、source_revision=`6c47450e6d4b…`、source_dirty=false、依赖 7/7 true。8792 同时点 healthy（`fbdbbfd2`，未受影响）。

---

## 附录 · 确认轮定论（2026-08-26 晚间另一会话追加；原写于主检出未提交层，2026-08-27 主检出同步 `75fc2236` 时搬运衔接）

> 上文「首轮读数的推进」停在「确认轮进行中」。确认轮已出定论，且候选单其后已被 #443 实施（见本节末补记）——上文「负信号确认前不动生产代码」「PR #422 open」等状态语以补记为准。

- **质量消融两轮定论**（收据 `fwp-wt-capability-switchboard-main/intelligence/eval/runs/20260826T101858Z` 与 `…T114208Z`，独立采样）：
  - reading-baseline：首轮 Δ=-0.4 → 确认轮 **Δ=+1.17，负信号未复现，无罪释放**，维持默认开。复盘题两轮翻面（-2→+4）＝单题 ±2 属噪声。
  - kb-rag：+1.5 → +0.33；估值题两轮恒 +8（强信号）。
  - **跨两轮唯一稳定负信号：主线题**——reading-baseline（-2/-4）与 kb-rag（-2/-2）四读数全负。幸存假设：主线/盘面态题型上知识注入类组件（KB 召回 + 判读规则）负贡献。
- r3 线注意：总开关 A/B 首两轮数据即上述两收据，结论=**维持默认开**。
- 全臂扫描修复后**失败 0**（PR #416）——上文 15:50 那轮「27 过 / 8 败」读数已被修复轮取代。
- **后续已发生（git 可证，2026-08-27 补记）**：主线题候选单（W 源降权 + 判读注入门控）已由 **#443**（`feat/market-watch-knowledge-gate`，合并 `47cf855d`）实施——含门控实现与静默失效修复（`8f227e96` / `e459b96a`）、5 道主线变体证伪夹具（`9bda272c`）、五轮消融收据入库（`be757c11`）；#424 的 kb_search 语义闸同批落地（`979453c7`）；#446 记录 **8792 已切 `47cf855dbe6a`**。#443 另立召回缺口工单（`1027a361`：门控覆盖 2/5）。本 inflight 上半篇叙事待该线收口重写。
