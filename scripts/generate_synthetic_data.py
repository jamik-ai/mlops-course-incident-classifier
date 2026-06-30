#!/usr/bin/env python3
"""Generate synthetic hourly call-volume data for the last N days.

Creates CSV at data/current/current_dataset.csv with columns:
datetime,hour,day_of_week,month,day_of_year,is_weekend,count,prediction
"""
from __future__ import annotations
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd


def generate_hourly_series(days: int = 90, end: datetime | None = None) -> pd.DataFrame:
    if end is None:
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    idx = pd.date_range(start=start, end=end, freq="H")

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

        # Trend (small upward drift)
        days_from_start = (ts - idx[0]).days
        trend = 0.02 * days_from_start

        base = 30
        noise = random.gauss(0, 2.5)

        count = base + daily + weekly + seasonal + trend + noise
        count = max(0.0, round(count, 1))

        # Simulate prediction as prior-hour value plus small noise
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

    df = pd.DataFrame(rows)
    return df


def main():
    out_dir = Path("data/current")
    out_dir.mkdir(parents=True, exist_ok=True)
    df = generate_hourly_series(days=90)
    out_path = out_dir / "current_dataset.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
