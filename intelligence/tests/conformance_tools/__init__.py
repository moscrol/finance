"""工具注册表缝契约符合性套件（工单 2026-08-29-conformance-seam-census 任务 B）。

缝：``research_tool_registry._DEFAULT_TOOL_METADATA`` 的 N 个工具 ×
统一的 ``ToolSpec`` / ``ToolObservation`` 契约。工具个数用解析器数
（``TOOL_NAMES``），不写死。

机制复用运行时后端套件的三件结构（参数表 × 能力声明表 × 棘轮 baseline，
见 ``intelligence/tests/conformance/``，在 test/runtime-conformance-suite
分支）：``tools.py`` 是参数表+声明表，``baseline.py`` 是棘轮，每个不变量
一个 ``test_t*_*.py``。零网络、零真实下游（DuckDB/检索服务用探针替身）。
"""
