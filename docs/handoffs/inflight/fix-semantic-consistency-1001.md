# fix/semantic-consistency-1001

## 当前交接

- PR14 OPEN draft，base fix/intent-negation-1001；不合main、不部署、不改默认off。日期接口生产实现46a79837c；R14受验新HEAD b96980cee，之后仅文档。
- R10/A四例各约50秒无响应，4物理请求；refuted只指本配置/窗口。R11/B仅thinking=disabled，7请求7响应/身份0，但D方向矛盾未明确识别、N日期误删、条件数字误标；partially_confirmed，无产品扩跑。
- R12共享writer日期投影、首判/复判context、身份/白名单/隔离/off测试及writer三组字节一致通过。但全量CI后来发现4个benchmark兼容失败，台账已由confirmed更正partially_confirmed，不能把定向689通过当全绿。
- R13另授权≤4，实际2请求，旧/新各一次均全文保留；partially_confirmed，旧误删未重现，不证明收益。
- R14另授权3对≤12，AB/BA/AB固定顺序；实际6请求6响应。旧完整保留1/3、日期误删2/3；新3/3全文保留，配对同过/新胜/新胜。判词确为缺少更晚日期查询而误拒运行时声明，首wire锁定R13、身份0；confirmed仅此三对，不外推普遍误删率/显著性/延迟。未补跑、未扩题，旧失败保留。本系列R10/11/13/14累计19请求，R12离线0。
- b96980cee相关8文件689通过/3.66秒；收据20261001T074319Z-b96980ce-4a22ad0accfa。postcheck：队列7385行/hash、main3a2718c6、生产healthy@2c394978/code_matches_repo=true、冻结库3.88GB/0444/hash不变。

## 明确阻塞与下一步

- R12全量GitHub run36828527701：4F/19033P/167S/2xfail，1536.82秒。当前benchmark单文件4F30P，旧de0同文件34P，已离线复现。
- 原因：_SemanticVerifierCapture.verify(**kwargs)隐藏delegate窄签名，adapter误认为可收context并透传到旧替身，报unexpected keyword argument。真实SemanticEpisodeVerifier支持context；不是GLM内容失败。当前未修，优先离线修包装层签名透明性并增加覆盖，不改日期语义、不追加模型预算、不覆盖R14受验SHA。
- 新HEAD CI尚未全完，既有红灯仍阻塞。D方向矛盾/条件数字问题未修；R09仍partially_confirmed；旧AB966/955/11 exit2、scorer空源码、PR8内容验收阻塞不变，不跑240。

私有证据根：semantic-consistency-20261001（R10–12）、review-context-live-20261001（R13）、review-context-repeat-20261001（R14）。均位于~/.finance-runtime；后者含summary、date-reason-review、ci-diagnosis、原始六组及新旧benchmark日志。不得公开凭据/私有请求或覆盖原件。

协议见docs/verification/2026-10-01-review-context-{live-pair,repeat-pairs}.md及review-runtime-context-fix.md。
