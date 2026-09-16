# Codex Isolation Interpreter Implementation Plan

> **For agentic workers:** Inline execution in this session under the user's instruction to continue; no delegation required.

**Goal:** 同一宿主 Python 下，PATH 前置虚拟环境不再使沙箱探针启动失败，失败输出可复核。

**Architecture:** 在现有 probe_sealed_isolation 内固定真实宿主解释器；HeadlessIsolationReceipt 仅追加可选观测字段，保留现有证明规则和权限边界。

**Tech Stack:** Python 3.12、pytest、现有 Codex OS sandbox。

---

### Task 1: 锁住失败

- [x] 修改 `intelligence/tests/test_codex_headless_runtime.py` 的安装测试：参数 `prepend_venv_path` 为 False/True；True 时用 monkeypatch 将 `Path(sys.executable).parent` 前置 PATH。
- [x] 在独立树运行 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q --showlocals intelligence/tests/test_codex_headless_runtime.py -k installed_codex_sandbox`。预期至少 True 分支为 unproven。
- [x] 增加观测合同测试：让真实 probe 的 subprocess 边界返回 71、四项 denied 的 JSON 和错误文字，仍要求 unproven 并保留返回码/输出。

### Task 2: 修复选择与观测

- [x] 在 `intelligence/runtime/codex_headless_runtime.py` 导入 sys，以 `python_executable = str(Path(sys.executable).resolve())` 代替 PATH 查询。
- [x] HeadlessIsolationReceipt 末尾追加 `python_executable: str = ""`、`probe_returncode: int | None = None`、`probe_stdout: str = ""`、`probe_stderr: str = ""`。同步 to_dict，已提供非零返回码的 proven 收据拒绝构造。
- [x] probe 返回填入解释器、completed.returncode、stdout/stderr 的前 4096 字符；安全配置和 proven 计算不变。

### Task 3: 验证与提交

- [x] 原两组 PATH 实验和整测试文件通过；运行该文件及 sealed 相关测试、Ruff。
- [x] 检查 diff，确认没有增加 filesystem 放行路径、删安全断言或跳过失败测试。
- [x] 完成独立分支交接，pathspec 提交。记录修复提交作为最终候选依赖。
最终集成阶段由 `docs/handoffs/inflight/fix-instruction-gate-clearance.md` 承接；最终完整门禁结果读取 `~/.finance-runtime/gates/instruction-migration-clearance-20260912/matrix.md`，不以本计划勾选状态作为通过证据。
