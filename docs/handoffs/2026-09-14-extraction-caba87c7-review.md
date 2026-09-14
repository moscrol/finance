# 工单 #53 返修复审 · caba87c7 · 2026-09-14

**结论：仍需返修。规范轴 2 项 P2，需求轴 4 项 P2。** 新全量收据可采信；不能据此将行为缺陷全部关闭。P2 表示应修的正确性问题。

固定候选 `caba87c7051c4f432c7b58297bf4758bcc3357ec`，固定目标 `gitea/main@1fef3d276d0e251158803fc09d5a81e60d79241b`；比较 `git diff 1fef3d27...caba87c7`，同时单独核对 `b42dc9bf..caba87c7` 返修。审查树 `/Users/a77/fwp-wt-qc-extraction-caba87c7`，测试前后干净，实现未改。本文编号 R-N/R-S 是本轮编号，不覆盖上轮 N/S。

## Standards（规范轴）

### R-N1 · P2 · N2 的残片修复漏掉中文半字符，整本台账仍会失去读写能力

位置：[observation_script.py:779](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/services/observation_script.py:779)。规范：`docs/learning/ledger-map.md:43` 与工单 §2.4 的完整行持久化、半行不算成功。

`load_raw` 先对全文件 UTF-8 解码，再逐行捕获 JSON 错误。先写一个完整尝试，再留下切在“观察”末字中间的残片，`load_raw` 和 `open_attempt` 都抛 `UnicodeDecodeError`；追加入口先读台账，因此根本到不了新增的补换行逻辑。直接调用 `_append_line` 补换行并成功追加后，重读照样异常，原有完整记录也读不出来。

应按字节分行，分别解码/校验，隔离坏行并保留原始字节。验证至少包含：完整旧记录 + 非 ASCII 半字符残片 + 下一条成功记录，三者分别可追溯，完整记录仍可读。证据：[standards-results.json](/Users/a77/.finance-runtime/reviews/extraction-caba87c7-20260914/standards-results.json) 的 `N2_truncated_utf8`。

### R-N2 · P2 · read 的完成收据与关闭状态之间仍有不可由重试修复的断裂

位置：[cli.py:3500](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/cli.py:3500)，重试出口 [cli.py:3423](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/cli.py:3423)。规范：工单 §2.4.4“成功 read 关闭尝试”，及交付未知与已持久化收据的区分。

在 `read_completed` 成功落盘后，仅注入关闭行追加失败：首次 exit=1，诊断声称“完成收据落盘失败／未知”，实际完成事件已有 1 条、尝试仍 pending。同 ID 重试 exit=0、返回原收据且不重建正文，但立即返回，pending 仍未收口。之后缺省入口还会复用这条本应已结束的尝试。

由唯一 writer 提供可重试补齐的完成操作；已有完成收据时补齐 close，并区分收据写失败与关闭失败。不能把 stdout 与收据之间允许的未知窗口扩展成“有完成事实也永久 pending”。证据：`standards-results.json.read_close_split`。

## Spec（需求轴）

### R-S1 · P2 · 复用旧草稿成功读取的新尝试，不能按尝试确认所读版本

位置：[observation_script.py:1009](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/services/observation_script.py:1009)、[cli.py:3548](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/cli.py:3548)。合同：§2.4.4“同键有效草稿仍可复用”“后续确认可关联已完成尝试的具体草稿版本”。

`draft → read(A) → read(B，复用旧草稿) → confirm --from-draft --attempt-id B`。B 的持久化完成收据已记录有效 `source_draft_id`，确认却 exit=1“该尝试里没有提交过草稿”。`draft_for_attempt` 只找草稿的提交归属，不读完成收据指向的版本；“在哪次提交”和“哪次读取选用了它”是两个不同关系。上轮 S4 要求按成功收据 source_draft_id 选版，返修尚未做到。

已完成尝试优先按原 read 收据选版并保留本次关联；未完成且没有收据时再按明定策略取草稿。证据：[reused-draft.json](/Users/a77/.finance-runtime/reviews/extraction-caba87c7-20260914/reused-draft.json)。

### R-S2 · P2 · 完整手填 confirm 仍忽略显式 attempt-id

位置：[cli.py:3521](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/cli.py:3521)、[cli.py:3645](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/cli.py:3645)。合同：§2.4.1“read/draft/confirm/skip/close 支持 --attempt-id 续接”“其他用户 / 目标的 ID 拒绝”；仅无关联尝试的手填确认使用独立动作口径。

把固态电池的尝试 ID 传给算力租赁的完整手填确认，命令仍 exit=0，并真实创建 checkpoint；写出的确认事件却是 `attempt_id=null / entrypoint=manual_confirm`。参数只在 from-draft/from-slice 分支消费，手填分支静默丢弃。

先校验显式关联的归属、目标与允许状态，再登记；未关联才用 manual_confirm，错误关联不得产生 checkpoint。证据：[spec-results.json](/Users/a77/.finance-runtime/reviews/extraction-caba87c7-20260914/spec-results.json) 的 `manual_wrong_attempt`。

### R-S3 · P2 · 尝试关闭后，系统确认与系统跳过仍能继续写入

位置：[observation_script.py:685](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/services/observation_script.py:685)。合同：§2.4.4“显式 close 后旧尝试不能复活”；§2.4.5“并发认领、追加与去重由同一写入者完成，不靠 CLI 先查再写”。

先有另一次尝试提交的有效草稿；在新尝试 `open_attempt` 返回后、confirm/skip 继续之前，插入真实 `close_attempt`。随后 `confirm --from-slice` 仍 exit=0，生成 confirmed 行及 checkpoint；同一尝试同时有 `closed / abandoned=true` 与 `script_confirmed`。系统 skip 同样在 close 后写 skipped 行。S9 对 submit_draft 的持锁复验已修，但 register 在锁内只去重，没有对应状态检查。

在副作用前持锁检查此系统操作仍有资格；已有确认重试可取原收据，已完成尝试的草稿后续确认按 §2.4.4 单独处理，不能把关闭状态一律禁写而误伤合法路径。证据：`spec-results.json.confirm_after_close / skip_after_close`。

### R-S4 · P2 · S6 去重键漏了回检日期，修改 due 被静默当作重试

位置：[observation_script.py:443](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/services/observation_script.py:443)、[observation_script.py:694](/Users/a77/fwp-wt-qc-extraction-caba87c7/intelligence/services/observation_script.py:694)。合同：§2.1 保留完整手填 confirm 原有语义；§2.4 仅“同动作重试”去重。

同内容先确认 `--due 2026-09-15`，再指定 `2026-09-16`，第二次 exit=0，却返回旧 due=15、同一 checkpoint，用户要求的新回检日期未生效。去重键只有四类文本字段、目标、入口和尝试；实际传给 checkpoint 的 due 在键外。

规范化动作身份应涵盖会改变实际登记效果的参数，至少包括 due；若产品决定修改日期必须走专门改点入口，也应明确拒绝而非成功回旧值。本轮另用同一个日期变更探针对照返修前 b42dc9bf 对应代码，修前按请求返回新日期、修后返回旧日期，确认为返修新回归。证据：`spec-results.json.changed_due`、[due-before-repair.json](/Users/a77/.finance-runtime/reviews/extraction-caba87c7-20260914/due-before-repair.json)、[due-key.json](/Users/a77/.finance-runtime/reviews/extraction-caba87c7-20260914/due-key.json)。

## 已关闭、非阻塞备注及验证范围

- **N1 可关闭。** 独立核对原始日志和 JSON 收据后，另建 d7e53805、7a86ce4e 两棵对应提交的 detached 树，在各自树运行自身 `check_test_receipt.py --expect-revision`，均 exit=0；两棵临时树已清理。9554P / 9657P、dirty=false、解释器/依赖指纹自洽；7a86→caba 仅验证文档差异。
- **+103 可对账。** 新增验收77、返修25、接缝+1；collect-only 独立核实。八叶日志现存且成功；13条变异摘要均 exit=1→0、恢复102P。变异未留每条完整失败 traceback，因此这里只确认摘要和复原结果自洽，没有宣称本轮重跑了全部变异。
- **原修补方向成立。** S1字段继承、S2无骨架不计完成、S3正常完成返回原收据、S5确认行不作草稿、S7两侧去重、S8过期不解除遮蔽、S9关闭后禁止新draft、S10 pending筛选均有对应实现和绿回归；N3 abandoned 重试补齐符合收窄合同。N2/S4仍有上述缺口，S6又引入due回归。
- **N4 留一个非阻塞修字。** inflight 已压到2962字节，但第9行仍称“已提交三笔”，只列到08ca525f；应补7a86ce4e/caba87c7。验收表A1写11实9、A9写7实8，总计77正确，随文档更正，不扩列行为问题。
- **本轮实际运行：200 passed / 0 failed，1.74s；8个变更Python文件ruff通过。** 7个测试模块覆盖新验收、返修、既有观察剧本、带读、日报接缝、个人导出。使用主树指定venv及 `FWP_TEST_RECEIPT=0`，避免覆盖全局latest收据；前后git状态记录均为空。一次初始命令因误写导出测试文件名未收集测试，已修正并完整重跑，200P来自修正后命令。
- **目标分支预演无文本冲突。** `git merge-tree --write-tree 1fef3d27 caba87c7` exit=0，tree `8abe7a553700478d0a5d4111466f57b3bb301144`，INDEX也无冲突。本轮未对该组合树跑全量，不能把无冲突当成可合并门禁。
- **未验证**：真人效果、§7阈值、真实用户与真库身份解析。探针仅用临时users、固定本地切片及受控失败/交错；未写生产台账、未推送合并部署实验。

## 复跑与返修顺序

在候选树设置 `PYTHONPATH=.`，用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python` 执行本目录 `standards-probes.py`、`spec-probes.py`、`reused-draft-probe.py`。脚本报告观察值，正确性期望见上述各项；不能将脚本自身 exit=0 误读为被测产品合格。

先补写入侧的字节恢复与终态约束，再修确认的来源/关联/去重参数。逐项把独立反例变成修前红、修后绿的回归；保持S6跨秒重试和N3补齐旧回归仍有约束力。最后在固定干净新提交重跑适用门禁，并相对当时最新目标分支复查。

本轮未列 A→B→A 为缺陷：当前合同将同内容同尝试视为同版本重试，回退动作与旧请求重放的区别未定义；保留观测，不作确定违规。并未因风格偏好或现存基线问题扩大清单。

规范轴：2项，最重影响为残片使整账不可读写；需求轴：4项，最重影响为关闭后仍创建确认和checkpoint。两轴分别结论，不用通过数量抵消反例。
