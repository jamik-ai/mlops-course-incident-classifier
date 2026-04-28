import pandas as pd
import joblib
from pathlib import Path
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
from src.utils.config import PROJECT_DIR, DATA_PATH, MODELS_PATH


def forecast_train(file_name: str):
    data = f'{PROJECT_DIR}/{DATA_PATH}/{file_name}'
    models_dir = f"{PROJECT_DIR}/{MODELS_PATH}"
    models_dir.mkdir(exist_ok=True)

    df = pd.read_csv(data, index_col=0, parse_dates=True)

    feature_cols = ['hour', 'day_of_week', 'month', 'day_of_year', 'is_weekend']
    X = df[feature_cols]
    y = df['count']

    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    model = XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    print(f"MAE: {mae:.2f}, RMSE: {rmse:.2f}")

    joblib.dump(model, f"{models_dir}/forecast_model.pkl")
    joblib.dump(feature_cols, f"{models_dir}/features.pkl")
    print("Модель прогноза сохранена")
