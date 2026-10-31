"""Read-only diagnostics. No writers, recovery, model connections or discovery."""
from dataclasses import dataclass

from ._files import PackageError, child_path, local_path
from .characters import load_character
from .instances import load_instance


@dataclass(frozen=True)
class Check:
    status: str
    name: str
    message: str


def _assets(character):
    available = len(character.files) - 2
    if character.missing_assets:
        return Check("WARN", "assets", f"{len(character.missing_assets)} optional assets missing; instance creation is allowed")
    if not available:
        return Check("WARN", "assets", "No optional assets supplied; instance creation is allowed")
    return Check("PASS", "assets", f"{available} optional assets readable; no rendering or execution performed")


def check_character(directory):
    try:
        character = load_character(directory)
        return [Check("PASS", "character", "Version 1 manifest and UTF-8 seed are valid"),
                Check("PASS", "paths", "Declared files are bounded local regular files"),
                _assets(character)]
    except PackageError as exc:
        return [Check("FAIL", "character", str(exc))]


def check_instance(directory):
    try:
        instance = load_instance(directory)
        return [Check("PASS", "identity", "Persistent identity and M1 store binding verified"),
                Check("PASS", "snapshot", "Character files match the creation hashes"),
                Check("PASS", "memory", "M1 schema, SQLite structure and foreign keys checked in RAM"),
                _assets(instance.character)]
    except PackageError as exc:
        return [Check("FAIL", "instance", str(exc))]


def check_current(directory):
    try:
        root = local_path(directory)
        if child_path(root, "instance.json").exists():
            return check_instance(root)
        if child_path(root, "character.json").exists():
            return check_character(root)
        return [Check("FAIL", "target", "No instance.json or character.json in current directory; select --instance or --character")]
    except (PackageError, OSError):
        return [Check("FAIL", "target", "Unsafe or inaccessible current directory")]
