"""Synthetic source/lifecycle/transaction counterexamples, including real processes."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from neurocore.memory import ConflictError, MemoryError, MemoryReader, MemoryStore


class MemoryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = MemoryStore.create(self.root, brain_id="synthetic-boundary")

    def event(self, eid="source", **changes):
        fields = dict(event_id=eid, source_id=eid, source_type="synthetic",
                      speaker_id="person", role="user", provenance="user_statement",
                      conversation_id="session", content="Synthetic sample alpha.",
                      occurred_at="2030-01-01T00:00:00Z")
        fields.update(changes)
        return self.store.append_event(**fields)["event"]

    def candidate(self, eid="source", **changes):
        fields = dict(conversation_id="session", subject_id="person", predicate="sample",
                      value="alpha", evidence=[self.store.cite(eid, 0, 22)])
        fields.update(changes)
        return fields

    def confirmed(self, **fields):
        fact = self.store.propose_fact(**fields)["fact"]
        return self.store.confirm_fact(fact["fact_id"], expected_revision=1, reason="Synthetic review")["fact"]

    def test_no_support_invalid_quote_and_stale_proposal_are_rejected(self):
        self.event()
        fields = self.candidate()
        for evidence in ([], [{**fields["evidence"][0], "quote": "X" * 22}],
                         [{**fields["evidence"][0], "relation": "context"}]):
            with self.subTest(evidence_kind=len(evidence)), self.assertRaises(MemoryError):
                self.store.propose_fact(**{**fields, "evidence": evidence})
        self.store.withdraw_event("source", reason="Synthetic revocation")
        with self.assertRaises(MemoryError):
            self.store.propose_fact(**fields)
        self.assertEqual(self.store.list_valid_facts()["facts"], [])

    def test_ai_support_cannot_hide_beside_user_support_but_context_is_permitted(self):
        self.event()
        for category in ("ai_generated", "ai_suggestion", "unverified_transcript", "external_unverified"):
            self.event(category, provenance=category)
            evidence = [self.store.cite("source", 0, 22), self.store.cite(category, 0, 22)]
            with self.subTest(category=category), self.assertRaises(MemoryError):
                self.store.propose_fact(**self.candidate(basis="reported_statement", evidence=evidence))
        self.event("assistant", role="assistant", provenance="ai_suggestion", speaker_id="model")
        evidence = [self.store.cite("source", 0, 22), self.store.cite("assistant", 0, 22, relation="context")]
        fact = self.confirmed(**self.candidate(basis="reported_statement", evidence=evidence))
        self.assertTrue(fact["current_usable"])
        self.store.withdraw_event("assistant", reason="Synthetic contextual withdrawal")
        self.assertFalse(self.store.get_fact(fact["fact_id"])["fact"]["current_usable"])

    def test_source_withdrawal_transitive_chain_duplicate_and_process_restart(self):
        for eid in ("source", "child-source", "grandchild-source"):
            self.event(eid)
        parent = self.confirmed(**self.candidate())
        child = self.confirmed(**self.candidate("child-source", predicate="child", parents=[parent["ref"]]))
        grandchild = self.confirmed(**self.candidate("grandchild-source", predicate="grandchild", parents=[child["ref"]]))
        refs = [f["ref"] for f in (parent, child, grandchild)]
        self.assertTrue(self.store.validate_references(refs)["valid"])
        self.store.withdraw_event("source", reason="Synthetic revoke")
        epoch = self.store.authority()["epoch"]
        for fact in (parent, child, grandchild):
            self.assertEqual(self.store.get_fact(fact["fact_id"])["fact"]["status"], "withdrawn")
        self.store.withdraw_event("source", reason="Synthetic retry", expected_version=1)
        self.assertEqual(self.store.authority()["epoch"], epoch)
        code = """
import sys
from neurocore.memory import MemoryReader
r = MemoryReader(sys.argv[1], brain_id='synthetic-boundary')
assert r.get_event('source')['event']['status'] == 'withdrawn'
assert r.authority()['epoch'] == int(sys.argv[2])
assert r.list_valid_facts()['facts'] == []
for fid in sys.argv[3:]:
    assert r.get_fact(fid)['fact']['status'] == 'withdrawn'
print('restart-ok')
"""
        result = subprocess.run([sys.executable, "-I", "-c", code, str(self.root), str(epoch),
            *[f["fact_id"] for f in (parent, child, grandchild)]], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "restart-ok")

    def test_correction_keeps_original_and_invalidates_old_refs_and_descendants(self):
        self.event()
        self.event("child")
        old = self.confirmed(**self.candidate())
        child = self.confirmed(**self.candidate("child", predicate="derived", parents=[old["ref"]]))
        self.event("replacement", content="Synthetic sample omega.")
        replacement = self.store.correct_fact(old["fact_id"], expected_revision=2,
            reason="Synthetic correction", **self.candidate("replacement", value="omega"))["fact"]
        self.assertEqual(replacement["status"], "pending")
        self.assertFalse(self.store.validate_references([old["ref"], child["ref"]])["valid"])
        new = self.store.confirm_fact(old["fact_id"], expected_revision=3, reason="Synthetic replacement review")["fact"]
        reopened = MemoryStore(self.root, brain_id="synthetic-boundary")
        self.assertEqual(reopened.get_fact(old["fact_id"], revision=2)["fact"]["status"], "corrected")
        self.assertEqual(reopened.list_valid_facts()["facts"][0]["payload"]["value"], "omega")
        self.assertTrue(reopened.validate_references([new["ref"]])["valid"])
        self.assertEqual(reopened.get_event("source")["event"]["payload"]["content"], "Synthetic sample alpha.")
        self.assertFalse(reopened.get_fact(child["fact_id"])["fact"]["current_usable"])

    def test_conflict_invalidates_derived_and_rejected_candidate_stays_suppressed(self):
        self.event()
        parent = self.confirmed(**self.candidate())
        self.event("child")
        child = self.confirmed(**self.candidate("child", predicate="child", parents=[parent["ref"]]))
        self.event("other")
        other = self.confirmed(**self.candidate("other", value="other"))
        self.assertFalse(other["current_usable"])
        self.assertEqual(self.store.list_valid_facts()["facts"], [])
        self.assertFalse(self.store.get_fact(child["fact_id"])["fact"]["current_usable"])
        proposal = self.store.propose_fact(**self.candidate(predicate="reject"))["fact"]
        self.store.review_fact(proposal["fact_id"], expected_revision=1, action="reject", reason="Synthetic reject")
        with self.assertRaises(MemoryError):
            self.store.propose_fact(**self.candidate(predicate="reject"))

    def test_event_identity_is_idempotent_but_conflicting_retry_is_not(self):
        original = self.event()
        epoch = self.store.authority()["epoch"]
        self.assertEqual(self.event(), original)
        self.assertEqual(self.store.authority()["epoch"], epoch)
        with self.assertRaises(ConflictError):
            self.event(content="Different synthetic content")
        self.store.withdraw_event("source", reason="Synthetic withdrawal")
        self.assertEqual(self.event()["status"], "withdrawn")

    def test_rejected_assertion_cannot_evade_suppression_by_changing_span(self):
        self.event()
        fields = self.candidate()
        fact = self.store.propose_fact(**fields)["fact"]
        self.store.review_fact(fact["fact_id"], expected_revision=1, action="reject", reason="Synthetic rejection")
        fields["evidence"] = [self.store.cite("source", 10, 22)]
        reopened = MemoryStore(self.root, brain_id="synthetic-boundary")
        with self.assertRaisesRegex(MemoryError, "cannot be reproposed"):
            reopened.propose_fact(**fields)

    def test_read_only_snapshot_has_no_writes_even_with_a_legal_external_writer(self):
        self.event()
        fact = self.confirmed(**self.candidate())
        reader = MemoryReader(self.root, brain_id="synthetic-boundary")
        with closing(sqlite3.connect(self.root / "memory.sqlite3")) as observer:
            before = list(observer.iterdump())
            version = observer.execute("PRAGMA data_version").fetchone()[0]
            entries = sorted(p.name for p in self.root.iterdir())
            for _ in range(3):
                reader.get_event("source")
                reader.get_fact(fact["fact_id"])
                reader.list_valid_facts()
                reader.validate_references([fact["ref"]])
            self.assertEqual(observer.execute("PRAGMA data_version").fetchone()[0], version)
            self.assertEqual(list(observer.iterdump()), before)
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), entries)
            self.store.withdraw_event("source", reason="Synthetic external write")
            after_write = list(observer.iterdump())
            self.assertNotEqual(after_write, before)
            version = observer.execute("PRAGMA data_version").fetchone()[0]
            self.assertFalse(reader.validate_references([fact["ref"]])["valid"])
            self.assertEqual(list(observer.iterdump()), after_write)
            self.assertEqual(observer.execute("PRAGMA data_version").fetchone()[0], version)

    def test_failed_commit_rolls_back_source_and_all_descendants(self):
        self.event()
        fact = self.confirmed(**self.candidate())
        before = self.store.authority()["epoch"]
        with patch.object(self.store._storage, "advance", side_effect=RuntimeError("Synthetic fault")):
            with self.assertRaisesRegex(RuntimeError, "Synthetic fault"):
                self.store.withdraw_event("source", reason="Synthetic withdrawal")
        self.assertEqual(self.store.authority()["epoch"], before)
        self.assertEqual(self.store.get_event("source")["event"]["status"], "active")
        self.assertTrue(self.store.validate_references([fact["ref"]])["valid"])

    def test_process_exit_rolls_back_uncommitted_write_and_writer_can_recover(self):
        self.event()
        before = self.store.authority()["epoch"]
        code = """
import os, sqlite3, sys
c = sqlite3.connect(sys.argv[1], isolation_level=None)
c.execute('PRAGMA cache_size=1')
c.execute('BEGIN IMMEDIATE')
c.execute("UPDATE events SET status='withdrawn', reason=?", ('synthetic-' * 20000,))
c.execute('UPDATE authority SET epoch=epoch+1')
os._exit(23)
"""
        result = subprocess.run([sys.executable, "-I", "-c", code, str(self.root / "memory.sqlite3")], timeout=15)
        self.assertEqual(result.returncode, 23)
        reopened = MemoryStore(self.root, brain_id="synthetic-boundary")
        self.assertEqual(reopened.authority()["epoch"], before)
        self.assertEqual(reopened.get_event("source")["event"]["status"], "active")

    def test_cross_process_duplicate_withdrawal_commits_once(self):
        self.event()
        before = self.store.authority()["epoch"]
        code = """
import sys
from neurocore.memory import MemoryStore
s = MemoryStore(sys.argv[1], brain_id='synthetic-boundary')
print('ready', flush=True)
sys.stdin.readline()
s.withdraw_event('source', reason='Synthetic competing withdrawal')
print('done', flush=True)
"""
        workers = [subprocess.Popen([sys.executable, "-I", "-c", code, str(self.root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        try:
            for worker in workers:
                self.assertEqual(worker.stdout.readline().strip(), "ready")
            for worker in workers:
                worker.stdin.write("go\n")
                worker.stdin.flush()
            for worker in workers:
                stdout, stderr = worker.communicate(timeout=15)
                self.assertEqual(worker.returncode, 0, stderr)
                self.assertIn("done", stdout)
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.communicate()
        self.assertEqual(self.store.authority()["epoch"], before + 1)

    def test_binding_schema_and_cross_store_collision_fail_closed(self):
        self.event()
        fact = self.confirmed(**self.candidate())
        with self.assertRaises(FileExistsError):
            MemoryStore.create(self.root, brain_id="different")
        with self.assertRaises(MemoryError):
            MemoryReader(self.root, brain_id="different")
        other = MemoryStore.create(self.root / "other", brain_id="synthetic-boundary")
        payload = self.store.get_event("source")["event"]["payload"]
        other.append_event(event_id="source", **payload)
        ref = self.store.get_event("source")["event"]["ref"]
        self.assertFalse(other.validate_references([ref])["valid"])
        with self.assertRaises(MemoryError):
            other.propose_fact(**self.candidate())
        with closing(sqlite3.connect(self.root / "memory.sqlite3")) as con:
            con.execute("UPDATE authority SET schema_version=999")
            con.commit()
        with self.assertRaises(MemoryError):
            self.store.validate_references([fact["ref"]])

    def test_stale_epoch_and_invalid_parent_index_are_not_valid_evidence(self):
        self.event()
        parent = self.confirmed(**self.candidate())
        self.event("child")
        child = self.confirmed(**self.candidate("child", predicate="child", parents=[parent["ref"]]))
        epoch = self.store.authority()["epoch"]
        self.event("unrelated")
        with self.assertRaises(ConflictError):
            self.store.validate_references([child["ref"]], expected_epoch=epoch)
        with closing(sqlite3.connect(self.root / "memory.sqlite3")) as con:
            con.execute("DELETE FROM dependencies WHERE child_id=?", (child["fact_id"],))
            con.commit()
        self.assertFalse(self.store.validate_references([child["ref"]])["valid"])


if __name__ == "__main__":
    unittest.main()
