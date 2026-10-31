"""Inspect M1 bytes in RAM; SQLite never opens the source database path."""
from contextlib import closing
import sqlite3

from ._files import PackageError, child_path, read_bytes, signature
from .memory._storage import SCHEMA, SCHEMA_VERSION

DATABASE_LIMIT = 256 * 1024 * 1024


def _no_sidecars(root):
    for suffix in ("-journal", "-wal", "-shm"):
        path = child_path(root, "memory.sqlite3" + suffix)
        if path.exists():
            raise PackageError("memory-state: journal/WAL present; inspect again after an explicit writer closes")


def inspect_memory(root, instance_id, store_id):
    _no_sidecars(root)
    path = child_path(root, "memory.sqlite3")
    before = signature(path.stat())
    data = read_bytes(path, DATABASE_LIMIT)
    if data[:16] != b"SQLite format 3\x00" or len(data) < 100:
        raise PackageError("memory-format: invalid SQLite header")
    if data[18:20] != b"\x01\x01":
        raise PackageError("memory-state: WAL or unsupported journal format; no recovery attempted")
    schema_query = "SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name"
    with closing(sqlite3.connect(":memory:")) as expected:
        for statement in SCHEMA:
            expected.execute(statement)
        expected_schema = expected.execute(schema_query).fetchall()
    with closing(sqlite3.connect(":memory:")) as con:
        con.deserialize(data)
        con.execute("PRAGMA trusted_schema=OFF")
        con.execute("PRAGMA query_only=ON")
        if con.execute(schema_query).fetchall() != expected_schema:
            raise PackageError("memory-schema: unsupported or incomplete M1 schema")
        if con.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise PackageError("memory-integrity: SQLite structure check failed")
        if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise PackageError("memory-integrity: broken foreign key")
        rows = con.execute("SELECT schema_version,brain_id,store_id,epoch FROM authority").fetchall()
        if (len(rows) != 1 or rows[0][:3] != (SCHEMA_VERSION, instance_id, store_id)
                or type(rows[0][3]) is not int or rows[0][3] < 0):
            raise PackageError("memory-authority: identity/store/version mismatch")
    _no_sidecars(root)
    if signature(path.stat()) != before:
        raise PackageError("memory-state: changed during inspection; retry when idle")
