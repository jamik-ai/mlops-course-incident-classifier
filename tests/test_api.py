import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestRootEndpoint:
    def test_root_returns_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "docs" in body


class TestForecastEndpoint:
    def test_forecast_valid_date(self, client):
        resp = client.post("/api/forecast", json={"date": "2026-01-01"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["date"] == "2026-01-01"
        assert len(body["hourly_forecast"]) == 24
        for v in body["hourly_forecast"]:
            assert isinstance(v, float)

    def test_forecast_invalid_date_format(self, client):
        resp = client.post("/api/forecast", json={"date": "not-a-date"})
        assert resp.status_code == 500


class TestPredictionsHistory:
    def test_history_empty_initially(self, client):
        resp = client.get("/api/predictions/history")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    def test_history_populates_after_forecast(self, client):
        client.post("/api/forecast", json={"date": "2026-06-15"})
        resp = client.get("/api/predictions/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) >= 1
        # assert body[-1]["date"] == "2026-06-15"
        assert len(body[-1]["hourly_forecast"]) == 24


class TestNotifications:
    def test_notifications_empty_initially(self, client):
        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_clear_notifications(self, client):
        resp = client.delete("/api/notifications/clear")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestDriftStatus:
    def test_drift_status_no_report(self, client):
        resp = client.get("/api/drift/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["any_drift"] is False
        assert body["last_check_at"] == ""
        assert body["feature_flags"] == []

    def test_drift_status_with_report(self, client, tmp_path):
        import os
        report_dir = Path(tmp_path) / "reports" / "drift"
        report_dir.mkdir(parents=True)
        report_file = report_dir / "latest.json"
        fake = {
            "data_drift_detected": True,
            "data_drift_share": 0.5,
            "target_drift_detected": False,
            "concept_drift_detected": True,
            "features": {
                "hour": {"psi": 0.3, "ks_pvalue": 0.01, "js_distance": 0.15, "drift_detected": True},
                "month": {"psi": 0.05, "ks_pvalue": 0.9, "js_distance": 0.02, "drift_detected": False},
            },
        }
        report_file.write_text(json.dumps(fake))

        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            resp = client.get("/api/drift/status")
            assert resp.status_code == 200
            body = resp.json()
            assert body["any_drift"] is True
            assert body["data_drift_detected"] is True
            assert body["concept_drift_detected"] is True
            assert len(body["feature_flags"]) == 2
            assert body["feature_flags"][0]["feature"] == "hour"
            assert body["feature_flags"][0]["drift_detected"] is True
        finally:
            os.chdir(orig_cwd)


class TestMlflowExperiments:
    @patch("mlflow.tracking.MlflowClient")
    @patch("mlflow.set_tracking_uri")
    def test_mlflow_experiments_success(self, mock_set_uri, mock_client_cls, client):
        mock_exp = MagicMock()
        mock_exp.name = "test-exp"
        mock_exp.experiment_id = "1"
        mock_run = MagicMock()
        mock_run.info.run_id = "abc123"
        mock_run.info.run_name = "run-1"
        mock_run.info.status = "FINISHED"
        mock_run.info.start_time = 1700000000000
        mock_run.info.experiment_id = "1"
        mock_run.data.params = {"lr": "0.05"}
        mock_run.data.metrics = {"mae": 1.5, "rmse": 2.0}

        mock_client = MagicMock()
        mock_client.search_experiments.return_value = [mock_exp]
        mock_client.search_runs.return_value = [mock_run]
        mock_client_cls.return_value = mock_client

        resp = client.get("/api/mlflow/experiments")
        assert resp.status_code == 200
        body = resp.json()
        assert "test-exp" in body["experiments"]
        assert len(body["runs"]) == 1
        assert body["runs"][0]["run_id"] == "abc123"
        assert body["runs"][0]["experiment_name"] == "test-exp"

    @patch("mlflow.tracking.MlflowClient", side_effect=ConnectionError("unreachable"))
    @patch("mlflow.set_tracking_uri")
    def test_mlflow_unavailable(self, mock_set_uri, mock_client, client):
        resp = client.get("/api/mlflow/experiments")
        assert resp.status_code == 503
        assert "MLflow unavailable" in resp.json()["detail"]


class TestModelReload:
    def test_model_reload(self, client):
        resp = client.post("/api/model/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestRetrain:
    @patch("src.api.backend.main._run_retrain_with_notification")
    def test_retrain_starts_background(self, mock_fn, client):
        resp = client.post("/api/retrain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
