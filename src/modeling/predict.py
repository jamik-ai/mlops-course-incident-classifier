from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from xgboost import XGBRegressor

from src.utils.config import MODELS_PATH

MODEL_PATH = Path(MODELS_PATH) / "forecast_model.pkl"
FEATURES_PATH = Path(MODELS_PATH) / "features.pkl"

_model: Any | None = None
_features: list[str] | None = None


def _build_fallback_model() -> tuple[XGBRegressor, list[str]]:
    features = ["hour", "day_of_week", "month", "day_of_year", "is_weekend"]
    X = pd.DataFrame(
        [{"hour": h, "day_of_week": h % 7, "month": 1, "day_of_year": h + 1, "is_weekend": int((h % 7) in [5, 6])} for h in range(48)]
    )[features]
    y = 10 + X["hour"] * 0.5 + X["is_weekend"] * 2
    model = XGBRegressor(n_estimators=20, max_depth=3, learning_rate=0.1, random_state=42, objective="reg:squarederror")
    model.fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(features, FEATURES_PATH)
    return model, features


def reload_model() -> None:
    global _model, _features
    if not MODEL_PATH.exists() or not FEATURES_PATH.exists():
        _model, _features = _build_fallback_model()
        return
    _model = joblib.load(MODEL_PATH)
    _features = joblib.load(FEATURES_PATH)


def get_model() -> tuple[Any, list[str]]:
    global _model, _features
    if _model is None or _features is None:
        reload_model()
    assert _model is not None and _features is not None
    return _model, _features


def create_features_for_hour(dt: datetime) -> pd.DataFrame:
    _, features = get_model()
    data = {
        "hour": dt.hour,
        "day_of_week": dt.weekday(),
        "month": dt.month,
        "day_of_year": dt.timetuple().tm_yday,
        "is_weekend": int(dt.weekday() in [5, 6]),
    }
    return pd.DataFrame([data])[features]


def predict(dt: datetime) -> float:
    model, _ = get_model()
    return float(model.predict(create_features_for_hour(dt))[0])
