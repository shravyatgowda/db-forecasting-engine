"""
data_generator.py

Generates synthetic per-server system metrics (disk usage %, memory
usage %) over time, with:
  - a slow upward trend (usage creeps up as a server runs longer between restarts)
  - daily seasonality (higher usage during business hours)
  - occasional genuine "saturation spike" events (a burst of usage
    crossing a critical threshold), which is what the forecasting model
    is trained to predict BEFORE it happens.

This is a demo/teaching dataset, not real infrastructure telemetry --
sized and shaped to have learnable signal for the forecasting model
below, not a claim about real-world server behavior.
"""

import numpy as np
import pandas as pd


SATURATION_THRESHOLD = 90.0  # percent usage considered "saturated"


def generate_server_metrics(
    n_points: int = 5000,
    interval_minutes: int = 1,
    n_spikes: int = 25,
    seed: int = 7,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n_points)

    # Trend: usage creeps up slowly over time (simulating memory/disk
    # accumulation between restarts), reset periodically (simulating restarts).
    restart_period = 1200
    trend = 40 + 25 * ((t % restart_period) / restart_period)

    # Daily seasonality (assuming 1-minute intervals, ~1440 points/day)
    seasonality = 8 * np.sin(2 * np.pi * t / 1440)

    noise = rng.normal(0, 2.5, size=n_points)

    usage = trend + seasonality + noise
    usage = np.clip(usage, 0, 100)

    # Inject genuine spike events: a rapid ramp up to a critical level,
    # then decay -- this is the pattern the forecasting model needs to
    # learn to recognize the LEAD-UP to, not just the spike itself.
    spike_starts = rng.choice(np.arange(50, n_points - 50), size=n_spikes, replace=False)
    for start in spike_starts:
        ramp_len = rng.integers(8, 20)
        peak = rng.uniform(92, 99)
        ramp = np.linspace(usage[start], peak, ramp_len)
        decay_len = rng.integers(5, 15)
        decay = np.linspace(peak, usage[min(start + ramp_len + decay_len, n_points - 1)], decay_len)
        end = min(start + ramp_len, n_points)
        usage[start:end] = ramp[: end - start]
        decay_end = min(end + decay_len, n_points)
        usage[end:decay_end] = decay[: decay_end - end]

    usage = np.clip(usage, 0, 100)

    timestamps = pd.date_range("2026-01-01", periods=n_points, freq=f"{interval_minutes}min")
    return pd.DataFrame({"timestamp": timestamps, "usage_pct": usage})


if __name__ == "__main__":
    df = generate_server_metrics()
    df.to_csv("data/server_metrics.csv", index=False)
    print(f"Generated {len(df)} points, {(df['usage_pct'] >= SATURATION_THRESHOLD).sum()} saturation points")
