#!/usr/bin/env python3
"""Generate synthetic reference dataset for drift detection baseline.

The reference dataset represents a "stable" historical period — by default
30 days ending 180 days before today (roughly 6 months ago). This ensures
a clear temporal separation from the current data used in drift checks.

Creates CSV at data/reference/reference_dataset.csv with columns:
datetime,hour,day_of_week,month,day_of_year,is_weekend,count,prediction

Usage:
    python scripts/generate_reference_data.py           # defaults: 30 days, 6 months ago
    python scripts/generate_reference_data.py --days 14 --offset-days 90
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def generate_reference_series(
    days: int = 30,
    end: datetime | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate hourly call-volume data for a reference (historical) period.

    Args:
        days: Number of days to generate.
        end: End datetime of the reference window. If None, defaults to
             180 days before the current UTC time.
        seed: Random seed for reproducibility. Reference data should always
              look the same so drift baselines are stable.
    """
    random.seed(seed)

    if end is None:
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        end = now - timedelta(days=180)

    start = end - timedelta(days=days)
    idx = pd.date_range(start=start, end=end, freq="h")

    rows = []
    for ts in idx:
        hour = ts.hour
        dow = ts.weekday()
        month = ts.month
        day_of_year = ts.timetuple().tm_yday
        is_weekend = 1 if dow >= 5 else 0

        # Daily pattern: low at night, peak in evening
        daily = 10 * (1 + math.sin((hour - 8) / 24 * 2 * math.pi))

        # Weekly pattern: weekends slightly different
        weekly = 3 * (1 + (0.5 if is_weekend else 0.0))

        # Yearly/seasonality (slow-moving)
        seasonal = 5 * math.sin(day_of_year / 365 * 2 * math.pi)

        # Trend — reference period has no drift by design
        days_from_start = (ts - idx[0]).days
        trend = 0.02 * days_from_start

        base = 30
        noise = random.gauss(0, 2.5)

        count = base + daily + weekly + seasonal + trend + noise
        count = max(0.0, round(count, 1))

        pred_noise = random.gauss(0, 1.5)
        prediction = round(max(0.0, count + pred_noise), 1)

        rows.append(
            {
                "datetime": ts.isoformat(),
                "hour": hour,
                "day_of_week": dow,
                "month": month,
                "day_of_year": day_of_year,
                "is_weekend": is_weekend,
                "count": count,
                "prediction": prediction,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reference dataset for drift detection.")
    parser.add_argument("--days", type=int, default=30, help="Length of reference window in days (default: 30)")
    parser.add_argument(
        "--offset-days",
        type=int,
        default=180,
        help="How many days before today the reference window ends (default: 180)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    end = now - timedelta(days=args.offset_days)

    print(f"Generating reference data:")
    print(f"  Period : {end - timedelta(days=args.days):%Y-%m-%d} → {end:%Y-%m-%d}")
    print(f"  Days   : {args.days}")
    print(f"  Seed   : {args.seed}")

    df = generate_reference_series(days=args.days, end=end, seed=args.seed)

    out_dir = Path("data/reference")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "reference_dataset.csv"
    df.to_csv(out_path, index=False)

    print(f"  Rows   : {len(df)}")
    print(f"  Saved  : {out_path}")


if __name__ == "__main__":
    main()
