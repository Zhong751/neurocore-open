"""Version 1 character seeds: initial guidance, never historical evidence."""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ._files import PackageError, child_path, json_object, local_path, read_bytes, relative_name

CHARACTER_VERSION = 1
MANIFEST_LIMIT = 64 * 1024
SEED_LIMIT = 256 * 1024
ASSET_LIMIT = 8 * 1024 * 1024
PACKAGE_LIMIT = 32 * 1024 * 1024


class CharacterError(PackageError):
    """Invalid or inaccessible character package."""


@dataclass(frozen=True)
class CharacterPackage:
    root: Path
    name: str
    seed: str
    files: Mapping[str, bytes]
    missing_assets: tuple[str, ...]


def load_character(directory):
    """Read only the manifest and declared files; never execute or render assets."""
    try:
        root = local_path(directory)
        manifest = read_bytes(child_path(root, "character.json"), MANIFEST_LIMIT)
        value = json_object(manifest, "character-json")
        required = {"format_version", "name", "seed"}
        if not required <= value.keys():
            raise CharacterError("character-fields: missing " + ", ".join(sorted(required - value.keys())))
        if value.keys() - (required | {"assets"}):
            raise CharacterError("character-fields: unknown field")
        if type(value["format_version"]) is not int or value["format_version"] != CHARACTER_VERSION:
            raise CharacterError("character-version: only format_version 1 is supported")
        name = value["name"]
        if (not isinstance(name, str) or not name.strip() or len(name) > 100
                or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in name)):
            raise CharacterError("character-name: expected nonempty text of at most 100 characters")
        seed = relative_name(value["seed"])
        if not seed.endswith(".md"):
            raise CharacterError("character-seed: expected a .md file")
        assets = value.get("assets", [])
        if not isinstance(assets, list) or len(assets) > 16:
            raise CharacterError("character-assets: expected at most 16 optional paths")
        paths = ["character.json", seed, *[relative_name(p) for p in assets]]
        folded = [p.casefold() for p in paths]
        if len(set(folded)) != len(folded) or any(
                a.startswith(b + "/") for a in folded for b in folded if a != b):
            raise CharacterError("character-paths: duplicate or overlapping file paths")
        files = {"character.json": manifest}
        try:
            seed_bytes = read_bytes(child_path(root, seed), SEED_LIMIT)
        except FileNotFoundError:
            raise CharacterError("character-seed: required seed file is missing") from None
        try:
            seed_text = seed_bytes.decode("utf-8")
        except UnicodeError:
            raise CharacterError("character-seed: expected UTF-8 Markdown") from None
        if not seed_text.strip() or "\x00" in seed_text:
            raise CharacterError("character-seed: expected nonempty Markdown without NUL")
        files[seed] = seed_bytes
        missing = []
        for asset in assets:
            path = child_path(root, asset)
            try:
                files[asset] = read_bytes(path, ASSET_LIMIT)
            except FileNotFoundError:
                missing.append(asset)
        if sum(map(len, files.values())) > PACKAGE_LIMIT:
            raise CharacterError("character-size: package exceeds 32 MiB")
        return CharacterPackage(root, name, seed, MappingProxyType(files), tuple(missing))
    except CharacterError:
        raise
    except PackageError as exc:
        raise CharacterError(str(exc)) from None
    except (OSError, ValueError):
        raise CharacterError("character-files: missing or inaccessible package files") from None
