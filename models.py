from pydantic import BaseModel, Field, field_validator, AwareDatetime
from typing import Optional
from enum import Enum
import re
from datetime import datetime

class UserRole(str, Enum):
    ADMIN = 'admin'
    MEMBER = 'member'
    MODERATOR = 'moderator'

class UserCreate(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=8, max_length=64)
    bio: Optional[str] = Field(max_length=5000)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r'\d', value):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        if not re.search(r'[A-Z]', value) and not re.search(r'[А-Я]', value):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not re.search(r'[a-z]', value) and not re.search(r'[а-я]', value):
            raise ValueError('Пароль должен содержать хотя бы одну строчную букву')
        return value

class UserInDB(UserCreate):
    is_admin: bool = False

class User(BaseModel):
    id: int
    username: str
    password: str
    is_admin: bool

class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=24)
    description: str = Field(max_length=1200)

class Team(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str
    members_count: int

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

class TodoBulkUpdate(BaseModel):
    ids: list[int]
    completed: bool