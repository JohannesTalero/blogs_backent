from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.blocks.schemas import BlockCreate, BlockUpdate, BlockResponse
from app.blocks.validator import validate_content_json, CONTENT_VALIDATORS
from app.database import supabase
from app.dependencies import require_role

router = APIRouter(prefix="/blocks", tags=["blocks"])

VALID_TYPES: set[str] = set(CONTENT_VALIDATORS.keys())


def _assert_project_ownership(user: dict[str, Any], project_id: str) -> None:
    """Verifica que el JWT corresponde al proyecto del recurso solicitado.

    Args:
        user: Payload del JWT con clave `project_id`.
        project_id: ID del proyecto extraído de la URL.

    Raises:
        HTTPException 403: Si el project_id del token no coincide con el de la URL.
    """
    if user["project_id"] != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


@router.get("/{project_id}/admin/all", response_model=list[BlockResponse])
def get_all_blocks_admin(
    project_id: str,
    user: dict[str, Any] = Depends(require_role("owner", "editor", "viewer")),
) -> list[dict[str, Any]]:
    """Retorna todos los bloques del proyecto, incluyendo los no visibles.

    Requiere rol `owner`, `editor` o `viewer`. Usado por el panel admin.

    Args:
        project_id: ID del proyecto cuyos bloques se consultan.
        user: Payload del JWT inyectado por `require_role`.

    Returns:
        Lista de bloques ordenados por `order` (ASC), incluyendo `visible=False`.

    Raises:
        HTTPException 401: Sin token.
        HTTPException 403: Token de otro proyecto o rol insuficiente.
    """
    _assert_project_ownership(user, project_id)
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("project_id", project_id)
        .order("order")
        .execute()
    )
    return result.data


@router.get("/{project_id}", response_model=list[BlockResponse])
def get_blocks(project_id: str) -> list[dict[str, Any]]:
    """Retorna los bloques visibles del proyecto. Endpoint público sin autenticación.

    Args:
        project_id: ID del proyecto cuyos bloques se consultan.

    Returns:
        Lista de bloques con `visible=True`, ordenados por `order` (ASC).
    """
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("project_id", project_id)
        .eq("visible", True)
        .order("order")
        .execute()
    )
    return result.data


@router.post("/{project_id}", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
def create_block(
    project_id: str,
    body: BlockCreate,
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    """Crea un nuevo bloque en el proyecto.

    Requiere rol `owner` o `editor`. Valida el `content_json` según el tipo.

    Args:
        project_id: ID del proyecto donde se crea el bloque.
        body: Datos del nuevo bloque (tipo, contenido, orden, visibilidad).
        user: Payload del JWT inyectado por `require_role`.

    Returns:
        El bloque creado.

    Raises:
        HTTPException 403: Rol insuficiente o token de otro proyecto.
        HTTPException 422: Tipo inválido o content_json no cumple el esquema.
    """
    _assert_project_ownership(user, project_id)

    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.type}")

    validated_content = validate_content_json(body.type, body.content_json)

    data: dict[str, Any] = {
        "project_id": project_id,
        "type": body.type,
        "content_json": validated_content,
        "order": body.order,
        "visible": body.visible,
    }
    result = supabase.table("blocks").insert(data).execute()
    return result.data[0]


@router.put("/{project_id}/{block_id}", response_model=BlockResponse)
def update_block(
    project_id: str,
    block_id: str,
    body: BlockUpdate,
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    """Actualiza parcialmente un bloque existente (PATCH-like via PUT).

    Solo los campos enviados en el body son modificados. Si se actualiza
    `content_json`, se revalida contra el tipo efectivo del bloque.

    Args:
        project_id: ID del proyecto al que pertenece el bloque.
        block_id: ID del bloque a actualizar.
        body: Campos a actualizar (todos opcionales).
        user: Payload del JWT inyectado por `require_role`.

    Returns:
        El bloque actualizado.

    Raises:
        HTTPException 403: Rol insuficiente o token de otro proyecto.
        HTTPException 404: Bloque no encontrado en el proyecto.
        HTTPException 422: Tipo inválido o content_json no cumple el esquema.
    """
    _assert_project_ownership(user, project_id)

    existing = (
        supabase.table("blocks")
        .select("id, type")
        .eq("id", block_id)
        .eq("project_id", project_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    updates: dict[str, Any] = body.model_dump(exclude_none=True)
    effective_type: str = body.type or existing.data[0]["type"]

    if body.type and body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.type}")
    if body.content_json is not None:
        updates["content_json"] = validate_content_json(effective_type, body.content_json)

    result = (
        supabase.table("blocks")
        .update(updates)
        .eq("id", block_id)
        .execute()
    )
    return result.data[0]


@router.delete("/{project_id}/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(
    project_id: str,
    block_id: str,
    user: dict[str, Any] = Depends(require_role("owner")),
) -> None:
    """Elimina un bloque del proyecto. Solo disponible para `owner`.

    Args:
        project_id: ID del proyecto al que pertenece el bloque.
        block_id: ID del bloque a eliminar.
        user: Payload del JWT inyectado por `require_role`.

    Raises:
        HTTPException 403: Rol insuficiente o token de otro proyecto.
        HTTPException 404: Bloque no encontrado en el proyecto.
    """
    _assert_project_ownership(user, project_id)

    existing = (
        supabase.table("blocks")
        .select("id")
        .eq("id", block_id)
        .eq("project_id", project_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    supabase.table("blocks").delete().eq("id", block_id).execute()
