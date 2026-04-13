from pydantic import BaseModel


class ForecastRequest(BaseModel):
    date: str  # "YYYY-MM-DD"

class ForecastResponse(BaseModel):
    date: str
    hourly_forecast: list  # 24 значения