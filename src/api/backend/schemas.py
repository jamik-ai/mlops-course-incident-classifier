from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ForecastRequest(BaseModel):
    date: str


class ForecastResponse(BaseModel):
    date: str
    hourly_forecast: list[float]


class RetrainResponse(BaseModel):
    status: str
    message: str


class RetrainStatusResponse(BaseModel):
    status: str
    message: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
