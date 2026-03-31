import pandas as pd
import joblib
from pathlib import Path
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    input_file = project_root / "data" / "processed" / "hourly_data.csv"
    models_dir = project_root / "models"
    models_dir.mkdir(exist_ok=True)

    df = pd.read_csv(input_file, index_col=0, parse_dates=True)

    feature_cols = ['hour', 'day_of_week', 'month', 'day_of_year', 'is_weekend']
    X = df[feature_cols]
    y = df['count']

    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    model = XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    print(f"MAE: {mae:.2f}, RMSE: {rmse:.2f}")

    joblib.dump(model, models_dir / "forecast_model.pkl")
    joblib.dump(feature_cols, models_dir / "features.pkl")
    print("Модель прогноза сохранена")

if __name__ == "__main__":
    main()