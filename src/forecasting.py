"""
forecasting.py

Predicts whether a server's usage will cross the saturation threshold
within the next LOOKAHEAD minutes, using lag and rolling-window features
-- the standard feature engineering approach for time-series
classification without needing a deep sequence model.

The target is deliberately framed as "will saturate soon" (a lead-time
prediction) rather than "is saturated right now" (which would be
trivial and useless -- by the time it's already saturated, forecasting
didn't do its job).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

SATURATION_THRESHOLD = 90.0
LOOKAHEAD = 10  # predict saturation within the next 10 minutes


def build_features(df: pd.DataFrame, lookahead: int = LOOKAHEAD) -> pd.DataFrame:
    df = df.copy()

    for lag in (1, 2, 3, 5, 10):
        df[f"lag_{lag}"] = df["usage_pct"].shift(lag)

    df["rolling_mean_5"] = df["usage_pct"].rolling(5).mean()
    df["rolling_std_5"] = df["usage_pct"].rolling(5).std()
    df["rate_of_change_5"] = df["usage_pct"] - df["usage_pct"].shift(5)
    df["rate_of_change_1"] = df["usage_pct"] - df["usage_pct"].shift(1)

    # Target: will ANY point in the next `lookahead` minutes cross the threshold?
    future_max = (
        df["usage_pct"].shift(-1).rolling(lookahead, min_periods=1).max().shift(-(lookahead - 1))
    )
    df["will_saturate"] = (future_max >= SATURATION_THRESHOLD).astype(int)

    df = df.dropna().reset_index(drop=True)
    return df


FEATURE_COLUMNS = [
    "usage_pct", "lag_1", "lag_2", "lag_3", "lag_5", "lag_10",
    "rolling_mean_5", "rolling_std_5", "rate_of_change_5", "rate_of_change_1",
]


def train_and_evaluate(df: pd.DataFrame, test_size: float = 0.25, seed: int = 42):
    featured = build_features(df)
    X = featured[FEATURE_COLUMNS]
    y = featured["will_saturate"]

    # Time-series split (no shuffling): train on the past, test on the
    # future -- the honest way to evaluate a forecasting model, since
    # random shuffling would leak future information into training.
    split_idx = int(len(X) * (1 - test_size))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=6, class_weight="balanced", random_state=seed, n_jobs=-1
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else float("nan"),
        "positive_rate_test": float(y_test.mean()),
        "n_test": len(y_test),
    }
    return metrics, clf, (X_test, y_test, y_pred)
