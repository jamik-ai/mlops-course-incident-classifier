from src.utils.config import MODELS_PATH
import joblib
from datetime import datetime
import pandas as pd

model = joblib.load(f"{MODELS_PATH}/forecast_model.pkl")
features = joblib.load(f"{MODELS_PATH}/features.pkl")

def create_features_for_hour(dt: datetime):
    """Создаёт признаки для заданного часа (без лагов)."""
    hour = dt.hour
    day_of_week = dt.weekday()
    month = dt.month
    day_of_year = dt.timetuple().tm_yday
    is_weekend = 1 if day_of_week in [5, 6] else 0
    data = {
        'hour': hour,
        'day_of_week': day_of_week,
        'month': month,
        'day_of_year': day_of_year,
        'is_weekend': is_weekend
    }
    X = pd.DataFrame([data])
    # Убеждаемся, что порядок колонок соответствует обученному списку
    X = X[features]
    return X


def predict(dt: datetime):
    X = create_features_for_hour(dt)
    pred = model.predict(X)[0]
    return pred
