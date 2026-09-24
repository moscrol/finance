# 双索引部署接手：隔离迁移已启动，生产写者冲突阻断切换

## 当前裁决

2026-09-18 21:40（UTC+8）现场：**不切8792、不提升索引、不覆盖他人产物**。
发现另一 Cursor 会话直接在共享 KB 主树执行 `publish_rag_index.py --build --tag
rag-index-full-latest --prerelease --clobber`，PID41455（父41453）；本窗口生产普通/全文
索引文件均已变化。不能再沿用“整个窗口生产字节未动”的说法。归属证据是进程与指纹，
不据此断言每一字节的具体写者。先请用户协调该发布任务的所有权；未终止对方进程。

8792现场仍 `bf662e9310ff751a4c31763815ee78fb7d6d5122`，本会话没有改启动器、运行链接、
用户数据或服务。新候选未推、未合、未部署。两仓共享脏内容与 `内蒙一机` 冲突未处理。

## 按发现顺序

1. 接用户提供的合入收据，fetch核定金融 `d32b8966`、KB `91725ea9b`。金融主树为脏的
   detached `b4a35fa2`，KB主树为脏的 `8a413cde5`。从已验金融主干另建
   `fwp-wt-kb-dual-index-deploy` / `fix/kb-dual-index-deploy`。
2. 手动补读偏好、项目笔记、前两轮交接；金融代码地图在新树为空，已完整build再查询。
   KB建树前使用命令级安全hooksPath，复制保留原pre-commit，省略post-*，未绕提交门。
   冻结KB代码 `~/.finance-runtime/kb-code-91725ea9ba02`，干净detached检出。
3. 旧KB三个post-*仍直接调用主树旧 `rag_auto_update.sh`。已备份原文件，并原子安装
   **仅维护暂停**包装：跨树调用skip，主树调用maintenance skip；不改变pre-commit。
   真实安装路径两种cwd共6次调用后，18份生产索引文件hash与入口基线一致。
   这是**Git钩子路径验证**，不是覆盖direct build/publish的全写者维护锁。
4. 复制21,819个资料文件至独立 `source/{wiki,raw}`，源前/副本/源后的SHA逐项相同。
   保留共享脏资料原样（包括冲突），不把git SHA冒充资料版本；文件清单SHA为
   `db479e9a54689007a52aef52a0d96534f68038cb59e46dd143086f9ed99bb96d`。
   两索引用macOS copy-on-write副本复制至 `staging/`，没有将生产路径设为更新目标。
5. 使用冻结KB的原 `rag_index.py update`，原生产RAG解释器（Python3.14）和本地缓存BGE-m3，
   HF/Transformers offline，不换模型、不改切块/排序/include_raw/max_files。
   普通迁移59.338秒，reused168861/embedded0/removed774；全文更新仍运行。
6. 发现金融的显式 `retrieve(code_root=...)` 未接生产env，prewarm/probe仍从资料树找脚本；
   worker取ambient KB_VAULT而不是调用参数。候选 `c0fa49cf` 修统一代码根与worker资料绑定。
   再发现full模式相对目录可能读回旧全文索引，`d95d4921` 加同代全文索引配置。
7. 普通副本只读验收：168861条向量全部finite/非零/归一，metadata v1，各证据字段有非空值；
   selected14448、indexed14434、隔离14页、缺口0、索引内冲突0。冻结源/实时源均fresh。
   health仍exit3/degraded，唯一原因是14页待语义恢复，**未放宽门禁或宣称全库健康**。
8. 同一验收脚本最后核生产文件hash失败。查明另一个直接发布会话正在写生产。
   保存差分（首次观测10个文件变化，非穷尽整窗）及现场进程，立刻停下提升/上线流程并询问用户。
   无回滚他人的写入，也无把新基线覆盖旧基线。

## 候选接线（未部署）

- `KB_RAG_CODE_ROOT`：prewarm/probe/CLI/worker统一加载不可变KB代码；显式参数优先。
  配置路径失效拒绝，不回退旧资料树代码。
- `kb_wiki`：worker启动时显式传为KB_VAULT，纳入worker池复用键；不能受ambient错误根劫持。
- 原 `RAG_INDEX_DIR` / `VECTOR_INDEX_DIR` 保持普通索引选择；`KB_RAG_FULL_INDEX_DIR` 仅覆盖
  full模式规范名 `.rag_index_full`，缺目录拒绝回退，其他显式路径不变。
- 门页与测试同步；没有改排序、预算、模型或证据合同。

## 方案取舍

| 方案 | 裁决 |
|---|---|
| 更新共享主树到main再建索引 | 否：覆盖他人dirty/未解冲突，且会载入可变代码 |
| 一次原地刷新生产两索引 | 否：磁盘写不是两目录原子事务，读者可能见到半代 |
| 冻结代码+复制资料+独立索引，验后显式切根 | 采用：旧服务/原索引可保留，不依赖共享树代码 |
| 用wiki软链伪装代码根分离 | 否：`.resolve()`最终仍回旧根，或丢失实时冲突核验 |
| 仅停post-*就声称维护封闭 | 被现场否证：direct publish/build仍有写权限 |
| 杀另一个会话、覆盖其新索引 | 否：不认领他人任务；先协调写者所有权 |
| 关冲突隔离让health转绿 | 否：fresh仅代表同步；历史14页继续隔离 |

## 验证与后台任务

- 新根回归在旧代码上4失败/3通过（含真实CLI与worker集成反例）；其中一个unit红有mock噪声，
  后已使mock返回真实字符串。不能把该噪声当行为证据；真实跨仓旧端probe失败明确。
- 第一片定向80通过；全文接线后定向81通过（变更树读数，不冒充固定HEAD全量）。
- 两个代码提交的原pre-commit、改动Ruff、diff-check通过。
- `c0fa49cf`第一轮全量**主动中断**，准备补full接线；不是pass。
- 固定干净`d95d4921b0a774a2f0de3266e69d9bcd78e2cfc0`完整门禁已启动：
  Ruff/registry五项exit0，Python全量尚在跑，frontend/E2E顺序待跑。不写全量通过。
- 后台都是有限任务，没有自动提升或切服务：迁移父PID40354（全文子PID41233），
  门禁父PID47887。先检查进程实际身份，不盲信未来重用的PID。

现场根：`~/.finance-runtime/kb-dual-index-20260918/`。
- `migration.pid`、`evidence/migration-results.json`、`evidence/rag_index_full-update.log`
- `gate.pid`、`gate-receipts/revision.txt`、`gate-receipts/runner.log`、最终`all.exit`
- `evidence/production-index-before.json` / `production-index-drift.json`
- `evidence/structured-health-frozen.json` / `rag_index-verification.json`
- `evidence/concurrency-block.json` / `health-concurrency-block.json`
- 原钩子 `evidence/post-{checkout,commit,merge}.before`；当前包装日志`hook.log`

`verify_indexes.py`在普通副本检查通过后因生产漂移**整体exit1**，不能用前段结果代签整条。
资料清单21,819项保留现场，不把大JSON全文注入上下文。关键小收据持久化在
`docs/verification/2026-09-18-kb-dual-index-deploy/`。

## 下一步 / 不要做

1. 用户协调direct publisher停止/交接后，重新盘点Git hook、ingest自动更新、build/update、
   publish所有写入口；维护保护必须围住实际发布目标及写者，而不仅是触发器。
2. 本轮三个post-*仍处于维护暂停（无自动恢复）。不要恢复旧绝对路径脚本；新自动刷新链尚未部署。
   正常资料入库和direct写者未被包装全面禁止，不能宣称全系统maintenance。
3. 检查后台完成及所有退出码。全文未完成不可提升。源在冻结后若变化，须重新核资料差分与freshness。
4. 两个候选代码提交未合，合并须用户确认与完整四叶/固定SHA收据。不能部署新main冒用旧收据。
5. 检查双索引版本、真实非空字段、raw白名单覆盖、冲突页不泄漏，做新consumer真实CLI/暖worker
   BGE smoke；14页正文问题仍是独立语义恢复，不删除marker伪装修复。
6. 再准备8792原子链切、完整启动器备份及反向回滚，按acceptance-workflow做真实服务核验与台账。
   当前只证明普通迁移副本，不证明生产检索恢复或金融答案质量改善。

## 沉淀

双根接线回归进入正式测试，防止只测显式fixture参数而漏真实env入口。单次迁移/检查驱动仅组合
已有维护器，不建立第二条索引算法；现场脚本作为本次证据保留，不作为无人值守通用部署器。
跨任务教训回写既有 `script-identity-binding-location-is-not-identity`：钩子隔离不等于写者隔离。
共享harness-reference仍有他人dirty，未改其文件。
