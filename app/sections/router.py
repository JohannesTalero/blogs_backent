from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.sections.schemas import SectionResponse
from app.sections.validator import validate_section_content, VALID_SECTION_TYPES
from app.database import supabase
from app.dependencies import require_role, assert_project_ownership

router = APIRouter(prefix="/sections", tags=["sections"])


class SectionUpdate(BaseModel):
    """Payload para actualizar el contenido de una sección estática.

    Attributes:
        content_json: Nuevo contenido de la sección; validado según el tipo de sección.
    """

    content_json: dict[str, Any]



@router.get("/{project_id}", response_model=list[SectionResponse])
def get_sections(project_id: str) -> list[dict[str, Any]]:
    """Retorna todas las secciones estáticas del proyecto. Endpoint público.

    Args:
        project_id: ID del proyecto cuyas secciones se consultan.

    Returns:
        Lista con las 4 secciones (perfil, toolkit, recomendaciones, contacto).
    """
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
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    """Actualiza el content_json de una sección estática existente.

    Las secciones existen desde el seed; este endpoint solo actualiza su contenido.
    Requiere rol `owner` o `editor`.

    Args:
        project_id: ID del proyecto al que pertenece la sección.
        section_type: Tipo de sección a actualizar (perfil | toolkit | recomendaciones | contacto).
        body: Nuevo content_json para la sección.
        user: Payload del JWT inyectado por `require_role`.

    Returns:
        La sección actualizada.

    Raises:
        HTTPException 403: Rol insuficiente o token de otro proyecto.
        HTTPException 404: Sección no encontrada (seed no ejecutado).
        HTTPException 422: Tipo de sección inválido o content_json no cumple el esquema.
    """
    assert_project_ownership(user, project_id)

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
