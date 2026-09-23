"""One rejection corpus shared by both archive entry points."""

INVALID_REPOSITORY_PATHS = (
    ".",
    "..",
    "../archive",
    "/archive",
    "archive/",
    "archive/../archive",
    ":(glob)*",
    ":!archive",
    ".git/config",
)
