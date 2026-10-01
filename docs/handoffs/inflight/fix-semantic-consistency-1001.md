# fix/semantic-consistency-1001

## 当前交接

- PR14仍OPEN draft，base fix/intent-negation-1001；不合main、不部署、不改生产默认off。
- R10/A四例全部无响应，4物理请求，约50秒各一次；refuted仅指现配置/时间窗，不能当模型内容评分。
- R11/B只改LLM_THINKING=disabled，四组首请求JSON差异严格只有thinking；7请求7响应、身份/父档准入均0，但内容目标未全过：D方向矛盾未明确识别，N正确日期句因judge漏上下文被删，条件句仍有机械numeric_unsupported误标。partially_confirmed，不启动产品复跑，不加第三配置。
- A+B实际11物理请求；24是上限，不是待消费额度。R12新增模型调用0。
- R12按事前登记仅修日期接口：共享writer日期投影（writer三组输入逐字不变），首判/复判传当前context、合同身份校验、白名单、缺席不推断、快照不复用、不把声明升级成行情证据。新增12测试、相关回归689通过；confirmed严格限离线接口，不代表真实GLM内容已修好。提交后同SHA再跑，私有收据留存。
- 私有证据 `~/.finance-runtime/semantic-consistency-20261001/`：comparison-summary.json、writer-byte-identity.json、context-red.log、context-neighbor-final.log、postcheck.json以及A/B原始请求/响应/判词/答卷。不得输出密钥或覆盖原件。
- postcheck：队列7385行/hash不变，main 3a2718c6不变，生产healthy@2c394978、code_matches_repo=true；冻结库3.88GB/0444/hash不变。
- 后续真实GLM复验须新协议/预算；本轮到此停模型调用。D方向推理与条件数字误标未修，不再顺手扩清单。R09仍partially_confirmed；旧AB966/955/11 exit2、scorer空源码、PR8内容验收阻塞均保留，240不跑。

协议/结果：docs/verification/2026-10-01-{semantic-consistency-probe,judge-thinking-control,review-runtime-context-fix}.md。
