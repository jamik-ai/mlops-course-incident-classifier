from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.backend.schemas import ForecastRequest, ForecastResponse, RetrainResponse, RetrainStatusResponse
from src.modeling.predict import predict, reload_model
from src.monitoring.drift import DriftConfig, current_data_is_stale, generate_synthetic_current, run_drift_check
from src.utils.config import CURRENT_DATA_PATH, DRIFT_REPORTS_PATH
from src.pipelines.retrain import retrain_pipeline

app = FastAPI(title="Call Volume Forecast API", version="1.3.0", description="Forecast API with drift detection, retraining and Prometheus metrics.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

retrain_status: dict[str, Any] = {
    "status": "idle",
    "message": "Готов к переобучению.",
    "started_at": None,
    "finished_at": None,
    "result": None,
}


def _update_retrain_status(status: str, message: str, result: dict[str, Any] | None = None) -> None:
    retrain_status["status"] = status
    retrain_status["message"] = message
    now = datetime.now(timezone.utc)
    if status == "running":
        retrain_status["started_at"] = now
        retrain_status["finished_at"] = None
        retrain_status["result"] = None
    else:
        retrain_status["finished_at"] = now
        if result is not None:
            retrain_status["result"] = result


def _execute_retrain() -> None:
    _update_retrain_status("running", "Переобучение запущено.")
    try:
        result = retrain_pipeline()
        reload_model()
        _update_retrain_status("completed", "Переобучение завершено.", result=result)
    except Exception as exc:
        _update_retrain_status("failed", f"Переобучение завершилось ошибкой: {exc}")


@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    try:
        target_date = datetime.strptime(request.date, "%Y-%m-%d")
        hourly_predictions = [float(round(predict(target_date.replace(hour=hour)), 2)) for hour in range(24)]
        return ForecastResponse(date=request.date, hourly_forecast=hourly_predictions)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/synthetic/generate")
def generate_synthetic():
    try:
        df = generate_synthetic_current()
        mtime = datetime.utcfromtimestamp(CURRENT_DATA_PATH.stat().st_mtime).isoformat() + "Z"
        return {"status": "ok", "rows": len(df), "generated_at": mtime}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/synthetic/info")
def synthetic_info():
    if not CURRENT_DATA_PATH.exists():
        return {"exists": False, "rows": 0, "generated_at": None, "stale": True}
    import pandas as pd
    df = pd.read_csv(CURRENT_DATA_PATH)
    mtime = datetime.utcfromtimestamp(CURRENT_DATA_PATH.stat().st_mtime).isoformat() + "Z"
    return {
        "exists": True,
        "rows": len(df),
        "generated_at": mtime,
        "stale": current_data_is_stale(CURRENT_DATA_PATH),
    }


@app.post("/api/drift/run")
def run_drift(auto_generate: bool = True):
    try:
        if auto_generate and current_data_is_stale(CURRENT_DATA_PATH):
            generate_synthetic_current()
        return run_drift_check(DriftConfig())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/drift/report")
def get_drift_report():
    report_path = DRIFT_REPORTS_PATH / "latest.html"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Drift report not found. Run /api/drift/run first.")
    return FileResponse(report_path, media_type="text/html", filename="drift_report.html")


@app.post("/api/retrain", response_model=RetrainResponse)
def retrain(background_tasks: BackgroundTasks):
    if retrain_status["status"] == "running":
        return RetrainResponse(status="running", message="Переобучение уже выполняется.")
    background_tasks.add_task(_execute_retrain)
    _update_retrain_status("running", "Переобучение запущено в фоне.")
    return RetrainResponse(status="started", message="Переобучение запущено. Статус можно проверить на /api/retrain/status.")


@app.get("/api/retrain/status", response_model=RetrainStatusResponse)
def retrain_status_endpoint():
    return RetrainStatusResponse(**retrain_status)


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
