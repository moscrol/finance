# feat/sandbox-derived-calculation

## 这个分支做什么
工单 #41：沙箱按 `derived_calculation` 落地（母稿 capability-amplification §3.4，验收 §5 第 16–18 条）。模型写一段 Python，在两层沙箱里对本回合已绑定证据做计算 / 跨源口径核对，产物带 `input_evidence_hashes` + 原样脚本 + 继承自输入最旧的 `as_of`。基线 `f90af450`（P0–P3 运行底座已合）。**能力扩张不是修复**：不改任何冻结题集读数。

## 决策与被否方案
- **两层隔离**：进程层守卫（独立解释器 `-s -B -P`、从零 env、prelude 换掉 socket / 拦 import / 写只许工作目录 / 拒 fork·exec、rlimit、墙钟）永远开；macOS 有 `/usr/bin/sandbox-exec` 时叠 Seatbelt deny-list（`deny network*` / `process-fork` / `file-write*` 只放工作目录）。产物 `enforcement` 记档。否：只 Seatbelt——macOS-only、deprecated、allow-list 调不通、离线测不了；只子进程——Python 守卫可被 ctypes 绕过。也否 bwrap / Docker / gVisor / WASM / 托管 code interpreter（见工单）。
- `input_evidence_hashes` = 本回合**全部**已绑定证据（母稿原文），不做「脚本实际读过哪几条」的遥测。否：按访问追踪——prelude 复杂化，且母稿定义就是整批。
- `produces={supporting_evidence}` 而非 `derived_calculation`：`test_produces_only_contains_known_output_ids` 规定 output_id ≠ 工具名；派生身份走 `evidence_tier` + `AgentEvidence.derived_from`。
- 授权从 `financial_data` 派生（同 `web_fetch` ← `web_search`），不进 20 条策略表。否：加进每条策略——占槽，纯盘面题没有可算输入。
- 绑定点：`_with_sub_research_tool` 改名 `_with_episode_bound_tools`，先绑派生计算再绑子研究；`run()` 只改那一行调用名。否：装配层绑——`build_episode_registry` 拿不到账本；contextvar / 全局——两个 loop 并跑会串。
- 禁用模块在 runner 里回结构化码，不在参数解析拒。否：参数拒——按 invalid_action 计数，模型改脚本就能过的事不该算写错参数。
- `derived_without_inputs` 归 INTEGRITY（与伪造哈希同族）。

## 当前状态
代码 + 测试 + 文档全落在本分支；`docs/runtime/tools.md` 重生成（15 个工具，`--check` 一致）；开关板两份 fixture 各加一行；`UBIQUITOUS_LANGUAGE.md` 加「派生计算」；INDEX 加 #41 行；母稿 §3.4 落地回写。等用户确认合入。

## 已验证
- 新增 32 条：`test_calculation_sandbox.py` 15（含 3 条 Seatbelt-only，非 macOS 跳过）+ `test_derived_calculation.py` 17。
- 变异：门关掉 → 1 红；`as_of` 取最新 → 3 红；prelude 守卫整段关掉 → 4 红（网络 / import / 起进程 / 越界写）。**注意**：只删 `create_connection` 或只删 `socket.socket` 的变异不红——`create_connection` 先走 `getaddrinfo`，三处都拦着，是纵深不是假门。
- Seatbelt 单独一层（Python 守卫关掉）：connect / 越界写 / `os.fork` 全部 `PermissionError`；工作目录内可写；DuckDB 只读 `insert` 抛 `InvalidInputException`。
- 端到端（§5 第 18 条）：`ContinuousAgentEpisode` + 脚本化模型，两源 1741.44 / 1740.0 → `diff=1.44`、`consistent=false`、`as_of=2025-04-03`、`derived_from` == 两条输入哈希、结论绑 E1/E2/E3 被 `admit_finish` 接受；严格派生（INV-R1）全程开。
- 全量门禁读数见 PR 正文（跑于本干净树）。

## 未验证 · 已知边界
- E 号按证据账本序编；账本跳过晚于截止日的证据、模型视图不跳，极少数情形错一位（脚本还有 hash / tool / observations 可选，产物 `input_refs` + 哈希可对账）。
- DuckDB 挂的是生产库只读连接 + 路径/大小/mtime 指纹，不是快照拷贝；`use_duckdb=true` 在库不存在时回 `sandbox_unavailable`。
- Linux 生产会落 `enforcement=process`（无 Seatbelt）。
- 没有 live 探针：真模型会不会写出能 emit 的脚本、契约文案够不够，要一次 live 才知道（烧配额，等一句「跑」）。
- 没另冻计算类题集；`HarnessReferenceLoop` 没有此工具；无 CLI / Workbench 入口。

## 下一步
- 用户确认后合入；随下次 8792 切流带上（零 live 判据改动，但新增了一个模型可见工具——切流后看第一次真调用的 `tool_result`）。
- live 探针一次：茅台年报 vs 网页净利润的口径核对题。
- 若要「实际读过哪几条」：prelude 里把 `EVIDENCE` 换成记录访问下标的 list 子类，结果里加 `evidence_read_refs`。

## 踩过的坑
- 变异实验后用 `cp` 还原源码：文件大小相同、mtime 同一秒 → Python 沿用变异版 `.pyc`，测试「莫名」红。还原后 `rm __pycache__/<模块>*.pyc && touch <文件>` 或改动后等一秒再跑。
- 死循环脚本被 `RLIMIT_CPU` 先杀（`SIGXCPU`，exit −24），墙钟超时还没到；把它归为 `timed_out`，否则会被读成脚本崩。
- Seatbelt profile 里路径要 realpath：`/var/folders/...` 实为 `/private/var/folders/...`，写错一层整条 allow 失效。
