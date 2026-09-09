# High-Volume Database Profiling & Statistical Forecasting Engine

Three connected pieces built around a common theme — operating on
system/infrastructure data at scale: forecasting resource saturation
before it happens, sweeping large log files to isolate corrupted
records, and profiling SQL query performance under realistic load.

## 1. Saturation forecasting (real measured results)

Predicts whether a server's disk/memory usage will cross a 90%
saturation threshold within the **next 10 minutes**, using lag and
rolling-window features (not just "is it high right now," which would
be trivial and too late to act on).

Run across 5 random seeds (`python -m benchmark.run_forecast`):

```
  seed |  accuracy |  precision |  recall |  roc_auc
-------------------------------------------------------
     1 |     0.938 |      0.426 |   0.694 |    0.896
     7 |     0.973 |      0.851 |   0.733 |    0.887
    21 |     0.954 |      0.658 |   0.923 |    0.967
    42 |     0.980 |      0.800 |   0.857 |    0.933
    99 |     0.973 |      0.889 |   0.814 |    0.972
-------------------------------------------------------
Average accuracy: 0.963  (range: 0.938 - 0.980)
```

**Honest caveat**: precision swings noticeably across seeds (43–89%)
even though accuracy stays consistently high. This is a real property
of the data, not a bug — saturation events are rare (2–7% of test
points), so a handful of false positives/negatives moves precision a
lot while barely denting overall accuracy. Accuracy alone is a
misleading metric here; precision/recall together tell the real story,
which is why both are reported rather than just the headline number.

Time-series train/test split (train on the past, test on the future) is
used deliberately instead of random shuffling, which would leak future
information into training and inflate the score artificially.

## 2. Log sweep & corruption isolation

A **trie (prefix tree)** based log-line classifier: registered log
formats (TXN/ERROR/INFO) are matched by walking a trie character-by-
character, so classification cost scales with line-prefix length, not
the number of registered formats — relevant when a real system has many
log format variants to check against.

Run on a real 300K-line, 13.6MB generated log (`python -m benchmark.run_log_sweep`):

```
Full parse + classify sweep: 1709.7 ms for 300,000 lines (175,473 lines/sec)
  transaction    : 219,026 (73.01%)
  error          :  44,719 (14.91%)
  info           :  30,190 (10.06%)
  corrupted      :   6,065 (2.02%)
```

Three distinct corruption types are correctly isolated with specific
reasons (truncated lines, wrong delimiter, binary garbage) — see sample
output in the benchmark script.

**Honest finding on "optimizing disk reading"**: I expected chunked
buffered reads to meaningfully beat naive `readline()`. Measured
difference was only ~1.04x — Python's built-in file iteration is
already OS-buffered, so there wasn't much naive inefficiency to fix at
this file size. The real throughput bottleneck is the *parsing/regex
matching* (175K lines/sec), not the disk read itself (4.7M lines/sec) —
worth knowing before "optimizing" the wrong part of a pipeline.

## 3. SQL query profiling matrix

500,000 synthetic metric rows (50 servers × 10,000 readings) in a
normalized SQLite schema, profiling 3 representative queries with and
without a composite index — using real `EXPLAIN QUERY PLAN` output, not
assumed behavior.

Run with `python -m benchmark.run_query_profiling`:

```
latest_reading_for_server:
  Without index: 17.24 ms  | SCAN metrics + TEMP B-TREE FOR ORDER BY
  With index:     0.007 ms | SEARCH metrics USING INDEX idx_metrics_server_ts
  Speedup: 2,596x

avg_usage_in_range:
  Without index: 16.15 ms  | SCAN metrics
  With index:     0.27 ms  | SEARCH metrics USING INDEX
  Speedup: 61x

count_saturated_readings:
  Without index: 16.09 ms  | SCAN metrics
  With index:     0.78 ms  | SEARCH metrics USING INDEX
  Speedup: 21x
```

**Concurrent load test** (20 simultaneous readers — simulating an ops
dashboard with many panels refreshing at once):

```
Without index: total wall time 342.8 ms, avg query latency 168.0 ms
With index:    total wall time  17.4 ms, avg query latency   1.6 ms
Total wall time improvement: 19.7x | Avg latency improvement: 108.6x
```

## Project structure

```
db-forecasting-engine/
├── schema.sql                    # normalized (3NF) servers/metrics schema
├── src/
│   ├── data_generator.py          # synthetic server usage time series
│   ├── forecasting.py             # lag/rolling features + RandomForest classifier
│   ├── log_parser.py              # trie-based log format classifier
│   ├── generate_log_file.py       # synthetic log file generator
│   ├── disk_reading.py            # naive vs buffered file reading
│   ├── db_setup.py                # schema init + bulk data loading
│   └── query_profiler.py          # indexed vs non-indexed query timing + EXPLAIN QUERY PLAN
├── benchmark/
│   ├── run_forecast.py
│   ├── run_log_sweep.py
│   └── run_query_profiling.py
├── tests/
│   ├── test_forecasting.py
│   ├── test_log_parser.py
│   └── test_disk_reading.py
└── requirements.txt
```

## Setup & run

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python -m benchmark.run_forecast          # saturation forecasting across 5 seeds
python -m benchmark.run_log_sweep         # generates + sweeps a 300K-line log
python -m benchmark.run_query_profiling   # builds 500K-row DB, profiles queries + concurrency
pytest tests/ -v                           # 18 unit tests
```

## Design trade-offs

- **RandomForest over a classical time-series model (ARIMA/Prophet)**:
  chosen because the lag/rolling-feature framing turns this into a
  standard tabular classification problem, which handles the
  nonlinear "ramp-up" pattern before a spike better than a linear
  ARIMA model would, at the cost of needing manual feature engineering
  Prophet would give for free.
- **Trie-based log parsing over a linear list of regexes**: the trie's
  advantage only materializes with many registered formats (tested up
  to 50 in `test_trie_scales_to_many_registered_formats`) — for the 3
  formats used in this demo, a linear regex list would perform
  similarly; the structural advantage is asymptotic, not dramatic here.
- **SQLite over a real production database engine**: EXPLAIN QUERY PLAN
  output and index behavior are SQLite-specific — the same underlying
  principle (index vs. full scan) applies to MySQL/PostgreSQL, but exact
  numbers and plan output syntax would differ.

## Possible extensions

- Add a proper baseline comparison (e.g. "always predict majority
  class") alongside the RandomForest to make the accuracy improvement
  concrete rather than implied.
- Extend the query profiler to cover write-heavy workloads (index
  maintenance cost on INSERT), not just read queries.
- Swap the synthetic log generator for a real anonymized production log
  sample to validate the trie parser against real-world format drift.

## Tech stack

Python · pandas · scikit-learn · SQLite · pytest
