"""
query_profiler.py

Runs a fixed set of representative analytical queries against the
metrics table, both WITHOUT and WITH the composite index on
(server_id, ts), measuring real latency differences -- and under
simulated concurrent read load, since an index's value is most visible
exactly when many queries are competing for engine time at once (the
"minimize database engine load during high-concurrency windows" framing).
"""

import sqlite3
import sys
import threading
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from db_setup import get_connection

QUERIES = {
    "latest_reading_for_server": """
        SELECT usage_pct, ts FROM metrics
        WHERE server_id = ?
        ORDER BY ts DESC LIMIT 1
    """,
    "avg_usage_in_range": """
        SELECT AVG(usage_pct) FROM metrics
        WHERE server_id = ? AND ts BETWEEN ? AND ?
    """,
    "count_saturated_readings": """
        SELECT COUNT(*) FROM metrics
        WHERE server_id = ? AND usage_pct >= 90
    """,
}


def explain_query(conn: sqlite3.Connection, sql: str, params: tuple) -> list[str]:
    plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    return [dict(row)["detail"] for row in plan]


def add_index(conn: sqlite3.Connection):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_server_ts ON metrics(server_id, ts)")


def drop_index(conn: sqlite3.Connection):
    conn.execute("DROP INDEX IF EXISTS idx_metrics_server_ts")


def time_query(conn: sqlite3.Connection, sql: str, params: tuple, n_trials: int = 30) -> float:
    """Average latency in ms over n_trials runs."""
    start = time.perf_counter()
    for _ in range(n_trials):
        conn.execute(sql, params).fetchall()
    elapsed = time.perf_counter() - start
    return (elapsed / n_trials) * 1000


def build_profiling_matrix(db_path: str, sample_server_ids: list[int]) -> dict:
    """
    For each query x {no index, with index}, measures average latency
    and captures the EXPLAIN QUERY PLAN, across a handful of sample
    servers to average out per-server variance.
    """
    results = {}

    for index_state in ("without_index", "with_index"):
        conn = get_connection(db_path)
        if index_state == "with_index":
            add_index(conn)
        else:
            drop_index(conn)

        for query_name, sql in QUERIES.items():
            latencies = []
            plan = None
            for server_id in sample_server_ids:
                if query_name == "avg_usage_in_range":
                    params = (server_id, "2026-01-01T00:00:00", "2026-01-03T00:00:00")
                else:
                    params = (server_id,)
                latencies.append(time_query(conn, sql, params))
                if plan is None:
                    plan = explain_query(conn, sql, params)

            key = (query_name, index_state)
            results[key] = {
                "avg_latency_ms": sum(latencies) / len(latencies),
                "explain_plan": plan,
            }
        conn.close()

    return results


def concurrent_load_test(db_path: str, sample_server_ids: list[int], n_threads: int = 20, use_index: bool = True) -> dict:
    """
    Fires n_threads concurrent readers, each repeatedly running the
    'avg_usage_in_range' query for a different server, and measures
    total wall-clock time and per-query latency under contention --
    this is the "high-concurrency window" scenario a real ops dashboard
    would create with many simultaneous panel refreshes.
    """
    setup_conn = get_connection(db_path)
    if use_index:
        add_index(setup_conn)
    else:
        drop_index(setup_conn)
    setup_conn.close()

    latencies = []
    lock = threading.Lock()

    def worker(server_id):
        conn = get_connection(db_path)
        start = time.perf_counter()
        conn.execute(
            QUERIES["avg_usage_in_range"], (server_id, "2026-01-01T00:00:00", "2026-01-05T00:00:00")
        ).fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        with lock:
            latencies.append(elapsed_ms)
        conn.close()

    threads = [
        threading.Thread(target=worker, args=(sample_server_ids[i % len(sample_server_ids)],))
        for i in range(n_threads)
    ]

    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_elapsed = time.perf_counter() - start

    return {
        "use_index": use_index,
        "n_threads": n_threads,
        "total_wall_time_ms": total_elapsed * 1000,
        "avg_query_latency_ms": sum(latencies) / len(latencies),
        "max_query_latency_ms": max(latencies),
    }
