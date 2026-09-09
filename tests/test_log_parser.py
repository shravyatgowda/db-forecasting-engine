import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.log_parser import build_default_trie, sweep_log_lines


def test_valid_transaction_line_parsed():
    trie = build_default_trie()
    result = trie.parse_line("TXN|1001|2026-09-06T10:00:00|COMMIT|45")
    assert result["valid"] is True
    assert result["format"] == "transaction"
    assert result["fields"]["txn_id"] == "1001"
    assert result["fields"]["status"] == "COMMIT"
    assert result["fields"]["duration_ms"] == "45"


def test_valid_error_line_parsed():
    trie = build_default_trie()
    result = trie.parse_line("ERROR|2026-09-06T10:00:02|DB_TIMEOUT|Connection timed out")
    assert result["valid"] is True
    assert result["format"] == "error"
    assert result["fields"]["code"] == "DB_TIMEOUT"


def test_valid_info_line_parsed():
    trie = build_default_trie()
    result = trie.parse_line("INFO|2026-09-06T10:00:03|Server started")
    assert result["valid"] is True
    assert result["format"] == "info"


def test_prefix_matches_but_body_malformed_is_corrupted():
    trie = build_default_trie()
    result = trie.parse_line("TXN|corrupted_garbage_line_here")
    assert result["valid"] is False
    assert result["format"] == "transaction"  # prefix WAS recognized
    assert "failed format validation" in result["reason"]


def test_no_matching_prefix_is_corrupted():
    trie = build_default_trie()
    result = trie.parse_line("RANDOM_JUNK_NOT_A_LOG_LINE")
    assert result["valid"] is False
    assert result["format"] is None
    assert "no matching prefix" in result["reason"]


def test_empty_line_is_corrupted():
    trie = build_default_trie()
    result = trie.parse_line("")
    assert result["valid"] is False


def test_wrong_status_value_rejected_by_full_pattern():
    trie = build_default_trie()
    # "MAYBE" is not one of the allowed status values in the regex
    result = trie.parse_line("TXN|1001|2026-09-06T10:00:00|MAYBE|45")
    assert result["valid"] is False


def test_sweep_log_lines_categorizes_correctly():
    lines = [
        "TXN|1|2026-09-06T10:00:00|COMMIT|10",
        "TXN|2|2026-09-06T10:00:01|ROLLBACK|20",
        "ERROR|2026-09-06T10:00:02|DEADLOCK|deadlock detected",
        "INFO|2026-09-06T10:00:03|batch done",
        "GARBAGE_LINE",
        "",
    ]
    results = sweep_log_lines(lines)
    assert len(results["transaction"]) == 2
    assert len(results["error"]) == 1
    assert len(results["info"]) == 1
    assert len(results["corrupted"]) == 2


def test_trie_scales_to_many_registered_formats():
    """Sanity check that adding more formats doesn't break lookup for
    existing ones -- the whole point of using a trie over a linear list
    of regexes is that lookup cost doesn't grow with format count."""
    from src.log_parser import LogFormatTrie

    trie = LogFormatTrie()
    for i in range(50):
        trie.register_format(f"TYPE{i}|", f"type{i}", rf"^TYPE{i}\|(?P<data>.+)$")
    trie.register_format("TXN|", "transaction", r"^TXN\|(?P<id>\d+)$")

    result = trie.parse_line("TXN|123")
    assert result["valid"] is True
    assert result["format"] == "transaction"

    result2 = trie.parse_line("TYPE25|somedata")
    assert result2["valid"] is True
    assert result2["format"] == "type25"
