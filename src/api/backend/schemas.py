from datetime import datetime

from pydantic import BaseModel


class ForecastRequest(BaseModel):
    date: str


class ForecastResponse(BaseModel):
    date: str
    hourly_forecast: list[float]


class RetrainResponse(BaseModel):
    status: str
    message: str


class DriftFlag(BaseModel):
    feature: str
    psi: float
    ks_pvalue: float
    js_distance: float
    drift_detected: bool


class DriftStatusResponse(BaseModel):
    data_drift_detected: bool
    data_drift_share: float
    target_drift_detected: bool
    concept_drift_detected: bool
    any_drift: bool
    last_check_at: str
    feature_flags: list[DriftFlag]


class PredictionEntry(BaseModel):
    timestamp: str
    date: str
    hourly_forecast: list[float]


class ExperimentParam(BaseModel):
    key: str
    value: str


class ExperimentMetric(BaseModel):
    key: str
    value: float


class ExperimentRun(BaseModel):
    run_id: str
    run_name: str
    status: str
    start_time: str
    params: list[ExperimentParam]
    metrics: list[ExperimentMetric]
    experiment_id: str
    experiment_name: str


class MlflowExperimentsResponse(BaseModel):
    experiments: list[str]
    runs: list[ExperimentRun]


class NotificationAlert(BaseModel):
    alert_type: str
    message: str
    severity: str
    timestamp: str
    details: dict
