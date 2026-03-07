from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.blocks.schemas import BlockResponse


class PostCreate(BaseModel):
    slug: str
    title: str
    order: int = 0
    visible: bool = True


class PostUpdate(BaseModel):
    slug: str | None = None
    title: str | None = None
    order: int | None = None
    visible: bool | None = None


class PostResponse(BaseModel):
    id: str
    project_id: str
    slug: str
    title: str
    order: int
    visible: bool
    created_at: datetime


class PostWithBlocks(PostResponse):
    blocks: list[BlockResponse] = []
