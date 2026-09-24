# E2 P5（D7）跨轮逐轴继承：真实链路五格 + 两处继承缺陷

日期：2026-09-16。执行树 `fwp-wt-e2-p5-inheritance`，分支 `feat/e2-p5-cross-turn-inheritance`，
从 `gitea/main@801d0fc2` 开出（该尖已含 #752 E2 P4、#753、#750）。本片是 E2 分片 P5，
不宣布 D7 全部完成，也不碰 P6/P7。

## 背景

P4 收口后，设计稿 §5 的下一片是 P5＝D7「逐轴继承 + 基底不可恢复 + 来源身份」。
在途交接已把起点指到 `conversation_orchestrator.py` 的 `conversation_materials` 传递处。
开工前确认：编译层（`compile_material_contract`）的两轴更新已有测试
（`test_e2_material_turn_delivery.py::test_axes_update_independently_and_new_task_resets`），
**但那是纯函数级**；A7 要求的是「全新会话 T2→T3 原始文本」走真实链路的五格。

## 按发现顺序

1. 探针打出编译层的五格与题内 B 轴现状：五格全对，题内 B 轴（消息级非 material_only）
   已按 D7.3 落 `boundary_uncertain`。唯一异常是**同值重申会多出一条前提标注**。
2. 写 11 条反例，压 `TurnOrchestrator.run_turn` → 真实 `decide_turn` → `TaskFrame` →
   `build_episode_context` / `build_episode_input`。首跑 7 红。
3. **逐条分清夹具错误与真缺陷**（P4 的教训：夹具构造错误不当产品缺陷证据）：
   - 两条「adapter 未到达」是我的夹具把继承与车道路由混在一起。换轴放宽成 full 后，
     题目主语「甲」是材料里的虚构公司、无法解析，于是本轮合法地走了澄清车道。
     单独复跑证实这两格的合同完全正确。改法：停在控制器之后断言 frame，再由该 frame
     装配 Episode；车道分流属 P3，不在本片。
   - 两条是多个测试共用 `task_id="p5"`，撞了 root budget 账本（`root budget already
     exists for live episode`）。改成每次装配用唯一 id。
   - 我的夹具还吞掉了真实堆栈：`run_turn` 把管线异常折成 `status=failed`、正文为空。
     补 `_fail` 探针后错误才可读。这一条与 P4 同型，已写进本轮教训。
   - 余下 2 红是真缺陷。
4. 修两处真缺陷（见下），11 绿；E2/episode/adapter/orchestrator 定向回归 580P/4S 零破坏。
5. 三个删保护变异全红（见下）。

## 两处真缺陷

| 缺陷 | 现象 | 修法 | 被否方案 |
|---|---|---|---|
| 同值重申不幂等 | `text_ref` 是原句哈希，重申得到同 ref、同 scope、只差 `source_turn` 的第二条；去重键是整条记录，挡不住。每续一轮重申一次，模型可见的前提标注就多一行，且两行指向同一个前提 | 按 `(text_ref, authenticity, scope)` 去重，保留**最早**轮次 | 否「按 text_ref 单独去重」（同一句在不同作用域是不同附着）；否「保留最新轮次」（与既有注释「题级标注带原轮次，不因续轮改写成当前轮」相反，且会让前提来历随重申漂移） |
| 题级标注跨轮同号 | 继承来的 `scope=q3`（来自轮次 1）与本轮 q3 渲染在同一位置，而本轮 q3 是另一道题。模型读到的是「本轮第 3 题有虚构前提」 | 作用域自带轮次：`轮次1的q3`；`message` 渲染成「消息级」 | 否「丢弃题号已不在本轮的继承标注」（前提仍在生效，丢了就丢状态）；否「只靠同行的 `轮次N` 字段」（那是另一个字段，读者要自己拼，正是误读的来源） |

两处都只动**模型可见投影与去重键**，不改两轴语义、不改权限、不改分流。
`premise_marks` 在生产代码里只有一个消费者（`episode_factory.py` 的渲染），已 grep 确认。

## 验证与收据

日志根 `~/.finance-runtime/e2-p5-20260916/`。

- 反例先红后绿：`p5-before.log`（7F/4P，含夹具错误）→ `p5-before3.log`（2F/9P，全是真缺陷）
  → `p5-after2.log`（11P）。中间两版保留，便于复核我如何把夹具错误从缺陷里摘出去。
- 定向回归 `p5-regression.log`：580P/4S（E2 全系 + episode_factory/protocol + adapter + orchestrator）。
- 删保护变异 `p5-mutations.json`（基线 570P/4S，还原后同）：

  | 变异 | 拆掉的门 | 红 |
  |---|---|---|
  | P5-M1 | 同值重申幂等（去重键回到整条记录） | 1 |
  | P5-M2 | 去重保留最早轮次（改成保留最新） | 1 |
  | P5-M3 | 题级标注带轮次（改回裸题号） | 1 |

  3 个全部落盘、全部转红、还原后回到基线。
- 四叶（都跑在 `fc9a130b`）：python ruff 0 + pytest 10963P/0F/81S/2xfail（467s）；frontend install(frozen)/lint/typecheck/vitest 94P（5 文件）/build 各 0；e2e 31P/2sk；registry 五条 0。
- e2e 首跑两次假红，都不是本片的代码：第一次 `RE06_E2E_PORT=8796` 被别的进程占；第二次只改了 `RE06_E2E_PORT` 而没改 `RE06_E2E_URL`——前者移服务端、后者移客户端，不成对设就得到 `ERR_CONNECTION_REFUSED`，读起来像 #750 的绑定链路红了。两个旋钮设成同一端口后 31P。已告知 #750 的作者 session。

## 不成立 / 未覆盖

- 作者自验，判官为离线替身；不是独立 QC，不是 P7 隔离验收。
- 本片**没有**证明 D7 全部条款：D7.3 题内 B 轴、D7.4 基底不可恢复、D7.6 来源身份分级
  这三条是**复核既有实现仍成立**（新反例锁住），不是本轮新写的。
- A7 的五格用的是构造查询（`ONLY_A`/`ONLY_B`/…）加 T2/T3 夹具，不是 P7 要求的
  「全新会话、原始 T3 文本、不重贴禁令」的正式验收；A7/A14 的验收资格仍在 P7。
- 两轴放宽成 full 后主语不可解析会走澄清车道——这是既有行为，本片未改，也未论证它对不对。
- 8792 未因本片重切；生产仍是 `6e23dd57`。
