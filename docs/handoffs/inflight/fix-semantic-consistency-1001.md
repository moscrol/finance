# fix/semantic-consistency-1001

## 当前结论

- PR14 OPEN draft，base fix/intent-negation-1001；不合main、不部署、不改默认off。日期接口实现46a79837c；R14真实受验b96980cee；R15包装层兼容修复a6cb22676。本次收尾仅文档。
- R15 confirmed：wraps透明暴露delegate签名，旧接口不收未声明context，新接口/真实判官仍收到context；不吞参、不捕获TypeError重试、不改日期语义。原4个benchmark失败已解除。
- 实现a6cb22676干净树：735定向通过/14.76秒；Mac全仓19141P/75S/2xfail、17警告/1050.60秒。收据20261001T081839Z-a6cb2267-a194eb7e4192，collected19218，无额外ignore/deselect/关键词筛选，无依赖门禁绕过，前后干净。
- 对应GitHub五检查全绿：workbench run36833617920、registry run36833618029；CI Python19049P/167S/2xfail。CI实际checkout为自动PR测试合并5b99e3f1，已核验其完整Git tree与a6cb22676相同；不是实际合并。后续文档HEAD的CI状态另计。
- 全仓任务已完成，无需重启。私有review-wrapper-compat-20261001/stage.json、full-result.json、ci-tree-equivalence.json及postcheck-final.json保存收尾证据。

## 真实实验与历史不覆盖

- R10/A：4请求0响应、各约50秒，refuted仅配置/窗口，不是内容评分。R11/B仅thinking=disabled，7请求7响应，但D方向矛盾未明确识别、N日期误删、条件数字误标，partially_confirmed。
- R12原版全量CI4F保留，仍partially_confirmed；后续兼容修复的成功只归R15，不把735或全量结果挪给旧实现。
- R13：2请求，新旧各一次均全文保留，partially_confirmed，未证明收益。R14：固定AB/BA/AB共6请求；旧完整保真1/3、日期误删2/3，新3/3全文保留；同过/新胜/新胜。confirmed只限此三对，不推导普遍误删率/显著性/延迟，未补跑或扩题。
- 本系列R10/11/13/14累计19模型请求；R12/R15为0。本次只是核验收尾，无新增模型调用。

## 隔离与下一关

- 最终队列7385行/hash、main3a2718c6、生产healthy@2c394978/code_matches_repo=true、冻结库3.88GB/0444/hash均未变。
- 原D“两日均放量”与09-29 −17.24%的方向矛盾、条件数字误标仍未解决。后续应回到该内容问题，不能把日期实验/CI绿当整体质量通过；新真实实验须独立协议/预算。
- R09仍partially_confirmed；旧AB966/955/11 exit2、11排除未批准、scorer空源码、PR8内容门禁仍阻塞，不跑240。

私有证据都在~/.finance-runtime：semantic-consistency-20261001（R10–12）、review-context-live-20261001（R13）、review-context-repeat-20261001（R14）、review-wrapper-compat-20261001（R15）。不得公开凭据/私有请求或覆盖原件。完整协议见docs/verification/2026-10-01-review-*.md。
