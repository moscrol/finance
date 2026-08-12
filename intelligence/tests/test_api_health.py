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
