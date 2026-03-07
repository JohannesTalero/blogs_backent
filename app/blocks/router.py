from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.blocks.schemas import BlockCreate, BlockUpdate, BlockResponse
from app.blocks.validator import validate_content_json, CONTENT_VALIDATORS
from app.database import supabase
from app.dependencies import require_role, assert_project_ownership

router = APIRouter(prefix="/blocks", tags=["blocks"])

VALID_TYPES: set[str] = set(CONTENT_VALIDATORS.keys())


def _get_post_project_id(post_id: str) -> str:
    """Obtiene el project_id del post. Lanza 404 si no existe."""
    result = supabase.table("posts").select("project_id").eq("id", post_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    return result.data[0]["project_id"]


@router.get("/{post_id}/admin/all", response_model=list[BlockResponse])
def get_all_blocks_admin(
    post_id: str,
    user: dict[str, Any] = Depends(require_role("owner", "editor", "viewer")),
) -> list[dict[str, Any]]:
    project_id = _get_post_project_id(post_id)
    assert_project_ownership(user, project_id)
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("post_id", post_id)
        .order("order")
        .execute()
    )
    return result.data


@router.get("/{post_id}", response_model=list[BlockResponse])
def get_blocks(post_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("post_id", post_id)
        .eq("visible", True)
        .order("order")
        .execute()
    )
    return result.data


@router.post("/{post_id}", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
def create_block(
    post_id: str,
    body: BlockCreate,
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    project_id = _get_post_project_id(post_id)
    assert_project_ownership(user, project_id)

    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.type}")

    validated_content = validate_content_json(body.type, body.content_json)

    data: dict[str, Any] = {
        "post_id": post_id,
        "type": body.type,
        "content_json": validated_content,
        "order": body.order,
        "visible": body.visible,
    }
    result = supabase.table("blocks").insert(data).execute()
    return result.data[0]


@router.put("/{post_id}/{block_id}", response_model=BlockResponse)
def update_block(
    post_id: str,
    block_id: str,
    body: BlockUpdate,
    user: dict[str, Any] = Depends(require_role("owner", "editor")),
) -> dict[str, Any]:
    project_id = _get_post_project_id(post_id)
    assert_project_ownership(user, project_id)

    existing = (
        supabase.table("blocks")
        .select("id, type")
        .eq("id", block_id)
        .eq("post_id", post_id)
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


@router.delete("/{post_id}/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(
    post_id: str,
    block_id: str,
    user: dict[str, Any] = Depends(require_role("owner")),
) -> None:
    project_id = _get_post_project_id(post_id)
    assert_project_ownership(user, project_id)

    existing = (
        supabase.table("blocks")
        .select("id")
        .eq("id", block_id)
        .eq("post_id", post_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    supabase.table("blocks").delete().eq("id", block_id).execute()
