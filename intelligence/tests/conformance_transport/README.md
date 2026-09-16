# LLM transport 缝契约符合性套件

缝：`llm_refine.complete()` 的返回契约 `(content, provider, reason)` × 两个
独立演化的传输实现——HTTP OpenAI-compatible（`_post_chat`，urllib）与 CLI
judge（`grok_cli_judge.complete_grok_cli`，子进程）。**按 transport 参数化，
禁按厂商名**：`_PROVIDERS` 8 槽共用 HTTP 路径，是配置不是实现（缝普查定性）。

来源工单：`docs/superpowers/specs/2026-08-29-llm-transport-conformance-workorder.md`
（缝普查 P1 #1）；机制复用三件结构。

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/conformance_transport/ -q
```

首轮读数（2026-08-29）：`21 passed`，baseline 为空。

## 三件

| 文件 | 是什么 |
|---|---|
| `transports.py` | 参数表（http/cli）+ 声明表（两路已声明偏差入 notes）+ 探针替身与标准驱动 |
| `baseline.py` | 棘轮 baseline（首轮为空） |
| `test_lt1..lt5_*.py` + `test_declarations.py` | 每不变量一文件，`parametrize(TRANSPORT_NAMES)` 逐路跑 |

## 不变量 → 断言落点

| # | 不变量 | 断言落点 |
|---|---|---|
| LT-1 | 成功三元组：(非空内容, 生效 provider, **空串** reason)，恰一次传输调用 | 逐路成功场景 |
| LT-2 | 失败词表可分类：HTTP 带状态码、CLI 由**异常类名**承载种类（空响应≠非零退出），无堆栈 | 逐路真实失败形状 + CLI 双故障区分 |
| LT-3 | 超时不越窗：传输边界收到的窗口 ≤ 请求窗口；CLI 的 max(1.0,·) 地板钉成显式契约 | 逐路 + 亚秒窗双向 |
| LT-4 | 预算在副作用前预占：超额拒发零传输触碰、拒发计数、成功恰耗一格 | 逐路 × max_calls∈{0,1} |
| LT-5 | 凭证不入痕：key 不进 reason/台账 summary/provider repr（repr=False 钉住） | 逐路 × 成败两态 |

## 替身边界（零网络）

HTTP 路只替换最外层 `urlopen`（headers/payload/timeout 组装走 `_post_chat`
原码）；CLI 路走 `complete_grok_cli` 官方 `runner=` 注入缝包一层转发（argv
组装/提示词落盘/stdout 提取走原码）——**不能** patch
`grok_cli_judge.subprocess.run`：`runner=subprocess.run` 默认参数在函数定义
时已绑定真身，事后改模块属性打不进去（首跑实测 FileNotFoundError 现场）。
provider 注入走官方 `provider_override` ContextVar，不碰 env 键。

## 与既有测试的分工（不重复）

`test_llm_provider_fallback.py` 管 `detect_providers` 的厂商槽解析次序；
`test_grok_cli_judge.py` 管 CLI 侧 argv/env/提取的细节矩阵。本套件只钉
`complete()` 跨传输的**统一返回契约**。

## 怎么加新传输

新增 transport 后：`TRANSPORT_NAMES` 加名、`make_provider`/`install_transport`
补构造与替身、`FAILURE_CASES` 补该路真实失败形状与 reason 投影、
`TRANSPORT_NOTES` 写形状差异。新路必须全绿。
