-- schema.sql
--
-- High-Volume Database Profiling — schema
--
-- Normalization (3NF): server identity/metadata (hostname, datacenter,
-- role) lives once in `servers`; `metrics` stores only the FK + the
-- atomic per-reading values, so no server attribute is repeated across
-- the (potentially millions of) metric rows.

CREATE TABLE IF NOT EXISTS servers (
    server_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname    TEXT NOT NULL UNIQUE,
    datacenter  TEXT NOT NULL,
    role        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    metric_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id   INTEGER NOT NULL REFERENCES servers(server_id),
    ts          TEXT NOT NULL,       -- ISO 8601 timestamp
    usage_pct   REAL NOT NULL CHECK (usage_pct >= 0 AND usage_pct <= 100)
);

-- Deliberately created WITHOUT the composite index below by default —
-- query_profiler.py adds it on demand so the same queries can be timed
-- both with and without it, to measure the actual before/after effect
-- rather than assert one.
-- CREATE INDEX idx_metrics_server_ts ON metrics(server_id, ts);
