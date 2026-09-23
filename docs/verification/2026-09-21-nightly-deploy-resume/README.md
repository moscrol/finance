# #827 复验、合入与夜跑配置发布证据

- 受测并fast-forward合入：`c097d712f9acfdd258709c7d0de054f978e0159c`。
- `final-gate-qc.json`：合入前四叶PASS，Python12502P/0F/0error/85S/2X；前端110P/E2E34P2S，registry五项、生成7+4及hooks通过。里面 `merged=false` / `nightly_deployed=false` 是当时的快照，勿倒改。
- `merge-result.json`：#827已合、main精确等于受测SHA。
- `deployment/result.json`：18:43 `CONFIG_DEPLOYED_NOT_EXECUTED`；四目标安装、六文件备份、loaded核验及未改动对象检查。没有kickstart，没有手动采集/切8792/删旧根。
- `post-deployment-recheck.json`：两个job均idle/runs0；sync/生成/L2三根adcda；8792保持他会话f2c3。
- `natural-old-sync-exit2.json`：旧配置18:30自然运行因东财连接断开和当日空数失败；staging拒换库；不是新装代码运行结果。主库stat前后相同，readiness503仍未解决。
- 原Spec签名2ea6、新Quality签名b0cf，适用范围和字节一致证明见`review-applicability-final.json`；不移签上游#830或文档尖。Quality两个low及自建rig修正史、stub限制保留。

`manifest.json`记录封存原件的来源、字节数和SHA256。日志尾空行不做格式规范化；`.py.txt` / `.sh.txt` / `.zsh.txt`是操作原件，不是第二条可执行部署/采集入口。

完整原件根：`~/.finance-runtime/reviews/nightly-deploy-resume-20260921/`。完整模型token事件流、83,907项临时文件大清单、经全项验证的313,705,315字节压缩包保留外部；compact事件流保留所有完成消息和工具调用。凭据/配置、缓存、数据库、临时检出不入仓。

本目录随后的文档提交不继承c097全量签名。详细经过、方案取舍、回退与下一步见 `docs/handoffs/2026-09-21-nightly-deployment-complete.md`。
