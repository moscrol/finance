"""intelligence/tests 共享夹具。"""

import pytest


@pytest.fixture
def numeric_delete_mode(monkeypatch):
    """回滚路径：数值条件无出处时整句删（``FINANCE_NUMERIC_CONDITION_MARK=0``）。

    2026-09-28 起默认是标注模式（留句 + 点名待核的数）。用这个夹具的测试钉的是删除
    语义本身，或借数值句当机械删句的触发器去测删句后的修稿 / 编号 / 槽位机制；
    标注模式另有 ``test_numeric_condition_mark.py``。
    """

    monkeypatch.setenv("FINANCE_NUMERIC_CONDITION_MARK", "0")
