# feat/adaptive-research-loop 在途

## 这个分支做什么
#72 / PR #868：传输层绝对截止。#75 双轴独审已闭合；#76 L6 自然验收待用户批准。WIP，未合 main。

## 决策与被否方案
- 受审候选固定；文档提交和前向都不继承候选收据；旧失败不续跑、不翻案；0.8s+0.2s 和检索 120s 的判据不放宽。
- `complete` 由控制器写入（#906 已并入）；审查者内容里出现身份字段或 `complete`，一律拒收。
- 09-25 定为只合 #868（A 路）：独审证据在 `f2610293f` 上已经齐了。#910 / #911 在 Pi 会话 `01a0d35f` 的组合树 `fb41cebda` 上，另走审查，#868 合入后改指 main。否掉的 B 路：组合树整体重审（约 78 次），会把未经独审的 #911 拉进同一次合并。
- 背景：`../2026-09-25-c3-c6-review-closeout.md`

## 当前状态
- 独审（`f2610293f`）：spec 轴 C1–C7 全部独立验证，零发现（C3 由批 c3 验证，累计 333/354）；quality 轴 PASS_WITH_LIMITS（批 next）。
- 本分支 = `f2610293f` + 纯文档 + 前向 main `55db731a6`（`ce60a6b0c`：INDEX 按行解，docstring 取并集）+ 本提交（删 #906 带进来的在途文件）。前向带入 #920：`llm_refine.py` 的 5 个 `_post_chat*` 调用点加了 `_apply_compat_payload`，与本分支的截止改动自动合并。
- 前向后的四叶与 #920 调用点作者复核在本提交之后跑，收据绑定本 head，位置 `~/.finance-runtime/reviews/pr868-fwd-20260925/`。

## 未验证 / 已知边界
- L6 未跑，自然验收仍是 NOT_PASSED。
- 旧 c315 的 RAG keepalive 失败根因未定。
- spec 轴的非阻塞观察：流式调用点在截止或取消时，抛出的异常类型各次运行不一致（`LLMStreamCancelled` / `LLMStreamAlreadyEmitted`）。截止本身生效。

## 下一步
1. 四叶绿 + 调用点复核通过后，快进推到本分支。
2. 用户批准后新建 L6 根：≤ 3 题，每题精确 Episode 审计 PASS 才出下一题。
3. L6 通过后合 main（等用户确认）。合并时 main 如果有代码前进，要再前向并重跑四叶。

## 踩过的坑
完成标志不要让模型负责；探针路径要在工具里当场核验；沙箱里 conftest 找解释器会调 git，工具环境要设 `FWP_WORKBENCH_PYTHON`。
