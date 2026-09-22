# feat/adaptive-research-loop 在途

## 这个分支做什么

研究回路取证、窗口收益、公开保真 + LLM 传输层绝对截止（`f514e6713`）。#72 收口接手：独立复核、补用例、前向 main、四叶、开 PR。#76/#75 条件卡与全部读数在 `docs/verification/2026-09-22-adaptive-deadline/README.md`。

## 决策与被否方案

- 验收变异（`deadline=` 不传）376 条全绿 → 判「无人守」补包装层用例；否了「作者四杀已够」：那四条只变传输层模块，包装函数没进过。
- 前向 `--no-ff` 合 main 在作者树做（分支已由工单移交，22:37 起无进程）；否了推 detached 提交：本地分支会与远端分叉。
- INDEX #72 行不改；否了写 #858 分支：它 23:22 仍在动。行文本放 PR 描述末尾。
- `is_cancelled=` 转发变异也存活但不补代码；否了再加一测：不在验收项，且会让门禁过的代码尖再漂一层。配方在 README。
- 预算 T900/75/150、`derived_calculation` 关、数字门单位（#852）均未动。

## 当前状态

代码尖 `013eb5c4a`（`c582d6755` + main@f24a61a8a 合流），其上只有 docs 提交。未 push、未开 PR、未合 main、未部署、未碰 8792。作者树与隔离树 `~/fwp-wt-adaptive-deadline-0922` 均干净。

## 已验证

隔离树 @`013eb5c4a`：ruff 0；pytest **12879P/85S/2X exit 0**（2030 s，load 9→17），收据 `check_test_receipt --expect-revision` ✅；前端六步 0（110 单测、E2E 34P/2S）；registry×4 + crosswalk 0；严格探针 0 越窗（`aa0509d61` 亦独立跑过一次）。变异 `deadline=None`：新用例 RED → 还原 GREEN，sha256 核对。收据根 `~/.finance-runtime/adaptive-deadline-0922/`。

## 未验证 / 已知边界

真实模型改稿复核（#76 L6）未跑；两位终审（#75）未做；`absence-live` 三个内容未过项仍成立。`is_cancelled=` 转发无人守（15 条 cancel 测试在变异下全绿）。四处调用点 `timeout` 片是否都经 `Deadline.slice()` 未逐点核。spawn 代价 0.15–0.35 s 计入预算，load>20 勿跑亚秒窗口。

## 下一步

1 push + 开 PR（base main），`gitea_pr.py conflict-check` 先跑；2 挂 #75 QUEUE 行；3 用户确认后合；4 #76 三题；5 内容层三项；6 可选补 `is_cancelled` 用例。

## 踩过的坑

`--basetemp=X/Y` 前先 `mkdir -p X`，否则 tmp_path 夹具在 setup 抛 FileNotFoundError 伪红。zsh 里无匹配的 glob 会让 `&&` 链整条中断。别人的全量 pytest 会把 13 分钟拖成 34 分钟，读数成立但不读快慢。
