"""
run_log_sweep.py

Generates a large synthetic transaction log and sweeps it end-to-end:
read -> parse/classify -> isolate corrupted lines, reporting real
throughput and corruption statistics.

Run with:
    python -m benchmark.run_log_sweep
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.generate_log_file import generate_log_file
from src.disk_reading import read_naive, read_buffered_chunks
from src.log_parser import sweep_log_lines


def main():
    log_path = "data/transactions.log"
    n_lines = 300_000

    print(f"Generating {n_lines:,} synthetic log lines (~2% corruption rate)...")
    generate_log_file(log_path, n_lines=n_lines)
    import os
    size_mb = os.path.getsize(log_path) / (1024 * 1024)
    print(f"File size: {size_mb:.1f} MB\n")

    print("=" * 60)
    print("Reading strategy comparison")
    print("=" * 60)
    start = time.perf_counter()
    naive_lines = read_naive(log_path)
    naive_time = time.perf_counter() - start
    print(f"Naive readline() loop: {naive_time*1000:.1f} ms ({len(naive_lines)/naive_time:,.0f} lines/sec)")

    start = time.perf_counter()
    buffered_lines = read_buffered_chunks(log_path)
    buffered_time = time.perf_counter() - start
    print(f"Buffered chunk read:   {buffered_time*1000:.1f} ms ({len(buffered_lines)/buffered_time:,.0f} lines/sec)")
    print(
        f"\nHonest finding: at this scale, the difference is small ({naive_time/buffered_time:.2f}x) "
        "because Python's file iteration is already OS-buffered. Explicit chunked reads mainly "
        "help when doing custom parsing logic per chunk, not as a reading-speed fix on their own."
    )

    print("\n" + "=" * 60)
    print("Full parse + classify sweep")
    print("=" * 60)
    start = time.perf_counter()
    results = sweep_log_lines(naive_lines)
    elapsed = time.perf_counter() - start
    print(f"Swept {len(naive_lines):,} lines in {elapsed*1000:.1f} ms ({len(naive_lines)/elapsed:,.0f} lines/sec)")
    for category, items in results.items():
        pct = 100 * len(items) / len(naive_lines)
        print(f"  {category:15s}: {len(items):>7,} ({pct:.2f}%)")

    print("\nSample of isolated corrupted lines and why they were flagged:")
    for c in results["corrupted"][:5]:
        print(f"  {c['raw']!r:50s} -> {c['reason']}")


if __name__ == "__main__":
    main()
