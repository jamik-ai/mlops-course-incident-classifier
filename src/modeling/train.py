from __future__ import annotations

import os
from pathlib import Path

import joblib
import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from src.utils.config import DATA_PATH, MODELS_PATH

FEATURE_COLS = ["hour", "day_of_week", "month", "day_of_year", "is_weekend"]
TARGET_COL = "count"


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    except Exception:
        return pd.read_csv(path, sep=";")


def forecast_train(file_name: str = "timeseries.csv") -> dict:
    data_path = Path(DATA_PATH) / file_name
    model_dir = Path(MODELS_PATH)
    model_dir.mkdir(parents=True, exist_ok=True)

    df = _read_csv(data_path)
    missing = [col for col in FEATURE_COLS + [TARGET_COL] if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[FEATURE_COLS]
    y = df[TARGET_COL]
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    model = XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05, random_state=42, objective="reg:squarederror")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    joblib.dump(model, model_dir / "forecast_model.pkl")
    joblib.dump(FEATURE_COLS, model_dir / "features.pkl")

    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        mlflow.set_tracking_uri(mlflow_uri)
        mlflow.set_experiment("call-volume-forecast-training")
        with mlflow.start_run(run_name="train_xgboost"):
            mlflow.log_params({"model_type": "XGBRegressor", "features": ",".join(FEATURE_COLS)})
            mlflow.log_metrics({"mae": mae, "rmse": rmse})
            mlflow.xgboost.log_model(model, artifact_path="model", registered_model_name=os.getenv("MLFLOW_MODEL_NAME", "call-volume-forecast"))

    return {"mae": mae, "rmse": rmse, "model_path": str(model_dir / "forecast_model.pkl")}


if __name__ == "__main__":
    print(forecast_train())
