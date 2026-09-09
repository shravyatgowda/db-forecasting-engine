"""
log_parser.py

A trie (prefix tree) based log-line classifier: instead of testing each
incoming log line against every known format with a list of regexes
(O(number of formats) per line), a trie lets classification cost scale
with the length of the line's prefix, not the number of known formats
-- this matters when sweeping large log files with many format variants.

Well-formed lines match one of the registered patterns and get parsed
into structured fields. Lines that don't match any registered prefix
are flagged as corrupted/unrecognized and isolated for separate
handling, rather than silently mis-parsed or crashing the sweep.
"""

import re
from dataclasses import dataclass, field


@dataclass
class TrieNode:
    children: dict = field(default_factory=dict)
    # If this node marks the end of a registered prefix, the format name
    # and the regex used to fully parse+validate a matching line.
    format_name: str | None = None
    full_pattern: re.Pattern | None = None


class LogFormatTrie:
    """
    Registers known log line PREFIXES (e.g. "TXN|", "ERROR|") in a trie,
    each mapped to a full regex used to validate and extract fields once
    the prefix identifies which format to expect.
    """

    def __init__(self):
        self.root = TrieNode()

    def register_format(self, prefix: str, format_name: str, full_pattern: str):
        node = self.root
        for ch in prefix:
            node = node.children.setdefault(ch, TrieNode())
        node.format_name = format_name
        node.full_pattern = re.compile(full_pattern)

    def _find_format(self, line: str):
        """Walk the trie along `line`'s characters; return the format
        registered at the deepest matching node reached, or None."""
        node = self.root
        best_match = None
        for ch in line:
            if ch not in node.children:
                break
            node = node.children[ch]
            if node.format_name is not None:
                best_match = (node.format_name, node.full_pattern)
        return best_match

    def parse_line(self, line: str) -> dict:
        match = self._find_format(line)
        if match is None:
            return {"valid": False, "format": None, "fields": None, "raw": line, "reason": "no matching prefix"}

        format_name, pattern = match
        m = pattern.match(line)
        if m is None:
            return {
                "valid": False,
                "format": format_name,
                "fields": None,
                "raw": line,
                "reason": "prefix matched but full line failed format validation",
            }

        return {"valid": True, "format": format_name, "fields": m.groupdict(), "raw": line, "reason": None}


def build_default_trie() -> LogFormatTrie:
    """Registers the log formats used in this project's synthetic logs."""
    trie = LogFormatTrie()
    trie.register_format(
        "TXN|",
        "transaction",
        r"^TXN\|(?P<txn_id>\d+)\|(?P<timestamp>[\d\-T:]+)\|(?P<status>COMMIT|ROLLBACK|PENDING)\|(?P<duration_ms>\d+)$",
    )
    trie.register_format(
        "ERROR|",
        "error",
        r"^ERROR\|(?P<timestamp>[\d\-T:]+)\|(?P<code>[A-Z0-9_]+)\|(?P<message>.+)$",
    )
    trie.register_format(
        "INFO|",
        "info",
        r"^INFO\|(?P<timestamp>[\d\-T:]+)\|(?P<message>.+)$",
    )
    return trie


def sweep_log_lines(lines: list[str], trie: LogFormatTrie | None = None) -> dict:
    """
    Parses every line, separating valid transaction/error/info entries
    from corrupted/unrecognized ones. Returns counts and the isolated
    corrupted lines for follow-up handling.
    """
    trie = trie or build_default_trie()
    results = {"transaction": [], "error": [], "info": [], "corrupted": []}

    for line in lines:
        parsed = trie.parse_line(line)
        if not parsed["valid"]:
            results["corrupted"].append(parsed)
        else:
            results[parsed["format"]].append(parsed)

    return results
