from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import re

class UserRole(str, Enum):
    ADMIN = 'admin'
    USER = 'user'
    MANAGER = 'manager'

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