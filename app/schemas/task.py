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