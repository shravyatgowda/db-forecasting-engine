"""
generate_log_file.py

Writes a large synthetic log file mixing well-formed TXN/ERROR/INFO
lines with a realistic fraction of corrupted lines, for benchmarking
the log sweep (parsing throughput + corruption isolation) at scale.
"""

import random


def generate_log_file(path: str, n_lines: int = 200_000, corruption_rate: float = 0.02, seed: int = 3):
    rng = random.Random(seed)
    statuses = ["COMMIT", "ROLLBACK", "PENDING"]
    error_codes = ["DB_TIMEOUT", "DEADLOCK", "CONN_REFUSED", "DISK_FULL"]

    with open(path, "w") as f:
        for i in range(n_lines):
            roll = rng.random()
            if roll < corruption_rate:
                # Inject one of a few realistic corruption patterns
                corruption_type = rng.choice(["truncated", "garbage", "empty", "wrong_delim"])
                if corruption_type == "truncated":
                    f.write(f"TXN|{i}|2026-09-06T10:00:00|COM\n")
                elif corruption_type == "garbage":
                    f.write("�\x00\x01CORRUPT_BINARY_FRAGMENT\n")
                elif corruption_type == "empty":
                    f.write("\n")
                else:
                    f.write(f"TXN,{i},2026-09-06T10:00:00,COMMIT,45\n")
            elif roll < corruption_rate + 0.15:
                code = rng.choice(error_codes)
                f.write(f"ERROR|2026-09-06T10:{i%60:02d}:00|{code}|Something went wrong on request {i}\n")
            elif roll < corruption_rate + 0.25:
                f.write(f"INFO|2026-09-06T10:{i%60:02d}:00|Processed batch {i}\n")
            else:
                status = rng.choice(statuses)
                duration = rng.randint(5, 500)
                f.write(f"TXN|{i}|2026-09-06T10:{i%60:02d}:00|{status}|{duration}\n")


if __name__ == "__main__":
    generate_log_file("data/transactions.log")
    print("Log file written to data/transactions.log")
