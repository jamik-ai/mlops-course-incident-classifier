from __future__ import annotations

import json
import math
import random
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from evidently import ColumnMapping
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.report import Report
from prometheus_client import Gauge
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp

from src.utils.config import (
    CURRENT_DATA_PATH,
    DRIFT_REPORTS_PATH,
    REFERENCE_DATA_PATH,
)

DATA_DRIFT_SCORE = Gauge("ml_data_drift_share", "Share of drifted input features")
DATA_DRIFT_DETECTED = Gauge("ml_data_drift_detected", "1 if data drift is detected, else 0")
TARGET_DRIFT_DETECTED = Gauge("ml_target_drift_detected", "1 if target drift is detected, else 0")
CONCEPT_DRIFT_DETECTED = Gauge("ml_concept_drift_detected", "1 if concept drift is detected, else 0")
MODEL_MAE = Gauge("ml_model_mae", "Latest model MAE on current labelled data")
PSI_BY_FEATURE = Gauge("ml_feature_psi", "Population Stability Index by feature", ["feature"])
KS_PVALUE_BY_FEATURE = Gauge("ml_feature_ks_pvalue", "KS-test p-value by feature", ["feature"])
JS_BY_FEATURE = Gauge("ml_feature_js_distance", "Jensen-Shannon distance by feature", ["feature"])


@dataclass(frozen=True)
class DriftConfig:
    reference_path: Path = REFERENCE_DATA_PATH
    current_path: Path = CURRENT_DATA_PATH
    report_html_path: Path = DRIFT_REPORTS_PATH / "latest.html"
    report_json_path: Path = DRIFT_REPORTS_PATH / "latest.json"
    target_col: str = "count"
    prediction_col: str = "prediction"
    psi_threshold: float = 0.2
    ks_pvalue_threshold: float = 0.05
    js_threshold: float = 0.1
    mae_relative_degradation_threshold: float = 0.2


def generate_synthetic_current(days: int = 90, output_path: Path | None = None) -> pd.DataFrame:
    """Generate fresh synthetic current dataset simulating realistic drift vs reference.

    Uses the same base formula as the reference but covers a recent period,
    introducing natural drift via seasonal shift and a stronger upward trend.
    """
    output_path = output_path or CURRENT_DATA_PATH
    end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    idx = pd.date_range(start=start, end=end, freq="h")

    rng = random.Random()  # unseeded — always fresh noise
    rows = []
    for ts in idx:
        hour = ts.hour
        dow = ts.weekday()
        month = ts.month
        day_of_year = ts.timetuple().tm_yday
        is_weekend = 1 if dow >= 5 else 0
        daily = 10 * (1 + math.sin((hour - 8) / 24 * 2 * math.pi))
        weekly = 3 * (1 + (0.5 if is_weekend else 0.0))
        seasonal = 5 * math.sin(day_of_year / 365 * 2 * math.pi)
        days_from_start = (ts - idx[0]).total_seconds() / 86400
        # Stronger trend than reference (0.05 vs 0.02) to create noticeable drift in count
        trend = 0.05 * days_from_start
        count = max(0.0, round(30 + daily + weekly + seasonal + trend + rng.gauss(0, 2.5), 1))
        prediction = round(max(0.0, count + rng.gauss(0, 1.5)), 1)
        rows.append({
            "datetime": ts.isoformat(),
            "hour": hour,
            "day_of_week": dow,
            "month": month,
            "day_of_year": day_of_year,
            "is_weekend": is_weekend,
            "count": count,
            "prediction": prediction,
        })

    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


def current_data_is_stale(path: Path, max_age_hours: int = 24) -> bool:
    if not path.exists():
        return True
    age = datetime.utcnow().timestamp() - path.stat().st_mtime
    return age > max_age_hours * 3600


def read_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.read_csv(path, sep=";")
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    return df


def psi(reference: pd.Series, current: pd.Series, bins: int = 10, eps: float = 1e-6) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna()
    cur = pd.to_numeric(current, errors="coerce").dropna()
    if ref.empty or cur.empty:
        return 0.0
    breakpoints = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(breakpoints) < 3:
        return 0.0
    ref_counts, _ = np.histogram(ref, bins=breakpoints)
    cur_counts, _ = np.histogram(cur, bins=breakpoints)
    ref_pct = np.clip(ref_counts / max(ref_counts.sum(), 1), eps, None)
    cur_pct = np.clip(cur_counts / max(cur_counts.sum(), 1), eps, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def _safe_ks_pvalue(reference: pd.Series, current: pd.Series) -> float:
    reference = pd.to_numeric(reference, errors="coerce").dropna()
    current = pd.to_numeric(current, errors="coerce").dropna()
    if reference.empty or current.empty:
        return 1.0
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        try:
            return float(ks_2samp(reference, current).pvalue)
        except Exception:
            return 1.0


def js_distance(reference: pd.Series, current: pd.Series, bins: int = 20, eps: float = 1e-8) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna()
    cur = pd.to_numeric(current, errors="coerce").dropna()
    if ref.empty or cur.empty:
        return 0.0
    min_value, max_value = min(ref.min(), cur.min()), max(ref.max(), cur.max())
    if min_value == max_value:
        return 0.0
    ref_hist, edges = np.histogram(ref, bins=bins, range=(min_value, max_value), density=True)
    cur_hist, _ = np.histogram(cur, bins=edges, density=True)
    ref_hist = np.clip(ref_hist, eps, None)
    cur_hist = np.clip(cur_hist, eps, None)
    return float(jensenshannon(ref_hist / ref_hist.sum(), cur_hist / cur_hist.sum()))


def numeric_features(df: pd.DataFrame, target_col: str, prediction_col: str) -> list[str]:
    excluded = {target_col, prediction_col}
    return [col for col in df.select_dtypes(include=[np.number]).columns if col not in excluded]


def _feature_metrics(reference_df: pd.DataFrame, current_df: pd.DataFrame, features: list[str], config: DriftConfig) -> tuple[dict[str, Any], int]:
    results: dict[str, Any] = {}
    drifted = 0
    for feature in features:
        ref = pd.to_numeric(reference_df[feature], errors="coerce").dropna()
        cur = pd.to_numeric(current_df[feature], errors="coerce").dropna()
        ks_pvalue = _safe_ks_pvalue(ref, cur)
        feature_psi = psi(ref, cur)
        feature_js = js_distance(ref, cur)
        is_drifted = feature_psi >= config.psi_threshold or ks_pvalue < config.ks_pvalue_threshold or feature_js >= config.js_threshold
        drifted += int(is_drifted)
        PSI_BY_FEATURE.labels(feature=feature).set(feature_psi)
        KS_PVALUE_BY_FEATURE.labels(feature=feature).set(ks_pvalue)
        JS_BY_FEATURE.labels(feature=feature).set(feature_js)
        results[feature] = {"psi": feature_psi, "ks_pvalue": ks_pvalue, "js_distance": feature_js, "drift_detected": is_drifted}
    return results, drifted


def run_drift_check(config: DriftConfig | None = None) -> dict[str, Any]:
    config = config or DriftConfig()
    reference_df = read_dataset(config.reference_path)
    current_df = read_dataset(config.current_path)
    common_columns = [col for col in reference_df.columns if col in current_df.columns]
    reference_df, current_df = reference_df[common_columns].copy(), current_df[common_columns].copy()

    features = numeric_features(reference_df, config.target_col, config.prediction_col)
    feature_results, drifted_features = _feature_metrics(reference_df, current_df, features, config)
    data_drift_share = drifted_features / max(len(features), 1)
    data_drift_detected = data_drift_share > 0

    target_drift_detected = False
    target_metrics: dict[str, Any] = {}
    if config.target_col in reference_df.columns and config.target_col in current_df.columns:
        target_ref = pd.to_numeric(reference_df[config.target_col], errors="coerce").dropna()
        target_cur = pd.to_numeric(current_df[config.target_col], errors="coerce").dropna()
        target_ks_pvalue = _safe_ks_pvalue(target_ref, target_cur)
        target_metrics = {
            "psi": psi(reference_df[config.target_col], current_df[config.target_col]),
            "ks_pvalue": target_ks_pvalue,
            "js_distance": js_distance(reference_df[config.target_col], current_df[config.target_col]),
        }
        target_drift_detected = target_metrics["psi"] >= config.psi_threshold or target_metrics["ks_pvalue"] < config.ks_pvalue_threshold or target_metrics["js_distance"] >= config.js_threshold

    concept_drift_detected = False
    concept_metrics: dict[str, Any] = {}
    if {config.target_col, config.prediction_col}.issubset(reference_df.columns) and {config.target_col, config.prediction_col}.issubset(current_df.columns):
        ref_mae = float(np.mean(np.abs(reference_df[config.target_col] - reference_df[config.prediction_col])))
        cur_mae = float(np.mean(np.abs(current_df[config.target_col] - current_df[config.prediction_col])))
        degradation = (cur_mae - ref_mae) / max(ref_mae, 1e-6)
        concept_drift_detected = degradation >= config.mae_relative_degradation_threshold
        concept_metrics = {"reference_mae": ref_mae, "current_mae": cur_mae, "relative_degradation": degradation}
        MODEL_MAE.set(cur_mae)

    config.report_html_path.parent.mkdir(parents=True, exist_ok=True)
    if "datetime" in reference_df.columns:
        reference_df["datetime"] = pd.to_datetime(reference_df["datetime"], errors="coerce")
    if "datetime" in current_df.columns:
        current_df["datetime"] = pd.to_datetime(current_df["datetime"], errors="coerce")
    column_mapping = ColumnMapping(
        target=config.target_col,
        prediction=config.prediction_col,
    )
    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        report.run(reference_data=reference_df, current_data=current_df, column_mapping=column_mapping)
    report.save_html(str(config.report_html_path))

    result = {"data_drift_detected": data_drift_detected, "data_drift_share": data_drift_share, "target_drift_detected": target_drift_detected, "concept_drift_detected": concept_drift_detected, "features": feature_results, "target": target_metrics, "concept": concept_metrics, "html_report": str(config.report_html_path)}
    config.report_json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    DATA_DRIFT_SCORE.set(data_drift_share)
    DATA_DRIFT_DETECTED.set(int(data_drift_detected))
    TARGET_DRIFT_DETECTED.set(int(target_drift_detected))
    CONCEPT_DRIFT_DETECTED.set(int(concept_drift_detected))
    return result


if __name__ == "__main__":
    print(json.dumps(run_drift_check(), indent=2, ensure_ascii=False))
