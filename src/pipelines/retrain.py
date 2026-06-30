from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
import mlflow
import mlflow.xgboost
from mlflow.models.signature import infer_signature
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from src.monitoring.drift import DriftConfig, run_drift_check
from src.utils.config import CURRENT_DATA_PATH, MODELS_PATH

FEATURE_COLS = ["hour", "day_of_week", "month", "day_of_year", "is_weekend"]
TARGET_COL = "count"
MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "call-volume-forecast")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")


def _get_s3_client() -> Any:
    import boto3
    from botocore.config import Config
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        config=Config(s3={"addressing_style": "path"}),
    )


def _ensure_s3_bucket(bucket_name: str) -> None:
    from botocore.exceptions import ClientError
    try:
        client = _get_s3_client()
        client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchBucket", "NoSuchBucketError", "NotFound"}:
            client.create_bucket(Bucket=bucket_name)
        else:
            raise


def _read_training_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Training data not found: {path}")
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep=";")


def retrain_pipeline(training_data_path: Path | None = None, model_dir: str | None = None) -> dict:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    _ensure_s3_bucket("mlflow")
    mlflow.set_experiment("call-volume-forecast-retraining")
    df = _read_training_data(training_data_path or CURRENT_DATA_PATH)
    missing = [col for col in FEATURE_COLS + [TARGET_COL] if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in training dataset: {missing}")

    X, y = df[FEATURE_COLS], df[TARGET_COL]
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, random_state=42, objective="reg:squarederror")
    with mlflow.start_run(run_name="retrain_xgboost") as run:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mlflow.log_params({"model_type": "XGBRegressor", "n_estimators": 300, "max_depth": 6, "learning_rate": 0.05, "features": ",".join(FEATURE_COLS)})
        mlflow.log_metrics({"mae": mae, "rmse": rmse})

        model_path = Path(model_dir) if model_dir else MODELS_PATH
        model_path.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path / "forecast_model.pkl")
        joblib.dump(FEATURE_COLS, model_path / "features.pkl")

        signature = infer_signature(X_test, y_pred)
        try:
            mlflow.xgboost.log_model(
                xgb_model=model,
                artifact_path="model",
                registered_model_name=MODEL_NAME,
                signature=signature,
                input_example=X_test.head(3),
            )
        except Exception as exc:
            mlflow.log_param("model_log_error", str(exc))
            print(f"Warning: mlflow model log failed: {exc}")

        mlflow.log_artifact(str(model_path / "features.pkl"))

        try:
            drift_result = run_drift_check(DriftConfig())
            mlflow.log_dict(drift_result, "drift/latest_drift_result.json")
            html_report = Path(drift_result["html_report"])
            if html_report.exists():
                mlflow.log_artifact(str(html_report), artifact_path="drift")
        except Exception as exc:
            mlflow.log_param("drift_check_error", str(exc))

        return {"status": "success", "run_id": run.info.run_id, "mae": mae, "rmse": rmse, "registered_model": MODEL_NAME}


if __name__ == "__main__":
    print(retrain_pipeline())
