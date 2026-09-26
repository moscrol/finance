# T3 六类比率边界返修 · 2026-09-19

## 结论与身份

**工程通过，外审未完成，仍 hold。** 用户“继续”授权沿原 q 线处理六类边界，不授权合并或部署。

- 工作树 `/Users/a77/fwp-q-research-data-readiness`，分支 `q/research-data-readiness`。
- 业务提交 `d46c2c3b10221483c811426e99ad379314289871`，已推 Gitea；父 `d402a563e8f868681ae8b1900c1837d53f9b795d`。
- 新 ARL-0005 累计范围 `d38dab3fea578f957794249a39d6b880d52f71f2..d46c2c3b`，依赖并 supersede ARL-0004；1725 artifact、38 唯一测试。
- 请求 SHA-256 `5fa3e7b7215bc83243e5f4a3e429cbca7770c791579cdce5d27d7a9cd13169d6`。
- 外审仅一次 CLI 调用，600秒超时，无最终信封/裁决，不是 PASS，也不伪造第四份有效 CR。
- 前三份有效 `CHANGES_REQUIRED` 和第四次 `INVALID_VERDICT` 原件保留；没有新有效裁决覆盖它们。
- main 末核 `b22ddf8b0285a952de1e6e18c04db0f4abe448e7`；未开 PR、未合 main、未部署。8792/夜跑/KB防写/其他T线/他人工作树/shim封存未动。

## 背景与发现顺序

746 的工程套件和原占位四例通过，却在独立排名、千分位金额、“的”邻期上产生误报；`元/元`、`个百分点`和占位后的分号续值仍漏检。原件见[上一轮交接](2026-09-19-t3-ratio-scope-review.md)。

1. 开工 q 树干净；读交接/偏好，刷新 stale 代码地图，只使用主树 workbench venv。
2. 原样边界探针在精确 d402 上复跑 **4P/12F，exit1**，不改原题、不 xfail。
3. 新回归首次夹具漏 `mode` 参数产生 **1 collection error**，单列为夹具错误；修正参数后行为首红 **120F/258P**。
4. 按数字角色、单位及期别修复；基础回归通过后再补格式化分号续值，首红 **3F/107P**；补序号后的英文逗号，首红 **3F/33P/77 deselected**。均保存首次失败日志，未覆盖。
5. 定向九文件最终 **781P**；冻结业务 d46，跑全套及原探针，46组撤保护逐项验红并还原。
6. 新独占目录提交 ARL-0005。独立环境机械预检 **1301P**、46组变异通过；随后唯一一次外部模型调用600秒超时，进程已收尾，无后台重试。

## 方案与取舍

| 问题 | 采用 | 否定及理由 |
|---|---|---|
| 千分位金额被拆碎 | 完整消费 `1,234.56` 数字词元；角色掩码用等长空格，不拼接两侧数字 | 不直接删除逗号；逗号也可能是句法分隔符，全局删除会改变归属 |
| 独立排名误降partial | 局部排除“排名/位列/第+整数”角色，并验中英文标点 | 不豁免整个后半句，排名后仍可能跟错比率 |
| “的”邻期混进上期 | `2025中报的含金量`为新声明并独立绑定；`2025中报的1.2倍`为参照，仍显式unknown | 不把所有“的”当参照，也不一律切断参照期 |
| 元/元漏检 | 复合比率单位优先于金额单元“元”；定位后连完整单位一起替换 | 不把任意带元数字当比率，独立金额仍保留 |
| 百分点漏检 | 绝对比率使用百分点即量纲不符，不能因标量相等认证；独立增减差值保留 | 不把百分点当百分比乘100核算；二者含义不同 |
| 分号漏检 | 仅分号后明确“实际为/该值为/本期为/比率为”延续值槽，兼容外层Markdown | 不扩大公告检测窗口，不跨句号/换行/独立分句猜归属 |
| 未定位剩余值 | 原文保留、局部标记、partial、原预算续修 | 不猜正确数，不整句删，不把已有标记当认证令牌 |

仅有限句法支持，不是通用中文语义解析器。隐含主体/期间、任意复合单位/格式、脚本实际消费输入及自然修复仍另验。原“3年最高，为1.588”仍可能显式unknown；这不等于认证数值错误。

## 验证与收据

以下完整工程收据**只签 d46 业务提交**，不能移签后续留证 tip。

| 检查 | 结果 |
|---|---|
| Ruff | exit0 |
| Python 全量 | **12173P / 0F / 0E / 87S / 2xfailed**；483.52秒，不作性能结论 |
| Python 收据 | `~/.finance-runtime/test-receipts/20260919T105730Z-d46c2c3b.json`；精确revision、解释器、完整target、干净树、base drift0验证通过 |
| 前端 lint/typecheck/test/build | exit0；110P |
| E2E | 34P/2S；8914/8915临时端口已停 |
| 固定三仓 registry | 5项exit0，前后干净；KB `1254224be89e2c4974350b7f3e985dbedb5dc043`、site `f606583867fe1cad8de96b06be1dd6cfe2b57e51` |
| 原保真/原占位/原边界量具 | **6P / 4P / 16P**；原输入未改、目标前后不变 |
| 撤保护 | 46组全部真实断言失败、逐项还原绿，baseline/restored-full各601P；无collection error/skip冒充检出 |
| 审查机械预检 | 38测试文件1301P、三原探针/46变异均过；不是模型自己运行工具、不是外审通过 |

原六类边界输入不变，均经过真实 `SemanticEpisodeVerifier.verify` 和最终公开出口重检；`judge=llm`仍是成功替身，不是自然模型回答。

## ARL-0005 调度和模型账

独占根：`~/.finance-runtime/convergence-20260919/retention-repair/qc-repair-d46c2c3b/`。

常规 worker 队列仍会选择缺少有效裁决的 ARL-0004；本轮没有重跑该请求、修改 worker 或伪造裁决填洞。一次性 **operations 显式指向 ARL-0005**：校验原request/claim、锁定独占根、建立精确 detached 树、跑机械预检、只调用一次原隔离 CLI；若返回则使用原 `validate_verdict_file` 决定是否发布。不能声称这是常规 `worker --once` 的选择或门禁批准。调度脚本作为惰性归档，不安装为第二常驻runner。

模型输入包含完整累计业务diff、源码/测试映射、三份有效CR和0004完整无效输出；1702件历史原件仅按逐字节manifest/hash/count摘要展示。完整request/claim原字节在独占根。提示509375字节；没有再发生本地Prompt too long，但上下文更大，本次超时不能据此单因素归因。

- 请求别名 `sonnet`，配置及stream消息模型 `claude-opus-5`。
- 上限 `$6`，600秒；实耗 **600.041秒**，CLI exit143，adapter exit124，状态 `REVIEWER_INACTIVE`。
- stream有思考进度和assistant事件，但没有最终结果信封、有效裁决或完整自然语言结论。不从中拼造裁决。
- 最终token/费用缺失，provider请求次数未知；不是0成本、不是本轮0模型。
- 无重试、无fallback、无tools/MCP/plugins/hooks/持久session；本轮未另跑聚合gate，不给其虚构状态。
- detached审查树已清理，仅清理本轮自建树；无后台review/工程进程。

## 留证、复跑与下一步

原件根 `~/.finance-runtime/convergence-20260919/retention-repair/`；归档
`docs/verification/2026-09-19-t3-ratio-boundaries/`：**561件 / 9,232,028字节**，manifest逐字节验证，保留原始空白；历史1702件原档案未动。

```bash
umask 022
cd /Users/a77/fwp-q-research-data-readiness
env -i HOME="$HOME" PATH="$PATH" LANG=en_US.UTF-8 FORESIGHT_LLM_KEYCHAIN=0 \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/review_probes/check_ratio_scope_boundaries.py \
  --code-root /Users/a77/.finance-runtime/convergence-20260919/retention-repair/candidate-d46c2c3b/registry-pinned/finance-workspace-private \
  --expect-revision d46c2c3b10221483c811426e99ad379314289871
```

预期exit0/16P；换原保真探针6P、原占位探针4P。

下一步先核对身份和归档，再安排**新的明确有界审查窗口**；不要复用旧state root覆盖超时，不自动加时或重试到绿。收到有效独立意见后按原题复现，再决定修复或验收。独立PASS也不代表自然金融质量：真实conversations仍需固定代码、题目、证据、GLM flash/5.3兜底及预算另验。

工具沉淀：新回归进pytest/CI及现有变异runner，未再造量具或修改准入器。可迁移原则是“先词元边界/角色/单位，再做数值比较”；领域特例保留在本仓。共享harness-reference仍有他人改动，未覆盖。未跑真实金融会话或市场取数，旧not_passed不翻案；合main、切8792、夜跑及KB解锁继续需另授权。
