from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import mlflow
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.backend.schemas import (
    DriftStatusResponse,
    ExperimentRun,
    ForecastRequest,
    ForecastResponse,
    MlflowExperimentsResponse,
    NotificationAlert,
    PredictionEntry,
    RetrainResponse,
)
from src.api.backend.storage import (
    add_notification,
    add_prediction,
    clear_notifications,
    get_notifications,
    get_predictions,
)
from src.modeling.predict import predict, reload_model
from src.monitoring.drift import DriftConfig, run_drift_check
from src.pipelines.retrain import retrain_pipeline

app = FastAPI(title="Call Volume Forecast API", version="2.0.0", description="Forecast API with drift detection, retraining, MLflow integration, Prometheus metrics и уведомления.")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://localhost:80,http://localhost:8080,http://localhost:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

_connected_ws: list[WebSocket] = []
_ws_queue: asyncio.Queue = asyncio.Queue()


async def _ws_broadcaster():
    """Background task that drains the queue and broadcasts to connected clients."""
    while True:
        message = await _ws_queue.get()
        dead: list[WebSocket] = []
        for ws in _connected_ws:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _connected_ws.remove(ws)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_ws_broadcaster())


def enqueue_ws_message(message: dict[str, Any]) -> None:
    """Thread-safe enqueue for broadcasting to WebSocket clients."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_ws_queue.put(message))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_ws_queue.put(message))
        loop.close()


@app.websocket("/ws/drift-alerts")
async def drift_alerts_websocket(ws: WebSocket):
    await ws.accept()
    _connected_ws.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _connected_ws.remove(ws)


@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    try:
        target_date = datetime.strptime(request.date, "%Y-%m-%d")
        hourly_predictions = [float(round(predict(target_date.replace(hour=hour)), 2)) for hour in range(24)]
        add_prediction(request.date, hourly_predictions)
        return ForecastResponse(date=request.date, hourly_forecast=hourly_predictions)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/drift/run")
def run_drift():
    try:
        result = run_drift_check(DriftConfig())
        any_drift = result.get("data_drift_detected") or result.get("target_drift_detected") or result.get("concept_drift_detected")

        if any_drift:
            reasons = []
            if result.get("data_drift_detected"):
                reasons.append("data drift")
            if result.get("target_drift_detected"):
                reasons.append("target drift")
            if result.get("concept_drift_detected"):
                reasons.append("concept drift")
            msg = f"Обнаружен дрейф: {', '.join(reasons)}"
            severity = "critical" if result.get("concept_drift_detected") else "warning"
            add_notification("drift_detected", msg, severity, result)
            enqueue_ws_message({
                "type": "drift_alert",
                "message": msg,
                "severity": severity,
                "details": result,
                "timestamp": datetime.utcnow().isoformat(),
            })

        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/drift/status", response_model=DriftStatusResponse)
def drift_status():
    json_path = Path("reports/drift/latest.json")
    if not json_path.exists():
        return DriftStatusResponse(
            data_drift_detected=False,
            data_drift_share=0.0,
            target_drift_detected=False,
            concept_drift_detected=False,
            any_drift=False,
            last_check_at="",
            feature_flags=[],
        )
    result = json.loads(json_path.read_text(encoding="utf-8"))
    feature_flags = []
    for fname, fdata in result.get("features", {}).items():
        feature_flags.append({
            "feature": fname,
            "psi": fdata.get("psi", 0.0),
            "ks_pvalue": fdata.get("ks_pvalue", 1.0),
            "js_distance": fdata.get("js_distance", 0.0),
            "drift_detected": fdata.get("drift_detected", False),
        })
    data_drift = result.get("data_drift_detected", False)
    target_drift = result.get("target_drift_detected", False)
    concept_drift = result.get("concept_drift_detected", False)
    ctime = json_path.stat().st_ctime
    return DriftStatusResponse(
        data_drift_detected=data_drift,
        data_drift_share=result.get("data_drift_share", 0.0),
        target_drift_detected=target_drift,
        concept_drift_detected=concept_drift,
        any_drift=data_drift or target_drift or concept_drift,
        last_check_at=str(ctime),
        feature_flags=feature_flags,
    )


@app.get("/api/drift/report")
def get_drift_report():
    report_path = Path("reports/drift/latest.html")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Drift report not found. Run /api/drift/run first.")
    return FileResponse(report_path, media_type="text/html", filename="drift_report.html")


@app.post("/api/retrain", response_model=RetrainResponse)
def retrain(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_retrain_with_notification)
    return RetrainResponse(status="started", message="Retraining pipeline started in background.")


def _run_retrain_with_notification() -> None:
    try:
        result = retrain_pipeline()
        msg = f"Модель переобучена. MAE: {result.get('mae', 'N/A')}"
        add_notification("retrain_success", msg, "info", result)
        enqueue_ws_message({
            "type": "retrain_done",
            "message": msg,
            "severity": "info",
            "details": result,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as exc:
        msg = f"Переобучение завершилось ошибкой: {exc}"
        add_notification("retrain_failed", msg, "critical", {})
        enqueue_ws_message({
            "type": "retrain_failed",
            "message": msg,
            "severity": "critical",
            "timestamp": datetime.utcnow().isoformat(),
        })


@app.post("/api/model/reload")
def reload_current_model():
    reload_model()
    add_notification("model_reload", "Модель перезагружена с диска", "info", {})
    return {"status": "ok", "message": "Model reloaded from local artifact path."}


@app.get("/api/predictions/history")
def predictions_history(limit: int = 50):
    entries = get_predictions(limit)
    return [PredictionEntry(**e) for e in entries]


@app.get("/api/notifications")
def notifications_list(limit: int = 50):
    entries = get_notifications(limit)
    return [NotificationAlert(**e) for e in entries]


@app.delete("/api/notifications/clear")
def clear_notifications_ep():
    clear_notifications()
    return {"status": "ok", "message": "Notifications cleared."}


@app.get("/api/mlflow/experiments", response_model=MlflowExperimentsResponse)
def mlflow_experiments():
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        experiments = client.search_experiments()
        exp_names = [e.name for e in experiments]
        exp_map = {e.experiment_id: e.name for e in experiments}

        runs = []
        for exp in experiments:
            exp_runs = client.search_runs(experiment_ids=[exp.experiment_id], order_by=["metrics.start_time DESC"], max_results=20)
            for r in exp_runs:
                params = []
                if r.data.params:
                    for k, v in r.data.params.items():
                        params.append({"key": k, "value": str(v)})
                metrics = []
                if r.data.metrics:
                    for k, v in r.data.metrics.items():
                        metrics.append({"key": k, "value": v})
                runs.append(ExperimentRun(
                    run_id=r.info.run_id,
                    run_name=r.info.run_name or "",
                    status=r.info.status,
                    start_time=datetime.fromtimestamp(r.info.start_time / 1000, tz=None).isoformat(),
                    params=params,
                    metrics=metrics,
                    experiment_id=r.info.experiment_id,
                    experiment_name=exp_map.get(r.info.experiment_id, ""),
                ))

        return MlflowExperimentsResponse(experiments=exp_names, runs=runs)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MLflow unavailable: {exc}") from exc


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Call Volume Forecast API", "docs": "/docs", "metrics": "/metrics"}