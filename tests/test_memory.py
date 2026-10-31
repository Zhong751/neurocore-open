import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

from neurocore.memory import ConflictError, MemoryError, MemoryReader, MemoryStore


class MemoryContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.store = MemoryStore.create(self.directory, brain_id="synthetic-a")
        self.reader = MemoryReader(self.directory, brain_id="synthetic-a")
        self.writer = getattr(self.store, "writer", self.store)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _event(self, *, event_id=None, content="I live in Synthetic City.", role="user",
               provenance="user_statement", speaker_id="user-1", conversation_id="c-1",
               source_type="conversation", source_id="synthetic-source"):
        self.n += 1
        return self.writer.append_event(
            event_id=event_id or f"event-{self.n}", source_id=source_id,
            source_type=source_type, speaker_id=speaker_id, role=role,
            provenance=provenance, conversation_id=conversation_id, content=content,
            occurred_at=datetime.now(timezone.utc).isoformat(), metadata={})

    def _fact(self, *, evidence=None, basis="direct_statement", subject_id="user-1",
              predicate="lives_in", value="Synthetic City", parents=None, conversation_id="c-1"):
        if evidence is None:
            event_id = f"event-{self.n + 1}"
            self._event(event_id=event_id)
            evidence = [self.reader.cite(event_id, 0, len("I live in Synthetic City."))]
        return self.writer.propose_fact(
            conversation_id=conversation_id, subject_id=subject_id, predicate=predicate,
            value=value, evidence=evidence, basis=basis, parents=parents or [])

    def test_event_survives_real_interpreter_restart_and_missing_open_is_read_only(self):
        receipt = self._event(event_id="restart-event")
        self.assertEqual(self.reader.get_event("restart-event")["event"]["payload"]["content"],
                         "I live in Synthetic City.")
        code = """
import sys
from neurocore.memory import MemoryReader
r = MemoryReader(sys.argv[1], brain_id='synthetic-a')
print(r.get_event('restart-event')['event']['payload']['content'])
"""
        result = subprocess.run([sys.executable, "-I", "-c", code, str(self.directory)],
                                cwd=Path(__file__).parents[1], capture_output=True, text=True,
                                check=True)
        self.assertEqual(result.stdout.strip(), "I live in Synthetic City.")
        missing = self.directory / "missing"
        with self.assertRaises(MemoryError):
            MemoryReader(missing, brain_id="synthetic-a")
        self.assertFalse((missing / "memory.sqlite3").exists())

    def test_direct_statement_requires_actual_user_source_and_exact_span(self):
        event = self._event(event_id="assistant-event", role="assistant", provenance="ai_generated")
        evidence = [{**self.reader.cite("assistant-event", 0, 4), "quote": "forged"}]
        with self.assertRaises(MemoryError):
            self.writer.propose_fact(conversation_id="c-1", subject_id="user-1",
                                     predicate="p", value="v", evidence=evidence,
                                     basis="direct_statement", parents=[])
        assistant_evidence = self.reader.cite("assistant-event", 0, 4)
        with self.assertRaises(MemoryError):
            self.writer.propose_fact(conversation_id="c-1", subject_id="user-1",
                                     predicate="p", value="v", evidence=[assistant_evidence],
                                     basis="direct_statement", parents=[])
        wrong_speaker = self._event(event_id="wrong-speaker", speaker_id="other")
        with self.assertRaises(MemoryError):
            self.writer.propose_fact(conversation_id="c-1", subject_id="user-1",
                                     predicate="p", value="v",
                                     evidence=[self.reader.cite("wrong-speaker", 0, 4)],
                                     basis="direct_statement", parents=[])

    def test_pending_and_reviewed_inference_never_becomes_usable_or_parent(self):
        event = self._event(event_id="ai-event", role="assistant", provenance="ai_generated",
                            content="The user probably likes tea.")
        receipt = self.writer.propose_fact(
            conversation_id="c-1", subject_id="user-1", predicate="likes", value="tea",
            evidence=[self.reader.cite("ai-event", 0, 10)], basis="model_inference", parents=[])
        fact = receipt["fact"]
        self.assertEqual(fact["status"], "pending")
        self.assertFalse(fact["current_usable"])
        reviewed = self.writer.review_fact(fact["fact_id"], expected_revision=1,
                                           action="accept", reason="synthetic review")
        self.assertEqual(reviewed["fact"]["review_status"], "accepted")
        self.assertFalse(self.reader.get_fact(fact["fact_id"])["fact"]["current_usable"])
        self._event(event_id="parent-source")
        with self.assertRaises(MemoryError):
            self.writer.propose_fact(
                conversation_id="c-1", subject_id="user-1", predicate="uses",
                value="inference", evidence=[self.reader.cite("parent-source", 0, 4)],
                basis="direct_statement", parents=[reviewed["fact"]["ref"]])

    def test_confirmation_correction_requires_new_confirmation(self):
        proposed = self._fact()
        fact_id = proposed["fact"]["fact_id"]
        confirmed = self.writer.confirm_fact(fact_id, expected_revision=1,
                                             reason="synthetic review")
        self.assertEqual(confirmed["fact"]["revision"], 2)
        self.assertTrue(self.reader.get_fact(fact_id)["fact"]["current_usable"])
        event_id = "correction-event"
        self._event(event_id=event_id, content="I live in Other City.")
        corrected = self.writer.correct_fact(
            fact_id, expected_revision=2, reason="synthetic correction", conversation_id="c-1",
            subject_id="user-1", predicate="lives_in", value="Other City",
            evidence=[self.reader.cite(event_id, 0, len("I live in Other City."))],
            basis="direct_statement", parents=[])
        self.assertEqual(corrected["fact"]["status"], "pending")
        self.assertEqual(corrected["fact"]["revision"], 3)
        self.assertEqual(self.reader.get_fact(fact_id, revision=2)["fact"]["status"], "corrected")
        latest = self.reader.get_fact(fact_id)["fact"]
        self.assertEqual(latest["revision"], 3)
        self.assertEqual(latest["status"], "pending")
        self.assertFalse(latest["current_usable"])

    def test_withdrawing_parent_retracts_dependent_and_is_idempotent(self):
        parent = self._fact()
        parent_id = parent["fact"]["fact_id"]
        parent_confirmed = self.writer.confirm_fact(parent_id, expected_revision=1,
                                                    reason="synthetic review")
        child_event = self._event(event_id="child-source", content="I use that place.")
        child = self.writer.propose_fact(
            conversation_id="c-1", subject_id="user-1", predicate="uses",
            value="that place", evidence=[self.reader.cite("child-source", 0, 8)],
            basis="direct_statement", parents=[parent_confirmed["fact"]["ref"]])
        child_id = child["fact"]["fact_id"]
        child_confirmed = self.writer.confirm_fact(child_id, expected_revision=1,
                                                   reason="synthetic review")
        before = self.reader.authority()["epoch"]
        withdrawn = self.writer.withdraw_fact(parent_id, expected_revision=2,
                                              reason="synthetic withdrawal")
        self.assertEqual(withdrawn["fact"]["status"], "withdrawn")
        self.assertFalse(self.reader.get_fact(child_id)["fact"]["current_usable"])
        after = self.reader.authority()["epoch"]
        self.assertGreater(after, before)
        audit_before = self._audit_count()
        again = self.writer.withdraw_fact(parent_id, expected_revision=2,
                                          reason="synthetic withdrawal")
        self.assertEqual(again["fact"]["status"], "withdrawn")
        self.assertEqual(self.reader.authority()["epoch"], after)
        self.assertEqual(self._audit_count(), audit_before)

    def test_event_withdrawal_invalidates_evidence_and_reference(self):
        self._event(event_id="withdraw-event")
        ref = self.reader.get_event("withdraw-event")["event"]["ref"]
        before = self.reader.authority()["epoch"]
        result = self.writer.withdraw_event("withdraw-event", reason="synthetic withdrawal")
        self.assertEqual(result["event"]["status"], "withdrawn")
        self.assertFalse(self.reader.validate_references([ref])["valid"])
        self.assertGreater(self.reader.authority()["epoch"], before)

    def test_active_event_with_tampered_payload_is_not_read_as_evidence(self):
        self._event(event_id="tampered-event")
        path = self.directory / "memory.sqlite3"
        con = sqlite3.connect(path)
        try:
            payload = json.dumps({"content": "forged", "conversation_id": "c-1"})
            con.execute("UPDATE events SET payload=? WHERE id=?", (payload, "tampered-event"))
            con.commit()
        finally:
            con.close()
        with self.assertRaises(MemoryError):
            self.reader.get_event("tampered-event")

    def test_reviewed_model_inference_cannot_be_relabelled_by_parent_reference(self):
        event = self._event(event_id="inference-event", role="assistant", provenance="ai_generated",
                            content="The user probably likes tea.")
        inference = self.writer.propose_fact(
            conversation_id="c-1", subject_id="user-1", predicate="likes", value="tea",
            evidence=[self.reader.cite("inference-event", 0, 10)], basis="model_inference", parents=[])
        inference = self.writer.review_fact(inference["fact"]["fact_id"], expected_revision=1,
                                            action="accept", reason="synthetic review")
        direct = self._event(event_id="direct-parent", content="I use tea.")
        with self.assertRaises(MemoryError):
            self.writer.propose_fact(
                conversation_id="c-1", subject_id="user-1", predicate="uses", value="tea",
                evidence=[self.reader.cite("direct-parent", 0, 6)], basis="direct_statement",
                parents=[inference["fact"]["ref"]])

    def test_instance_references_cannot_be_mixed(self):
        other_dir = Path(self.tmp.name) / "other"
        other = MemoryStore.create(other_dir, brain_id="synthetic-a")
        other_writer = getattr(other, "writer", other)
        other_writer.append_event(event_id="other-event", source_id="s", source_type="conversation",
                                  speaker_id="user-1", role="user", provenance="user_statement",
                                  conversation_id="c-1", content="Other.",
                                  occurred_at=datetime.now(timezone.utc).isoformat(), metadata={})
        self._event(event_id="event-1")
        ref = self.reader.get_event("event-1")["event"]["ref"]
        other_reader = MemoryReader(other_dir, brain_id="synthetic-a")
        self.assertFalse(other_reader.validate_references([ref])["valid"])

    def test_read_connection_rejects_dml_ddl_attach_and_pragma(self):
        with self.reader.read_connection() as con:
            for sql in ("INSERT INTO events VALUES ('x','{}','x',1,'active','')",
                        "CREATE TABLE injected(x)", "ATTACH DATABASE ':memory:' AS injected",
                        "PRAGMA user_version=9"):
                with self.assertRaises(sqlite3.DatabaseError):
                    con.execute(sql)

    def test_invalid_write_rolls_back_without_epoch_or_partial_event(self):
        before = self.reader.authority()["epoch"]
        with self.assertRaises((MemoryError, ValueError)):
            self.writer.append_event(event_id="bad", source_id="s", source_type="conversation",
                                     speaker_id="user-1", role="user", provenance="user_statement",
                                     conversation_id="c-1", content="bad",
                                     occurred_at="not-an-iso-time", metadata={})
        self.assertEqual(self.reader.authority()["epoch"], before)
        with self.assertRaises(MemoryError):
            self.reader.get_event("bad")

    def _audit_count(self):
        with self.reader.read_connection() as con:
            return con.execute("SELECT count(*) FROM audit").fetchone()[0]


if __name__ == "__main__":
    unittest.main()
