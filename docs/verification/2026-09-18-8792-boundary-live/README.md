# 3faf64fb：隔离真实 Workbench 会话验收

**结论：整体验收未通过，禁止据此推进部署。** 四次预注册首条消息、零重发：3 次 completed 有正文，1 次 failed。边界局部有效不等于完整研究任务合格。

- 被验代码：`3faf64fbadcfe45fdd0b306acd223d9e78c56525`；独立 detached 树、端口 8828。
- 原件 **R**：`~/.finance-runtime/reviews/8792-boundary-live-20260918/`，含四个独立测试用户，金融原文/私有上下文不提交 Git。
- 本轮走真正的建会话→发消息→run→指定 assistant 消息 HTTP 合同；不是浏览器点击或 CLI ask 验收。
- 主 writer：结构化回执 `glm-5.3-flash`；semantic judge `llm`、evidence `auto`，沿用生产未改。
- 8828 已停止、自己的锁已移除，R 全部保留。生产 8792 前后仍 bf662e9310ff、healthy、加载指纹/用户根/agent_runtime 一致。
- [决策、失败史与下一步](../../handoffs/2026-09-18-8792-boundary-live-acceptance.md)；[在途交接](../../handoffs/inflight/fix-8792-boundary-integration.md)；[机器索引](results.json)。

## 结果分层

| 样本 | 真实终态 | 目标边界 | 未通过/未签收部分 |
|---|---|---|---|
| F1 拒登记 | completed | 研究保留，无 checkpoint/judgment | 数字门删无依据阈值后，清单缺触发条件 |
| F3 格式化财务 | failed | 主体和 financial_analysis 路由保留 | `mappingproxy` JSON 序列化中断；非空失败存根不算答案 |
| F2 日期与引用 | completed，report partial | 2026-10-21 计划及 E45/E43 保留，E43 source_date=2026-08-22 | 完整金融质量、稳定性、时点合同未签 |
| 登记阳性 | completed，report partial | 真实写 1 条，绑定本 run，due=2026-10-21 | 最近两期口径和完整金融质量未签 |

六个**离线谓词**对照使用 F2 实际证据：合法计划/正确来源日放行，错来源日、虚构业务阈值、未知协议引用拦截，connect 尝试 0。不是 live 模型变异或完整 verifier 重放。同份 F1 公开答案离线拒写 0 / 允许写 2，第二条误收清单后“缺口”段，是相邻解析缺陷，**不是第二条 live 写入**。

原工程四叶、组合最终交付与变异证据仍见 [09-17 索引](../2026-09-17-8792-boundary-integration/README.md)。本轮没有修改业务源码、重发工程收据或把候选部署到 8792。

## 原件入口

| 文件/目录（相对 R） | 用途 |
|---|---|
| `protocol.json`、`cases/*/question.txt` | 首题前冻结题面/hash、用户、顺序、预算、判据 |
| `cases/*/receipt.json`、`probe.log/.exit` | 准确 run/conversation/message ID，原退出码和复制工件 hash |
| `cases/*/public-message.json`、`public-projections.json` | 公开答案、run/trace/report/消息 API 投影 |
| `cases/*/artifacts/` | 私有 episode、report、trace、原答案和 LLM context |
| `run-inspection.json` | 路由、引用、判官、用量、实际写入及扫描结果；不是新模型评价 |
| `offline-controls-final.json` | 六谓词对照、原答案写侧控制、格式化原题投影 |
| `acceptance-summary.json` | 机器结论 `overall_acceptance=not_passed`；每层状态/时长单列 |
| `closure.json`、`production-health-after.json` | 停服、锁释放、生产身份和固定盘面 hash 对照 |
| `evidence-index.json` | 首轮封存的 219 份私有原件 bytes/SHA256；后续文档/记忆收据单列 |
| `finalize-final.log/.exit` | 原件封存成功，不是业务验收通过 |

不能原样重跑 `prepare.py`、`launch.py`、`run_cases.py`：它们绑定这次 revision/路径，拒已有资源；重新运行不是重现同一模型轨迹。只读检查 hash 可用下列命令，不会发题或重启服务：

```sh
umask 022
env -i PATH="$PATH" HOME="$HOME" \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
from pathlib import Path
import hashlib, json
root = Path.home()/'.finance-runtime/reviews/8792-boundary-live-20260918'
index = json.loads((root/'evidence-index.json').read_text())
for rel, expected in index['files'].items():
    p = root/rel
    assert p.is_file() and not p.is_symlink(), rel
    actual = {'bytes': p.stat().st_size,
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    assert actual == expected, rel
print('identity checked:', len(index['files']), 'files; not a quality verdict')
PY
```

## 读数限制与错误原件

- 服务记录时长 142/71/174/203 秒；客户端 145.458/154.602/175.484/205.637 秒。F3 客户端包含暂停等开销，不能当模型耗时或稳定性统计。
- 成功 writer 有 tokens，五次判官无 tokens；失败题确有调用但用量产物丢失。整轮费用 unknown，不能填 0 或套用宽泛 `glm-5.3*` 价目当 coding 套餐账单。
- 用户请求截至 09-16/17，四个 research_context cutoff 却为 runtime_default 09-18；没有完整的截止后证据审计。F1/阳性跳过已有 Q1 而取年报+中报，不能签“最近两期”语义合格。
- 只冻结市场 DB/exports/snapshot。F10 财务、知识库、网页/L3 在线；行情最大日 09-17 不代表每张表/值完整。
- 最初 static 嵌套复制和辅助修正异常保留；两题后补隔离 rejudge 条件写口，未重发题、共享索引未发现本轮行且 stat 未变。
- 初始离线未知引用例用了超协议 E99999，断言红；改为 E999 后通过，初始脚本/输出/exit1 不删除。
- 初次 expanded secret scan 因代码词形误报让 finalizer exit1；原件保留。最终 184 文件/122395 字符串、5 条来源/规则命中逐项认定为 dotted import / scanner 构造表达式，未解决命中 0；不是全系统安全证明。
- 未 push/PR/合 main/部署；#770、RE06/#53、关闭判官的 #56 观察、真人金融效果均不在本轮签收范围。
