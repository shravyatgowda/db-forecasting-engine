import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.disk_reading import read_naive, read_buffered_chunks


def _write_test_file(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def test_naive_and_buffered_produce_identical_output(tmp_path):
    path = tmp_path / "test.log"
    lines = [f"TXN|{i}|2026-01-01T00:00:00|COMMIT|{i%100}" for i in range(1000)]
    _write_test_file(path, lines)

    naive_result = read_naive(str(path))
    buffered_result = read_buffered_chunks(str(path), chunk_size=4096)  # small chunks to force boundary-splitting

    assert naive_result == buffered_result
    assert len(naive_result) == 1000


def test_buffered_reading_handles_chunk_boundary_mid_line(tmp_path):
    """The riskiest bug in chunked reading is splitting a line exactly
    at a chunk boundary -- use a tiny chunk size to force this and
    confirm no line gets corrupted or duplicated."""
    path = tmp_path / "test.log"
    lines = ["A" * 50, "B" * 50, "C" * 50, "D" * 50]
    _write_test_file(path, lines)

    result = read_buffered_chunks(str(path), chunk_size=17)  # deliberately awkward size
    assert result == lines


def test_empty_file(tmp_path):
    path = tmp_path / "empty.log"
    path.write_text("")
    assert read_naive(str(path)) == []
    assert read_buffered_chunks(str(path)) == []


def test_file_without_trailing_newline(tmp_path):
    path = tmp_path / "no_trailing_newline.log"
    path.write_text("line1\nline2\nline3")  # no trailing \n
    naive_result = read_naive(str(path))
    buffered_result = read_buffered_chunks(str(path), chunk_size=6)
    assert naive_result == buffered_result == ["line1", "line2", "line3"]
