"""测试环境门禁：解释器不对就**在收集之前**失败，并说清该用哪个。

## 为什么必须在这一层

本仓有两个 python，依赖完全不同：

    宿主 /usr/bin/python3        无 fastapi / agents / duckdb / yaml …
    .venv-workbench/bin/python   全部具备（AGENTS.md 与 CLAUDE.md 都写了用它）

用错的后果不是"跑不了"，而是**跑出一个看起来合理的错读数**。2026-08-10 实测，
同一棵树同一时刻：

    宿主 python3        71 failed / 3819 passed
    .venv-workbench     14 failed / 3996 passed

差出来的 57 条全是环境噪声。而当时的结论是「71 条分布在 11 个文件、本轮只碰
1 个文件，所以非本轮引入」——推理过程没错，输入数字是错的，于是错读数还通过了
一次看似严谨的归属分析，差点被写进提交记录当证据。

这个洞此前**已经有**一道门禁在管（`scripts/check_agent_workspace_facts.py`，
挂在 pre-commit 上），它确实抓住了这次错误。但它只在 `git commit` 时才说话——
那时二十多次错误的 pytest 已经跑完，结论已经形成。**门禁的位置必须在错误
产生的那一刻，而不是错误被提交的那一刻。**

pytest 启动时读 rootdir 的 conftest.py，对**所有**调用方一律生效：
agent、人、CI、`python -m pytest`、IDE 里点运行。这是本仓唯一一个"任何人跑测试
都必然经过"的位置，所以检查放这里。

## 为什么按"能力"判而不是按"路径"判

判据是**依赖在不在**，不是 `sys.executable` 等不等于某个字面路径。原因：
worktree 里跑测试时用的是主树的 `.venv-workbench/bin/python`（AGENTS.md:67），
路径与所在树不同；将来若换 venv 名字，按路径判会误伤一个完好的环境。
按能力判则永远只在"真的跑不动"时才拦，且拦的理由就是失败的真实原因。

要绕过（例如故意在裸环境验证依赖缺失时的行为）：`FWP_ALLOW_ANY_PYTHON=1`。
绕过时仍然打印横幅，不会静默。
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.metadata as _md
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent

# 唯一真本源。初版把清单硬编码在这里、并在 docstring 里写「与
# check_agent_workspace_facts.py 两处都改才算改完」——当天就漂了（uvicorn 与 ruff
# 只在其中一处）。用一句提醒去同步两份清单，正是这两道门禁本身要治的病。
_SPEC_PATH = REPO / "test-environment.json"


def _spec() -> dict[str, object]:
    """读环境契约。**只用 json + pathlib**：conftest 在收集前执行，此刻不能假设
    ``intelligence/`` 可 import（缺依赖时正是它要报错的场景），`scripts/` 也不是包。
    """

    try:
        return json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_SPEC = _spec()
EXPECTED_PY = Path(
    str(_SPEC.get("interpreter"))
    if _SPEC.get("interpreter")
    else REPO / ".venv-workbench" / "bin" / "python"
)
REQUIRED: tuple[str, ...] = tuple(_SPEC.get("required_modules") or ())
_ESCAPE = str(_SPEC.get("escape_env_var") or "FWP_ALLOW_ANY_PYTHON")


def _missing() -> tuple[str, ...]:
    """当前解释器里装不上的必需依赖。"""

    return tuple(m for m in REQUIRED if importlib.util.find_spec(m) is None)


def _git(*args: str) -> str:
    """在**本仓根**执行 git。模块级而非嵌套：收据钩子也要用它取 revision。"""

    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


# 能影响被测行为的路径前缀。判据是「改了它，测试结果就可能变」——
# 代码、测试、依赖契约、pytest 配置。
#
# 反面：`docs/`、`market_feature_store/exports/`、`复盘/`、`skills/*/state/`、
# `work/` 是每日 ingest 的正常产物，本仓工作区长期有 44 个这类脏文件。把它们
# 计入会让收据永远 dirty、校验器永远建议重跑——那比没有门禁更糟。
# 不在这里硬编码：两处各写一份清单必漂——本仓当天已在依赖清单上栽过一次
# （conftest 与 check_agent_workspace_facts 各存一份，uvicorn/ruff 只在其中一处）。
# 与 scripts/check_test_receipt.py 共读 test-environment.json 同两个字段。
_CODE_PREFIXES = tuple(_SPEC.get("code_path_prefixes") or ())

# `market_feature_store/` 整体算代码，但它下面的 exports/ 是数据产物，要挖掉。
_DATA_EXCEPTIONS = tuple(_SPEC.get("data_path_exceptions") or ())


def _code_dirt() -> list[str]:
    """未提交改动里**能影响被测行为**的那些路径，排序后返回。

    只看代码/测试/契约/配置。收窄依据是实验而非推理：那 44 个长期脏文件中有 9 个
    被测试按路径提到，全部是 ``tmp_path`` 自建夹具或字符串字面量，无一读取真实
    脏文件；实测这 9 个测试在当前脏树上 25 passed。
    """

    out: list[str] = []
    for line in (_git("status", "--porcelain") or "").splitlines():
        if not line.strip():
            continue
        # porcelain 格式：两位状态 + 空格 + 路径（重命名为 "old -> new"）。
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith(_CODE_PREFIXES):
            continue
        if path.startswith(_DATA_EXCEPTIONS):
            continue
        out.append(path)
    return sorted(out)


def _revision() -> str:
    """自述 revision——`14 failed` 单独看无法复核是对哪棵树哪个提交成立的。"""

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    rev = _git("rev-parse", "--short", "HEAD") or "(unknown)"
    dirty = " +未提交改动" if _git("status", "--porcelain") else ""
    return f"{branch} @ {rev}{dirty}"


def pytest_configure(config: pytest.Config) -> None:
    """收集之前先判解释器。用 UsageError 而非 assert：前者输出干净且退出码明确。"""

    missing = _missing()
    if not missing:
        return

    hint = (
        f"改用  {EXPECTED_PY} -m pytest ..."
        if EXPECTED_PY.exists()
        else f"⚠ 预期解释器不存在：{EXPECTED_PY}（环境本身需要修）"
    )
    detail = (
        f"\n解释器缺少必需依赖：{', '.join(missing)}"
        f"\n  当前解释器 : {sys.executable}"
        f"\n  应当使用   : {EXPECTED_PY}"
        f"\n"
        f"\n这不是「环境缺包」，是**解释器用错了**——这些包在 .venv-workbench 里都有。"
        f"\n继续跑下去不会得到空结果，而会得到一个偏高的失败数（实测 71 vs 14），"
        f"\n那个数字看起来完全合理，足以支撑一次错误的归属分析。"
        f"\n"
        f"\n{hint}"
        f"\n确实要在当前解释器上跑（例如故意验证缺依赖时的行为）：{_ESCAPE}=1"
    )
    if os.environ.get(_ESCAPE) == "1":
        print(f"\n⚠ {_ESCAPE}=1 已放行，但读数不可与正常环境比较：{detail}\n")
        return
    raise pytest.UsageError(detail)


def pytest_report_header() -> list[str]:
    """让每一次读数自带出处。

    「凡引用测试计数当证据，必须同时写明解释器路径」——把它做成自动输出，
    而不是指望调用方记得写。注意 `--no-header` 会压掉本行，引用计数时别加它。
    """

    lines = [f"解释器: {sys.executable}", f"树: {REPO}  {_revision()}"]
    if os.environ.get(_ESCAPE) == "1":
        lines.append(f"⚠ {_ESCAPE}=1 —— 依赖门禁已被绕过，读数不可跨环境比较")
    return lines


# ---------------------------------------------------------------------------
# 读数收据：让下一个 agent 不必重跑就能判断「这个读数能不能用」
#
# 多 agent 协作里反复出现的浪费：上一个 agent 报「3943 passed」，下一个不采信、
# 重跑一遍。这不是不礼貌，是**理性反应**——那个数字没有说明它在哪个解释器、
# 哪棵树、哪个 revision 上得出，因此不可复核。而 2026-08-10 的实测证明这种怀疑
# 是必要的：同一棵树，宿主 python3 得 71 failed，.venv-workbench 得 14 failed。
#
# 解决方向不是「互相信任」（做不到，也不该做），而是**把验证成本降到几乎为零**：
# 结论自带它成立的条件，下一个 agent 比对条件即可决定采信还是重跑。
# 业界叫 provenance（来源溯源）。核心一句话：结论必须携带它成立的条件。
#
# 上面的 report_header 已经在做这件事，但那是给人读的文本。收据是机器可读版，
# 供 scripts/check_test_receipt.py 做「能不能采信」的判定。
# ---------------------------------------------------------------------------

_RECEIPT_DIR = Path.home() / ".finance-runtime" / "test-receipts"
_RECEIPT_ENV = "FWP_TEST_RECEIPT"


def _dependency_fingerprint() -> str:
    """当前环境已安装发行版的指纹。

    只取**锁文件里声明的那些包**的版本，而不是整个 site-packages：后者含 pytest
    插件、ipython 之类与被测行为无关的东西，噪声会让指纹永远对不上，于是校验器
    永远建议重跑——那等于没做。
    """

    names = tuple(_SPEC.get("required_modules") or ())
    lock = REPO / "requirements-consumer.lock"
    if lock.is_file():
        pinned = [
            line.split("==")[0].strip()
            for line in lock.read_text(encoding="utf-8").splitlines()
            if "==" in line and not line.startswith("#")
        ]
        names = tuple(sorted({*names, *pinned}))
    parts = []
    for name in names:
        try:
            parts.append(f"{name}=={_md.version(name)}")
        except _md.PackageNotFoundError:
            parts.append(f"{name}==<缺失>")
    blob = ";".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """落一份机器可读收据。

    刻意**不**因写收据失败而影响测试结果：收据是观测设施，观测设施故障不该改变
    被观测对象的结论。任何异常静默跳过，但会在终端提示（不静默到无痕）。
    """

    if os.environ.get(_RECEIPT_ENV) == "0":
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    stats = reporter.stats
    failed_ids = sorted(
        report.nodeid
        for key in ("failed", "error")
        for report in stats.get(key, [])
        if hasattr(report, "nodeid")
    )
    counts = {
        key: len(stats.get(key, []))
        for key in ("passed", "failed", "error", "skipped")
    }
    receipt = {
        # ——— 判定采信所需的条件（校验器逐条比对这些）———
        "interpreter": sys.executable,
        "python_version": platform.python_version(),
        "dependency_fingerprint": _dependency_fingerprint(),
        "tree": str(REPO),
        "revision": _git("rev-parse", "HEAD") or "(unknown)",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)",
        # dirty=True 时收据只能用于「本机此刻」，不可跨 agent 采信：
        # 未提交改动无法被 revision 描述，别人无从复现同一份代码。
        #
        # 但判据不能是**全树**脏。本仓工作区长期有 44 个脏文件（复盘台账、
        # market_feature_store/exports、复盘/ 下的 HTML 产物等），它们是每日
        # ingest 的正常产物，与消费侧代码无关。若按全树判，收据将**永远** dirty，
        # 于是校验器永远建议重跑——永远发红的门禁比没有门禁更糟，它训练人忽略它。
        #
        # 收窄依据是实验，不是推理：那 44 个脏文���里有 9 个被测试文件按路径提到，
        # 全部是 `tmp_path` 自建夹具或字符串字面量，无一读取真实脏文件；实测这
        # 9 个测试在当前脏树上 25 passed。故只把**能影响被测行为的路径**计入。
        "dirty": bool(_code_dirt()),
        # 完整脏文件数另存，便于人判断「这棵树整体有多脏」而不参与采信判定。
        "dirty_paths": _code_dirt(),
        "worktree_dirty_total": len(
            [ln for ln in (_git("status", "--porcelain") or "").splitlines() if ln]
        ),
        "dependency_gate_bypassed": os.environ.get(_ESCAPE) == "1",
        # ——— 读数本身 ———
        "target": " ".join(session.config.args or []),
        "counts": counts,
        # 存 ID 而非只存个数：修好 3 条 + 引入 3 条 = 总数不变。
        # 失败归属必须按名字比，这是 baseline_diff.py 学到的同一条。
        "failed_ids": failed_ids,
        "exit_status": int(exitstatus),
        "finished_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
    }
    try:
        _RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        path = _RECEIPT_DIR / f"{stamp}-{receipt['revision'][:8]}.json"
        path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (_RECEIPT_DIR / "latest.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        reporter.write_line(f"读数收据: {path}")
    except OSError as exc:
        reporter.write_line(f"⚠ 收据未写出（不影响测试结论）: {exc}")


# --------------------------------------------------------------------------- #
# 环境隔离：把「本机个人状态」类环境变量挡在测试之外
# --------------------------------------------------------------------------- #
# 2026-08-11 实测的事故（15 条常年失败里的 11 条，根因都是这个）：
#
#   本机为了「两台机器共享一个大脑」，真实设置了这三个变量（值指向云同步 vault
#   与真人 user_id，故此处不抄具体路径——注释里的绝对路径同样会过期）：
#       FORESIGHT_USERS_DIR   → 云同步盘上的大脑目录
#       FORESIGHT_USER        → 真人 user_id
#       SUBCONSCIOUS_VAULT    → Obsidian 沉淀 vault 根
#   而 userspace.users_dir() / resolve_user_id() 是**运行时**读 env 的（这是对的，
#   跨机同步就靠它）。于是不显式指定用户的测试直接落到**真人的目录**：
#
#   · test_subconscious 断言 len(buf)==1，实际读到 913 条——那是真实的会话缓冲
#   · 断言 judgments_path 不存在，实际 True——真实目录里本来就有
#   · 断言 weight==1.5，实际 1.0——读到的是真人数据
#   · 更糟的是**写**：实测 .foresight/tester/ 与 .foresight/alice/ 被测试创建，
#     真人目录 mtime 也被改动。这些还会被云同步推到另一台机器。
#
# 所以这不只是「测试挂了」，是**测试在污染生产数据**。失败本身反而是唯一的警报。
#
# 为什么用 delenv 而不是重定向到 tmp_path：
#   test_userspace 断言的就是「没设 env 时应落在 userspace.USERS_DIR」——
#   删掉变量正好恢复它想测的那条路径。重定向到 tmp 会让这些断言换一种方式失败。
#
# 为什么放 conftest 而不是逐个测试改：
#   逐个改只治已知的 5 个文件，下一个忘了隔离的测试照样直连真人数据，
#   而且**失败方式是读到真数据后断言不符**——看起来像业务 bug，不像环境问题，
#   会把人引向错误的方向（这 15 条挂了很久没人定位，就是这个原因）。
#   放这里让「密封」成为默认，显式需要时各测试自己 monkeypatch.setenv 覆盖回来
#   （test_workbench_api.py 里 20 多处已经是这个正确写法，不受影响）。
_PERSONAL_STATE_ENV = (
    "FORESIGHT_USERS_DIR",  # 大脑目录重定位（云同步盘）
    "FORESIGHT_USER",  # 默认 user_id
    "SUBCONSCIOUS_VAULT",  # Obsidian 沉淀 vault 根
)


@pytest.fixture(autouse=True)
def _isolate_personal_state_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认清掉「指向真人数据」的环境变量，让测试密封。

    需要这些变量的测试自己 ``monkeypatch.setenv`` 显式设回去——测试内的设置
    发生在本夹具之后，天然覆盖。
    """
    for name in _PERSONAL_STATE_ENV:
        monkeypatch.delenv(name, raising=False)
