import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

# Определяем пути
PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# Загружаем модель и список признаков
model = joblib.load(MODELS_DIR / "forecast_model.pkl")
features = joblib.load(MODELS_DIR / "features.pkl")

app = FastAPI(title="Call Volume Forecast API", version="1.0")

class ForecastRequest(BaseModel):
    date: str  # "YYYY-MM-DD"

class ForecastResponse(BaseModel):
    date: str
    hourly_forecast: list  # 24 значения

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

@app.post("/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    try:
        target_date = datetime.strptime(request.date, "%Y-%m-%d")
        hourly_predictions = []
        for hour in range(24):
            dt = target_date.replace(hour=hour)
            X = create_features_for_hour(dt)
            pred = model.predict(X)[0]
            hourly_predictions.append(float(round(pred, 2)))
        return ForecastResponse(date=request.date, hourly_forecast=hourly_predictions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    html_content = """
    <html>
        <head>
            <title>Call Forecast</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #333; }
                form { margin-bottom: 20px; }
                label { font-weight: bold; }
                input, button { padding: 8px; margin: 5px; }
                button { background-color: #4CAF50; color: white; border: none; cursor: pointer; }
                button:hover { background-color: #45a049; }
                #result { margin-top: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <h1>Прогноз количества вызовов на день</h1>
            <form id="forecastForm">
                <label for="date">Дата (YYYY-MM-DD):</label>
                <input type="date" id="date" name="date" required>
                <button type="submit">Прогноз</button>
            </form>
            <div id="result"></div>
            <script>
                document.getElementById('forecastForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const date = document.getElementById('date').value;
                    const response = await fetch('/forecast', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({date})
                    });
                    const data = await response.json();
                    if (response.ok) {
                        let html = '<h2>Прогноз на ' + data.date + '</h2>';
                        html += '<table><tr><th>Час</th><th>Прогноз</th></tr>';
                        for (let i=0; i<data.hourly_forecast.length; i++) {
                            html += `<tr><td>${i}:00</td><td>${data.hourly_forecast[i]}</td></tr>`;
                        }
                        html += '</table>';
                        document.getElementById('result').innerHTML = html;
                    } else {
                        document.getElementById('result').innerHTML = '<p style="color:red;">Ошибка: ' + data.detail + '</p>';
                    }
                });
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/")
def root():
    return {"message": "Call Volume Forecast API. Use POST /forecast or visit /ui"}

@app.get("/health")
def health():
    return {"status": "ok"}