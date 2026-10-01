# semantic-consistency / 2026-10-01

- 用户要求持续推进现有门禁；不合main、不部署、不改默认off。模型语义系列23请求（旧19+R18的4），预算已耗尽关闭，不自行续费/开240。
- PR14保持draft。受验实现R19=`84d8e38ae8d87c461cc76b3ae2e66f1ee3b6b077`；后续结案提交只改docs，不把文档HEAD冒充受验SHA。R16～R19已领取并入账，勿重复claim。GitHub主协作，原始答卷/凭据/库只在Mac私有根。
- R16 confirmed：实现8dd20f49d，新9项7F2P→9P；同SHA744P、Mac19150P75S2xfail/19227收集，CI19058P167S2xfail/五绿；自动checkout e6d1e610与8dd完整tree相等。只修注入回调上下文，真实HTTP原本不漏；不冒称内容修复。官方full-scope收据校验亦过。
- R17 confirmed仅恢复一致性：完整模块同旧缓存；152组中126有答评分相同、26缺答单列，D9变异过、133源hash不变。恢复件`machine-scorer-recovery-20261001/score_machine_truth.py`，0444/SHA dee223de6a93bcb7412bdb47606ea4f2df6ecb7adba5692e2f283114f8e4ff80；原0字节源不覆盖。非原字节找回或尺度充分性证明。
- R18 partially_confirmed：用户另批≤4，实跑4请求4响应/身份0即停，源码8dd。错句首判明确−17.24%=缩量与均放量冲突；正确句首判未拒，但二判又拒日期归属，第3逻辑判被预算挡在HTTP前，整稿退缺证提示，正确句最终丢失。不得记整对通过或补跑。`direction-isolation-live-20261001/closeout.json`已关闭预算。
- 条件“两日”历史指代/未来持续对照都被机械标注，没加豁免；`direction-isolation-20261001/`。数值rubric两案均2/2不检验方向。未获条件新模型预算；不能把首判未拒当剩余句全已验证来绕过降级。
- R19 confirmed：用户批准原精确11项，非泛化排除。84d8提交后616P；真实重扫966=955适用成功+11不适用，保留11条raw error；默认exit2、显式manifest+SHA才exit0。新增/消失/漂移/范围差0，966原件及旧baseline未改。40新测试39F1P→40P，额外守卫变异2/2，真范围错pin→2/改baseline副本metric→1。
- R19全仓Mac19190P75S2xfail/1102.97s、19267收集、exit0/clean；官方full-scope收据`20261001T101638Z-84d8e38a-5fcd3691a3d7.json`校验过。CI19098P167S2xfail/1465.97s、五绿，runs36845950938/36845951012；checkout1c251736完整tree同84d8的91069a7ea24ed78508bc5d13aca23af2a2fd5787。gh观察器EOF是查询失败，没重跑CI。
- 私有R19根`label-ab-approved-scope-20261001/`含授权/manifest/严格与授权结果/全测/CI/变异/postcheck。PR10原983另有1107P本机范围验证；未改他人分支，后续集成须包含84修复。
- main3a2718c6、生产healthy@2c394978/code_matches_repo=true、队列7385/hash、冻结库hash/0444均未变。PR8内容门、D端到端、条件语义与四格先于240未解除；不拿工程绿灯替代内容验收。
