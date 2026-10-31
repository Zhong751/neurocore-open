"""Audit reads and currently usable evidence are deliberately separate."""
import json

from ._storage import ConflictError, MemoryError, Storage, digest, integer, text


class MemoryReader:
    def __init__(self, directory, *, brain_id):
        self._storage = Storage(directory, brain_id)

    def read_connection(self):
        """Restricted SQL read snapshot; no DDL/DML/ATTACH/PRAGMA allowed."""
        return self._storage.connect()

    def _read(self, operation):
        with self.read_connection() as con:
            result = self._storage.receipt(con, **operation(con))
        with self.read_connection() as con:
            if self._storage.authority(con)["epoch"] != result["epoch"]:
                raise ConflictError("Evidence changed during read; retry")
        return result

    def authority(self):
        return self._read(lambda con: {})

    def _ref(self, kind, row):
        return {"brain_id": self._storage.brain_id, "store_id": self._storage.store_id,
                "kind": kind, "record_id": row["id" if kind == "event" else "fact_id"],
                "version": row["version" if kind == "event" else "revision"], "digest": row["digest"]}

    def _matches(self, ref, kind, row):
        return (isinstance(ref, dict) and type(ref.get("version")) is int
                and ref == self._ref(kind, row))

    @staticmethod
    def _event(con, event_id):
        row = con.execute("SELECT * FROM events WHERE id=?", (text(event_id),)).fetchone()
        if row is None:
            raise MemoryError("Event not found")
        if digest(json.loads(row["payload"])) != row["digest"]:
            raise MemoryError("Event integrity check failed")
        return row

    @staticmethod
    def _fact(con, fact_id, revision=None):
        row = con.execute("SELECT r.*, f.head FROM facts f JOIN revisions r ON r.fact_id=f.id "
                          "AND r.revision=COALESCE(?,f.head) WHERE f.id=?",
                          (revision, text(fact_id))).fetchone()
        if row is None:
            raise MemoryError("Fact revision not found")
        if digest(json.loads(row["payload"])) != row["digest"]:
            raise MemoryError("Fact integrity check failed")
        return row

    def _sources(self, con, candidate):
        support = False
        for item in candidate["evidence"]:
            row = self._event(con, item["ref"]["record_id"])
            event = json.loads(row["payload"])
            if (not self._matches(item["ref"], "event", row) or row["status"] != "active"
                    or event["content"][item["start"]:item["end"]] != item["quote"]
                    or event["conversation_id"] != candidate["conversation_id"]):
                raise MemoryError("Evidence is stale, withdrawn or mismatched")
            if candidate["basis"] == "direct_statement" and (
                    event["speaker_id"] != candidate["subject_id"] or event["role"] != "user"):
                raise MemoryError("Direct statements must retain the actual user speaker")
            if item["relation"] == "supports":
                support = True
                if candidate["basis"] != "model_inference" and (
                        event["role"] != "user" or event["provenance"] != "user_statement"):
                    raise MemoryError("Only user statements can support user facts")
        if not support:
            raise MemoryError("At least one supporting source is required")

    def _usable(self, con, fact_id, revision):
        # Iterative traversal avoids Python recursion limits; cycles fail closed.
        todo, done, active = [(fact_id, revision, False)], set(), set()
        while todo:
            fid, rev, leaving = todo.pop()
            key = (fid, rev)
            if leaving:
                active.remove(key)
                done.add(key)
                continue
            if key in active:
                raise MemoryError("Dependency cycle")
            if key in done:
                continue
            row = self._fact(con, fid, rev)
            candidate = json.loads(row["payload"])
            if (row["head"] != rev or row["status"] != "confirmed"
                    or row["review_status"] != "accepted" or row["conflicted"]
                    or candidate["basis"] == "model_inference"):
                raise MemoryError("Fact revision is not currently usable")
            self._sources(con, candidate)
            indexed = {tuple(r) for r in con.execute(
                "SELECT parent_id,parent_revision FROM dependencies WHERE child_id=? AND child_revision=?", key)}
            if indexed != {(p["record_id"], p["version"]) for p in candidate["parents"]}:
                raise MemoryError("Dependency integrity check failed")
            sources = {r[0] for r in con.execute(
                "SELECT event_id FROM evidence WHERE fact_id=? AND revision=?", key)}
            if sources != {e["ref"]["record_id"] for e in candidate["evidence"]}:
                raise MemoryError("Source index integrity check failed")
            active.add(key)
            todo.append((fid, rev, True))
            for parent in candidate["parents"]:
                if not self._matches(parent, "fact", self._fact(con, parent["record_id"], parent["version"])):
                    raise MemoryError("Parent reference mismatch")
                todo.append((parent["record_id"], parent["version"], False))

    def _view(self, con, row):
        try:
            self._usable(con, row["fact_id"], row["revision"])
            usable, reason = True, None
        except MemoryError as exc:
            usable, reason = False, str(exc)
        return {**dict(row), "payload": json.loads(row["payload"]),
                "ref": self._ref("fact", row), "current_usable": usable, "unusable_reason": reason}

    def get_event(self, event_id):
        def read(con):
            row = self._event(con, event_id)
            return {"event": {**dict(row), "payload": json.loads(row["payload"]),
                              "ref": self._ref("event", row), "current_usable": row["status"] == "active"}}
        return self._read(read)

    def cite(self, event_id, start, end, *, relation="supports"):
        integer(start, 0)
        integer(end)
        if relation not in {"supports", "opposes", "context"}:
            raise MemoryError("Invalid evidence relation")
        event = self.get_event(event_id)["event"]
        if not event["current_usable"] or not start < end <= len(event["payload"]["content"]) or end-start > 4096:
            raise MemoryError("Invalid or unavailable source span")
        return {"ref": event["ref"], "start": start, "end": end,
                "quote": event["payload"]["content"][start:end], "relation": relation}

    def get_fact(self, fact_id, *, revision=None):
        if revision is not None:
            integer(revision)
        return self._read(lambda con: {"fact": self._view(con, self._fact(con, fact_id, revision))})

    def get_sources(self, fact_id, *, revision=None):
        if revision is not None:
            integer(revision)
        def read(con):
            fact = self._view(con, self._fact(con, fact_id, revision))
            sources = []
            for evidence in fact["payload"]["evidence"]:
                row = self._event(con, evidence["ref"]["record_id"])
                sources.append({"evidence": evidence, "event": json.loads(row["payload"]),
                    "status": row["status"], "version": row["version"],
                    "valid": row["status"] == "active" and self._matches(evidence["ref"], "event", row)})
            return {"fact_ref": fact["ref"], "current_usable": fact["current_usable"], "sources": sources}
        return self._read(read)

    def list_valid_facts(self, *, subject_id=None, conversation_id=None, limit=100):
        integer(limit)
        if limit > 1000:
            raise MemoryError("Limit exceeds 1000")
        def read(con):
            hits = []
            for row in con.execute("SELECT r.*,f.head FROM facts f JOIN revisions r "
                                   "ON r.fact_id=f.id AND r.revision=f.head ORDER BY f.rowid"):
                view = self._view(con, row)
                p = view["payload"]
                if (view["current_usable"] and (subject_id is None or p["subject_id"] == subject_id)
                        and (conversation_id is None or p["conversation_id"] == conversation_id)):
                    hits.append(view)
                    if len(hits) == limit:
                        break
            return {"facts": hits}
        return self._read(read)

    def validate_references(self, refs, *, expected_epoch=None):
        if not isinstance(refs, list) or len(refs) > 64:
            raise MemoryError("Expected at most 64 references")
        if expected_epoch is not None:
            integer(expected_epoch, 0)
        def read(con):
            if expected_epoch is not None and self._storage.authority(con)["epoch"] != expected_epoch:
                raise ConflictError("Authority epoch changed")
            results = []
            for ref in refs:
                try:
                    if not isinstance(ref, dict):
                        raise MemoryError("Invalid reference")
                    if ref.get("kind") == "event":
                        row = self._event(con, ref.get("record_id"))
                        valid = row["status"] == "active" and self._matches(ref, "event", row)
                    elif ref.get("kind") == "fact":
                        row = self._fact(con, ref.get("record_id"), integer(ref.get("version")))
                        self._usable(con, row["fact_id"], row["revision"])
                        valid = self._matches(ref, "fact", row)
                    else:
                        raise MemoryError("Unknown reference kind")
                    results.append({"valid": valid, "reason": None if valid else "Reference mismatch or withdrawal"})
                except MemoryError as exc:
                    results.append({"valid": False, "reason": str(exc)})
            return {"valid": all(r["valid"] for r in results), "results": results}
        return self._read(read)
