# 标签口径升版的迁移方案（v3 / v4 / v5 三版并存的收口）

> 日期：2026-09-12（**第二版**：初版第二步按当时写法执行不通，复核指出后按实测重写）
> 触发：复核 #738 时指出「共享库重建前要先补迁移方案」；核实后确认这是 **#671 升 v4 时就欠下的债**，不是 #49 引入的。
> 状态：**方案，未执行**。执行要用户逐步点头（写共享库 / 动在途实验）。

## 1. 现状（只读实测，2026-09-12）

| 处 | 标签口径 | 证据 |
|---|---|---|
| 前向协议 `475597e2…`（双红方法，唯一在跑的方法验证实验） | **v3** | `protocol.json` 的 `label_version` |
| 共享旁路库 `db/history_labels.duckdb` | **v4** | `history_build_meta`（#737 记录的 v4 重建） |
| 代码 `labels.LABEL_VERSION` | **v5**（本单） | `labels.py` |

### 1.1 真实待办清点（初版没做这一步，先清点再定方案）

| 项 | 实测 |
|---|---|
| `history` 收据 | 1 份（2026-09-09） |
| `capture` 观察 | **1 份**（2026-09-10，`features.daily` 为 0 条） |
| `recheck` 结算 | 1 份（2026-09-10），分类 **`stage_not_applicable`**（非适用阶段） |
| **待回检对象** | **0** |

**订正初版的一句夸大**：初版写「09-10 起的在途回检目前是断的」。实际是**没有待回检对象**——
唯一那次观察当天就结算完并归类为「非适用阶段」。真实状况是「新的 `capture` 跑不了」，
不是「有对象卡在半路」。这个差别决定了方案：旧协议**不需要**在途结算，可以直接封存。

### 1.2 三道门，不止一道（初版只看到第二道）

对真实 v3 协议 + v3 备份库逐个试，三处都会拒：

| 门 | 报错 | 含义 |
|---|---|---|
| `validate_protocol(protocol)` | `unsupported protocol contract or label version/spec` | **v3 协议在当前代码下连协议校验都过不了**，与库无关 |
| `read_outcomes(v3 备份, protocol, features)` | 同上 | 同一道门，先于库版本检查 |
| `_check_sources(...)` | `outcomes must come from the frozen labels database` | 观察冻结的是库的**绝对路径** `/Users/a77/finance-workspace-private/db/history_labels.duckdb`，换成备份路径即被拒 |

另外备份库的数据水位停在 **2026-09-10**——即便前两道门都过，也**算不出 D+5 收益**，
静态备份不能结算未来。

⇒ **初版方案第二步「用 v3 备份库跑该协议剩余的 recheck」不成立**，三个理由各自独立。

## 2. 不可接受的做法

- 不把旧观察改标成新版本（协议冻结的是「在哪个口径下观察」，改标 = 事后篡改实验条件）。
- 不原地覆盖共享库就算完事（旧库一被覆盖，v3 / v4 下的收据再也无法复算）。
- 不为了让旧协议跑起来而放宽 `validate_protocol` / `_meta` / `_check_sources` 任何一道门。
- 不把「旧库 + 旧运行时」当成常备设施去维护——只在需要**复算既有收据**时临时起。

## 3. 方案：旧协议直接封存，新协议在 v5 上另起

前提就是 §1.1 那条：待回检为 0，所以不需要"跨版本把在途对象接过来"这种最难的迁移。

### 3.1 备份留档（无风险，可先做）

```
db/history_labels.duckdb → history_labels.v4-<日期>.duckdb   （只读留档）
db/history_labels.duckdb.bak-v3-20260911                      （#737 留的 v3 备份，保持不动）
```

`methodology/receipts/`、`methodology/refuted/`、用户态 `method_validation/` 一律不动。

### 3.2 旧协议（v3）：封存，不尝试跨版本结算

1. **不跑任何 v3 的 `capture` / `recheck`**——三道门都会拒，而且没有待回检对象需要它跑。
2. 封存旧协议：

   ```bash
   scripts/method_validation.py supersede --study-dir <v3 目录> \
       --successor <v5 协议 id> --reason "口径 v3 → v5；封存时待回检 = 0"
   ```

   它写 `superseded.json` 并**带运行语义**：`list_studies()` 默认不再枚举该目录，
   因此 `flywheel` 指纹、standing 摘要不再把它当活跃对象；审计时用
   `list_studies(root, include_superseded=True)` 仍能看到全部。

   旧版方案写的是「写一条 `superseded` 记录」，那是行不通的：`write_record` 只接
   `history/capture/recheck`，传 `superseded` 直接 `invalid record kind`；即使手写一个
   标记文件，09-12 质检实测 `list_studies` 照常枚举、`fingerprint` 不变、standing 仍
   `fresh=True`——**那只是人工备忘，不是停用开关**。

   已有的 history / capture / recheck 收据原样保留（封存 ≠ 删除）。
3. 复算既有收据（若将来需要）走「临时起一个旧 revision 的运行时 + v3 备份库」，
   属一次性取证，不进日常流程。**本方案不安排它**。

### 3.3 新协议（v5）：重建库之后另起

1. `build-labels` → `outcomes` 重建共享库到 v5（**这一步才是需要点头的写操作**）。
2. 用同一份方法定义 `register` 新协议，`label_version` = v5，
   **`forward_start` = max(重建日, 实际登记日) 的下一个交易日**。

   不能把它固定成「重建日次日」：②③ 之间可以停（本方案自称每步可停），周五重建、
   周一才登记的话，「重建日次日」已经是过去，`register` 会被
   「history must end by registration day; forward_start must be after registration day」
   拒掉（09-12 复核实测）。取两者较晚的那个再往后一个交易日，两条约束才同时成立：
   前瞻不含重建前的口径，起点也确实晚于登记日。
   登记时才计算这个日期，**不要在方案里写死具体某一天**。
3. `history` 段在 v5 库上重跑，得到与旧协议可并排、**不可合并**的读数。
   这是**本协议自己的历史演练**，与 §3.4 的规则收据重跑是两件事，互不替代。
4. **把消费者的绑定切过来**：

   ```bash
   scripts/method_validation.py activate --user "$U" --study-dir <v5 目录>
   scripts/method_validation.py active   --user "$U"   # 核对：rc=0 且 protocol_id 为 v5
   ```

   **`register` 只建目录，不改任何人的绑定。** 夜跑的 `METHOD_STUDY_DIR` 按
   「显式环境变量 > `active` 指针 > 内置默认」取值；不执行这一步，登记完成后
   夜跑仍会选旧协议（09-12 质检）。若生产环境显式设了 `METHOD_STUDY_DIR`，
   指针会被它覆盖——切换前先确认启动环境里没有这个变量。

   顺序有意义：**先 `activate` 新的，再 `supersede` 旧的**。反过来会出现一段
   无有效绑定的窗口（`active` 返回非零，夜跑回退到内置默认）。

### 3.4 规则收据（methodology_backtest）

重建后所有 v4 收据按 #42 认证门自动降为历史观察（#49 补的 `current_label_version` 让这一条
**真正生效**，此前只有「收据彼此版本不同」才切轮次）。四条种子规则按阶段重跑
`run/scan --stage discovery → validation → holdout`。旧收据留档不删。

## 4. 执行顺序（每步可停）

```
① 备份现有 v4 库为只读留档                          ← 无风险，可先做
② 重建共享库到 v5                                   ← 写共享库，最需要点头
③ 新协议 register（forward_start = max(重建日, 登记日) 的次个交易日）  ← 写用户态
④ 新协议 history 段在 v5 库上重跑（§3.3 第 3 条）    ← 写用户态，**不是**⑦的替代
⑤ activate 切绑定到新协议 → 核对                     ← 写指针，不做则夜跑仍跑旧协议
⑥ supersede 封存旧协议（含「待回检 = 0」）           ← 写用户态，有停用语义
⑦ 四条种子规则按阶段重跑                            ← 写收据目录（methodology_backtest）
```

① 不依赖 #49 是否合入；②③④⑤⑥⑦ 依赖。

两处排序理由，别再倒回去：

- 上一版把封存排在重建之前且标为「不依赖合入」。现在封存真的会停用旧协议，而新协议要等
  共享库重建完才能 `register`——先封存就会留出一段无活跃协议的空窗。
- ④（`method_validation history`）与⑦（`methodology_backtest run/scan`）是**两件事**：
  前者是本协议自己的历史演练读数，后者是规则收据。上一版只列了⑦，§3.3 要求的 history
  重跑就没有任何一步对应。

**所有命令都显式带 `--user <生产用户>`（或 `--root`），不要依赖当前 shell 恰好继承了对的
环境。** 指针只按目录名存放、按 root 拼回，跨根写入会被拒；但若操作时用错用户，写出来的
就是另一个用户的绑定——这正是 09-12 质检复现的 `USER_SCOPE` 反例。

### 4.1 切换后的逐项核对

下表每行都是**能直接粘贴执行**的命令。先设好这几个变量（`$PY` 必须显式给出：
仓库里的 `scripts/*.py` **没有执行位**，`./scripts/xxx.py` 会 permission denied）：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
MV="$PY $CODE_ROOT/scripts/method_validation.py"
MB="$PY $CODE_ROOT/scripts/methodology_backtest.py"
ROOT="$FORESIGHT_USERS_DIR/$U/method_validation"     # $U = 生产用户
OLD="$ROOT/<v3 协议 id>";  NEW="$ROOT/<v5 协议 id>"
LABELS_DB="$DATA_ROOT/db/history_labels.duckdb"
```

`--user` 有**两种互不相干的语义**，别混：

- `register` / `activate` / `supersede` / `active`：`--user`（或 `--root`）**选的是协议根目录**，
  决定读写哪个用户的协议与指针。切换类操作必须显式带，否则会落到 `users/default`。
- `capture` / `daily` / `recheck`：`--user` 只是 **checkpoint 台账的归属**，
  **不选协议**——协议一律由必填的 `--study-dir` 指定。
- `status` / `history` / `report`：**根本没有 `--user`**，只认 `--study-dir`
  （`status` 还不读库，见 §5，所以库版本不能拿它查）。

下表按这个事实给命令，别再写 `status --user`。

| 查什么 | 最早时点 | 命令 | 期望 |
|---|---|---|---|
| 库版本确实是 v5 | ② 后 | `$MB report --labels-db "$LABELS_DB"` | `label_version` 为 v5 |
| 新协议已登记 | ③ 后 | `$MV status --study-dir "$NEW"` | 出协议卡片，`forward_start` 符合预期 |
| history 已在 v5 上重跑 | ④ 后 | `$MV status --study-dir "$NEW"` | 有 history 段读数，且口径为 v5 |
| 指针指向新协议 | ⑤ 后 | `$MV active --user "$U"` | rc=0，`protocol_id` 为 v5 |
| 旧协议退出枚举 | ⑥ 后 | `$MV active --user "$U" --print-dir` 之外用 `list_studies(root)` | 默认结果不含 v3（⑥ 之前**本就应该**还在） |
| 旧协议拒绝新观察 | ⑥ 后 | `$MV capture --study-dir "$OLD" --labels-db "$LABELS_DB"` | 非零且提示**「协议已封存」**；**若报的是缺参数就不算数**——那说明没走到封存闸 |
| 夜跑**实际**选中 | 次个交易日 | `grep 'study=' "$LOG_DIR/method-validation-daily.log" \| tail -1` | study 为 v5 且写出 capture |

`active` 的退出码是三态：**0 有效 / 4 从未配置 / 3 配置过但失效**（含指针损坏、目标缺失、
协议加载失败、指向已封存）。「从未配置」刻意不用 1——Python 未捕获异常正好退 1，
两者混用就会把崩溃读成「没配过」而静默回退旧协议。

**`active` 只证明「这个用户的指针」，不等于夜跑的最终选择。** 夜跑取值优先级是
「显式 `METHOD_STUDY_DIR` > 指针 > 内置默认」，还叠加三个变量：`FORESIGHT_USER`
决定读哪个用户的指针，`FINANCE_CODE_ROOT` 决定跑哪棵树的代码，而那棵树的 CLI
**可能根本没有 `active` 子命令**（运行快照的 `scripts/` 不随 `deploy_workbench_runtime.sh`
更新，它只 rsync `intelligence/`）——那种情况下夜跑按「从未配置」走内置默认并在日志写明。
切换前先确认启动环境没有 `METHOD_STUDY_DIR`，并确认 `$CODE_ROOT` 的 CLI 认识 `active`：

```bash
$PY "$CODE_ROOT/scripts/method_validation.py" --help | grep -qE '[{,]active[,}]' \
  && echo "链切已完成" || echo "链切未做：夜跑会用内置默认协议"
```

最终确认只能看上表最后一行的日志。

### 4.2 暂停 / 恢复边界

- 停在①②之后：指针未动，夜跑继续跑旧协议。旧协议在 v5 库上会被版本门拦住（抛错而非误算），
  这是预期行为；要避免呆报错，就不要在②与⑤之间跨交易日停留。
- 回退：`activate --study-dir <旧目录>` 即可切回（前提是还没 `supersede`；
  已封存的协议会被 `activate` 拒绝，这是故意的——要真想回退得先显式撤销封存标记）。
- **删除指针文件 = 回到「从未配置」**，夜跑按内置默认继续。注意这只保证 shell 取到一个目录，
  不保证那个协议还能算：旧协议在 v5 库上仍会被版本门拒。**不要把它当成安全的回滚手段。**
- 指针「配置过但失效」（损坏 / 目标缺失 / 指向已封存）与「从未配置」不同：夜跑会
  **停掉方法日步并告警**，不会静默回退旧实验。要恢复就 `activate` 到有效协议。

### 4.3 执行 ⑤ 之前：运行快照里得真的有 `activate`

`activate` / `supersede` 是 `scripts/method_validation.py` 的子命令，而**运行快照的
`scripts/` 不由 `deploy_workbench_runtime.sh` 更新**——它只把 `intelligence/` rsync 进
已有快照；`install_eval_launchd.sh` 的安装清单也不含 `scripts/method_validation.py`
（跨会话质检实测）。合入本单不等于生产路径拿得到这两个子命令。

所以 ⑤ 之前要先链切：

```bash
git worktree add --detach ~/.finance-runtime/finance-workspace-<sha> <sha>   # 切新快照
# 换 CODE_ROOT 符号链接指向新快照
$PY "$CODE_ROOT/scripts/method_validation.py" --help | grep -qE '[{,]activate[,}]' \
  && echo "链切已完成" || echo "链切未做"
```

两点别踩：**脚本没有执行位**，必须显式给解释器（`./scripts/xxx.py` 会 permission denied）；
探针看**顶层 `--help` 的子命令列表**。旧 CLI 上 `activate --help` 确实也会非零
（argparse 先校验子命令，`invalid choice` → exit 2），拿它当探针能用；但**别按
「argparse 优先处理 --help、两边都返 0」那套理由去理解**——那是错的，本文档与夜跑注释
里一度写过这句，已更正（09-12 跨会话质检对真实旧快照实跑：`active --help` 与
`activate --help` 均为 exit 2）。顶层 `--help` 的好处是它不依赖这条微妙规则。

验的是 `$CODE_ROOT` 那条路径，不是当前工作树——夜跑用的是前者。

## 5. 要补的门（本方案未实现，另立单）

1. **`status` 显式打印口径对照**：现在版本不匹配只在**执行**时抛 `ValueError`，
   `status` 读收据不查库，看不出来。应打印「协议口径 vs 当前库口径」，不一致时标明
   「新的 capture 已停」。#671 升 v4 至今无人发现，就是因为没有这一行。
2. **协议注册时记录「口径可用窗口」**：协议冻结库的**绝对路径**（`_check_sources` 据此判定），
   库一搬家就永久失配。改为记录库的身份（`label_version` + 内容指纹）而非路径，
   才谈得上"把旧库挪到归档目录还能复算"。本单不改——它会动到已冻结观察的语义。
