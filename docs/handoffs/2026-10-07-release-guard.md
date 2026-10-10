# 发布保护、旧 PR 同步与安全阻塞 — 2026-10-07

## 背景与授权

前轮核查见 [接手审查](2026-10-07-review-takeover.md)。用户确认保持公开、扫描公开全分支/历史、
配置 main 保护、同步旧 PR 并推送。每次合并、生产部署、写库、删除仍须另行确认。
后续“继续”用于调查与本地准备；发现凭据风险后，未将它推定为更改可见性、撤销账号、删枝或
强推历史的授权。扫描事件具体定位和账号信息仅保留在本机私有目录，不写入本文件。

独占树 `~/fwp-wt-review-takeover-1007`；同步候选在 `~/fwp-wt-pr-sync-1007`。
主检出、其他会话的 #61/#62/#66 收尾树和核验器均未修改。

## 按发现顺序

### 1. 平台保护已从纪律变为强制

- main 原为 `ea217633ceeaceeb41d3b3f30fa58708fe14ecc9`；本轮未改变。
- 01:39 配置、09:21 +08:00 独立回读：required checks = `workbench-check`、`registry-check`，
  绑定 GitHub Actions app ID `15368`；`strict=true`，管理员受约束，禁止强推/删除。
- 必须经 PR、解决讨论；必需审批人数 0，避免单人仓库无法获得另一名真人批准。
  这不替代用户逐次合并许可。
- 仓库仍 PUBLIC。secret scanning / push protection 仍 disabled，本轮没有声称已开启。
- 原配置及回读分别保存，未覆盖 01:05 “当时未保护”的历史观察。

### 2. 公开引用冻结，历史与完整内容分开扫描

私有根：`~/.finance-runtime/reviews/release-guard-20261007/`（目录 700）。

- GitHub heads/tags 导入独立 bare 仓，未混入本地私有 refs：665 heads、306 tags、8179 可达提交。
- 工具 Gitleaks v8.30.1，官方包校验；上游默认规则，无仓库 allowlist/ignore，忽略 allow 注释，
  报告/日志 `redact=100`，未打印原始凭据，未以候选凭据联网验证。
- 历史差异扫描 9002 条候选；工具日志报告扫描 8163 commits，与 Git 可达图计数区分记账。
- 完整内容补扫：43004 个唯一 blob / 1152280430 字节，929 条命中。
  原始文件通过内存管道传给扫描器，不导出额外明文副本；OID/行号索引另记。
- 会话规则补扫全历史再得 2 条命中，指向同一事故对象的两种形状。
- 09:21 重新 `ls-remote`，refs 与冻结集无漂移。不是以后永远无漂移。

### 3. 发现真实凭据暴露后暂停公开上传

大量候选与文件哈希、证据键、合成测试值有关，但至少两类历史凭据已由源码用途/结构确认。
其中“某访问令牌过期”不足以证明同文件的另一会话凭据失效；“旧功能退役”也不足以证明
应用已删除或凭据已撤销。已提醒账号持有人撤销，尚未收到完成证明。

- 具体 refs、对象、身份字段、到期字段和人工处置步骤：私有 `INCIDENT-PLAN.md`。
- 不将原值、完整文件、具体可下载定位上传到 GitHub Issue/PR/CI。
- 已建议临时转私有缩小新增暴露，明确需要用户确认；它不能收回已有副本，还可能影响
  当前套餐下分支保护。没有执行可见性变更、账号撤销、删引用或历史改写。
- FINANCEWORKS-1 已评论协调本会话暂停公开推送，未改他人归属/状态。
- 误报分类尚非逐条全部签结，扫描不是安全通过，更不证明没有被滥用。

### 4. 旧 PR 仅本地同步，保留原 head 为祖先

所有同步使用独立树和普通 merge，无改写远端，无切换他人工作树。

| PR | 本地分支 | 候选 SHA | 本机定向核验 |
|---|---|---|---|
| #50 | `baseline/pr-sync-1007` | `570142a2498a6486cc1558b18982bf224cbc8d5e` | 4 项 registry checks + ledger crosswalk 通过；反向台账 warning 101 条 |
| #51 | `baseline/pr51-sync-1007` | `a8fe098a83ddb6cd7e99004d24dbb20c6693c933` | 123 passed，ruff/收据校验通过 |
| #49 | `baseline/pr49-sync-1007` | `a136e41e62bc20c1c9debfce0bf9901d309f2ff1` | 90 passed，ruff/收据校验通过 |
| #53 | `baseline/pr53-sync-1007` | `4594192cc5ba5a2706779b491b4be13a5c12b3b2` | 99 passed，ruff/收据校验通过 |

#53 同步的是本地 #49 候选，仍为堆叠 PR；尚未修改 GitHub base。
解释器均为主检出 `.venv-workbench/bin/python`。收据 `pr{49,51,53}-scoped.json`。
**都是定向，不是全量**：#49/#53 仍使用旧 checker，输出“收集面未被收窄”正是 #51 待修的
位置参数漏检；不能拿那行代签全量。另用 #51 checker 的 `describe_collection_scope` 对四张
收据复核（含新闸30P）均明确判为收窄，元数据在 `scoped-receipts-not-full.json`。
#50 首次 crosswalk 误写文件名，改用实际 workflow 的
`scripts/audit_ledger_spec_crosswalk.py` 后通过，未掩盖首次命令错误。

没有推送这些候选，所以旧远程 CI 不移签新 head；推送后须重新 CI 和语义集成验收。

### 5. 本地提交期内容闸补洞

旧 `block-forbidden-files` 只按文件名拦；另有私钥检测，但普通归档文本中的会话 JSON 可漏过。
新增 `scripts/check_staged_credentials.py` 与 `staged-credentials` pre-commit hook：

- 检查本次 changed index blobs（实际准备提交的内容），不是工作区，不靠扩展名或测试目录豁免。
- 覆盖新增/修改/改名/首个提交，Git 读取失败和未解决冲突 fail closed；不跟随软链或扫描子模块外部内容。
- 只报告文件、行号和规则名，转义异常文件名；不输出匹配值或值哈希。
- 狭义覆盖长会话/刷新/访问字面量、应用密钥、签名/加密令牌形状；不解压/解码封装、不扫历史，
  不宣称替代通用密钥扫描，不因过期而放行。

提交 `a3b239f55a8163151d257244cd53f292ec78f41a` 含门禁、22 项测试和 AGENTS/流程纠偏。
提交后干净树用生产解释器重跑新测试 + 交接预算测试：**30 passed，3.66s**；版本/解释器/
依赖/干净树收据验证通过。该树尚未合入 #51，旧 checker 的“未被收窄”仍不成立，这是定向收据。

变异实验在私有隔离副本中把实现改坏：
- 恒返回空：13 项测试失败；
- 误读工作区而非 index：3 项测试失败；
- 均无测试执行错误，不把配置失败当“变异被抓住”。

对真实历史 blob 仅做离线 `scan_bytes`，两类均被检出，值不进日志。
本地 review 增量 `ea21763..a3b239f55` 的默认 Gitleaks 扫描 0 命中；这不覆盖继承历史。

## 决策与被否方案

| 选择 | 被否方案 | 原因 |
|---|---|---|
| 本地同步保留祖先 | rebase / force-push 旧 PR | 多 agent 正在使用原分支，先快进式同步避免改写身份 |
| 先确认撤销再恢复公开推送 | 以 CI 绿或功能退役当安全结案 | CI 不证明凭据失效，退役记录甚至可能明确留有人工作业 |
| 历史差异 + 完整 blob + 会话补扫 | 只扫 main 工作区 / 默认规则一次 | 归档分支也公开；通用规则可能不识别加密会话 |
| 狭义无依赖暂存闸 + 通用离线扫描 | 大型自研安全平台 / 测试目录整体白名单 | 先封本轮已证失败形状，保留工具边界，不把低噪声冒充全面覆盖 |
| 请求临时私有化，不自动改 | 擅自改可见性 / 直接重写全部历史 | 用户此前确认公开；保护能力与 665 分支的历史改写都有附加影响 |
| 敏感定位仅私有保存 | 将脱敏报告整份提交 | 即便值遮住，准确位置仍可让人直接定位未撤销的公开凭据 |

## 验证收据与未覆盖范围

私有根关键文件：`protection-latest.json`、`scan-scope.json`、`history-scan-summary.json`、
`full-blob-summary.json`、`session-history-summary.json`、`public-ref-drift.json`、
`gate-mutation-summary-v2.json`、`staged-gate-clean-pytest.json`、`staged-gate-clean-junit.xml`、
`local-review-delta-summary.json`、`scoped-receipts-not-full.json`。开发期 dirty-tree 22P 收据保留，不移签干净提交。

没有运行本轮本机全量 Python/前端/E2E，没有新内容评测或真实模型调用，没有部署/写生产库。
扫描不覆盖远端隐藏 refs、fork、LFS 实体、归档解包、CI artifacts、未跟踪文件；没有账号滥用
审计、凭据撤销回执或实际远程认证边界验收。旧 v6/12 题评测资格约束不变。

工具沉淀：真正通用的回归闸已进 `scripts/` 并挂到提交入口；事件扫描 wrapper/逐项定位脚本
留私有目录，因绑定敏感事件且尚不构成通用平台，不搬到公开源码。harness-reference 树已脏且
基线旧，本轮未编辑；不把“应回写”写成“已回写”。

## 下一步

1. 收到账号撤销状态/时间；确认是否临时 PRIVATE，以及是否允许平台 secret scanning/push protection。
   这些都不是本文件发布即生效。
2. 点名审批删事故引用/敏感历史清理；需要时联系平台支持处理缓存，不能声称删枝等于删除历史。
3. 安全阻塞闭合后，回读远端 expected heads，再推送旧 PR/核查分支、重跑 CI。逐次合并仍确认。
4. 保持 #66 单 owner，不增加答案规则；#30 能力接替对照、新留出实验及生产依赖最终全量仍独立推进。
