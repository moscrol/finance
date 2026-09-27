"""Narrow an audited review sandbox to one writer's explicit output paths.

This preserves the existing read/network policy and refuses unfamiliar write
rules. Host evidence must be outside every writable subtree. A test child's
JUnit is untrusted output; copy it only after the child exits, without following
links. This does not certify the semantics of arbitrary reviewer test code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat


def narrow_write_policy(
    profile: str,
    shared_work: Path,
    *,
    directories: tuple[Path, ...] = (),
    files: tuple[Path, ...] = (),
    protected: tuple[Path, ...] = (),
) -> str:
    def quote(path: Path) -> str:
        return json.dumps(str(path), ensure_ascii=False)

    old_rule = f'(allow file-write* (subpath {quote(shared_work)}) (literal "/dev/null"))'
    rules = [line.strip() for line in profile.splitlines() if line.strip()]
    if rules.count(old_rule) != 1 or rules.count('(deny file-write*)') != 1:
        raise ValueError('unrecognized shared-work write policy')
    if any(line.startswith('(allow file-write') and line != old_rule for line in rules):
        raise ValueError('additional write capability in base profile')
    for path in (*directories, *files, *protected):
        if not path.is_absolute() or path != path.resolve():
            raise ValueError('sandbox paths must be absolute and canonical')
    for guard in protected:
        for directory in directories:
            if guard.is_relative_to(directory) or directory.is_relative_to(guard):
                raise ValueError('writable subtree overlaps protected evidence')
        if any(file == guard or file.is_relative_to(guard) for file in files):
            raise ValueError('writable file overlaps protected evidence')
    selectors = ['(literal "/dev/null")']
    selectors.extend(f'(subpath {quote(p)})' for p in directories)
    selectors.extend(f'(literal {quote(p)})' for p in files)
    return profile.replace(old_rule, '(allow file-write* ' + ' '.join(selectors) + ')')


def snapshot_child_file(source: Path, destination: Path, *, max_bytes: int = 8_000_000) -> None:
    """Snapshot a single-link regular child output to a host-owned, new file."""
    directory = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(source.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PermissionError('child output must be a single-link regular file')
        if info.st_size > max_bytes:
            raise ValueError('child output too large')
        data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError('child output too large')
    with destination.open('xb') as stream:
        stream.write(data)
