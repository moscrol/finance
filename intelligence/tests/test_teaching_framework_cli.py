from scripts.teaching_framework import parser


def test_cli_exposes_slice_one_commands() -> None:
    for command in ("build-labels", "build-succession", "report"):
        args = parser().parse_args([command])
        assert args.command == command
        assert callable(args.func)
