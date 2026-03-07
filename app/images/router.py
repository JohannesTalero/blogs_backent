import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.database import supabase
from app.dependencies import assert_project_ownership, require_role

router = APIRouter(prefix="/images", tags=["images"])

BUCKET = "images"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/{project_id}")
def upload_image(
    project_id: str,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, str]:
    assert_project_ownership(user, project_id)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Tipo de archivo no permitido. Use JPEG, PNG, GIF o WebP.",
        )

    content = file.file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="El archivo supera el límite de 5 MB.")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    path = f"{project_id}/{uuid.uuid4()}.{ext}"

    supabase.storage.from_(BUCKET).upload(path, content, {"content-type": file.content_type})

    url: str = supabase.storage.from_(BUCKET).get_public_url(path)
    return {"url": url}
