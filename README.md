# MLOps проект: прогнозирование количества вызовов

Этот проект демонстрирует учебный MLOps-пайплайн для прогноза количества вызовов. Основные компоненты:

- FastAPI backend с REST API
- XGBoost модель для прогнозов
- MLflow для экспериментов и регистрации модели
- Drift detection и retraining pipeline
- Docker Compose для локальной отладки
- Дополнительно: мониторинг Prometheus/Grafana и Kubernetes манифесты

## Что реализовано

- API прогноза: `POST /api/forecast`
- Проверка работоспособности: `GET /api/health`
- Запуск drift detection: `POST /api/drift/run`
- Просмотр отчёта drift: `GET /api/drift/report`
- Запуск retraining: `POST /api/retrain`
- Перезагрузка текущей модели: `POST /api/model/reload`
- Prometheus метрики: `GET /metrics`
- MLflow трекинг и регистрация модели
- Простой веб-интерфейс для вызова прогноза и drift проверки

## Структура проекта

- `src/api/backend/main.py` — FastAPI приложение
- `src/modeling/predict.py` — логика прогноза
- `src/pipelines/retrain.py` — retraining pipeline и логирование в MLflow
- `src/monitoring/drift.py` — drift detection
- `models/` — сохранённые артефакты модели и признаков
- `data/` — reference и current датасеты
- `Dockerfile` — бэкенд образ
- `Dockerfile.mlflow` — образ MLflow
- `docker-compose.yml` — локальный стек для отладки
- `k8s/` — Kubernetes манифесты
- `argocd/application.yaml` — ArgoCD application

## Основные технологии

- Python 3.11+
- FastAPI
- XGBoost
- MLflow
- Docker / Docker Compose
- Prometheus / Grafana
- Kubernetes / Minikube
- DVC (структура и шаблон для remote)

## Запуск локально

1. Создайте виртуальное окружение:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Запустите тесты:

```bash
pytest -q
```

3. Запустите бэкенд напрямую:

```bash
uvicorn src.api.backend.main:app --reload --host 0.0.0.0 --port 8000
```

4. Проверьте работу API:

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/forecast -H "Content-Type: application/json" -d '{"date":"2025-01-01"}'
curl -X POST http://localhost:8000/api/drift/run
```

## Docker Compose

Для локальной проверки всего стека используйте Docker Compose:

```bash
docker compose down -v
docker compose build --no-cache mlflow
docker compose up --build
```

Основные сервисы:

- Frontend: http://localhost
- Backend: http://localhost:8000
- Документация OpenAPI: http://localhost:8000/docs
- MLflow: http://localhost:5001
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana:

```text
admin / admin
```

### Важные настройки MLflow

В текущей конфигурации MLflow использует PostgreSQL + MinIO:

- `postgres` для бэкенд-хранилища
- `minio` для артефактов

Если нужно, можно упростить проект и оставить MLflow на локальном SQLite и файловом артефакте.

## API эндпоинты

- `GET /api/health` — проверка статуса сервиса
- `POST /api/forecast` — прогноз по дате
- `POST /api/drift/run` — запуск drift detection
- `GET /api/drift/report` — получение HTML отчёта
- `POST /api/retrain` — запуск retraining pipeline
- `POST /api/model/reload` — перезагрузка модели
- `GET /metrics` — метрики Prometheus

## Drift detection

Drift detection реализован в `src/monitoring/drift.py`.

Анализируется:

- Data Drift по входным признакам
- Target Drift по колонке `count`
- Concept Drift по изменению MAE
- PSI
- KS-test
- Jensen-Shannon distance

Исходные данные хранятся в:

- `data/reference/reference_dataset.csv`
- `data/current/current_dataset.csv`

Отчёты генерируются в:

- `reports/drift/latest.html`
- `reports/drift/latest.json`

## MLflow и регистр модели

Retraining pipeline сохраняет в MLflow:

- параметры модели
- метрики MAE/RMSE
- артефакт модели
- зарегистрированную модель `call-volume-forecast`
- отчёт drift

Запуск retraining:

```bash
python -m src.pipelines.retrain
```

Автоматический retraining по drift:

```bash
python -m src.pipelines.auto_retrain
```

## Kubernetes / Minikube

Для демонстрации Kubernetes есть манифесты в каталоге `k8s/`.

Запуск:

```bash
minikube start
kubectl apply -f k8s/
```

Проверка:

```bash
kubectl get pods -n mlops
kubectl get svc -n mlops
```

Примеры port-forward:

```bash
kubectl port-forward -n mlops svc/call-forecast-backend 8000:8000
kubectl port-forward -n mlops svc/mlflow 5000:5000
```

## ArgoCD

Для GitOps есть готовый объект ArgoCD:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/application.yaml
```

## Важные заметки

Для production-версии рекомендуется:

1. Использовать реальный DVC remote вместо локального placeholder
2. Заменить тестовые dataset'ы на реальные данные
3. Настроить имена образов в `k8s/*.yaml` для своего Docker Registry
4. Подключить PostgreSQL/S3-compatible storage для MLflow
5. Добавить persistent volume для MLflow, Prometheus и Grafana

## Быстрый запуск

```bash
docker compose down -v
docker compose up --build --force-recreate
```

Основной стек:

- Frontend: http://localhost
- OpenAPI: http://localhost:8000/docs
- MLflow: http://localhost:5001
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Контакты

Этот проект подготовлен как учебная MLOps работа. Для проверки доступны все основные компоненты: модель, API, логирование, drift detection и простой деплоймент.
