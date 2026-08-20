"""Lock the zero-flag ask door: retrieval knobs stay optional.

See docs/superpowers/specs/2026-08-20-finance-agent-door-depth-design.md PR3.
Defaults follow the baseline AskOptions / argparse values; do not flip products.
"""

from __future__ import annotations

import argparse

from dataclasses import fields

from intelligence.cli import build_parser
from intelligence.services.ask_types import AskOptions

_SHARED_RETRIEVAL_FLAGS = {
    "--date",
    "--exports-dir",
    "--kb-wiki",
    "--top-companies",
    "--module-timeout",
    "--wiki-rag-k",
    "--wiki-rag-mode",
    "--wiki-rag-timeout",
    "--kb-mode",
}

_MODULE_FANOUT_FLAGS = {"--modules", "--no-modules", "--no-wiki-rag"}


def _subcommand(parser: argparse.ArgumentParser, command: str) -> argparse.ArgumentParser:
    action = next(
        item for item in parser._actions if isinstance(item, argparse._SubParsersAction)
    )
    return action.choices[command]


def test_ask_options_query_only_is_deep_path() -> None:
    options = AskOptions(query="液冷")
    assert options.use_modules is True
    assert options.use_wiki_rag is True
    assert options.wiki_rag_mode == "hybrid"
    assert options.use_llm is False
    assert options.wiki_rag_index_dir is None
    assert options.modules is None


def test_ask_options_has_no_per_block_include_flags() -> None:
    leaked = {
        item.name
        for item in fields(AskOptions)
        if item.name.startswith("include_") and item.name.endswith("_block")
    }
    assert leaked == set(), leaked


def test_cli_ask_parses_without_retrieval_escape_hatches() -> None:
    args = build_parser().parse_args(["ask", "液冷"])
    assert args.query == "液冷"
    assert args.no_modules is False
    assert args.no_wiki_rag is False
    assert args.wiki_rag_mode == "hybrid"
    assert args.llm is False
    assert args.modules is None
    assert args.kb_mode is None


def test_ask_chat_agent_share_retrieval_flag_names() -> None:
    parser = build_parser()
    for command in ("ask", "chat", "agent"):
        flags = set(_subcommand(parser, command)._option_string_actions)
        missing = _SHARED_RETRIEVAL_FLAGS - flags
        assert not missing, f"{command} missing shared retrieval flags: {missing}"

    agent_flags = set(_subcommand(parser, "agent")._option_string_actions)
    assert "--market-db-path" in agent_flags
    assert not (_MODULE_FANOUT_FLAGS & agent_flags)

    for command in ("ask", "chat"):
        flags = set(_subcommand(parser, command)._option_string_actions)
        missing_fanout = _MODULE_FANOUT_FLAGS - flags
        assert not missing_fanout, f"{command} missing module fan-out flags: {missing_fanout}"
        assert "--market-db-path" not in flags
