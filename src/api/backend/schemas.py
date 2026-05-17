from pydantic import BaseModel


class ForecastRequest(BaseModel):
    date: str


class ForecastResponse(BaseModel):
    date: str
    hourly_forecast: list[float]


class RetrainResponse(BaseModel):
    status: str
    message: str
