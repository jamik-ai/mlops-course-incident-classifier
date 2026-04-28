import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime
from src.modeling.predict import predict
from src.api.backend.schemas import ForecastRequest, ForecastResponse

app = FastAPI(title="Call Volume Forecast API", version="1.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://localhost:80").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    try:
        target_date = datetime.strptime(request.date, "%Y-%m-%d")
        hourly_predictions = []
        for hour in range(24):
            dt = target_date.replace(hour=hour)
            prediction = predict(dt)
            hourly_predictions.append(float(round(prediction, 2)))
        return ForecastResponse(date=request.date, hourly_forecast=hourly_predictions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Call Volume Forecast API. Use POST /api/forecast"}