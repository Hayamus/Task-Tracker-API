from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import re

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