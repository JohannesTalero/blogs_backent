from pydantic import BaseModel
from typing import Any
from datetime import datetime


class BlockCreate(BaseModel):
    type: str   # text | image | card | cta | document
    content_json: dict[str, Any]
    order: int = 0
    visible: bool = True


class BlockUpdate(BaseModel):
    type: str | None = None
    content_json: dict[str, Any] | None = None
    order: int | None = None
    visible: bool | None = None


class BlockResponse(BaseModel):
    id: str
    project_id: str
    type: str
    content_json: dict[str, Any]
    order: int
    visible: bool
    created_at: datetime
