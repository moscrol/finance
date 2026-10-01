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
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

from scripts.workspace_env import python_path

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
EXPECTED_PY = python_path(REPO)
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


def _git_status_lines() -> list[str]:
    """porcelain 行，**整体不 strip**。

    ``_git`` 对 stdout 做 ``.strip()``——rev-parse 那类单值输出需要它，但
    porcelain 的未暂存改动行形如 ``" M path"``（前两位是 XY 状态、第三位是空格）。
    整体 strip 会吃掉**第一行**的前导空格，随后 ``line[3:]`` 多切一个字符，
    路径变成 ``"ntelligence/services/…"``，前缀匹配失败后被静默丢弃。

    后果不是少列一条路径而已：当它是**唯一**的脏代码文件时 ``dirty`` 变成
    False，收据自称干净树、``check_test_receipt.py`` 判「可采信」——那正是这套
    收据要防的那件事（未提交改动无法被 revision 描述）。

    实测 2026-08-26：judge 修复树里只改 ``intelligence/services/llm_refine.py``
    一个文件，``_code_dirt()`` 返回 ``[]``；同日 17:49 那份收据也因此只列出了
    ``test_grok_cli_judge.py``，漏掉同样未提交的 ``llm_refine.py``。
    """

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


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
    for line in _git_status_lines():
        # porcelain 格式：两位状态 + 空格 + 路径（重命名为 "old -> new"）。
        # 必须用 _git_status_lines：整体 strip 过的输出会让首行少一个字符。
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


# Config-local proof is not inherited by another pytest.main() in this process.
# PID in the environment still blocks inherited subprocesses; neither is a sandbox.
_RECEIPT_OWNER = pytest.StashKey[tuple[str, str]]()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """收集之前先判解释器。用 UsageError 而非 assert：前者输出干净且退出码明确。"""

    path = os.environ.get("FWP_TEST_RECEIPT_PATH")
    previous_owner = os.environ.get("FWP_TEST_RECEIPT_OWNER_PID")
    if path and not previous_owner:
        owner = str(os.getpid())
        config.stash[_RECEIPT_OWNER] = (owner, path)
        os.environ["FWP_TEST_RECEIPT_OWNER_PID"] = owner

        def release_owner() -> None:
            # Cleanup also runs when configure fails, before sessionfinish exists.
            # Restore only our claim; never clear a caller's replacement owner.
            if os.environ.get("FWP_TEST_RECEIPT_OWNER_PID") == owner:
                if previous_owner is None:
                    os.environ.pop("FWP_TEST_RECEIPT_OWNER_PID", None)
                else:
                    os.environ["FWP_TEST_RECEIPT_OWNER_PID"] = previous_owner

        config.add_cleanup(release_owner)

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
    for lock in (REPO / "requirements-consumer.lock",
                 REPO / str(_SPEC.get("development_lock", "requirements-dev.lock"))):
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


def latest_pointer_name(tree: Path) -> str:
    """本棵树专属的 latest 指针文件名。

    规则刻意选得能在 shell 里一行算出来（``tr -c 'A-Za-z0-9._-' '_'``），
    这样 session_facts.sh 不必调 Python 就能找到同一个文件。
    """

    slug = re.sub(r"[^A-Za-z0-9._-]", "_", str(tree))
    return f"latest-{slug}.json"


def _collection_scope(session: pytest.Session) -> dict:
    """收窄旋钮 + 实收数：让一张收据能自证「跑的是多大一片」。

    ``target`` 只是位置参数，``--ignore`` / ``-k`` / ``-m`` / ``--deselect``
    这些真正决定收集面的选项一个都不进收据。
    """

    option = getattr(session.config, "option", None)

    def _get(name: str, default):
        return getattr(option, name, default) if option is not None else default

    return {
        "ignore": list(_get("ignore", None) or []),
        "ignore_glob": list(_get("ignore_glob", None) or []),
        "deselect": list(_get("deselect", None) or []),
        "keyword": _get("keyword", "") or "",
        "markexpr": _get("markexpr", "") or "",
        "maxfail": int(_get("maxfail", 0) or 0),
        "last_failed": bool(_get("lf", False)),
        "collected": int(getattr(session, "testscollected", 0) or 0),
    }


def _write_test_receipt(receipt: dict) -> Path:
    """Immutable run file plus atomic, non-authoritative latest pointers.

    不可变的那张是本轮的权威收据（#814：`FWP_TEST_RECEIPT_PATH` 显式指定或带 uuid 的
    时间戳文件名）。两个 latest 指针只服务被动读者（session_facts.sh、人、agent）。
    """
    directory = Path(os.environ.get("FWP_TEST_RECEIPT_DIR") or _RECEIPT_DIR).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{stamp}-{receipt['revision'][:8]}-{uuid.uuid4().hex[:12]}.json"
    path = Path(os.environ.get("FWP_TEST_RECEIPT_PATH") or directory / filename).expanduser()
    encoded = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    # latest.json 是全机**单个**文件：多棵树并跑时，谁后结束谁覆盖（2026-09-22 两次撞上），
    # 而 session_facts.sh 正是拿它的 revision 与本树 HEAD 比——同 base 的两棵干净树
    # revision 天然相等，它会拿**别人跑的**读数劝你「不必重跑」。故再写一份按树区分的
    # 指针；latest.json 保留，旧读法不破。两份都原子替换，读者永远看不到半截文件。
    _replace_atomically(directory, "latest.json", encoded)
    _replace_atomically(directory, latest_pointer_name(REPO), encoded)
    return path


def _replace_atomically(directory: Path, name: str, encoded: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".latest-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        os.replace(temporary, directory / name)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """落一份机器可读收据。

    刻意**不**因写收据失败而影响测试结果：收据是观测设施，观测设施故障不该改变
    被观测对象的结论。任何异常静默跳过，但会在终端提示（不静默到无痕）。
    """

    if os.environ.get(_RECEIPT_ENV) == "0":
        return
    path = os.environ.get("FWP_TEST_RECEIPT_PATH")
    if path and (
        os.environ.get("FWP_TEST_RECEIPT_OWNER_PID") != str(os.getpid())
        or session.config.stash.get(_RECEIPT_OWNER, None) != (str(os.getpid()), path)
    ):
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
    # 带上 xfailed/xpassed：没有它们，collected 与读数天然对不平，
    # 「收了 N 条只跑了 M 条」这种截断就永远解释得通、也就永远查不出来。
    counts = {
        key: len(stats.get(key, []))
        for key in ("passed", "failed", "error", "skipped", "xfailed", "xpassed")
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
        "worktree_dirty_total": len(_git_status_lines()),
        "dependency_gate_bypassed": os.environ.get(_ESCAPE) == "1",
        # ——— 读数本身 ———
        "target": " ".join(session.config.args or []),
        # target 只是**位置参数**：`pytest -q` 与 `pytest -q --ignore=scripts/archive -k x`
        # 写出来的收据一模一样，「全量绿」无法从收据自身审计收集面。把收窄旋钮与实收数
        # 一并记账；collected 与 counts 对不上，就是被截断过（maxfail / -x / 收集期中断）。
        "scope": _collection_scope(session),
        "counts": counts,
        # 存 ID 而非只存个数：修好 3 条 + 引入 3 条 = 总数不变。
        # 失败归属必须按名字比，这是 baseline_diff.py 学到的同一条。
        "failed_ids": failed_ids,
        "exit_status": int(exitstatus),
        "finished_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
    }
    try:
        path = _write_test_receipt(receipt)
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

# 证券名单词典（entity_anchor 第二本词典）在测试里必须显式禁用，不能只 delenv：
# 它的默认路径经 data_repo_root() 回退解析，**不设任何 env 也能命中真实生产
# DuckDB**——在有库的机器上，实体锚定测试会随全市场股票名单变化而变（#310
# 刚修过的同一种环境依赖病）。需要该词典的测试自己 setenv 指向 tmp 库，
# 或直接给 resolve_entity_anchor 传 securities_db_path 参数。
_FORCED_TEST_ENV = (
    ("ENTITY_ANCHOR_SECURITIES_DB", "0"),
    # INV-R1「模型可见即已落账」在测试里是硬断言：两条 loop 每次请求前都对账，
    # 不一致即抛（生产只记账不炸）。全量套件里每一次脚本化模型请求都因此在验它，
    # 不另写一套「覆盖」它的用例。见 intelligence/services/episode_messages.py 文首。
    ("FORESIGHT_STRICT_DERIVATION", "1"),
    # 语义判官生产默认关（2026-09-27，intelligence/services/judge_mode.py）。套件里大量用例
    # 注入 judge_fn 验判官路径，在这里显式开着；验「默认关」的用例自己 delenv。
    ("ASK_SEMANTIC_JUDGE", "llm"),
)


# ⚠ 必须在**模块级**先清一次，不能只靠下面的 autouse 夹具（2026-08-12 实测补）：
#
#   夹具是每个用例执行前跑的，而**导入期比它早得多**。实测
#   `intelligence/tests/test_acceptance_trace_capture.py` 里一句
#   `from intelligence.api.app import ...` ——**光是导入这个模块就会碰真人目录**
#   （app 在 import 时就初始化了用户态存储）。于是 `pytest --collect-only`
#   一次都不执行任何用例，真人目录 mtime 照样变。
#
#   这也是为什么加了夹具之后「全量跑仍在动真人目录」：夹具没错，是**时机**错了。
#   定位手法值得记：逐用例探针一无所获 → 换 `--collect-only` 复现 → 证明是导入期 →
#   再按收集单元归因到具体文件。**副作用发生在哪个阶段，探针就得架在哪个阶段。**
#
# conftest.py 由 pytest 在收集任何测试模块之前导入，所以这里是最早的可控点。
for _name in _PERSONAL_STATE_ENV:
    os.environ.pop(_name, None)
for _name, _value in _FORCED_TEST_ENV:
    os.environ[_name] = _value


@pytest.fixture(autouse=True)
def _isolate_personal_state_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例再兜一次底，防止中途有代码把变量设回去。

    需要这些变量的测试自己 ``monkeypatch.setenv`` 显式设回去——测试内的设置
    发生在本夹具之后，天然覆盖。
    """
    for name in _PERSONAL_STATE_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in _FORCED_TEST_ENV:
        monkeypatch.setenv(name, value)


def _make_tree_removable(root: Path) -> None:
    """把 root 及其下所有目录补回 u+rwx（软链不跟、不改），尽力而为。"""

    def fix(path: str) -> None:
        try:
            mode = os.lstat(path).st_mode
            if stat.S_ISDIR(mode) and mode & stat.S_IRWXU != stat.S_IRWXU:
                os.chmod(path, stat.S_IMODE(mode) | stat.S_IRWXU)
        except OSError:
            pass

    fix(str(root))
    for dirpath, dirnames, _ in os.walk(root):
        for name in dirnames:  # 自顶向下：先修子目录，os.walk 才进得去
            fix(os.path.join(dirpath, name))


@pytest.fixture(autouse=True)
def _leave_tmp_path_removable(request: pytest.FixtureRequest):
    """用例收尾把 tmp_path 里的只读目录改回可写，免得污染 pytest 的共享临时根。

    导出 / 冻结 / 封存类产品代码会把目录设成 0o555（这是它们要测的行为）。pytest 删旧
    编号目录时，``rm_rf`` 的权限修复只向上修**文件**的父目录，删不动只读子目录，于是
    改名成 ``garbage-*`` 留在 ``$TMPDIR/pytest-of-<user>/``，之后**每次**启动都重扫重删
    一遍。2026-09-30 Mac 上积了约 1.4 万条目、200 多个只读子目录，拖慢并发门禁到超时。
    会留只读目录的用例分散在多个文件，逐条补 finally 会漏掉以后新增的，所以收在这一层。
    """
    if "tmp_path" not in request.fixturenames:
        yield
        return
    root = request.getfixturevalue("tmp_path")
    yield
    # 本夹具在 tmp_path 之后登记收尾，LIFO 下先于它执行，目录此刻一定还在。
    _make_tree_removable(root)


# ---------------------------------------------------------------------------
# 非 macOS 机器上的 zsh 依赖（2026-10-01 质检 P2）
#
# launchd / 交易日守卫 / method_flywheel 等 49 条测试直接执行 /bin/zsh 或以
# ``#!/bin/zsh`` 为 shebang 的脚本。Linux（CI、沙箱）上没有 /bin/zsh，它们报
# FileNotFoundError，一片红淹没真问题。这里只把**恰好是「zsh 不存在」**的失败转成
# skip：机器上有 /bin/zsh（你的 Mac）时永不触发，其他任何失败原样上报。
# 不用模块级 skipif，是因为同文件里不依赖 zsh 的测试在 Linux 上照样该跑。
# ---------------------------------------------------------------------------

_ZSH = "/bin/zsh"


def _is_missing_zsh(exc: BaseException) -> bool:
    if not isinstance(exc, FileNotFoundError) or Path(_ZSH).exists():
        return False
    missing = str(getattr(exc, "filename", "") or "")
    if missing == _ZSH:
        return True
    # 执行 shebang 为 #!/bin/zsh 的脚本：内核找不到解释器，errno 报的是脚本本身。
    try:
        with open(missing, "rb") as handle:
            return handle.readline().strip() == b"#!" + _ZSH.encode()
    except OSError:
        return False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item):
    outcome = yield
    excinfo = outcome.excinfo
    if excinfo is not None and _is_missing_zsh(excinfo[1]):
        outcome.force_exception(
            pytest.skip.Exception(f"需要 {_ZSH}（macOS 默认 shell），本机没有", _use_item_location=True)
        )
