"""Synthetic character, identity, creation and strictly read-only doctor checks."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from neurocore.characters import CharacterError, load_character
from neurocore.doctor import check_character, check_instance
from neurocore.instances import InstanceError, create_instance, load_instance
from neurocore.memory import MemoryError, MemoryStore


class InstanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.character = self.root / "synthetic-character"
        self.character.mkdir()
        self.manifest = {"format_version": 1, "name": "Synthetic Sample",
                         "seed": "seed.md"}
        self.seed = ("# Synthetic seed\n\nVoice: direct.\n\nInitial interest: patterns.\n"
                     "\nInteraction: ask when unclear.\n\nExample: a fictional greeting.\n")
        (self.character / "seed.md").write_text(self.seed, encoding="utf-8", newline="\n")
        self.write_manifest()

    def write_manifest(self, **changes):
        value = {**self.manifest, **changes}
        (self.character / "character.json").write_text(json.dumps(value), encoding="utf-8")

    @staticmethod
    def inventory(root):
        """Detect writes and new sidecars while excluding read-access timestamps."""
        if not root.exists():
            return None
        return {str(path.relative_to(root)): (
                    "directory" if path.is_dir() else "file",
                    path.stat().st_mtime_ns,
                    None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest())
                for path in [root, *sorted(root.rglob("*"))]}

    def assert_healthy(self, results):
        self.assertTrue(results)
        self.assertTrue(all(check.status in {"PASS", "WARN", "FAIL"} for check in results))
        self.assertFalse(any(check.status == "FAIL" for check in results), results)

    def assert_failed(self, results):
        self.assertTrue(any(check.status == "FAIL" for check in results), results)

    @staticmethod
    def append_sample(instance, content="Synthetic event alpha."):
        return instance.writer().append_event(
            event_id="same-event-id", source_id="synthetic-source", source_type="synthetic",
            speaker_id="synthetic-user", role="user", provenance="user_statement",
            conversation_id="synthetic-conversation", content=content,
            occurred_at="2030-01-01T00:00:00Z")["event"]

    def cli(self, *arguments, cwd=None):
        return subprocess.run([sys.executable, "-I", "-m", "neurocore", *map(str, arguments)],
                              cwd=cwd or self.root, capture_output=True, text=True,
                              encoding="utf-8", timeout=20)

    def test_same_character_creates_independent_identity_and_memory(self):
        first = create_instance(self.character, self.root / "first")
        second = create_instance(self.character, self.root / "second")
        self.assertNotEqual(first.instance_id, second.instance_id)
        self.assertNotEqual(first.memory_store_id, second.memory_store_id)
        self.assertNotEqual(first.memory_directory, second.memory_directory)
        original = self.append_sample(first)
        with self.assertRaises(MemoryError):
            second.reader().get_event("same-event-id")
        second_event = self.append_sample(second, "Synthetic event beta.")
        self.assertEqual(first.reader().get_event("same-event-id")["event"], original)
        self.assertEqual(second.reader().get_event("same-event-id")["event"], second_event)
        self.assertFalse(second.reader().validate_references([original["ref"]])["valid"])
        self.assertFalse(first.reader().validate_references([second_event["ref"]])["valid"])
        self.assert_healthy(check_instance(first.root))
        self.assert_healthy(check_instance(second.root))

    def test_seed_is_snapshot_not_an_event_or_confirmed_fact(self):
        instance = create_instance(self.character, self.root / "sample")
        with instance.reader().read_connection() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM facts").fetchone()[0], 0)
        self.assertEqual(instance.reader().authority()["epoch"], 0)
        before = self.inventory(instance.root)
        (self.character / "seed.md").write_text("Changed synthetic seed.", encoding="utf-8")
        self.write_manifest(name="Changed Name")
        reloaded = load_instance(instance.root)
        self.assertEqual(reloaded.instance_id, instance.instance_id)
        self.assertEqual(reloaded.character.name, "Synthetic Sample")
        self.assertEqual(reloaded.character.files["seed.md"].decode("utf-8"), self.seed)
        self.assertEqual(self.inventory(instance.root), before)

    def test_identity_and_memory_survive_a_real_interpreter_restart(self):
        instance = create_instance(self.character, self.root / "sample")
        self.append_sample(instance)
        code = """
import json, sys
from neurocore.instances import load_instance
i = load_instance(sys.argv[1])
print(json.dumps([i.instance_id, i.memory_store_id,
    i.reader().get_event('same-event-id')['event']['payload']['content']]))
"""
        result = subprocess.run([sys.executable, "-I", "-c", code, str(instance.root)],
                                cwd=self.root, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout),
                         [instance.instance_id, instance.memory_store_id, "Synthetic event alpha."])

    def test_optional_assets_are_copied_once_and_unlisted_files_are_not_read(self):
        assets = self.character / "assets"
        assets.mkdir()
        (assets / "sample.txt").write_bytes(b"synthetic asset")
        (self.character / "unlisted.txt").write_text("Unlisted synthetic data.", encoding="utf-8")
        self.write_manifest(assets=["assets/sample.txt"])
        instance = create_instance(self.character, self.root / "sample")
        self.assertEqual(instance.character.files["assets/sample.txt"], b"synthetic asset")
        self.assertFalse((instance.root / "character" / "unlisted.txt").exists())
        (assets / "sample.txt").write_bytes(b"changed synthetic asset")
        self.assertEqual(load_instance(instance.root).character.files["assets/sample.txt"],
                         b"synthetic asset")

    def test_no_image_is_valid_and_has_an_explicit_warning(self):
        self.assert_healthy(check_character(self.character))
        self.assertTrue(any(check.status == "WARN" for check in check_character(self.character)))
        instance = create_instance(self.character, self.root / "sample")
        self.assert_healthy(check_instance(instance.root))

    def test_existing_targets_are_never_overwritten_even_if_empty(self):
        for kind in ("empty", "occupied", "file", "instance"):
            target = self.root / kind
            if kind == "file":
                target.write_bytes(b"synthetic original")
            elif kind == "instance":
                create_instance(self.character, target)
            else:
                target.mkdir()
                if kind == "occupied":
                    (target / "sentinel.txt").write_bytes(b"synthetic original")
            before = target.read_bytes() if target.is_file() else self.inventory(target)
            with self.subTest(kind=kind), self.assertRaises((InstanceError, FileExistsError)):
                create_instance(self.character, target)
            after = target.read_bytes() if target.is_file() else self.inventory(target)
            self.assertEqual(after, before)

    def test_failed_creation_cannot_be_loaded_as_a_complete_instance(self):
        target = self.root / "failed"
        with patch("neurocore.instances.MemoryStore.create", side_effect=RuntimeError("Synthetic fault")):
            with self.assertRaises((InstanceError, RuntimeError)):
                create_instance(self.character, target)
        with self.assertRaises(InstanceError):
            load_instance(target)
        self.assert_failed(check_instance(target))
        self.assertFalse((target / "instance.json").exists())

    def test_missing_explicit_parent_is_not_silently_created(self):
        target = self.root / "missing-parent" / "sample"
        with self.assertRaises((InstanceError, FileNotFoundError)):
            create_instance(self.character, target)
        self.assertFalse(target.parent.exists())

    def test_invalid_character_does_not_create_a_target(self):
        self.write_manifest(format_version=999)
        target = self.root / "sample"
        with self.assertRaises((CharacterError, InstanceError)):
            create_instance(self.character, target)
        self.assertFalse(target.exists())

    def test_character_manifest_rejects_malformed_duplicate_unknown_and_wrong_types(self):
        variants = [b"{", b"[]", b"null", b'\xff',
                    b'{"format_version":1,"format_version":1,"name":"Synthetic","seed":"seed.md"}']
        for value in (dict(self.manifest, format_version=True), dict(self.manifest, format_version=2),
                      dict(self.manifest, name=""), dict(self.manifest, name=" " * 2),
                      dict(self.manifest, name="x" * 101), dict(self.manifest, name=123),
                      dict(self.manifest, seed=None), dict(self.manifest, assets="asset.txt"),
                      dict(self.manifest, assets=[17]), dict(self.manifest, unexpected="value"),
                      {"name": "Synthetic", "seed": "seed.md"}):
            variants.append(json.dumps(value).encode("utf-8"))
        for raw in variants:
            with self.subTest(raw=raw):
                (self.character / "character.json").write_bytes(raw)
                with self.assertRaises(CharacterError):
                    load_character(self.character)
                self.assert_failed(check_character(self.character))

    def test_character_errors_distinguish_json_missing_field_and_version(self):
        cases = [(b"{", "character-json"),
                 (json.dumps({"format_version": 1, "name": "Synthetic"}).encode("utf-8"),
                  "character-fields"),
                 (json.dumps(dict(self.manifest, format_version=999)).encode("utf-8"),
                  "character-version")]
        diagnostics = []
        for raw, category in cases:
            with self.subTest(category=category):
                (self.character / "character.json").write_bytes(raw)
                with self.assertRaisesRegex(CharacterError, category):
                    load_character(self.character)
                results = check_character(self.character)
                self.assert_failed(results)
                message = next(check.message for check in results if check.status == "FAIL")
                self.assertIn(category, message)
                diagnostics.append(message)
        self.assertEqual(len(set(diagnostics)), 3)

    def test_seed_rejects_empty_invalid_encoding_missing_and_directory(self):
        seed = self.character / "seed.md"
        for raw in (b"", b" \n\t", b"\xff", b"synthetic\x00text"):
            with self.subTest(raw=raw):
                seed.write_bytes(raw)
                with self.assertRaises(CharacterError):
                    load_character(self.character)
        seed.unlink()
        with self.assertRaises(CharacterError):
            load_character(self.character)
        seed.mkdir()
        with self.assertRaises(CharacterError):
            load_character(self.character)

    def test_paths_cannot_escape_or_use_windows_aliases(self):
        outside = self.root / "outside.md"
        outside.write_text("Synthetic outside sentinel.", encoding="utf-8")
        paths = ["../outside.md", "a/../../outside.md", str(outside), "/outside.md",
                 "C:/outside.md", "C:outside.md", "//server/share/seed.md",
                 "..\\outside.md", "assets\\file.md", "seed.md:stream", "CON", "NUL.md",
                 "a/./seed.md", "a//seed.md", "seed.md.", "seed.md "]
        original = outside.read_bytes()
        for reference in paths:
            for field in ("seed", "assets"):
                with self.subTest(reference=reference, field=field):
                    self.write_manifest(**{field: reference if field == "seed" else [reference]})
                    with self.assertRaises(CharacterError):
                        load_character(self.character)
                    self.assert_failed(check_character(self.character))
        self.assertEqual(outside.read_bytes(), original)

    def test_missing_declared_image_warns_and_still_allows_creation(self):
        self.write_manifest(assets=["missing-image.png"])
        package = load_character(self.character)
        self.assertIn("missing-image.png", package.missing_assets)
        self.assert_healthy(check_character(self.character))
        self.assertTrue(any(check.status == "WARN" for check in check_character(self.character)))
        instance = create_instance(self.character, self.root / "sample")
        self.assert_healthy(check_instance(instance.root))
        self.assertIn("missing-image.png", load_instance(instance.root).character.missing_assets)

    def test_hardlinked_character_and_memory_files_are_rejected(self):
        seed = self.character / "seed.md"
        external = self.root / "linked-seed.md"
        os.link(seed, external)
        with self.assertRaises(CharacterError):
            load_character(self.character)
        external.unlink()
        instance = create_instance(self.character, self.root / "sample")
        os.link(instance.memory_directory / "memory.sqlite3", self.root / "linked-store.sqlite3")
        self.assert_failed(check_instance(instance.root))
        with self.assertRaises(InstanceError):
            load_instance(instance.root)

    def test_directory_links_cannot_expose_external_assets(self):
        external = self.root / "outside"
        external.mkdir()
        (external / "sample.txt").write_bytes(b"synthetic outside asset")
        linked = self.character / "linked"
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(linked), str(external)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            linked.symlink_to(external, target_is_directory=True)
        self.addCleanup(lambda: linked.unlink() if os.name != "nt" else linked.rmdir())
        self.write_manifest(assets=["linked/sample.txt"])
        before = self.inventory(external)
        with self.assertRaises(CharacterError):
            load_character(self.character)
        self.assert_failed(check_character(self.character))
        self.assertEqual(self.inventory(external), before)

    def test_instance_metadata_and_snapshot_tampering_are_detected(self):
        for mutation in ("identity", "store", "version", "hash", "seed", "missing-manifest"):
            with self.subTest(mutation=mutation):
                instance = create_instance(self.character, self.root / mutation)
                path = instance.root / "instance.json"
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if mutation == "identity":
                    manifest["instance_id"] = "0" * 32
                elif mutation == "store":
                    manifest["memory_store_id"] = "0" * 32
                elif mutation == "version":
                    manifest["format_version"] = 999
                elif mutation == "hash":
                    manifest["character_hashes"]["seed.md"] = "0" * 64
                elif mutation == "seed":
                    (instance.root / "character" / "seed.md").write_text("Altered seed.", encoding="utf-8")
                if mutation == "missing-manifest":
                    path.unlink()
                else:
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                before = self.inventory(instance.root)
                with self.assertRaises(InstanceError):
                    load_instance(instance.root)
                self.assert_failed(check_instance(instance.root))
                self.assertEqual(self.inventory(instance.root), before)

    def test_replacement_store_with_same_brain_id_is_rejected(self):
        instance = create_instance(self.character, self.root / "sample")
        other = self.root / "replacement"
        MemoryStore.create(other, brain_id=instance.instance_id)
        (instance.memory_directory / "memory.sqlite3").write_bytes((other / "memory.sqlite3").read_bytes())
        with self.assertRaises(InstanceError):
            load_instance(instance.root)
        self.assert_failed(check_instance(instance.root))

    def test_doctor_is_read_only_for_healthy_character_and_populated_instance(self):
        instance = create_instance(self.character, self.root / "sample")
        self.append_sample(instance)
        before = self.inventory(self.root)
        with closing(sqlite3.connect(instance.memory_directory / "memory.sqlite3")) as observer:
            logical = list(observer.iterdump())
            version = observer.execute("PRAGMA data_version").fetchone()[0]
            epoch = observer.execute("SELECT epoch FROM authority").fetchone()[0]
            for _ in range(2):
                self.assert_healthy(check_character(self.character))
                self.assert_healthy(check_instance(instance.root))
            self.assertEqual(list(observer.iterdump()), logical)
            self.assertEqual(observer.execute("PRAGMA data_version").fetchone()[0], version)
            self.assertEqual(observer.execute("SELECT epoch FROM authority").fetchone()[0], epoch)
        self.assertEqual(self.inventory(self.root), before)

    def test_doctor_missing_paths_and_database_never_initialize_storage(self):
        missing = self.root / "does-not-exist"
        before = self.inventory(self.root)
        self.assert_failed(check_character(missing))
        self.assert_failed(check_instance(missing))
        self.assertEqual(self.inventory(self.root), before)
        instance = create_instance(self.character, self.root / "sample")
        (instance.memory_directory / "memory.sqlite3").unlink()
        before = self.inventory(instance.root)
        self.assert_failed(check_instance(instance.root))
        with self.assertRaises(InstanceError):
            load_instance(instance.root)
        self.assertEqual(self.inventory(instance.root), before)

    def test_doctor_corrupt_or_incomplete_database_is_not_repaired(self):
        for kind in ("corrupt", "missing-table", "wrong-authority"):
            with self.subTest(kind=kind):
                instance = create_instance(self.character, self.root / kind)
                database = instance.memory_directory / "memory.sqlite3"
                if kind == "corrupt":
                    database.write_bytes(b"synthetic non-database")
                else:
                    with closing(sqlite3.connect(database)) as con:
                        if kind == "missing-table":
                            con.execute("DROP TABLE audit")
                        else:
                            con.execute("UPDATE authority SET brain_id='synthetic-wrong-authority'")
                        con.commit()
                before = self.inventory(instance.root)
                self.assert_failed(check_instance(instance.root))
                self.assertEqual(self.inventory(instance.root), before)

    def test_doctor_wal_header_does_not_create_sqlite_sidecars(self):
        instance = create_instance(self.character, self.root / "sample")
        database = instance.memory_directory / "memory.sqlite3"
        with closing(sqlite3.connect(database)) as con:
            self.assertEqual(con.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        self.assertFalse(Path(str(database) + "-wal").exists())
        self.assertFalse(Path(str(database) + "-shm").exists())
        before = self.inventory(instance.root)
        self.assert_failed(check_instance(instance.root))
        self.assertEqual(self.inventory(instance.root), before)

    def test_doctor_existing_sidecars_are_never_removed_or_recovered(self):
        for suffix in ("-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                instance = create_instance(self.character, self.root / suffix.lstrip("-"))
                sidecar = instance.memory_directory / ("memory.sqlite3" + suffix)
                sidecar.write_bytes(b"synthetic recovery marker")
                before = self.inventory(instance.root)
                self.assert_failed(check_instance(instance.root))
                self.assertEqual(self.inventory(instance.root), before)

    def test_cli_explicit_and_default_creation_and_doctor_exit_codes(self):
        target = self.root / "explicit"
        result = self.cli("new", "--character", self.character, "--instance", target)
        self.assertEqual(result.returncode, 0, result.stderr)
        created = json.loads(result.stdout)
        self.assertEqual(Path(created["instance_directory"]), target)
        self.assertEqual(created["instance_id"], load_instance(target).instance_id)
        result = self.cli("new", "--character", self.character)
        self.assertEqual(result.returncode, 0, result.stderr)
        default = Path(json.loads(result.stdout)["instance_directory"])
        self.assertEqual(default.parent, self.root / "instances")
        self.assertNotEqual(load_instance(default).instance_id, created["instance_id"])
        for arguments, cwd in ((("doctor", "--character", self.character), self.root),
                               (("doctor", "--instance", target), self.root),
                               (("doctor",), target), (("doctor",), self.character)):
            result = self.cli(*arguments, cwd=cwd)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("PASS", result.stdout)
        before = self.inventory(self.root)
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("FAIL", result.stdout)
        result = self.cli("doctor", "--instance", self.root / "missing")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(self.inventory(self.root), before)
        result = self.cli("doctor", "--instance", target, "--character", self.character)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_two_processes_cannot_both_create_the_same_target(self):
        target = self.root / "contended"
        command = [sys.executable, "-I", "-m", "neurocore", "new", "--character",
                   str(self.character), "--instance", str(target)]
        processes = [subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for _ in range(2)]
        outputs = [process.communicate(timeout=20) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], outputs)
        self.assert_healthy(check_instance(target))
        succeeded = next(output for process, output in zip(processes, outputs) if process.returncode == 0)
        self.assertEqual(json.loads(succeeded[0])["instance_id"], load_instance(target).instance_id)

    def test_chinese_and_space_paths_work_through_cli_and_restart(self):
        character = self.root / "合成 角色包"
        self.character.rename(character)
        target = self.root / "独立 实例"
        result = self.cli("new", "--character", character, "--instance", target)
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)["instance_id"]
        instance = load_instance(target)
        self.append_sample(instance)
        result = self.cli("doctor", "--instance", target)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(load_instance(target).instance_id, identity)
        self.assertEqual(load_instance(target).reader().get_event("same-event-id")["event"]
                         ["payload"]["content"], "Synthetic event alpha.")


if __name__ == "__main__":
    unittest.main()
