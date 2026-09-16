# fix/audit-followup-0916

## 这个分支做什么
E-008 审计补漏：研究过程 UI 投影模型请求前的**实际工具菜单**（`tool_menu.visible`），授权 / 调用 / 取回资料 / 服务可用分列。同轮订正 E-009 工作清单 W1–W6 状态、把 C 线证据汇成失效模式清单。单提交 `ef1d56f5`，PR #760。

## 决策与被否方案
| 选了 | 否了 | 为什么 |
|---|---|---|
| 读请求前 `tool_menu.visible` | 投影 `configure.allowed_capabilities`；UI 重算权限表 | configure 早于子研究动态装配；授权只是上限；第二份表会漂 |
| 每个开放工具的模型步都落 `tool_menu` | 只在藏工具时落 | 无裁剪轮没记录，分不清「没工具」与「没记」；代价是放弃「无裁剪轮事件流不变」 |
| 公开边界封闭语法（固定句 ∪ 前缀+闭集标签+后缀） | 只验前缀；枚举子集 | 前缀会带出私有工具名（变异证实）；子集指数级 |
| 收口步 `definitions=[]` | 照算菜单 | 不给模型的工具不能记成可调用 |
| 进研究过程，不进 `session_projection` | 塞进金融答案 | 那是纯函数终局出口 |

## 当前状态
代码 `ef1d56f5` + 交接 `cdb20071`（本文）已推 gitea，PR #760 开着，基线 main=32bff514、落后 0。**未合、未部署**（8792 跑 6e23dd57）。树干净。

## 下一步
1. 用户确认后合并；先重探 `git merge-tree --write-tree gitea/main fix/audit-followup-0916`。
2. 部署后用一条真实问题看研究过程是否出现「此步模型可调用工具：…」。
3. E-008 §5 候选、W3 阈值、W4 暂停 B 线待用户裁决，本分支不动。

## 踩过的坑
- 桩内 `AssertionError` 被运行器吞成 `status=failed`，像「模型不可用」；先捕获请求时事件，退出运行器后再断言。
- worktree 里 e2e webServer 会拿宿主 python3.14（无 uvicorn）；venv 进 PATH。
- zsh 不分词：`cmd $sub` 把 `backfill-tables --check` 整串喂 argparse，假红。
- 首次全量在 69% 中断，留下零计数收据 `063317Z`，别当证据。

## 未验证 / 已知边界
- 无真实模型回归；无「菜单句出现在页面」的 e2e，只有组件测试与 trace/SSE 重放。
- 13:29 e2e 一次 1F（desktop 研究进化绑定），后两次 31P/2S，n=1 不定性。
- 不含 provider_status / 网关修复；旧 run 显示「未记录」不反推授权。

## 已验证
四叶全绿 @ef1d56f5：pytest 10961P/0F/83S/2xf（收据 `20260916T064327Z-ef1d56f5.json` 可采信）、ruff、前端 lint/typecheck/vitest 95/build、e2e 31P/2S、registry 4/4。变异：删落账 2 红，放宽语法 3 红。展开 `docs/handoffs/2026-09-16-audit-followup-tool-menu.md`。
