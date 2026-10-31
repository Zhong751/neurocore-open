"""Independent identities with frozen seed snapshots and explicit M1 writers."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from ._files import PackageError, child_path, json_object, local_path, read_bytes, write_new
from ._memory_check import inspect_memory
from .characters import CharacterPackage, MANIFEST_LIMIT, load_character
from .memory import MemoryReader, MemoryStore


class InstanceError(PackageError):
    """Missing, incomplete, incompatible or unsafe instance."""


def _hashes(character):
    return {name: hashlib.sha256(data).hexdigest() for name, data in character.files.items()}


@dataclass(frozen=True)
class Instance:
    root: Path
    instance_id: str
    created_at: str
    character: CharacterPackage
    memory_store_id: str

    @property
    def memory_directory(self):
        return self.root / "memory"

    def reader(self):
        load_instance(self.root)
        return MemoryReader(self.memory_directory, brain_id=self.instance_id)

    def writer(self):
        # Explicit write access, after verifying identity and snapshot binding.
        load_instance(self.root)
        return MemoryStore(self.memory_directory, brain_id=self.instance_id)


def _uuid(value):
    return isinstance(value, str) and len(value) == 32 and uuid.UUID(value).hex == value


def load_instance(directory):
    """Strictly read-only load; absent or partial state is never initialized."""
    try:
        root = local_path(directory)
        value = json_object(read_bytes(child_path(root, "instance.json"), MANIFEST_LIMIT), "instance-json")
        if set(value) != {"format_version", "instance_id", "created_at", "character_hashes", "memory_store_id"}:
            raise InstanceError("instance-fields: missing or unknown field")
        if type(value["format_version"]) is not int or value["format_version"] != 1:
            raise InstanceError("instance-version: only format_version 1 is supported")
        if not _uuid(value["instance_id"]) or not _uuid(value["memory_store_id"]):
            raise InstanceError("instance-identity: expected canonical UUID hex")
        if not isinstance(value["created_at"], str):
            raise InstanceError("instance-time: expected a timezone-aware ISO timestamp")
        try:
            stamp = datetime.fromisoformat(value["created_at"])
            if stamp.utcoffset() is None:
                raise ValueError
        except ValueError:
            raise InstanceError("instance-time: expected a timezone-aware ISO timestamp") from None
        character = load_character(child_path(root, "character"))
        if value["character_hashes"] != _hashes(character):
            raise InstanceError("instance-snapshot: character files differ from the creation snapshot")
        inspect_memory(child_path(root, "memory"), value["instance_id"], value["memory_store_id"])
        return Instance(root, value["instance_id"], value["created_at"], character, value["memory_store_id"])
    except InstanceError:
        raise
    except PackageError as exc:
        raise InstanceError(str(exc)) from None
    except (OSError, sqlite3.Error, ValueError, TypeError):
        raise InstanceError("instance-files: missing, incomplete, unreadable or corrupt instance") from None


def create_instance(character_path, instance_dir=None):
    """Reserve a fresh directory; publish instance.json only after all data passes."""
    character = load_character(character_path)
    instance_id = uuid.uuid4().hex
    try:
        if instance_dir is None:
            parent = local_path(Path.cwd() / "instances")
            parent.mkdir(mode=0o700, exist_ok=True)
            root = local_path(parent / instance_id)
        else:
            root = local_path(instance_dir)
        if not root.parent.is_dir():
            raise InstanceError("instance-parent: destination parent must already exist")
        # mkdir is the exclusive reservation, including against concurrent creators.
        # Never reuse an existing empty directory or delete a failed target.
        root.mkdir(mode=0o700)
        snapshot = child_path(root, "character")
        snapshot.mkdir(mode=0o700)
        for name, data in character.files.items():
            path = child_path(snapshot, name)
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            write_new(path, data)
        memory_dir = child_path(root, "memory")
        store = MemoryStore.create(memory_dir, brain_id=instance_id)
        store_id = store.authority()["store_id"]
        frozen = load_character(snapshot)
        if _hashes(frozen) != _hashes(character):
            raise InstanceError("instance-snapshot: copy verification failed")
        inspect_memory(memory_dir, instance_id, store_id)
        created_at = datetime.now(timezone.utc).isoformat()
        manifest = dict(format_version=1, instance_id=instance_id, created_at=created_at,
                        character_hashes=_hashes(frozen), memory_store_id=store_id)
        pending = child_path(root, ".instance.pending")
        write_new(pending, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        # Atomic completion marker inside the newly reserved directory.
        pending.rename(child_path(root, "instance.json"))
        return Instance(root, instance_id, created_at, frozen, store_id)
    except FileExistsError:
        raise InstanceError("instance-exists: refusing to overwrite existing data") from None
    except InstanceError:
        raise
    except PackageError as exc:
        raise InstanceError(str(exc)) from None
    except (OSError, sqlite3.Error, ValueError):
        raise InstanceError("instance-create: creation failed; any incomplete destination is retained") from None
