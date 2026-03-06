from pydantic import BaseModel
from typing import Any


class SectionResponse(BaseModel):
    id: str
    project_id: str
    type: str
    content_json: dict[str, Any]
