# 06 研究进化 · 第八轮 QC 返修（Y1/Y2）收口说明

对应裁决：审查树 `codex/review-re06-round8-fdb5f91d` 的 `docs/verification/re06-fdb5f91d/REVIEW.md`
（候选 fdb5f91d / 代码 7abaa938）。两针原样回放（未改判定路径），探针已收编同目录
`test_review_round8.py`。返修落 `c5359120`。

## 根因（两针共用一个）

旧合同用同一个 `None` 表达三种来源状态：**确认无来源**（裸 run）、**来源未就绪**
（消息 run 的源消息还在持久化）、**读取失败**（OSError 等）。后两者被折算成
「无冲突」放行，分别覆盖终态先到（Y1）与读取失败（Y2）两条路径。

## 修法：来源身份三态 + 发布前保存的可信启动身份

裁决授权的实现方向：「可用发布前保存的可信启动身份或明确的 pending 状态」。取前者。

1. **创建时落身份**（Y1）：消息 API 的 `create_run` 新增 `maintenance_launch` 参数，
   坐标随 run 记录原子落盘——run 一旦对外可见/可取消，身份已就绪，终态折回不再依赖
   「源消息是否已落盘」。「未就绪」窗口由此消除（运行期只剩读取失败一种 unavailable）。
   `Run` 加字段 `maintenance_launch: dict | None = None`；旧记录无此键 → 默认 None，兼容。
2. **三态裁决**（`_source_launch_identity`）：run 记录身份优先（消息时序无关）→ 已落盘
   源消息坐标（覆盖本修复前的 run 与测试直写路径）→ 读取成功且两边都没有 = `confirmed_none`
   （裸 run，R7 合同保留；会话不存在归此类——消息入口要求会话先存在，不存在的会话永不
   有来源落盘）→ 读取故障（OSError / ValueError / 完整性错误）= `unavailable`。
3. **终态闸**（`_terminal_source_gate`，消费侧专用）：ready 矛盾 → `ERR_RUN_BINDING_MISMATCH`
   （链接只留审计）；unavailable → 新错误码 `ERR_SOURCE_UNAVAILABLE`（503，追加不改名），
   终态保持待复核、恢复后重试；ready 一致 / confirmed_none → 放行。
   `fold_run_terminal` 照吞 ApiError（观察器与确定性恢复不外抛），unavailable 不留
   半成品、不毒化幂等键（恢复后重试可正常折回，有正向测试钉住）。
4. **补偿登记同走三态**（`_compensate_terminal_link`）：创建时落的身份与源消息坐标同为
   可信启动身份——「消息永不落盘」的 run 也能凭记录身份补偿折回（身份就绪即可恢复）；
   unavailable 抛 503 而非冒充「无法证明归属」。

## 合同边界（明确不动的）

- **接受侧保持乐观**：运行中登记仍用消息坐标核验（`_source_coordinate_conflict`），
  窗口期抢登返回 200 是 R7 合法延伸（Y1 探针 setup 断言保留）；收口在消费侧终态闸。
- X1（无身份成果一律显式确认）、X2（不双登记 + 矛盾不驱动状态）、Q2 过渡合同原样保留。
- 普通聊天 run（无坐标）任何时点的裁决都是 confirmed_none，窗口期消费它不算错——
  它的源消息永远不会带坐标。

## 验证证据

- 新两针 **2/2 原样**：中立目录回放（PYTHONPATH 指向本树）与仓内收编位置各绿一次。
  注意陷阱：从审查树根目录跑探针会被 pytest 的 conftest 插入把 `intelligence` 解析到
  审查树（收据 SHA 暴露：d51b5e6c ≠ 本树）——验证修复必须拷到中立目录跑。
- 组合门禁：仓内五套件 + round3–7 探针 **133 passed**（含本轮 4 条 Y 镜像）；round8 收编探针
  仓内 **2 passed**；round2 外部探针（中立目录）**10 passed**。合计 **145** = 历史 139 + 本轮 6。
- 干净候选 `c5359120`（dirty=false）裸 pytest **10147 passed / 0 failed / 77 skipped /
  2 xfailed**，收据 `~/.finance-runtime/test-receipts/20260914T083228Z-c5359120.json`
  ——算术吻合：10141@7abaa938 + 本轮 4 条 Y 镜像 + 2 条 round8 收编探针（被裸 pytest 收进全量）。
- e2e 重跑 **31 passed / 2 skipped**；ruff 全绿；pre-commit 11 道全过。
- 前端零改动：94 tests 沿用。run 公开载荷新增 `maintenance_launch` 键——前端无严格
  schema 校验（结构类型容忍额外键），e2e 真后端集成已覆盖。

## 留痕

- 来源身份三态是消费侧合同：确认无来源才可按登记归属消费；未就绪由创建时落身份消除；
  读取失败一律 pending + 503，不折算。
- run 记录里的 `maintenance_launch` 是创建时的客户端声明（与源消息坐标同信任级），
  实质校验仍在 rejudge 台账回查与 (项, 代际) 比对。
- judgments writer 归属扩展仍是登记依赖（若未来恢复自动关闭，先动它 + 升级 Q2 正例）。
