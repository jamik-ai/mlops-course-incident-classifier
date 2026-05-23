Fixed MLflow configuration.

Run:

docker compose down -v
docker system prune -f
docker compose up --build

URLs:
Frontend: http://localhost
Swagger: http://localhost:8000/docs
MLflow: http://localhost:5001
Prometheus: http://localhost:9090
Grafana: http://localhost:3000

Grafana:
admin / admin
