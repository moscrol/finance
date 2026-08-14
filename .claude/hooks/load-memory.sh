#!/usr/bin/env bash
# SessionStart hook：注入记忆底座（用户偏好 + 项目笔记的**开工必读段**）。
# 在 Mac 本机经软链 .agent-memory 读取；软链不在则回退绝对路径。
#
# ## 2026-08-10 收窄：189,184 → 预算内
#
# 收窄前实测（这是收窄的全部依据，不是感觉）：
#
#     preferences.md                     3,851 字符
#     20_projects/<repo>.md            181,939 字符  ← 其中「交接记录」134,510（74%）
#     git status --short                    44 行（全树，含 ingest 产物）
#     ────────────────────────────────────────────
#     合计                             189,184 字符
#
# 对照族 B 马书 ch19 §19.6（claudemd.ts:93）：`MAX_MEMORY_CHARACTER_COUNT = 40000`
# **是警告阈值而非硬拦截**——「系统会提示用户，但不会阻止加载。实际上限受制于
# 整个系统提示词的 token 预算，过大的 CLAUDE.md 会挤压其他上下文空间。」
#
# 189K 字符约 60-90K token，每个会话开头就消耗掉。而它挤掉的正是 agent 干活的
# 预算——更讽刺的是：**收窄前它没有注入最要紧的那条事实（用哪个解释器）**，
# 那条错误在 2026-08-10 让一个 agent 连续二十多次跑出错误读数（71 vs 14 failed）。
# 解释器/树/上次读数现由 scripts/session_facts.sh 探测注入。
#
# ## 三处收窄，各有判据
#
# 1. **项目笔记只注入开工必读段**。「交接记录」是历史流水（74%），开工不需要，
#    需要时可 Read 全文。同章对「随使用膨胀的内容」（AutoMem/TeamMem）的处置
#    就是主动截断行数与字节，不是任其增长。
# 2. **git status 收窄到代码路径**。本仓工作区长期有 40+ 个脏文件（复盘台账、
#    market_feature_store/exports、复盘/ 下 HTML），全是每日 ingest 的正常产物；
#    整块注入会把真信号（我改了哪些代码）埋掉。判据前缀与 test-environment.json
#    的 code_path_prefixes 同源。
# 3. **超预算主动截断并声明**。静默截断会让 agent 以为看到了全部。
#
# 预算 12000 是本仓自己的取舍，不抄那个 40000——INDEX 已把 40000 标为
# 「不可搬运量纲」：用它的机制，不抄它的数字。preferences.md 全文必须进
# （教学模式与红线要全程遵守），余量留给项目笔记的必读段。
#
# 退出码恒 0：观测设施故障不该阻断会话。

set -uo pipefail

V=".agent-memory"
[ -d "$V" ] || V="$HOME/agent-memory"
[ -d "$V" ] || exit 0   # vault 不可达（如在别的机器）就静默退出，不打扰

BUDGET=12000
# 预算要为**尾部固定段**（Git 现状 + 回写约定 + 头部横幅）预留额度。
# 初版只对 preferences 与项目笔记累加 `used`，尾部两段完全不计入——于是总输出
# 13,298 字节稳定超出 12,000 预算，而脚本自己认为还在预算内。
# 「预算不约束的部分」等于没有预算：这是本轮第三次撞见同一形状（收据 dirty 判据
# 按全树算、门禁基线掺入假阳性、这里漏算尾部），都属「量具自己没被校准」。
# RESERVED 从 900 提到 1000：实测尾部两段（Git 现状 + 回写约定 + 在途交接标题）
# 在「有未提交代码改动」时约 940 字节，900 不够导致总量 12,034 > 12,000。
# 预留量必须按**最坏情况**取，不是按当前观测值——git status 的行数会变。
RESERVED=1000
used=0

# 横幅先存进变量再算长度，不写死常量：文案一改，手写的 320 立刻失真而没有任何
# 报错（「手写清单必漂」同一形状，本轮第三次）。让长度由内容自己算出来。
banner="# 记忆底座（SessionStart 自动注入）
> 用户长期偏好与项目要点，请全程严格遵守（尤其教学模式：讲原理 + 技术选型/替代方案对比 + 标注可复用知识点；中文）。
> 工作区事实（哪棵树/哪个解释器/上次读数）由 scripts/session_facts.sh 另行注入。"
printf '%s\n\n' "$banner"
used=$((used + $(printf '%s\n\n' "$banner" | wc -c | tr -d ' ')))

# ── 用户偏好：全文注入（教学模式与红线必须全程可见）────────────────────
if [ -f "$V/30_conventions/preferences.md" ]; then
  echo "## 用户偏好 (preferences.md)"
  cat "$V/30_conventions/preferences.md"
  echo
  used=$((used + $(wc -c < "$V/30_conventions/preferences.md" | tr -d ' ')))
fi

# ── 项目笔记：只注入开工必读段，跳过历史流水 ──────────────────────────
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$repo_root" ] || repo_root="$(pwd)"
remote="$(git -C "$repo_root" remote get-url origin 2>/dev/null || true)"
if [ -n "${remote:-}" ]; then repo="$(basename "${remote%.git}")"; else repo="$(basename "$repo_root")"; fi
note="$V/20_projects/$repo.md"

# ── 尾部固定段：先生成到变量，用**实测长度**做预留，不写死 RESERVED ──────
# 原来写 RESERVED=1000（估的），是「手写常量必漂」同一形状——本轮已在横幅那处
# 修过一次（320 → 由内容自算），这里当时只修了一半。git status 行数一变，估值
# 立刻失真且无任何报错：预留太小则总量超预算，太大则白扔额度。
#
# 顺序上尾部排在最后，但预留值必须在**截断项目笔记之前**就知道，
# 所以这里先把它整段算出来存着，最后再打印。
# 这个「先量后裁、最后输出」的次序，就是上一处 bug（先写「未提交」再提交，
# 文档当场失效）的反面：**凡是要用到某个量，就必须在用它之前把它测准。**
build_tail() {
  echo "## Git 现状（开工先看）"
  br="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "当前分支：${br:-?}"
  all_n="$(git status --porcelain 2>/dev/null | grep -c . || true)"
  code="$(git status --porcelain 2>/dev/null \
    | sed 's/^...//' | sed 's/^"//;s/"$//' | sed 's/.* -> //' \
    | grep -E '^(intelligence/|evolution/|market_feature_store/|scripts/|tests/|conftest\.py|pytest\.ini|ruff\.toml|test-environment\.json|requirements-consumer\.lock)' \
    | grep -v '^market_feature_store/exports/' || true)"
  code_n="$(printf '%s' "$code" | grep -c . || true)"
  if [ "${code_n:-0}" -gt 0 ]; then
    echo "未提交的**代码**改动 ${code_n} 个（全树另有 $((all_n - code_n)) 个 ingest 数据产物，与被测行为无关）："
    echo '```'
    printf '%s\n' "$code" | head -15
    [ "$code_n" -gt 15 ] && echo "…另 $((code_n - 15)) 个"
    echo '```'
  else
    echo "无未提交代码改动（全树 ${all_n} 个脏文件均为 ingest 数据产物）"
  fi
  echo "Git 约定：大任务开分支；合并 main 必须等确认，不强推。"
  echo
  echo "## 回写约定"
  echo "完工后按 $V/40_playbooks/devin-writeback.md 分层沉淀：项目级决策写 $V/20_projects/$repo.md（**只写一行索引**，正文进 docs/handoffs/inflight/<分支>.md）；稳定方法论写 $V/10_knowledge/；单次纠偏/评分样本写项目学习层。"
  echo "在途交接：完工前覆写 docs/handoffs/inflight/<当前分支，/ 换 ->.md，SessionStart 会自动注入给下一个 agent。**在动作完成之后写**，否则注入的是假状态。"
}
tail_part="$(build_tail)"
tail_bytes="$(printf '%s\n' "$tail_part" | wc -c | tr -d ' ')"

# 切点：`## 交接记录` 之前的全部内容 = 开工必读（概述/导览/数据流/环境要求/
# 关键约定/任务看板/用户决策线路）；它之后是交接流水与逐条 PR 记录，需要时
# Read 全文即可。
#
# 用 sed 按**标题**切，不按行号：行号会随笔记增长漂移（能力图谱里那条
# 「数数别用固定行号」同一形状）。
#
# 初版用 awk 传两个正则做 KEEP/SKIP 判定，**实测退出码 2（语法错误）**：
# macOS 自带 BSD awk 不支持 `[0-9]{4}` 这类区间量词。后果不是报错而是静默失真
# ——`section` 为空、`if [ -n ]` 跳过，注入里一个字的项目笔记都没有，而总字符数
# 看起来正常（12,425，全来自 preferences 与 git 段）。这正是「静默降级只能靠
# 内容比对抓到，计数检查永远发现不了」的又一例。
# 截断必须按**行**，不能按字节。初版用 `head -c $remain`：多字节中文被切成半个
# 字符，产出**非法 UTF-8**。后果远超「末尾一个乱码字」——下游所有文本工具都会把
# 输出当二进制：`grep -c "Git 现状"` 返 0（看起来像那一段根本没输出）、`cut` 报
# Illegal byte sequence、`rg` 直接跳过整个文件。排查时我据此误判成「脚本提前
# 退出了」，实际是**测量工具被自己污染的输出骗了**。
# 按行切则永远落在字符边界上，且 markdown 本就不该切在行中间。
#
# awk 在 LC_ALL=C 下 length() 按字节计——与字节预算同口径。混用 `${#var}`（字符数）
# 和 `wc -c`（字节数）会让截断判定本身失准，那是初版的第二个隐患。
# 「任务看板」在必读段里占 6,078 字节（必读段共 17,397），因为每条任务后面都跟着
# 几百字的历史排查细节（`[实测 2026-08-05] …` 那些）。开工需要知道「有哪些任务、
# 什么状态」，不需要当时怎么排查的。所以对该段做**行级摘要**：只留表格的前若干行
# （标题行 + 分隔行 + 前几条），其余折叠成一句提示。
#
# 为什么不是直接砍字节：那会把 markdown 表格切成半截，注入一堆残缺的 `| … |`。
# 按行裁并保留表头，注入的仍是合法表格。
BOARD_ROWS=8

if [ -f "$note" ]; then
  # 取到「## 交接记录」为止，再删掉那一行本身；文件里没有该标题时退回全文。
  head_part="$(sed -n '1,/^## 交接记录/p' "$note" 2>/dev/null | sed '$d')"
  [ -n "$head_part" ] || head_part="$(cat "$note" 2>/dev/null)"
  full_bytes="$(printf '%s' "$head_part" | wc -c | tr -d ' ')"
  # 折叠任务看板：进入该段后只放行前 BOARD_ROWS 行，之后到下一个 ## 为止全部跳过。
  # 匹配用 `任.*板` 而不是 `任务看板`：笔记里的标题实际是 `## 任**务**看**板**`
  # ——中文字符之间夹着 markdown 粗体标记。用 od -c 才看出来，肉眼读渲染后的
  # 文本完全看不出区别，而 awk 匹配的是原始字节。
  # 这类「看起来对、匹配不上」的正则失败没有报错，只是静默不生效（折叠一行没生，
  # 字节数一字不变），必须靠内容比对而非退出码来发现。
  head_part="$(printf '%s\n' "$head_part" | LC_ALL=C awk -v keep="$BOARD_ROWS" '
    /^## / { inboard = ($0 ~ /任.*板/); n = 0 }
    {
      if (!inboard) { print; next }
      n++
      if (n <= keep) { print; next }
      if (n == keep + 1) print "> …看板其余条目已折叠（含历史排查细节）。需要全部任务时 Read 笔记全文。"
    }
  ')"
  # 减去 RESERVED：尾部「Git 现状」「回写约定」两段是固定要输出的，必须先占位，
  # 否则项目笔记会吃满预算、尾部再无条件追加，总量必然超支（实测 13,298 > 12,000）。
  remain=$((BUDGET - used - RESERVED))
  [ "$remain" -gt 0 ] || remain=0
  section="$(printf '%s\n' "$head_part" | LC_ALL=C awk -v lim="$remain" '
    { n += length($0) + 1; if (n > lim) exit; print }
  ')"
  if [ -n "$section" ]; then
    total="$(wc -c < "$note" | tr -d ' ')"
    kept="$(printf '%s' "$section" | wc -c | tr -d ' ')"
    echo "## 本项目笔记 ($repo) — 开工必读段"
    printf '%s\n' "$section"
    echo
    # 变量放在行尾且后接中文标点时，用 ${var} 花括号形式显式界定边界。
    # 初版写 `Read $note。**` —— 中文句号加 markdown 星号跟在 $note 后面，
    # shell 报 `line 107: note` 并**终止脚本**，于是后面「Git 现状」「回写约定」
    # 两段一个字都没输出、退出码 1。而前面已输出 8K 内容，看起来只是「少了两段」。
    # 我为此错判了两次根因（先猜 SIGPIPE，再猜算术溢出）——因为同一版还带着
    # 非法 UTF-8，把 grep/cut 全污染了，测量工具本身在骗人。
    if [ "$kept" -lt "$full_bytes" ]; then
      echo "> 必读段被预算截断（注入 ${kept} / 必读段 ${full_bytes} / 全文 ${total} 字节）。缺的部分请 Read ${note}"
    else
      echo "> 以上为必读段全文（${kept} / 全文 ${total} 字节）。交接记录等历史流水未注入，需要时请 Read ${note}"
    fi
    echo
    used=$((used + kept))
  fi
fi

# ── 尾部固定段：打印前面已量过的那一份 ─────────────────────────────────
# 内容在 build_tail() 里（第 ~90 行），此处只输出。**不要在这里重新生成**：
# 那会让「量到的」和「打印的」是两次不同的 git status 结果，预留值随之失准。
# 一份内容只算一次、只有一处定义，是本轮反复出现的同一条纪律。
printf '%s\n' "$tail_part"
exit 0
