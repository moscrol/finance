# 2026-09-14 · 工单 #53 提取前置 P0：设计取舍与质检返修的完整背景

在途件 `docs/handoffs/inflight/feat-extraction-first-p0.md` 只放当前状态（≤3KB 预算）；
不限长的背景、被否方案与逐条根因在这里。收据 `docs/verification/2026-09-14-extraction-first-p0.md`。

---

## 一 · 五个非显然的设计取舍

### 1 成功事件随成功剧本行一次写入，不追加第二行

`draft_submitted` / `script_confirmed` 的元数据放在剧本行的 `action_event` 字段里，
读取时由 `projected_events` 投影出来。

**被否**：保存剧本成功后再 append 一条事件行。
**理由**：那是两次写。中间崩溃会留下「剧本在、事件不在」，而这种断裂**事后无法与
「根本没提交」区分**——两者在台账上长得一模一样。把事件元数据放进那一行本身，
「事件发生过」与「剧本存在」从此是同一个事实。

**代价**（质检暴露的）：这条原则只在 `submit_draft` / `register` 上贯彻了，
`close_attempt` 的 abandoned 仍是第二次追加，于是 N3 那条断裂原样留着。返修没有把
abandoned 也改成投影（§2.4 明写「其他事件用独立事件行」），而是让**重试可补齐**：
关闭行自己记了 `abandoned=true`，重试据此重新追加，按 `action_key` 幂等。

### 2 顺序门放在 `guided_reading.build` 之前

**被否**：在渲染前拦、或在输出前拦。
**理由**：`build` 出来的对象**已经是系统的答案**。只要它存在，任何一个 `--json` 分支、
日志行或异常回显都可能把它漏出去。不生成，才是真的不泄漏。所以 A3/A7 断言的是
`gr.build` 的**调用次数为 0**，不是「输出里没有那几个字」。

「先记跳过、再生成骨架」的顺序也放进共用门内部（`gated(on_skip=...)`）：
**被否**：让每个调用方自己按顺序写两行。
**理由**：靠约定维持的顺序，总有一个入口会写反，而写反了从输出上看不出来。

### 3 尝试与事件寄存在 `observation_scripts.jsonl`，用 `record_kind` 分型

**被否 A**：新建一个 `extraction_events.jsonl`。
**理由**：违反台账地图「一条台账线只有一个 canonical 落点」；两个文件之间的一致性
没人维护，迟早漂。

**被否 B**：写 `interactions.jsonl`。
**理由**：这是**最危险的一个**。`interactions.jsonl` 是 `guided_reading.is_new_user`
的三条判据台账之一，任意非空行都会把新用户翻成老用户 → 带读默认开关随之翻转。
**记录过程的动作反过来改变了被观测的行为**，而且不会有人发现。
A11 有一条专门钉这个：`test_recording_extraction_alone_does_not_flip_the_new_user_verdict`。

### 4 确认动作的去重键由内容算出，不含录入时刻

`_confirm_action_key` = `(user, as_of, scope, entity_ids, 四个业务字段, entrypoint, attempt_id)` 的哈希。

**被否**：用 `record_id`（初版就是这么写的）。
**理由**：`record_id` 派生自 `recorded_at`，秒级。跨秒重试就换了一把键——
**去重在唯一需要它的场景（重试）恰好失效**。质检 S6 实测：同一条 confirm 跑两次得到
两条 `script_confirmed`，还多登记了一个可证伪点。

配套：认领必须发生在**产生 checkpoint 之前**。先登记再发现重复，回检队列里已经多了
一条，而台账 append-only，删不掉也不该删。

### 5 关联键里的 `scope` 由身份推导，两侧共用一个函数

工单 §2.1 把 `scope` 写进了关联键。直接读用户 `--scope` 填的值会出事：用户填 `index`、
系统按 entity_id 推出 `theme`，同一个阅读目标裂成两个键，**表现是「昨天写的草稿凭空
消失」而不是报错**。所以 `extraction.scope_for()` 是唯一推导处，`_draft_script` 与
`_key_of` 都用它；剧本正文里的 `scope` 仍是用户填的那个，受同一道硬门校验。

> 如实记一句：`scope` 由 `canonical_entity_id` 唯一决定，放进键里**不增加区分度**，
> 是冗余项。按工单口径实现了；将来若精简键，这是可以去掉的那一位。

---

## 二 · 2026-09-14 质检 14 项的逐条根因

质检目标 `git diff d7e5380551ba...b42dc9bf`，独立跑隔离 CLI 反例与故障注入。
14 项全部成立，无误报。返修提交 `08ca525f`（12 项行为缺陷）+ 本轮文档（N1 / N4）。

| # | 根因一句话 | 形状 |
|---|---|---|
| N1 | 全量跑到一半我就开始建文件，收据 `dirty=true` 且 revision 对不上最终提交，却被写成「干净基线全绿」 | **假证据** |
| N2 | 半行残片没有结尾换行，下一次 append 直接粘上去，一个断电吃掉两条记录 | 持久化恢复缺失 |
| N3 | closed 行已落、abandoned 追加失败 → 重试在「已关闭」处提前返回，断裂永久化 | 两次写的第二次 |
| N4 | 交接写「未提交」而实际已两次提交；6991 字节超 3KB 预算 | 状态过期 |
| S1 | `confirm` 的 upgrade / machine conditions 只认命令行 | 字段静默丢失 |
| S2 | 六轨全缺时仍记 `read_completed` 并关闭尝试 | 终态误判 |
| S3 | 成功 read 关闭尝试 → 同 ID 重试撞「已结束」退 2，收据分支不可达；测试还断言 exit=2 | **名实不符的测试** |
| S4 | `--from-draft` 完全没读 `--attempt-id` | 参数被忽略 |
| S5 | `user_drafts` 只看 author，确认行冒充最新草稿 | 判据不足 |
| S6 | 去重键含时间戳派生位，跨秒重试换键 | 去重形同虚设 |
| S7 | repoint 整行复制，把原确认的动作元数据也复制成第二次确认 | 派生行复制事实 |
| S8 | list 先 expire_stale 再遮蔽，而遮蔽只挡 drafted | **展示层换算解除了安全判据** |
| S9 | submit_draft 不复验尝试状态，open→close→submit 交错下关闭后还能提交 | check-then-act |
| S10 | `--attempt-id` 只过滤 events 不过滤 pending | 查询面谓词不一致 |

### 三条最值得带走的

**1 · 假证据比没证据更糟（N1）。** 第一次基线跑到第 3 分钟我就创建了
`observation_extraction.py`，第 4 分钟改了 `observation_script.py`。pytest 在收集期导入
模块，之后导入的测试拿到的是新代码——**那个 9554P 不是基线读数，是混合树读数**。
我却在收据里把它写成「干净基线全绿，所以任何失败都不能推给存量红」。
回填 SHA 不能把脏树读数变成那个 SHA 的收据。仓内 `check_test_receipt.py` 本来就能
一句话拆穿（`--expect-revision` exit=1），我没跑。

**2 · 夹具可以把缺陷编码进去（S8）。** 我那条遮蔽用例之所以绿，是因为夹具行**没有
`due` 字段**，`expire_stale` 要求 `due` 非空才改状态，于是正好躲过了缺陷路径。
「测试绿」证明的是「这个夹具下绿」。同类形状在记忆里已有一条
（golden-fixtures-can-encode-the-defect），这次是自己又踩了一遍。

**3 · 同名两道防线要分别钉（S7）。** 写入侧（repoint 不复制 `action_event`）与读取侧
（`projected_events` 按 `action_key` 去重）都修了。只断言「事件数 = 1」时，回退写入侧
那道，测试仍然绿——被另一道兜住了。变异 M12 第一次跑出「没有牙」就是这个。
补了一条直接断言「改点行里没有 `action_event`」的用例，两道各有独立的牙。

---

## 三 · 变异清单（13 条，逐条 RED→GREEN）

harness `/tmp/xfp0/mutate.py`，每次运行前清 `__pycache__` 且 `PYTHONDONTWRITEBYTECODE=1`
（防同长度改动 + 秒内还原被 `.pyc` 缓存伪造成回归），锚点唯一性由 harness 自检。

M1 差异恒空 · M2 绕过共用门 · M3 系统 drafted 冒充用户草稿 · M4 命令返回即 abandoned ·
M5 关联键去掉用户 · M6 确认行冒充最新草稿 · M7 过期解除遮蔽 · M8 残片吃掉下一次写入 ·
M9 关闭后仍可提交 · M10 确认重试不去重 · M11 确认丢掉用户机检条件 ·
M12 改点伪造第二次确认（写入侧）· M13 读取面不去重（读取侧）。
