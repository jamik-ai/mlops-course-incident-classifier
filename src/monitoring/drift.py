from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.report import Report
from prometheus_client import Gauge
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp

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
    reference_path: Path = Path("data/reference/reference_dataset.csv")
    current_path: Path = Path("data/current/current_dataset.csv")
    report_html_path: Path = Path("reports/drift/latest.html")
    report_json_path: Path = Path("reports/drift/latest.json")
    target_col: str = "count"
    prediction_col: str = "prediction"
    psi_threshold: float = 0.2
    ks_pvalue_threshold: float = 0.05
    js_threshold: float = 0.1
    mae_relative_degradation_threshold: float = 0.2


def read_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep=";")


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
        ks_pvalue = 1.0 if ref.empty or cur.empty else float(ks_2samp(ref, cur).pvalue)
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
        target_ks = ks_2samp(pd.to_numeric(reference_df[config.target_col], errors="coerce").dropna(), pd.to_numeric(current_df[config.target_col], errors="coerce").dropna())
        target_metrics = {"psi": psi(reference_df[config.target_col], current_df[config.target_col]), "ks_pvalue": float(target_ks.pvalue), "js_distance": js_distance(reference_df[config.target_col], current_df[config.target_col])}
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
    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(reference_data=reference_df, current_data=current_df)
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
