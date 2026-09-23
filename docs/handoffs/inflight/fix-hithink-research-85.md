# #85 同花顺研究观察值

## 这个分支做什么
承接 #810，前向 main，补429有界退避与局部失败，维持日期/生产写入保护。

## 决策与被否方案
- 只吞类型化429；否掉捕获一切异常，避免掩盖解析/写入错误。
- monotonic时间预算+次数双界；否掉只累计sleep，避免零等待无界循环。4001仍走旧retries。
- 研究请求继续不等于允许发布；CLI partial=3，夜跑/旧单体不得洗成成功。
- 展开、部署草稿：`docs/handoffs/2026-09-23-hithink-research-observations-85.md`。

## 当前状态
实现已提交并推送至 `gitea/fix/hithink-research-85`：最终代码 `0f0231553acf788e7d42440ce54d3d101fdca187`。未合/部署；本轮没有采集或生产写入。主树L2覆盖层未带入。
新WIP PR #894已回读确认（创建接口30秒/90秒超时后成功），承接#810；原PR仍打开，接替评论6524已留。完整四叶与独审阻塞，已登记#75队列。

## 未验证 / 已知边界
- 最终head完整Python、前端、E2E尚未跑；本轮load峰值86，收尾降到19仍有两套全量运行超1小时，不再叠加。不能以定向或旧164b02e4收据代签。
- 未获独立Spec/Quality或用户豁免，未启付费审查。
- 在途网络读取不是硬截止；每请求独立预算，默认不保证覆盖实测7至9分钟窗口。
- 夜跑重试后仍partial则不导出/换库；数据完整性和真实供应商恢复效果未新验。

## 下一步
1. PR #894补完整四叶，最终head须干净树；#75独审，用户确认前不合main。
2. 后续前向main或修改代码，须重建同SHA收据；不借旧绿结论。
3. 部署另立单：installer不会自动把HEAD写成sync根，先准备已合SHA快照与审过的plist；命令只在日期快照，不执行。

## 已验证
冻结独占树 `/Users/a77/.finance-runtime/reviews/hithink-research-85-20260923/candidate-final`：定向130P/0F/0E，Ruff及registry五项exit0（跨仓跳过；台账98 warning）。合并预演无冲突。
收据根 `/Users/a77/.finance-runtime/reviews/hithink-research-85-20260923/`，`final-receipts/gate-3GXIgpu2/pytest.json` dirty=false，身份校验通过。429禁重试2F→恢复2P；CLI/夜跑/单体三条先红再绿。验收窗口生产stat与8792身份一致。

## 踩过的坑
只累计sleep不是墙钟；Retry-After=0须回退并限次；CLI输出partial但rc0会被父编排洗绿。代码图empty不代表全仓没有能力。复用原生门禁，无新临时工具需归仓。
