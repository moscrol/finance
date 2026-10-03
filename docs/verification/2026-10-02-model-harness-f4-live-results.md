# R-20261002-17 结案：四格已各执行一次，但F4未通过

**结论：预注册的“四格全部技术接通并完成评分”预测 refuted；只有PC通过本次技术格条件。模型/harness收益未建立，240仍阻塞。** 不补跑、不替换、不改旧分、不合并部署。

## 固定条件与实际用量

- 运行revision `9ae16ab03954bf04eac7fd93e366f11c44255358`；产品基线main `3a2718c6c7dbf5af8ddad249b50835d09deef8a4`。前序预注册commit `46d79b378`，均在真实请求前双推至GitHub/Gitea，Draft PR20。
- 启动manifest SHA256 `27e003d7c0546b4e0fee7ec5ced1b7842546956b22186b275dac80dcdafd4f3c`。四份只读快照均为 `71c03b7e…c023`，运行后复核全部冻结文件未变；各格独立可变根。
- 已见D1（2026-07-22盘后整体行情），各一次。G=`glm-5.3-flash`、C=`glm-5.3`，未标定强弱。两者请求thinking enabled、不请求effort档位，不认证网关实际推理模式/权重。
- 实际启动间隔90.032/90.049/90.130秒；一层R15进程组监督，整体303.372秒，退出1是实验格未通过，不是外层超时。已核所属组无存活进程。
- **9次原生请求均观察到HTTP200响应头；8份完整响应身份符合对应型号，PG另1份未收齐、身份不明。累计物理HTTP请求口径100→109。** 不把管道request_sent或预留当计费证明；未确认服务商计费，缺失用量不补0。

| 格 | 入口 | 最终状态 | 请求/完整身份 | 原旧分 | 本次技术条件 |
|---|---|---|---:|---:|---|
| PG | 完整HTTP P × flash | failed，缺口占位 | 2 / 1 | 0/7 | 不通过 |
| RG | 薄R × flash | failed，空答 | 2 / 2 | 0/7 | 不通过 |
| PC | 完整HTTP P × glm-5.3 | completed | 3 / 3 | 7/7 | 通过，但不是全文保真通过 |
| RC | 薄R × glm-5.3 | failed，空答 | 2 / 2 | 0/7 | 不通过 |

诊断时长：P官方probe为80.375/63.730秒；R循环为31.414/25.682秒，计时边界不同，不能直接比较。完整body缓冲改变增量呈现时序，不作首字延迟/效率收益结论。

## 找到的是harness限制，不是给弱模型加语义硬规则

1. **PG的研究阶段被预算分配挤空。** 首轮约39.50秒后给出工具调用；派发时episode尚余约40.06秒，但研究阶段授予0秒，前4个工具均`tool_not_dispatched`、实际工具执行0；第五个另为工具预算错误。`ResearchDeadline.stage_timeout`扣除合成硬预留后授予研究时间。随后40秒修复请求未收齐响应。不可简化为“数据库没数据”“模型没能力”，也不是“5个工具超帽导致整批原子拒绝”。下一步应先复现阶段预算分配，不能只盲目拉长超时。
2. **薄R两型号都撞到工具额度后的硬退出。** 原默认工具帽4；第一轮用尽后，第二轮仍看到原工具菜单，继续发出查询意图就整格失败，最终答案为空。RG已有全部核心数据；RC则有字段错误/空结果，需要进一步纠正。RC后续提案仍把stage_day放在metrics，不能说其修复已经正确。应研究额度透明与预算内收尾，而不是默许超额、给某型号专用题目规则。
3. **PC确有普通循环内的参数纠正，但不是“修复模块收益已证”。** 初次stage_day字段类别错误，后续改为dimension并取到数据，6次数据工具尝试后完成。其repair_attempts=0；P与R资源/提示不同，不能把这一个例子包装成净收益或泛化。
4. **旧满分与产品内部passed仍不等于全文可信。** PC核心数字、日期、单位及阶段天数都正确；完整核对27份证据后发现科技板块的混合量能被概括成笼统“放量分歧”。CPO/存储为负边际量，不能无聚合依据确认列举对象普遍放量。主事实覆盖很好，但全文保真仍需范围修订/复核。PC的“贵金属/锌放量启动”则由启动日期、周期和正价量共同支持，不能因为未逐字照抄另一个标签就判错。

全文评审见[执行者全文审查](2026-10-02-model-harness-f4-live-full-review.md)。评审不是独立盲评；不采用固定整句、公司名或已知坏句黑名单。

## 保留的不利结果与解释边界

- 原模型准入工具四格退出均为0，但PG有1次物理响应身份不完整。本轮预先增加的严格物理门正确拦下PG；不能拿父artifact准入0遮住失败尝试。
- PG公共摘要`model.used=false`不代表整格0调用；原生收据有2次HTTP200头。该字段不能直接当成本计数。
- PC内部judge为deterministic、独立judge调用0。验证器入稿与最终回答hash一致，不据此把范围问题归咎于发布改写；也不认领“从所有模型token到展示的普遍保真”。
- PC phase_trace保留`finalizing -> research (model_turn)`非法转换告警。此次没有真实子研究调用；不得宣称整条状态机无异常或真实子研究覆盖。
- 既有环境doctor仍因httpx0.25.2/锁0.28.1偏离而blocked，代码地图empty；四格均校验相同实际版本，不豁免旧CI或生产门。历史回填快照不证明当时信息可得性。
- 该题已见、每格n=1、工具集合/资源不同、传输完整缓冲，均限制解释。本批没有优化处理组，不能产生harness改进收益结论。
- PR19@38a的registry/frontend/python/e2e/workbench-check此次复查均成功；只归该revision，不转签R17私有driver、旧PR16红门、语义验收或部署。

## 可复核私有证据

根目录 `~/.finance-runtime/model-harness-f4-live-20261002/`：

- `launch-manifest.json`、`live/absolute-launch.json`、四格`*-absolute-spec.json`/`*-started.json`。
- `live/{PG,RG,PC,RC}/result.json`、原生`http/*/{request.bin,response.bin,finished.json}`（PG第二次无完整response.bin，保留失败）、P真实HTTP probe/保存消息/continuous-episode，R原始thin-result。
- `review/postrun-integrity.json`、`review/raw-artifact-hashes.json`、`review/product-evidence.json`、`review/full-answer-review.md`。
- 24项离线单元；多轮明确标为synthetic的native/HTTP/数据工具组合夹具；挂起负向夹具。都不计真实模型调用，也不代替本次失败。
- 凭据静态读取拒绝的准备失败、仅获取原配置Keychain条目的私有供给收据、瞬时index.lock冲突保留；没有执行旧实验脚本或删除他人锁。

**下一步优先级**：先做模型无关的阶段预算/额度可见性与收尾机制小改动的离线可证伪复现，再另批预注册同模型同题同数据A/B，并包含未调试题和信息足够控制。语义理解可以修订，权限/来源身份/根截止/物理预算仍刚性。R17永不重开；正式240不自动放行。

临时provider-only凭据副本已在结束审计后删除，原Keychain未改；该冻结条目有意退役见credential-retired.json，不要重跑启动器。
