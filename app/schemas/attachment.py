from pydantic import BaseModel, Field
from datetime import datetime

class AttachmentUploadRequest(BaseModel):
    filename: str = Field(..., max_length=255, description="Оригинальное имя файла")
    size: int = Field(..., gt=0, description="Размер файла в байтах")
    content_type: str = Field(..., description="MIME-тип (например, 'image/png')")

class AttachmentUploadResponse(BaseModel):
    attachment_id: int
    storage_key: str
    upload_url: str

class AttachmentOut(BaseModel):
    id: int
    task_id: int
    filename: str
    size: int
    content_type: str
    storage_key: str
    created_at: datetime