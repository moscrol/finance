# feat/sandbox-derived-calculation

## 这个分支做什么
工单 #41：`derived_calculation` 落地（母稿 capability-amplification §3.4，验收 §5 第 16–18 条）。模型写一段 Python，在两层沙箱里对本回合已绑定证据做计算 / 口径核对，产物带 `input_evidence_hashes` + 原样脚本 + 输入最旧的 `as_of`。基线 `f90af450`。**能力扩张不是修复**，不改冻结题集读数。

## 决策与被否方案
全部取舍在工单 #41 原文（INDEX 有路径），这里只留两条会被改错的：
- **两层隔离**：进程守卫（`-s -B -P`、从零 env、prelude 换 socket / 拦 import / 只许写工作目录 / 拒 fork·exec、rlimit、墙钟）永远开；有 `sandbox-exec` 再叠 Seatbelt，`enforcement` 记档。否：只 Seatbelt（macOS-only、离线测不了）、只子进程（ctypes 可绕）。
- `input_evidence_hashes` = 本回合**全部**已绑定证据（母稿原文），不做实读遥测；派生身份走 `evidence_tier` + `derived_from`，不占 output_id。

## 当前状态
**PR #682 已开**，等用户确认合入。树干净；`conflict-check` 对 `gitea/main` clean，与 #684（P4）`merge-tree` 无冲突。

## 已验证
- 干净树全量 8338P / 0F（收据 `…T161253Z-dc85e602` = 本次文档提交的父，其后只有文档提交），新增 32 条。
- 端到端（§5 第 18 条）两源 1741.44 / 1740.0 → `diff=1.44`、`consistent=false`、`as_of=2025-04-03`，结论绑 E1/E2/E3 被 `admit_finish` 接受。
- 变异：门关掉 → 1 红；`as_of` 取最新 → 3 红；prelude 守卫整段关 → 4 红。**注意**：只删 `create_connection` 或 `socket.socket` 不红——先走 `getaddrinfo`，三处都拦，是纵深不是假门。

## 未验证 · 已知边界
- E 号按账本序编，账本跳过晚于截止日的证据而模型视图不跳，极少数错一位（`input_refs` + 哈希可对账）。
- DuckDB 挂生产库只读连接 + 指纹，非快照拷贝；库不存在回 `sandbox_unavailable`。
- Linux 生产落 `enforcement=process`（无 Seatbelt）。
- **没有 live 探针**：真模型写不写得出能 emit 的脚本、契约文案够不够，要一次 live 才知道（烧配额，等一句「跑」）。
- 没另冻计算类题集；`HarnessReferenceLoop` 无此工具，无 CLI / Workbench 入口。

## 下一步
- 用户确认后合入 #682；与 #684 谁后合谁前向合并一次。
- 随下次 8792 切流带上，看第一次真调用的 `tool_result`。
- live 探针一次：茅台年报 vs 网页净利润口径核对题。
- 若要实读遥测：`EVIDENCE` 换成记下标的 list 子类，加 `evidence_read_refs`。

## 踩过的坑
- 变异后 `cp` 还原同大小同秒 → 沿用变异版 `.pyc`；`rm __pycache__/<模块>*.pyc && touch`。
- 死循环被 `RLIMIT_CPU` 先杀（`SIGXCPU`，exit −24），墙钟超时还没到；归 `timed_out`，否则会读成脚本崩。
- Seatbelt profile 路径要 realpath：`/var/folders/...` 实为 `/private/var/folders/...`，写错一层整条 allow 失效。
