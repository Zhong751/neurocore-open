"""Single-instance SQLite authority. Opening never creates or migrates a store."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

CONTRACT = "neurocore.memory/1"
SCHEMA_VERSION = 1


class MemoryError(ValueError):
    """Invalid input, source, schema or authority; no silent fallback."""


class ConflictError(MemoryError):
    """A revision, epoch or idempotency key no longer matches."""


def dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))


def digest(value):
    return hashlib.sha256(dump(value).encode("utf-8")).hexdigest()


def text(value, maximum=256):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise MemoryError("Expected bounded nonempty text")
    return value


def integer(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise MemoryError("Invalid integer")
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


SCHEMA = (
    "CREATE TABLE authority(schema_version INTEGER, brain_id TEXT, store_id TEXT, epoch INTEGER)",
    "CREATE TABLE events(id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL, "
    "version INTEGER NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL)",
    "CREATE TABLE facts(id TEXT PRIMARY KEY, head INTEGER NOT NULL)",
    "CREATE TABLE revisions(fact_id TEXT REFERENCES facts(id), revision INTEGER, "
    "payload TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, review_status TEXT NOT NULL, "
    "conflicted INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, "
    "PRIMARY KEY(fact_id,revision))",
    "CREATE TABLE evidence(fact_id TEXT, revision INTEGER, event_id TEXT REFERENCES events(id), "
    "PRIMARY KEY(fact_id,revision,event_id), "
    "FOREIGN KEY(fact_id,revision) REFERENCES revisions(fact_id,revision))",
    "CREATE TABLE dependencies(child_id TEXT, child_revision INTEGER, parent_id TEXT, parent_revision INTEGER, "
    "PRIMARY KEY(child_id,child_revision,parent_id,parent_revision), "
    "FOREIGN KEY(child_id,child_revision) REFERENCES revisions(fact_id,revision), "
    "FOREIGN KEY(parent_id,parent_revision) REFERENCES revisions(fact_id,revision))",
    "CREATE INDEX source_dependents ON evidence(event_id)",
    "CREATE INDEX parent_dependents ON dependencies(parent_id,parent_revision)",
    "CREATE TABLE suppressions(digest TEXT PRIMARY KEY)",
    "CREATE TABLE audit(sequence INTEGER PRIMARY KEY, action TEXT, record_id TEXT, reason TEXT, epoch INTEGER)",
)


def safe_path(directory):
    root = Path(directory).absolute()
    path = root / "memory.sqlite3"
    for item in (*root.parents, root, path):
        if item.is_symlink() or item.is_junction():
            raise MemoryError("Linked storage paths are unsupported")
    if path.exists() and path.stat().st_nlink != 1:
        raise MemoryError("Hard-linked stores are unsupported")
    return path


def create(directory, brain_id):
    text(brain_id)
    path = safe_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation: never initialize over an existing or failed store.
    with path.open("xb"):
        pass
    con = sqlite3.connect(path, isolation_level=None)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA:
            con.execute(statement)
        con.execute("INSERT INTO authority VALUES(?,?,?,0)",
                    (SCHEMA_VERSION, brain_id, uuid.uuid4().hex))
        con.commit()
    finally:
        con.close()


def readonly_authorizer(action, *_):
    return sqlite3.SQLITE_OK if action in {
        sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_RECURSIVE,
    } else sqlite3.SQLITE_DENY


class Storage:
    def __init__(self, directory, brain_id, *, recover=False):
        self.path = safe_path(directory)
        self.brain_id = text(brain_id)
        self.store_id = None
        # Only an explicit writer open may let SQLite recover a hot journal.
        with self.connect(write=recover) as con:
            self.store_id = self.authority(con)["store_id"]

    def authority(self, con):
        rows = con.execute("SELECT * FROM authority").fetchall()
        if (len(rows) != 1 or rows[0]["schema_version"] != SCHEMA_VERSION
                or rows[0]["brain_id"] != self.brain_id or not rows[0]["store_id"]
                or (self.store_id is not None and rows[0]["store_id"] != self.store_id)):
            raise MemoryError("Unsupported schema or mismatched instance authority")
        integer(rows[0]["epoch"], 0)
        return dict(rows[0])

    @contextmanager
    def connect(self, *, write=False):
        path = safe_path(self.path.parent)
        if not path.is_file():
            raise MemoryError("Store missing; explicit creation is required")
        con = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"),
                              uri=True, isolation_level=None, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            if write:
                con.execute("PRAGMA foreign_keys=ON")
                con.execute("PRAGMA synchronous=FULL")
            else:
                con.execute("PRAGMA query_only=ON")
                con.set_authorizer(readonly_authorizer)
            con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self.authority(con)
            yield con
            con.commit()
        finally:
            con.close()  # Also rolls back any uncommitted write on failure.

    def receipt(self, con, **fields):
        return {"contract_version": CONTRACT, **self.authority(con), **fields}

    def advance(self, con, action, record_id, reason):
        con.execute("UPDATE authority SET epoch=epoch+1")
        con.execute("INSERT INTO audit(action,record_id,reason,epoch) VALUES(?,?,?,?)",
                    (action, record_id, reason, self.authority(con)["epoch"]))
