# MLOps проект: прогнозирование количества вызовов

Проект доработан поверх существующей архитектуры: FastAPI backend, простой Web UI, XGBoost модель, Docker, DVC-структура, MLflow, drift detection, Prometheus/Grafana, Kubernetes/Minikube и ArgoCD manifests.

## Что реализовано

- FastAPI API с OpenAPI-документацией на `/docs`.
- Endpoint прогноза: `POST /api/forecast`.
- Drift detection: `POST /api/drift/run`.
- HTML drift report: `GET /api/drift/report`.
- Prometheus metrics: `GET /metrics`.
- Ручной retraining: `POST /api/retrain`.
- Перезагрузка модели: `POST /api/model/reload`.
- MLflow tracking и model registry.
- Docker и Docker Compose для локальной отладки.
- Kubernetes manifests для Minikube.
- ArgoCD Application для GitOps.
- Web UI с кнопками drift check и retraining.

## Архитектура

```text
Frontend UI
  ├─ POST /api/forecast
  ├─ POST /api/drift/run
  ├─ GET  /api/drift/report
  └─ POST /api/retrain

FastAPI backend
  ├─ XGBoost model: models/forecast_model.pkl
  ├─ features: models/features.pkl
  ├─ drift detection: src/monitoring/drift.py
  ├─ retraining: src/pipelines/retrain.py
  └─ metrics: /metrics

Data
  ├─ data/reference/reference_dataset.csv
  └─ data/current/current_dataset.csv

Observability
  ├─ Prometheus scrapes /metrics
  └─ Grafana dashboard shows drift and model metrics

Deployment
  ├─ Docker Compose: local debug only
  ├─ Kubernetes/Minikube: k8s/
  └─ ArgoCD: argocd/application.yaml
```

## Drift detection

Файл: `src/monitoring/drift.py`.

Считаются:

- Data Drift по входным признакам.
- Target Drift по колонке `count`.
- Concept Drift по деградации MAE между reference и current.
- PSI.
- KS-test.
- Jensen-Shannon distance.

Reference dataset хранится в:

```text
data/reference/reference_dataset.csv
```

Current dataset хранится в:

```text
data/current/current_dataset.csv
```

Отчеты сохраняются в:

```text
reports/drift/latest.html
reports/drift/latest.json
```

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Запуск API:

```bash
uvicorn src.api.backend.main:app --reload --host 0.0.0.0 --port 8000
```

Проверка:

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/drift/run
curl -X POST http://localhost:8000/api/retrain
```

## Docker Compose

```bash
docker compose down -v
docker compose build --no-cache mlflow
docker compose up --build
```

В этой версии MLflow собирается локально из `Dockerfile.mlflow`, поэтому Docker больше не тянет проблемный образ `ghcr.io/mlflow/mlflow:v2.19.0`.

Сервисы:

- Frontend: http://localhost
- Backend: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- MLflow: http://localhost:5000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana login:

```text
admin / admin
```

Если остался старый контейнер MLflow, удалить его можно так:

```bash
docker rm -f call_forecast_mlflow
docker compose down -v
docker compose up --build
```

## MLflow Registry

Retraining pipeline логирует:

- параметры модели;
- MAE/RMSE;
- XGBoost model artifact;
- registered model `call-volume-forecast`;
- drift JSON/HTML report.

Файл:

```text
src/pipelines/retrain.py
```

Ручной запуск:

```bash
python -m src.pipelines.retrain
```

Автоматический запуск при drift:

```bash
python -m src.pipelines.auto_retrain
```

## Kubernetes / Minikube

```bash
minikube start
kubectl apply -f k8s/
```

Проверка:

```bash
kubectl get pods -n mlops
kubectl get svc -n mlops
```

Port-forward backend:

```bash
kubectl port-forward -n mlops svc/call-forecast-backend 8000:8000
```

Port-forward MLflow:

```bash
kubectl port-forward -n mlops svc/mlflow 5000:5000
```

## ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/application.yaml
```

## Git flow и conventional commits

```bash
git checkout -b develop
git checkout -b feature/drift-retraining-monitoring

git add .
git commit -m "feat(monitoring): add drift detection and prometheus metrics"
git commit -m "feat(training): add mlflow retraining pipeline"
git commit -m "feat(deploy): add kubernetes and argocd manifests"
```

## Что важно заменить под реальный проект

1. Подключить реальный DVC remote вместо локального placeholder.
2. Заменить sample datasets на реальные данные.
3. Настроить image name в `k8s/*.yaml` под свой GHCR/DockerHub registry.
4. Для production заменить SQLite MLflow backend на PostgreSQL/S3-compatible artifact storage.
5. Для production добавить persistent volumes для MLflow, Prometheus и Grafana.
