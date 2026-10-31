"""Explicit trusted-host writes; candidates never authorize their own review."""
from datetime import datetime
import json
import uuid

from ._reader import MemoryReader
from ._storage import ConflictError, MemoryError, Storage, create, digest, dump, integer, now, text


class MemoryStore(MemoryReader):
    def __init__(self, directory, *, brain_id):
        self._storage = Storage(directory, brain_id, recover=True)

    @classmethod
    def create(cls, directory, *, brain_id):
        create(directory, brain_id)
        return cls(directory, brain_id=brain_id)

    def append_event(self, *, event_id, source_id, source_type, speaker_id, role,
                     provenance, conversation_id, content, occurred_at, metadata=None):
        for value in (event_id, source_id, source_type, speaker_id, conversation_id):
            text(value)
        text(content, 32768)
        text(occurred_at, 80)
        if datetime.fromisoformat(occurred_at).utcoffset() is None:
            raise MemoryError("Event time must include timezone")
        if role not in {"user", "assistant", "system", "tool", "unknown"} or provenance not in {
            "user_statement", "ai_generated", "ai_suggestion", "external_unverified",
            "unverified_transcript", "execution_result",
        }:
            raise MemoryError("Invalid role or source provenance")
        if not isinstance(metadata if metadata is not None else {}, dict):
            raise MemoryError("Metadata must be a JSON object")
        metadata = json.loads(dump(metadata if metadata is not None else {}))
        if len(dump(metadata)) > 8192:
            raise MemoryError("Metadata exceeds bounds")
        payload = dict(source_id=source_id, source_type=source_type, speaker_id=speaker_id,
                       role=role, provenance=provenance, conversation_id=conversation_id,
                       content=content, occurred_at=occurred_at, metadata=metadata)
        with self._storage.connect(write=True) as con:
            old = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if old is not None:
                if old["digest"] != digest(payload) or old["payload"] != dump(payload):
                    raise ConflictError("Event ID already binds different content")
            else:
                con.execute("INSERT INTO events VALUES(?,?,?,1,'active','')",
                            (event_id, dump(payload), digest(payload)))
                self._storage.advance(con, "append_event", event_id, "")
            row = self._event(con, event_id)
            return self._storage.receipt(con, event={**dict(row), "payload": payload,
                "ref": self._ref("event", row), "current_usable": row["status"] == "active"})

    def _candidate(self, con, *, conversation_id, subject_id, predicate, value, evidence,
                   basis="direct_statement", parents=(), valid_time_text=None, conditions=()):
        for item in (conversation_id, subject_id, predicate):
            text(item)
        text(value, 512)
        if basis not in {"direct_statement", "reported_statement", "model_inference"}:
            raise MemoryError("Invalid fact basis")
        if not isinstance(evidence, (list, tuple)) or not 1 <= len(evidence) <= 8:
            raise MemoryError("Expected one to eight evidence spans")
        if not isinstance(parents, (list, tuple)) or len(parents) > 8:
            raise MemoryError("Expected at most eight parent references")
        if not isinstance(conditions, (list, tuple)) or len(conditions) > 8:
            raise MemoryError("Expected at most eight conditions")
        for condition in conditions:
            text(condition, 512)
        if valid_time_text is not None:
            text(valid_time_text, 512)
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {"ref", "start", "end", "quote", "relation"}:
                raise MemoryError("Invalid evidence shape")
            integer(item["start"], 0)
            integer(item["end"])
            text(item["quote"], 4096)
            if (not isinstance(item["ref"], dict) or not isinstance(item["ref"].get("record_id"), str)
                    or not 0 <= item["start"] < item["end"] <= 32768
                    or len(item["quote"]) != item["end"] - item["start"]
                    or item["relation"] not in {"supports", "opposes", "context"}):
                raise MemoryError("Invalid evidence span or reference")
        if len({dump(e) for e in evidence}) != len(evidence) or len({dump(p) for p in parents}) != len(parents):
            raise MemoryError("Duplicate evidence or parents")
        candidate = json.loads(dump(dict(conversation_id=conversation_id, subject_id=subject_id,
            predicate=predicate, value=value, basis=basis, evidence=list(evidence),
            parents=list(parents), valid_time_text=valid_time_text, conditions=list(conditions))))
        self._sources(con, candidate)
        known = any((p := json.loads(row[0]))["conversation_id"] == conversation_id
                    and p["speaker_id"] == subject_id for row in con.execute("SELECT payload FROM events"))
        if not known:
            raise MemoryError("Subject must be a known source identity in this conversation")
        for parent in parents:
            if not isinstance(parent, dict):
                raise MemoryError("Invalid parent reference")
            row = self._fact(con, parent.get("record_id"), integer(parent.get("version")))
            if not self._matches(parent, "fact", row):
                raise MemoryError("Invalid parent reference")
            self._usable(con, row["fact_id"], row["revision"])
        if con.execute("SELECT 1 FROM suppressions WHERE digest=?", (digest(candidate),)).fetchone():
            raise MemoryError("Rejected or withdrawn candidate cannot be reproposed")
        return candidate

    @staticmethod
    def _insert(con, fid, revision, candidate, status, review, reason):
        con.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?,0,?,?)",
                    (fid, revision, dump(candidate), digest(candidate), status, review, reason, now()))
        for event_id in {item["ref"]["record_id"] for item in candidate["evidence"]}:
            con.execute("INSERT INTO evidence VALUES(?,?,?)", (fid, revision, event_id))
        for parent in candidate["parents"]:
            con.execute("INSERT INTO dependencies VALUES(?,?,?,?)",
                        (fid, revision, parent["record_id"], parent["version"]))
        con.execute("UPDATE facts SET head=? WHERE id=?", (revision, fid))

    @staticmethod
    def _invalidate(con, fid, revision, reason):
        con.execute("""WITH RECURSIVE chain(id,rev) AS (
            SELECT child_id,child_revision FROM dependencies WHERE parent_id=? AND parent_revision=?
            UNION SELECT d.child_id,d.child_revision FROM dependencies d JOIN chain c
            ON d.parent_id=c.id AND d.parent_revision=c.rev)
            UPDATE revisions SET status='withdrawn',reason=? WHERE status IN ('pending','confirmed')
            AND (fact_id,revision) IN (SELECT id,rev FROM chain)""", (fid, revision, reason))

    def _expected(self, con, fid, revision):
        integer(revision)
        row = self._fact(con, fid)
        if row["revision"] != revision:
            raise ConflictError("Fact revision changed")
        return row

    def propose_fact(self, **candidate_fields):
        with self._storage.connect(write=True) as con:
            candidate = self._candidate(con, **candidate_fields)
            old = con.execute("SELECT r.*,f.head FROM revisions r JOIN facts f "
                "ON f.id=r.fact_id AND f.head=r.revision WHERE r.digest=?", (digest(candidate),)).fetchone()
            if old is not None:
                if old["status"] in {"withdrawn", "corrected"}:
                    raise MemoryError("Inactive candidate cannot be reproposed")
                return self._storage.receipt(con, fact=self._view(con, old))
            fid = uuid.uuid4().hex
            con.execute("INSERT INTO facts VALUES(?,1)", (fid,))
            self._insert(con, fid, 1, candidate, "pending", "pending", "")
            self._storage.advance(con, "propose_fact", fid, "")
            return self._storage.receipt(con, fact=self._view(con, self._fact(con, fid)))

    def _conflicts(self, con, fid, revision, candidate):
        if candidate["basis"] == "model_inference":
            return
        rows = list(con.execute("SELECT r.* FROM revisions r JOIN facts f ON f.id=r.fact_id "
                    "AND f.head=r.revision WHERE r.status='confirmed' AND r.fact_id<>?", (fid,)))
        for row in rows:
            other = json.loads(row["payload"])
            if (all(other[k] == candidate[k] for k in ("conversation_id", "subject_id", "predicate"))
                    and other["value"] != candidate["value"]):
                for key in ((fid, revision), (row["fact_id"], row["revision"])):
                    con.execute("UPDATE revisions SET conflicted=1 WHERE fact_id=? AND revision=?", key)
                    self._invalidate(con, *key, "Conflicting parent")

    def confirm_fact(self, fact_id, *, expected_revision, reason):
        return self.review_fact(fact_id, expected_revision=expected_revision, action="accept", reason=reason)

    def review_fact(self, fact_id, *, expected_revision, action, reason):
        text(reason, 2048)
        if action not in {"accept", "reject", "retract"}:
            raise MemoryError("Invalid review action")
        with self._storage.connect(write=True) as con:
            integer(expected_revision)
            current = self._fact(con, fact_id)
            if (action != "accept" and current["status"] == "withdrawn"
                    and expected_revision in {current["revision"], current["revision"]-1}):
                return self._storage.receipt(con, fact=self._view(con, current))
            old = self._expected(con, fact_id, expected_revision)
            candidate = json.loads(old["payload"])
            if action == "accept":
                if old["status"] != "pending" or old["review_status"] != "pending":
                    raise MemoryError("Only active pending proposals may be accepted")
                self._candidate(con, **candidate)
            elif old["status"] == "withdrawn":
                return self._storage.receipt(con, fact=self._view(con, old))
            revision = expected_revision + 1
            self._invalidate(con, fact_id, expected_revision, "Parent revision changed")
            con.execute("UPDATE revisions SET status='corrected' WHERE fact_id=? AND revision=?",
                        (fact_id, expected_revision))
            status = ("pending" if candidate["basis"] == "model_inference" else "confirmed") if action == "accept" else "withdrawn"
            self._insert(con, fact_id, revision, candidate, status,
                         "accepted" if action == "accept" else "rejected", reason)
            if action == "accept":
                self._conflicts(con, fact_id, revision, candidate)
            else:
                con.execute("INSERT OR IGNORE INTO suppressions VALUES(?)", (digest(candidate),))
            self._storage.advance(con, action, fact_id, reason)
            return self._storage.receipt(con, fact=self._view(con, self._fact(con, fact_id)))

    def correct_fact(self, fact_id, *, expected_revision, reason, **replacement):
        text(reason, 2048)
        with self._storage.connect(write=True) as con:
            old = self._expected(con, fact_id, expected_revision)
            if old["status"] == "withdrawn":
                raise MemoryError("Withdrawn facts cannot be resurrected by correction")
            candidate = self._candidate(con, **replacement)
            if candidate == json.loads(old["payload"]):
                raise MemoryError("Correction requires new content or evidence")
            self._invalidate(con, fact_id, expected_revision, "Parent corrected")
            con.execute("UPDATE revisions SET status='corrected' WHERE fact_id=? AND revision=?",
                        (fact_id, expected_revision))
            self._insert(con, fact_id, expected_revision+1, candidate, "pending", "pending", reason)
            self._storage.advance(con, "correct_fact", fact_id, reason)
            return self._storage.receipt(con, fact=self._view(con, self._fact(con, fact_id)))

    def withdraw_fact(self, fact_id, *, expected_revision, reason):
        # The retry check and withdrawal share the same writer transaction.
        return self.review_fact(fact_id, expected_revision=expected_revision, action="retract", reason=reason)

    def withdraw_event(self, event_id, *, reason, expected_version=None):
        text(reason, 2048)
        if expected_version is not None:
            integer(expected_version)
        with self._storage.connect(write=True) as con:
            row = self._event(con, event_id)
            if row["status"] != "withdrawn":
                if expected_version is not None and expected_version != row["version"]:
                    raise ConflictError("Event version changed")
                affected = list(con.execute("SELECT fact_id,revision FROM evidence WHERE event_id=?", (event_id,)))
                for fid, revision in affected:
                    self._invalidate(con, fid, revision, "Source withdrawn")
                    con.execute("UPDATE revisions SET status='withdrawn',reason='Source withdrawn' "
                                "WHERE fact_id=? AND revision=? AND status IN ('pending','confirmed')", (fid, revision))
                con.execute("UPDATE events SET status='withdrawn',version=version+1,reason=? WHERE id=?", (reason, event_id))
                self._storage.advance(con, "withdraw_event", event_id, reason)
            row = self._event(con, event_id)
            return self._storage.receipt(con, event={**dict(row), "payload": json.loads(row["payload"]),
                "ref": self._ref("event", row), "current_usable": False})
