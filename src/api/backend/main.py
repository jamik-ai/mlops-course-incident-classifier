from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.backend.schemas import ForecastRequest, ForecastResponse, RetrainResponse
from src.modeling.predict import predict, reload_model
from src.monitoring.drift import DriftConfig, run_drift_check
from src.pipelines.retrain import retrain_pipeline

app = FastAPI(title="Call Volume Forecast API", version="1.1.0", description="Forecast API with drift detection, retraining and Prometheus metrics.")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://localhost:80,http://localhost:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    try:
        target_date = datetime.strptime(request.date, "%Y-%m-%d")
        hourly_predictions = [float(round(predict(target_date.replace(hour=hour)), 2)) for hour in range(24)]
        return ForecastResponse(date=request.date, hourly_forecast=hourly_predictions)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/drift/run")
def run_drift():
    try:
        return run_drift_check(DriftConfig())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/drift/report")
def get_drift_report():
    report_path = Path("reports/drift/latest.html")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Drift report not found. Run /api/drift/run first.")
    return FileResponse(report_path, media_type="text/html", filename="drift_report.html")


@app.post("/api/retrain", response_model=RetrainResponse)
def retrain(background_tasks: BackgroundTasks):
    background_tasks.add_task(retrain_pipeline)
    return RetrainResponse(status="started", message="Retraining pipeline started in background.")


@app.post("/api/model/reload")
def reload_current_model():
    reload_model()
    return {"status": "ok", "message": "Model reloaded from local artifact path."}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Call Volume Forecast API", "docs": "/docs", "metrics": "/metrics"}
