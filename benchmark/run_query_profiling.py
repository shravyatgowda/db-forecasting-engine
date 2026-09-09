"""
run_query_profiling.py

Sets up the metrics database (500K rows), then runs the profiling
matrix (query x indexed/not) and the concurrent-load test, printing a
clean summary of real, measured latency differences.

Run with:
    python -m benchmark.run_query_profiling
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from src.db_setup import init_schema, bulk_load_metrics
from src.query_profiler import build_profiling_matrix, concurrent_load_test


def main():
    db_path = "data/metrics.db"
    Path(db_path).unlink(missing_ok=True)

    print("Setting up database with 50 servers x 10,000 readings each...")
    init_schema(db_path)
    rows = bulk_load_metrics(db_path, n_servers=50, n_points_per_server=10_000)
    print(f"Loaded {rows:,} rows.\n")

    sample_servers = [1, 10, 25, 40, 50]

    print("=" * 70)
    print("Query Profiling Matrix (avg latency over 30 trials, 5 sample servers)")
    print("=" * 70)
    matrix = build_profiling_matrix(db_path, sample_servers)

    for query_name in ("latest_reading_for_server", "avg_usage_in_range", "count_saturated_readings"):
        without = matrix[(query_name, "without_index")]
        with_idx = matrix[(query_name, "with_index")]
        speedup = without["avg_latency_ms"] / with_idx["avg_latency_ms"]
        print(f"\n{query_name}:")
        print(f"  Without index: {without['avg_latency_ms']:>10.4f} ms  | plan: {without['explain_plan']}")
        print(f"  With index:    {with_idx['avg_latency_ms']:>10.4f} ms  | plan: {with_idx['explain_plan']}")
        print(f"  Speedup:       {speedup:>10.1f}x")

    print("\n" + "=" * 70)
    print("Concurrent Load Test (20 simultaneous readers, high-concurrency window)")
    print("=" * 70)
    without_load = concurrent_load_test(db_path, sample_servers, n_threads=20, use_index=False)
    with_load = concurrent_load_test(db_path, sample_servers, n_threads=20, use_index=True)

    print(f"\nWithout index: total wall time {without_load['total_wall_time_ms']:.1f} ms, "
          f"avg query latency {without_load['avg_query_latency_ms']:.2f} ms, "
          f"max {without_load['max_query_latency_ms']:.2f} ms")
    print(f"With index:    total wall time {with_load['total_wall_time_ms']:.1f} ms, "
          f"avg query latency {with_load['avg_query_latency_ms']:.2f} ms, "
          f"max {with_load['max_query_latency_ms']:.2f} ms")
    print(f"\nTotal wall time improvement: {without_load['total_wall_time_ms']/with_load['total_wall_time_ms']:.1f}x")
    print(f"Avg query latency improvement: {without_load['avg_query_latency_ms']/with_load['avg_query_latency_ms']:.1f}x")


if __name__ == "__main__":
    main()
