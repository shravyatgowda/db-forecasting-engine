"""
db_setup.py

Creates the servers/metrics schema and bulk-loads synthetic metrics for
many servers, so the query profiler has a realistically large table to
work against (not just a handful of rows, where an index wouldn't show
any measurable effect).
"""

import sqlite3
from pathlib import Path

import numpy as np

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(db_path: str):
    conn = get_connection(db_path)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()


def bulk_load_metrics(
    db_path: str,
    n_servers: int = 50,
    n_points_per_server: int = 10_000,
    seed: int = 11,
) -> int:
    """
    Populates `servers` and `metrics` with synthetic data: n_servers
    servers, each with n_points_per_server readings. Returns the total
    row count inserted into `metrics`.
    """
    rng = np.random.default_rng(seed)
    conn = get_connection(db_path)

    conn.execute("BEGIN")
    for i in range(n_servers):
        conn.execute(
            "INSERT INTO servers (hostname, datacenter, role) VALUES (?, ?, ?)",
            (f"server-{i:03d}", rng.choice(["us-east-1", "us-west-2", "ap-south-1"]), rng.choice(["db", "app", "cache"])),
        )
    conn.execute("COMMIT")

    server_ids = [row["server_id"] for row in conn.execute("SELECT server_id FROM servers").fetchall()]

    conn.execute("BEGIN")
    total_rows = 0
    batch = []
    for server_id in server_ids:
        base_usage = rng.uniform(30, 60)
        for t in range(n_points_per_server):
            ts = f"2026-01-{1 + (t // 1440):02d}T{(t % 1440) // 60:02d}:{t % 60:02d}:00"
            usage = float(np.clip(base_usage + rng.normal(0, 10), 0, 100))
            batch.append((server_id, ts, usage))
            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT INTO metrics (server_id, ts, usage_pct) VALUES (?, ?, ?)", batch
                )
                total_rows += len(batch)
                batch = []
    if batch:
        conn.executemany("INSERT INTO metrics (server_id, ts, usage_pct) VALUES (?, ?, ?)", batch)
        total_rows += len(batch)
    conn.execute("COMMIT")
    conn.close()

    return total_rows


if __name__ == "__main__":
    db_path = "data/metrics.db"
    Path(db_path).unlink(missing_ok=True)
    init_schema(db_path)
    rows = bulk_load_metrics(db_path)
    print(f"Loaded {rows:,} metric rows into {db_path}")
