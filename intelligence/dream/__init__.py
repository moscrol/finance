"""dream-loop 自进化回路（决策 1）。

本包是「dream loop」的**采集半 + 落盘**部分，对应路线图 C-1A / 阶段 S0：

- 把多源对话（S0 仅接**飞书** chat 一个源）归一化成统一 transcript schema；
- 写入 transcript store（``<date>/<source>-<session>.jsonl`` 正文，**gitignore**）；
- 维护 ``manifest.jsonl``（可审计元数据）与 ``digest-<date>.md``（**脱敏摘要**，可提交）；
- 脱敏是硬门：密钥 / token / 持仓 / PII 命中即打码，保证可提交物不泄密。

边界（铁律）：suggest-only、不碰 DuckDB、不自动合并 main。推理半（读摘要→开 PR）
是 Devin 定时 session（playbook + schedule），属后续阶段 S2，不在本包内。

设计依据见 ``design-decision1-dream-loop.md`` 与 ``master-roadmap.md``。
"""
