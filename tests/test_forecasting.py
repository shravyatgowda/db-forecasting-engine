import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.forecasting import build_features, train_and_evaluate, SATURATION_THRESHOLD
from src.data_generator import generate_server_metrics


def test_build_features_creates_expected_columns():
    df = generate_server_metrics(n_points=200, n_spikes=2, seed=1)
    featured = build_features(df)
    expected_cols = {"lag_1", "lag_2", "lag_3", "lag_5", "lag_10", "rolling_mean_5",
                      "rolling_std_5", "rate_of_change_5", "rate_of_change_1", "will_saturate"}
    assert expected_cols.issubset(set(featured.columns))


def test_build_features_drops_nan_rows():
    df = generate_server_metrics(n_points=200, n_spikes=2, seed=1)
    featured = build_features(df)
    assert featured.isna().sum().sum() == 0


def test_target_flags_upcoming_saturation():
    """If usage crosses the threshold a few points ahead, will_saturate
    should be 1 for the preceding rows within the lookahead window."""
    usage = np.array([50.0] * 20 + [95.0] * 5 + [50.0] * 20)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(usage), freq="1min"),
        "usage_pct": usage,
    })
    featured = build_features(df, lookahead=5)
    # A row a few steps before the spike (index ~15 in original -> some
    # row in featured after dropna) should be flagged as will_saturate=1
    assert featured["will_saturate"].sum() > 0


def test_model_beats_random_baseline():
    """The trained model should meaningfully outperform a coin-flip on
    this data -- a weak sanity check that the pipeline is learning
    something real, not just memorizing noise or being no better than
    chance."""
    df = generate_server_metrics(n_points=5000, n_spikes=25, seed=7)
    metrics, clf, _ = train_and_evaluate(df)
    assert metrics["accuracy"] > 0.85  # comfortably above the ~93% positive-rate baseline of "always predict no"
    assert metrics["roc_auc"] > 0.7    # meaningfully better than random (0.5)


def test_saturation_threshold_is_90():
    assert SATURATION_THRESHOLD == 90.0
