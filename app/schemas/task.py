from pydantic import BaseModel, Field, AwareDatetime
from typing import Optional

class TaskCreate(BaseModel):
    title: str = Field(..., max_length=24)
    description: str = Field(max_length=1500)
    deadline: Optional[AwareDatetime] = None
    is_personal: bool
    team_id: Optional[int] = None

class TaskInDB(BaseModel):
    owner_id: int
    team_id: Optional[int] = None
    title: str
    description: str
    deadline: Optional[AwareDatetime] = None
    is_personal: bool

class TaskUpdate(BaseModel):
    description: Optional[str] = None
    completed: bool
    version: int

class TaskFilterParams(BaseModel):
    completed: Optional[bool] = None
    is_personal: Optional[bool] = None
    team_id: Optional[int] = None
    search: Optional[str] = Field(None, max_length=50, description="Поиск по названию задачи")
    limit: int = Field(20, ge=1, le=100, description="Количество записей (макс. 100)")
    offset: int = Field(0, ge=0, description="Смещение")