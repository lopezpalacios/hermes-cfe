"""SQLite durable queue with leases for offline worker tests and single-host use."""
from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class LeaseConflict(RuntimeError):
    """Lease is expired, superseded, or not held by the caller."""


@dataclass(frozen=True)
class JobRef:
    job_id: str
    state: str
    created: bool


@dataclass(frozen=True)
class Lease:
    job_id: str
    lease_token: str
    worker_id: str
    attempts: int
    bucket: str
    object_key: str
    object_version: str
    sha256: str | None
    lease_until: float


@dataclass(frozen=True)
class Job:
    job_id: str
    state: str
    attempts: int
    bucket: str
    object_key: str
    object_version: str
    sha256: str | None
    error_class: str | None
    result: dict[str, Any] | None


class DurableJobQueue:
    """Transactional SQLite queue; production adapter still needs schema review."""

    def __init__(self, path: str | Path, *, lease_seconds: float = 60,
                 max_attempts: int = 5, base_retry_seconds: float = 2):
        self.path = str(path)
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=30, isolation_level=None,
                                    check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              bucket TEXT NOT NULL,
              object_key TEXT NOT NULL,
              object_version TEXT NOT NULL,
              sha256 TEXT,
              state TEXT NOT NULL CHECK(state IN ('queued','running','harvested','business_exception','failed')),
              attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
              next_attempt REAL NOT NULL DEFAULT 0,
              lease_token TEXT,
              lease_owner TEXT,
              lease_until REAL,
              error_class TEXT,
              result_json TEXT,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              UNIQUE(bucket, object_key, object_version)
            );
            CREATE INDEX IF NOT EXISTS jobs_claimable ON jobs(state, next_attempt, created_at);
        """)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def enqueue(self, bucket: str, object_key: str, object_version: str,
                sha256: str | None = None) -> JobRef:
        if not bucket or not object_key or not object_version:
            raise ValueError("bucket, object key, and immutable version are required")
        now = time.time()
        job_id = str(uuid.uuid4())
        with self._lock:
            cur = self._conn.execute("""
                INSERT INTO jobs(job_id,bucket,object_key,object_version,sha256,state,created_at,updated_at)
                VALUES(?,?,?,?,?,'queued',?,?)
                ON CONFLICT(bucket,object_key,object_version) DO NOTHING
            """, (job_id,bucket,object_key,object_version,sha256,now,now))
            row = self._conn.execute("SELECT job_id,state FROM jobs WHERE bucket=? AND object_key=? AND object_version=?",
                                     (bucket,object_key,object_version)).fetchone()
            return JobRef(row["job_id"], row["state"], cur.rowcount == 1)

    def claim(self, worker_id: str) -> Lease | None:
        if not worker_id:
            raise ValueError("worker ID required")
        now = time.time()
        token = str(uuid.uuid4())
        until = now + self.lease_seconds
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("""
                    SELECT * FROM jobs
                    WHERE (state='queued' AND next_attempt<=?)
                       OR (state='running' AND lease_until<=?)
                    ORDER BY created_at, job_id LIMIT 1
                """, (now,now)).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return None
                attempts = row["attempts"] + 1
                self._conn.execute("""
                    UPDATE jobs SET state='running',attempts=?,lease_token=?,lease_owner=?,lease_until=?,updated_at=?
                    WHERE job_id=?
                """, (attempts,token,worker_id,until,now,row["job_id"]))
                self._conn.execute("COMMIT")
                return Lease(row["job_id"],token,worker_id,attempts,row["bucket"],row["object_key"],
                             row["object_version"],row["sha256"],until)
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _assert_lease(self, lease: Lease) -> None:
        row = self._conn.execute("SELECT state,lease_token,lease_until FROM jobs WHERE job_id=?",
                                 (lease.job_id,)).fetchone()
        if row is None or row["state"] != "running" or row["lease_token"] != lease.lease_token or row["lease_until"] <= time.time():
            raise LeaseConflict("lease no longer belongs to this worker")

    def finish(self, lease: Lease, state: str, *, result: dict[str, Any] | None = None) -> None:
        if state not in {"harvested","business_exception"}:
            raise ValueError("finish state must be harvested or business_exception")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._assert_lease(lease)
                self._conn.execute("""
                    UPDATE jobs SET state=?,result_json=?,error_class=NULL,lease_token=NULL,lease_owner=NULL,lease_until=NULL,updated_at=?
                    WHERE job_id=?
                """, (state,json.dumps(result,sort_keys=True) if result is not None else None,time.time(),lease.job_id))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def fail(self, lease: Lease, error_class: str, *, retryable: bool) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._assert_lease(lease)
                terminal = not retryable or lease.attempts >= self.max_attempts
                state = "failed" if terminal and retryable else ("business_exception" if not retryable else "queued")
                retry_at = time.time() + self.base_retry_seconds * (2 ** max(0,lease.attempts-1)) if state == "queued" else 0
                self._conn.execute("""
                    UPDATE jobs SET state=?,error_class=?,next_attempt=?,lease_token=NULL,lease_owner=NULL,lease_until=NULL,updated_at=?
                    WHERE job_id=?
                """, (state,error_class,retry_at,time.time(),lease.job_id))
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def get(self, job_id: str) -> Job:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE job_id=?",(job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            result = json.loads(row["result_json"]) if row["result_json"] else None
            return Job(row["job_id"],row["state"],row["attempts"],row["bucket"],row["object_key"],
                       row["object_version"],row["sha256"],row["error_class"],result)
