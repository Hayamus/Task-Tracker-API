from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = 'admin'
    USER = 'user'
    MANAGER = 'manager'

class UserCreate(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=8, max_length=64)
    bio: Optional[str] = Field(max_length=5000)
    role: UserRole = UserRole.USER

class User(BaseModel):
    id: int
    username: str
    password: str
    role: UserRole

class TodoCreate(BaseModel):
    owner_id: int
    title: str = Field(..., max_length=24)
    description: str = Field(max_length=1500)

class TodoUpdate(BaseModel):
    id: int
    title: Optional[str] = Field(max_length=24)
    description: Optional[str] = Field(max_length=1500)
    completed: bool = False

class TodoBulkUpdate(BaseModel):
    ids: list[int]
    completed: bool