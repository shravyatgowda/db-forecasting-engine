"""
run_forecast.py

Trains and evaluates the saturation forecasting model across several
random seeds, reporting the real spread of results honestly rather
than a single cherry-picked number.

Run with:
    python -m benchmark.run_forecast
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.data_generator import generate_server_metrics
from src.forecasting import train_and_evaluate


def main():
    print("Forecasting saturation spikes 10 minutes ahead of time (across 5 seeds):\n")
    print(f"{'seed':>6} | {'accuracy':>9} | {'precision':>10} | {'recall':>7} | {'roc_auc':>8}")
    print("-" * 55)

    accuracies = []
    for seed in (1, 7, 21, 42, 99):
        df = generate_server_metrics(n_points=5000, n_spikes=25, seed=seed)
        metrics, _, _ = train_and_evaluate(df, seed=seed)
        accuracies.append(metrics["accuracy"])
        print(
            f"{seed:>6} | {metrics['accuracy']:>9.3f} | {metrics['precision']:>10.3f} | "
            f"{metrics['recall']:>7.3f} | {metrics['roc_auc']:>8.3f}"
        )

    avg = sum(accuracies) / len(accuracies)
    print("-" * 55)
    print(f"Average accuracy across seeds: {avg:.3f}")
    print(f"Range: {min(accuracies):.3f} - {max(accuracies):.3f}")
    print(
        "\nNote: precision varies more than accuracy across seeds because saturation events "
        "are rare (~2-7% of test points), so a handful of false positives/negatives swings "
        "precision noticeably even though overall accuracy stays high."
    )


if __name__ == "__main__":
    main()
