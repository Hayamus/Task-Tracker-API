from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class AnalyticsComputeRequest(BaseModel):
    timezone: str = Field(
        default='UTC',
        description='Таймзона по стандарту IANA, например "Europe/Kyiv" или "UTC"'
    )
    scope: str = Field(
        default='user'
    )

class AnalyticsJobResponse(BaseModel):
    job_id: int
    status: str
    message: str

class AnalyticsResultResponse(BaseModel):
    job_id: int
    status: str
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None