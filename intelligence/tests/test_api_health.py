from intelligence.services.kb_rag import rag_runtime_ready



class TestRagRuntimeDependencyIsExecutabilityNotExistence:
    """索引目录在 ≠ 检索跑得起来。

    2026-08-12 实测到这个缺口的代价：``knowledge-base-private/.rag_venv`` 是指向
    ``~/知识库/.rag_venv`` 的符号链接，而那个目录已不存在（链接建于 07-14）。
    kb_search 每次 7ms 抛 FileNotFoundError，被脱敏成「研究过程中出现内部错误」，
    历史 22 次调用 22 次空手（20 次 error/timeout）——**静默停摆约一个月，
    而 health 一直报 vector_index: true**，因为它只判 `vector_index_dir.is_dir()`。

    判据必须对齐**消费方的失败条件**（subprocess 能否拉起解释器），
    不是对齐「文件系统里有没有这个名字」——悬空符号链接、目录、无执行位
    三种情况 `exists()` 的答案各不相同，对 subprocess 却是同一个结果。
    """

    def test_dangling_symlink_reads_as_not_ready(self, tmp_path, monkeypatch) -> None:
        target = tmp_path / "gone" / "python"
        link = tmp_path / "python"
        link.symlink_to(target)
        monkeypatch.setenv("KB_RAG_PYTHON", str(link))

        assert not rag_runtime_ready()

    def test_directory_is_not_an_interpreter(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("KB_RAG_PYTHON", str(tmp_path))

        assert not rag_runtime_ready()

    def test_file_without_exec_bit_reads_as_not_ready(
        self, tmp_path, monkeypatch
    ) -> None:
        """存在但不可执行——`exists()` 会说 True，subprocess 会 PermissionError。"""
        fake = tmp_path / "python"
        fake.write_text("#!/bin/sh\n")
        fake.chmod(0o644)
        monkeypatch.setenv("KB_RAG_PYTHON", str(fake))

        assert not rag_runtime_ready()

    def test_real_executable_reads_as_ready(self, monkeypatch) -> None:
        """反面也要钉：误报 not-ready 会让一个健康的部署被判成坏的。"""
        import sys

        monkeypatch.setenv("KB_RAG_PYTHON", sys.executable)

        assert rag_runtime_ready()


class TestRagReadinessGateCoversTheInterpreter:
    """就绪门禁必须判「解释器能不能跑」，不只判「索引新不新鲜」。

    2026-08-12 的实测教训：`.rag_venv` 悬空期间 kb_search 每次 7ms
    FileNotFoundError，而**两个仪表同时发绿**——health 报 vector_index: true
    （只判索引目录存在）、check_rag_readiness 报「就绪」退出 0（只判索引元数据）。
    一个专门用来判「向量层能不能当证据用」的门禁，漏掉了最基本的那一问。

    本类钉住的是**判据的存在性**，不是它的实现：门禁与 health 必须共用
    ``kb_rag.rag_runtime_ready`` 这一个真相源。两份判据必漂，且漂的时候两边都绿。
    """

    def test_readiness_gate_imports_the_shared_predicate(self) -> None:
        """门禁脚本必须复用同一个判据，不得另写一份。"""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "check_rag_readiness.py"
        ).read_text(encoding="utf-8")

        assert "rag_runtime_ready" in source

    def test_health_and_gate_agree_on_a_dangling_interpreter(
        self, tmp_path, monkeypatch
    ) -> None:
        """同一个坏路径，两处必须得出同一个结论——否则就是两份判据。"""
        dangling = tmp_path / "gone" / "python"
        monkeypatch.setenv("KB_RAG_PYTHON", str(dangling))

        assert rag_runtime_ready() is False

    def test_deploy_script_runs_the_readiness_gate(self) -> None:
        """判据存在但没人调用等于不存在——部署链必须真的跑它。

        这是「授予的额度必须真的传到最下游执行者」的同构：
        只写进脚本不接进流程，比不做更危险（看起来有防护）。
        """
        from pathlib import Path

        deploy = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "deploy_workbench_runtime.sh"
        ).read_text(encoding="utf-8")

        assert "check_rag_readiness.py" in deploy
