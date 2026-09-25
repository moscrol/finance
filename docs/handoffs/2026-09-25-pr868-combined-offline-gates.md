# #868 + #910 + #911 联合候选离线工程门禁

## 背景与冻结身份

用户要求“那就继续推进”。本轮限于独立工作树组合和离线验证；没有启动新的付费独审、L6、main 合入或 8792 部署，没有改 owner 树、共享环境或封存批。

- 分支：`baseline/pr868-combined-0925`；树：`~/fwp-wt-pr868-combined-0925`。
- 基座：`d21707ca6c71e4e39194b01ef9549bc893595d3f`，结束时 Gitea main 仍为此值。
- #868 owner：`89624eac7e76c325c14aeee090bc4610bf05f97c`。
- #910：`2d7b99e6d798269133bce146d36ab46be451ef91`；第一次 merge 为 `142941050166a3e349fc08df36d95d513e285fb8`。
- #911：`6c6a6774fcd2667078071a9356e6a21394d114f8`。
- **唯一受测联合候选：`adbe0ba11822f02530def67e4c375af28f6e23f2`**。三条交付均为其祖先。
- 本交接是测试之后追加的文档，文档提交及未来合并提交不继承 adbe 的完整收据。
- 解释器：`~/fwp-wt-pi-research/.venv-workbench/bin/python`；Python 3.12.13，httpx 0.28.1，依赖指纹 `66726d345bf37ce5`。未修改环境，未使用依赖门绕过。

## 发现顺序与决策

1. 主检出树有其他会话改动，因此新建独立树；#868 留认领评论 [6947](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/868#issuecomment-6947)。owner 树保持干净，分支未前进。
2. 从 main 合入 #910 时仅 INDEX 文档冲突。保留 main 的 #75 新独审记录、owner 的 #76 L6 历史；#72 对照原始报告，纠正“CHANGES_REQUIRED 仅为异常类型建议”的解释。实际 reason 要求补 C3/C5/C7 行为证据，findings 为空不能撤销要求。#911 自动合入，无产品代码冲突。
3. 重建代码地图并执行查询，doctor 为 offline_development ready。地图不证明架构完整或生产可用。相对 owner，运行时代码未新增变化，差分是审查修补、研究链测试和文档。
4. 第一次资源准入负载 8.761 > 8，零测试启动，记录保留。负载恢复后在新 `attempt02` 目录准入，阈值不变；每叶前检查负载、20 GiB 空间、候选/净树身份，前端另验隔离端口。资源观察不是全程隔离或跨会话锁。
5. 串行执行 registry 五项、前端六步、全仓 Python。外部日志和独占收据绑定新候选，不读共享 latest。前端端口 19981/19984，结束后均无监听。测试与监督进程全部结束。
6. 全量期间收到另一会话的新 c3c7 独审结果，原件只读核对，未接管授权。另做零 IO 的回调签名最小复现，详见下节。
7. 四份沙箱内层 JUnit 与 C3 字段记录复制到外部证据目录；全绿后门禁按既有规则清掉本轮 basetemp。最终证据约 2.7 MiB，不留下临时整库副本。

| 选择 | 被否方案 | 理由 |
| --- | --- | --- |
| 在独立树组合三条交付 | 直接改 owner/main | 多 agent 并发，owner 与生产授权独立 |
| 冻结新 SHA 后全量重跑 | 加总 #910/#911 旧计数或移签 f261 | 旧收据没有测过此组合 |
| 原件保留，格式失败单列 | 裁剪封存日志尾空白求绿 | 字节和哈希是审查证据的一部分 |
| 按轴、候选、覆盖面记独审 | 用跨轴汇总宣称全清 | 同一 claim 名称不代表同一验收签字 |
| 签名最小复现交 owner | 修改封存探针或恢复旧批 | 探针修复与独立重验需要新运行身份 |

## 实际验证

证据根 `E=~/.finance-runtime/reviews/pr868-combined-20260925/attempt02`。

| 项目 | 结果 | 原件 |
| --- | --- | --- |
| workspace doctor | ready，无 errors | `E/doctor.log` |
| registry 五项 | parseability/check/tables/views/crosswalk 全部 exit 0 | `E/{registry-parse,registry-check,registry-tables,registry-views,ledger-crosswalk}.log` |
| 前端 | install/lint/typecheck/test/build/test:e2e 六步 exit 0；单元 120P | `E/frontend/frontend.json` 和六份日志 |
| 浏览器 | 34P/2S，桌面/平板/手机；绑定链仅 desktop 跑一次 | `E/frontend/frontend-5.log.txt` |
| Ruff + 全仓 pytest | **15969P/0F/0E/88S/2X，collected 16059**；1501.41s | `E/receipts/gate-4Qw8d2n1/{pytest.json,pytest.log.txt}`、`E/python.xml` |
| 精确收据复核 | exit 0；full scope、收执对账、SHA、净树、解释器、指纹及冻结基座零漂移 | `E/receipt-check.log` |
| 新研究链目标 | conformance 36P；Workbench 进程内 API 20P；review repair 73P；无跳过 | 同一全仓 JUnit 按 classname 解析，非额外测试批次 |
| 沙箱作者检查 | spec/quality 各 C3 3P、C7 66P，零失败/错误/跳过 | `E/inner-author/manifest.json` 与四份 XML |

C3 两轴均实际观察到 `request_count=1`、headers、`report_received=false`、`unavailable=true`；实际耗时约 0.803s，9.6s 根预算剩余约 8.796s。字段原件 `inner-author/{spec,quality}-c3-fields.json`。这是作者检查，不加到外层 15969 的分母，也不签独审。

88 个 skip 按原因拆分：真实市场库缺席 57、尚未提交的 BP 脚本 13、跨仓 KB 入口未配置 4、嵌套边界声明 4、脚本桩不适用 3、现有地图场景 3、真实 SDK opt-in 2、没有历史 tmp 冲突源 1、缺 tdxpy 1。未补共享环境或接生产数据求零 skip。

两个已有 xfail：Codex headless 缺 resume 时的修复缺席收据、KOL 示例与旧路由 pattern 不匹配。原节点名/理由保留在 pytest 日志；不把它们写成已修。

**格式边界**：`git diff --check d217...adbe` exit 2，涉及 8 个 `docs/verification/` 封存文件的尾随空白/末尾空行；这些文件相对 owner 逐字无差异。去掉封存目录后的检查 exit 0，只定位责任范围，不是豁免整份 PR 格式检查，也不称“所有检查全绿”。

## 同期独审与 C3 定位

另一会话的 `~/.finance-runtime/reviews/pr868-glm-qc-20260925-c3c7/`：候选仍为 f261、基座 033；host audit 本批 34 次，累计 315/320。本轮未调用它的模型或续额度。

- spec 终稿 `BLOCKED_INCOMPLETE_EVIDENCE`；C7 verified 有明确 limits：`run_main_gate.sh` 独立探针 5/5，但 `check_test_receipt.py` 探针、baseline 红集比较和嵌套所有权未覆盖；C3 not_verified。
- C1/C2/C4/C5/C6 在该批为 out_of_scope。host 的跨批/跨轴汇总不改写各轴原 verdict；next spec 的 C5 未验证、quality 的既有边界也不能据此移除。
- 更不能把 f261 的签字移给本轮 adbe。next 原件、c3c7 原件和本轮工程收据是三份不同身份的证据。

只读查看其 `probe_c3_judge_window.py`：`observer=events.append`，而候选 `llm_http_transport.py` 的 headers 调用是 `observer("headers", status=...)`，closed 也带命名参数。锁定 Python 最小复现 `events.append("headers", status=200)` 得 `TypeError: list.append() takes no keyword arguments`；接受 `(event, **fields)` 的小函数能记录两种事件。f261/adbe 的该传输文件完全一致。

这是签名层复现，不是完整探针重跑；它解释为何及时正控也因记录函数异常失败，不能推出产品 C3 行为已过。现有 `diagnose_llm_timeout.py::observe` 是正确签名示例。定位已交 [#868 comment 6961](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/868#issuecomment-6961)，同期状态确认见 comment 6959。

## 下一步与边界

1. #868 owner 审阅采用本组合；#910/#911 原 PR 保持 WIP，未被本轮合入或关闭。
2. 选择最终受审候选，重绑 base/input/interpreter/dependencies 到全新根。`prepare_pi_review_repair.py` 仍包含历史配置，不能直接启动生成物；旧 receipts/授权/预算均不复制。
3. 新独审需要另行授权与预算，各轴缺口、C7 limits 单独处理；C3 的及时正控和迟到触发阶段先验接口。作者全量和回调最小复现不能补独立签字。
4. L6 自然金融验收仍未通过；没有证明真实模型持续研究、真来源/子研究、反证修订、金融质量或 8792 运行身份。
5. 真正合 main 前仍验届时组合，main 合入和 8792 部署分别授权。所有已有封存批保持原样。

工具沉淀：复用仓内 main/frontend gate、receipt checker、review generator/tests；外部 `run_engineering.py` 只是带本批路径/SHA 的一次性编排记录，不冒充通用调度器或资源锁。回调接口问题先用无 IO 的签名实验定位，属于量具核验方法；未凭此新增产品抽象。方法回写现有证据卫生笔记。
