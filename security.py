import jwt
import datetime
from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN_EXPIRES_MINUTES = 15
REFRESH_TOKEN_EXPIRES_MINUTES = 300
ALGORITHM='HS256'

def create_access_token(data: Dict):
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES)
    to_encode.update({'exp': expire, 'type':'access'})
    SECRET = os.getenv('SECRET_KEY')
    return jwt.encode(to_encode, SECRET, ALGORITHM)

def create_refresh_token(data: Dict):
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=REFRESH_TOKEN_EXPIRES_MINUTES)
    to_encode.update({'exp': expire, 'type': 'refresh'})
    SECRET = os.getenv('REFRESH_SECRET_KEY')