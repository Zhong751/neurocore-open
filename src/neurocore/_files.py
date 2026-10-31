"""Bounded local files; package metadata never grants access outside its root."""
import json
import os
from pathlib import Path, PureWindowsPath
import stat


class PackageError(ValueError):
    """A stable, non-content-bearing diagnostic for untrusted local input."""


def relative_name(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise PackageError("path: expected a bounded relative file path")
    parts = value.split("/")
    if (PureWindowsPath(value).drive or "\\" in value
            or any(p in {"", ".", ".."} for p in parts)):
        raise PackageError("path: absolute paths and traversal are forbidden")
    for part in parts:
        if (any(ord(c) < 32 or c in '<>:"|?*' for c in part)
                or part.endswith((".", " ")) or PureWindowsPath(part).is_reserved()):
            raise PackageError("path: unsupported or reserved file name")
    return value


def local_path(value):
    path = Path(value).absolute()
    if ".." in path.parts:
        raise PackageError("path: parent traversal is forbidden")
    # Check ancestors before resolving: resolve() alone hides junctions/symlinks.
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or item.is_junction()
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise PackageError("path: linked or reparse paths are forbidden")
    return path


def child_path(root, name):
    relative_name(name)
    path = local_path(root / name)
    if not path.is_relative_to(root):
        raise PackageError("path: file escapes the selected root")
    return path


def signature(info):
    # Python 3.12 on Windows exposes different ctime semantics through stat
    # and fstat. Compare identity, size and modification time across those APIs.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def read_bytes(path, limit):
    path = local_path(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise PackageError("file: expected a regular file with no hard links")
    if before.st_size > limit:
        raise PackageError("file: size limit exceeded")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if signature(opened) != signature(before):
            raise PackageError("file: changed during inspection; retry when idle")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if (len(data) > limit or signature(after) != signature(before)
            or signature(local_path(path).stat()) != signature(before)):
        raise PackageError("file: changed during inspection; retry when idle")
    return data


def json_object(data, label):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PackageError(f"{label}: duplicate JSON field")
            result[key] = value
        return result

    def invalid_constant(_):
        raise PackageError(f"{label}: invalid JSON constant")

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, PackageError):
            raise
        raise PackageError(f"{label}: invalid UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise PackageError(f"{label}: expected a JSON object")
    return value


def write_new(path, data):
    local_path(path)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
