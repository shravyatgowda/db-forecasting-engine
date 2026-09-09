"""
disk_reading.py

Compares naive line-by-line file reading against chunked/buffered
reading for sweeping a large log file -- Python's built-in file
iteration is already buffered at the OS level, but explicit large-block
reads reduce the number of Python-level I/O calls, which matters when
sweeping files with hundreds of thousands of lines.
"""

import time


def read_naive(path: str) -> list[str]:
    """One readline() per line -- simplest approach, most function-call overhead."""
    lines = []
    with open(path, "r") as f:
        line = f.readline()
        while line:
            lines.append(line.rstrip("\n"))
            line = f.readline()
    return lines


def read_buffered_chunks(path: str, chunk_size: int = 1024 * 1024) -> list[str]:
    """
    Reads in large fixed-size byte chunks and splits into lines manually,
    carrying over any partial line at a chunk boundary to the next chunk
    -- fewer, larger read() syscalls instead of many small ones.
    """
    lines = []
    leftover = ""
    with open(path, "r") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunk = leftover + chunk
            parts = chunk.split("\n")
            leftover = parts.pop()  # last part may be incomplete -- carry to next chunk
            lines.extend(parts)
    if leftover:
        lines.append(leftover)
    return lines


def benchmark_reading(path: str) -> dict:
    start = time.perf_counter()
    naive_lines = read_naive(path)
    naive_time = time.perf_counter() - start

    start = time.perf_counter()
    buffered_lines = read_buffered_chunks(path)
    buffered_time = time.perf_counter() - start

    return {
        "naive_seconds": naive_time,
        "buffered_seconds": buffered_time,
        "speedup": naive_time / buffered_time if buffered_time > 0 else float("inf"),
        "lines_match": naive_lines == buffered_lines,
        "line_count": len(naive_lines),
    }
