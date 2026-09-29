只读代码复核：审查上一轮独立review找到的非材料协议回归及修复。禁止改文件、联网、运行命令或自然金融答题；仅用read。候选 7c16a38ec65eee96996d873e88270a1b2f692378。附件是 11f7ce233 -> 7c16a38ec 的diff和上一轮review原文，不隐藏其阻断。

可读：
/Users/a77/fwp-wt-8792-answer-closeout-0929/intelligence/services/episode_protocol.py
/Users/a77/fwp-wt-8792-answer-closeout-0929/intelligence/services/material_grounding.py
/Users/a77/fwp-wt-8792-answer-closeout-0929/intelligence/tests/test_episode_protocol.py
/Users/a77/fwp-wt-8792-answer-closeout-0929/intelligence/tests/test_material_quote_recovery.py
/Users/a77/fwp-wt-8792-answer-closeout-0929/intelligence/tests/test_prior_evidence.py

修复目标：frozen(material_only/local_only)仍先扫全部已可解析binding的来源，再处理可恢复错误；普通非冻结evidence协议恢复父版按binding的output/basis/hash拒收顺序。本次抽出同一纯校验函数，非冻结每条立即用，冻结所有来源扫完用。不是新增全仓硬错全序：坏JSON/错误claim结构仍是前置拒收；非冻结既有先出现E9再伪hash的行为不在本次扩大范围内。请验证旧复审反例确实不会再降级；查看差异是否有新阻断、未知ordinal是否有静默删除成功路径、合法quote-only与#819旧证据是否保持。输出具体阻断及路径/反例，或“未发现本次差异的阻断问题”；如实注明只静态复核，不能代签全量工程或实际答案质量。一轮审查，不反复重抽好结论。