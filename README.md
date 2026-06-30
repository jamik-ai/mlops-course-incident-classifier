# Прогнозирование вызовов для колл-центра

Учебный проект MLOps по прогнозированию количества вызовов для контакт-центра. Проект закрывает полный жизненный цикл модели:

- прием новых данных
- обнаружение деградации (data/target/concept drift)
- ручное и автоматическое переобучение
- обновление модели в сервисе
- мониторинг метрик через веб-интерфейс

## Что есть в проекте

- FastAPI сервис с OpenAPI
- `POST /api/forecast` для прогноза объема звонков
- MLflow трекинг и регистрация модели
- drift detection и генерация отчётов
- retraining pipeline
- Prometheus / Grafana мониторинг
- Docker Compose для локальной отладки
- Kubernetes/Minikube + ArgoCD для демонстрации деплоя
- DVC-структура для данных
- Git с conventional commits

## Технологии

- Python 3.11+
- FastAPI
- XGBoost
- MLflow
- Docker / Docker Compose
- Kubernetes / Minikube
- Prometheus / Grafana
- DVC

## Быстрый запуск

1. Создать окружение и установить зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Запустить тесты:

```bash
pytest -q
```

3. Запустить сервис:

```bash
uvicorn src.api.backend.main:app --reload --host 0.0.0.0 --port 8000
```

4. Проверить базовый API:

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/forecast -H "Content-Type: application/json" -d '{"date":"2025-01-01"}'
```

## Docker Compose

Для локальной отладки используйте:

```bash
docker compose down -v
docker compose build --no-cache mlflow
docker compose up --build
```

Серверы:

- Backend: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- MLflow: http://localhost:5001
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Основные API

- `GET /api/health`
- `POST /api/forecast`
- `POST /api/drift/run`
- `GET /api/drift/report`
- `POST /api/retrain`
- `POST /api/model/reload`
- `GET /metrics`

## Drift detection

Выполняется в `src/monitoring/drift.py`.

Проверяются:

- data drift
- target drift
- concept drift
- PSI
- KS-test
- Jensen-Shannon distance

Отчёты сохраняются в `reports/drift/latest.html` и `reports/drift/latest.json`.

## MLflow

Retraining pipeline логирует:

- параметры модели
- метрики MAE/RMSE
- артефакт модели
- зарегистрированную модель `call-volume-forecast`
- отчёт drift

Запуск тренировки:

```bash
python -m src.pipelines.retrain
```

Авто retraining при drift:

```bash
python -m src.pipelines.auto_retrain
```

## Kubernetes и ArgoCD

Доступны манифесты в `k8s/` и ArgoCD приложение в `argocd/application.yaml`.

Локальный запуск через Minikube:

```bash
minikube start --driver=docker

# Собрать образы внутри minikube (чтобы не тянуть из registry)
eval $(minikube docker-env)
docker build -t ghcr.io/jamik-ai/mlops-course-incident-classifier:latest .
docker build -t ghcr.io/jamik-ai/mlops-course-incident-classifier-frontend:latest -f Dockerfile.frontend .
docker build -t ghcr.io/jamik-ai/mlops-course-incident-classifier-mlflow:latest -f Dockerfile.mlflow .

# Применить манифесты
kubectl apply -f k8s/

# Открыть frontend
Dataset not found: /app/data/reference/reference_dataset.csv
```

ArgoCD:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/application.yaml
```

## CI/CD и деплой

В репозитории настроен GitHub Actions workflow, который:
- запускает линтеры и тесты,
- собирает Docker-образы `backend`, `frontend`, `mlflow`,
- пушит их в GitHub Container Registry (GHCR),
- подцепляет Kubernetes через секрет `KUBE_CONFIG_DATA` и применяет манифесты из `k8s/`.

Для работы CD нужно в GitHub установить секрет `KUBE_CONFIG_DATA` с Base64-кодированным kubeconfig и дать `GITHUB_TOKEN` доступ к GHCR.

## Структура

- `src/api/backend/main.py` — FastAPI
- `src/modeling/predict.py` — прогнозирование
- `src/pipelines/retrain.py` — retraining и MLflow
- `src/monitoring/drift.py` — drift detection
- `models/` — сохранённая модель
- `data/` — reference и current датасеты
- `docker-compose.yml` — локальная отладка
- `k8s/` — Kubernetes манифесты

## Важно

Проект реализует учебный MLOps-цикл для прогноза нагрузки колл-центра. Для production-версии можно добавить реальный DVC remote, CI/CD, persistent volumes и обновить образы в Kubernetes.
