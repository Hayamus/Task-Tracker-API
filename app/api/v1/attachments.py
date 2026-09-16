import os
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.database import get_db_connection
from app.api.deps import get_current_user, check_task_access
from app.repositories.attachment_repo import AttachmentRepository
from app.schemas.attachment import AttachmentUploadRequest, AttachmentUploadResponse

router = APIRouter(tags=["Attachments"])

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.post(
    "/todos/{id}/attachments/request-upload",
    response_model=AttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED
)
async def request_attachment_upload(
    id: int,
    upload_req: AttachmentUploadRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    await check_task_access(id, current_user["id"], db)

    if upload_req.size > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой. Максимальный размер: {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} МБ"
        )

    if upload_req.content_type.lower() not in [m.lower() for m in settings.ALLOWED_MIME_TYPES]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Недопустимый тип файла '{upload_req.content_type}'. Разрешены: {settings.ALLOWED_MIME_TYPES}"
        )

    file_ext = os.path.splitext(upload_req.filename)[1]
    storage_key = f"{uuid.uuid4().hex}{file_ext}"

    repo = AttachmentRepository(db)
    attachment_id = await repo.create_attachment(
        task_id=id,
        owner_id=current_user["id"],
        filename=upload_req.filename,
        size=upload_req.size,
        content_type=upload_req.content_type,
        storage_key=storage_key
    )

    base_url = str(request.base_url).rstrip("/")
    upload_url = f"{base_url}/attachments/upload/{storage_key}"

    return AttachmentUploadResponse(
        attachment_id=attachment_id,
        storage_key=storage_key,
        upload_url=upload_url
    )


@router.put("/attachments/upload/{storage_key}", status_code=status.HTTP_200_OK)
async def upload_file_binary(storage_key: str, request: Request):
    file_path = os.path.join(settings.UPLOAD_DIR, storage_key)
    
    total_bytes = 0
    with open(file_path, "wb") as f:
        async for chunk in request.stream():
            total_bytes += len(chunk)
            if total_bytes > settings.MAX_FILE_SIZE_BYTES:
                f.close()
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Превышен максимальный лимит размера файла"
                )
            f.write(chunk)

    return {"status": "success", "message": "Файл успешно загружен"}


@router.delete("/attachments/{id}", status_code=status.HTTP_200_OK)
async def delete_attachment(
    id: int,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    repo = AttachmentRepository(db)
    attachment = await repo.get_by_id(id)

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вложение не найдено"
        )


    if attachment["owner_id"] != current_user["id"]:
        await check_task_access(attachment["task_id"], current_user["id"], db)

    file_path = os.path.join(settings.UPLOAD_DIR, attachment["storage_key"])
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    await repo.delete(id)

    return {"message": "Вложение успешно удалено"}