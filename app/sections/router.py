from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any
from pydantic import BaseModel
from app.sections.schemas import SectionResponse
from app.sections.validator import validate_section_content, VALID_SECTION_TYPES
from app.database import supabase
from app.dependencies import require_role

router = APIRouter(prefix="/sections", tags=["sections"])


class SectionUpdate(BaseModel):
    content_json: dict[str, Any]


def _assert_project_ownership(user: dict, project_id: str):
    if user["project_id"] != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


@router.get("/{project_id}", response_model=list[SectionResponse])
def get_sections(project_id: str):
    result = (
        supabase.table("sections")
        .select("*")
        .eq("project_id", project_id)
        .execute()
    )
    return result.data


@router.put("/{project_id}/{section_type}", response_model=SectionResponse)
def update_section(
    project_id: str,
    section_type: str,
    body: SectionUpdate,
    user: dict = Depends(require_role("owner", "editor")),
):
    _assert_project_ownership(user, project_id)

    if section_type not in VALID_SECTION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido: '{section_type}'. Válidos: {sorted(VALID_SECTION_TYPES)}"
        )

    validated_content = validate_section_content(section_type, body.content_json)

    existing = (
        supabase.table("sections")
        .select("id")
        .eq("project_id", project_id)
        .eq("type", section_type)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Sección no encontrada. Ejecutar seed primero.")

    result = (
        supabase.table("sections")
        .update({"content_json": validated_content})
        .eq("project_id", project_id)
        .eq("type", section_type)
        .execute()
    )
    return result.data[0]
