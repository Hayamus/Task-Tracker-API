import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "develop")

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT == 'production'

    SECRET_KEY: str = os.getenv("SECRET_KEY", "fallback-secret-key-for-dev-only")
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

    @property
    def REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60

    @property
    def REFRESH_COOKIE_MAX_AGE(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://myuser:mypassword@localhost:5432/mydatabase"
    )
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        'redis://localhost:6379/0'
    )

    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024 

    ALLOWED_MIME_TYPES: list[str] = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/zip"
    ]

    UPLOAD_DIR: str = "uploads"
    

settings = Settings()