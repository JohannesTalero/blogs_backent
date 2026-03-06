from fastapi import APIRouter, Depends, HTTPException, status
from app.blocks.schemas import BlockCreate, BlockUpdate, BlockResponse
from app.database import supabase
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/blocks", tags=["blocks"])

VALID_TYPES = {"text", "image", "card", "cta", "document"}


def _assert_project_ownership(user: dict, project_id: str):
    """Garantiza que el JWT pertenece al mismo proyecto del recurso."""
    if user["project_id"] != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


# --- GET admin (protegido) — debe ir antes que /{project_id}/{block_id} ---
@router.get("/{project_id}/admin/all", response_model=list[BlockResponse])
def get_all_blocks_admin(
    project_id: str,
    user: dict = Depends(require_role("owner", "editor", "viewer")),
):
    _assert_project_ownership(user, project_id)
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("project_id", project_id)
        .order("order")
        .execute()
    )
    return result.data


# --- GET público ---
@router.get("/{project_id}", response_model=list[BlockResponse])
def get_blocks(project_id: str):
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("project_id", project_id)
        .eq("visible", True)
        .order("order")
        .execute()
    )
    return result.data


# --- POST: owner o editor ---
@router.post("/{project_id}", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
def create_block(
    project_id: str,
    body: BlockCreate,
    user: dict = Depends(require_role("owner", "editor")),
):
    _assert_project_ownership(user, project_id)

    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.type}")

    data = {
        "project_id": project_id,
        "type": body.type,
        "content_json": body.content_json,
        "order": body.order,
        "visible": body.visible,
    }
    result = supabase.table("blocks").insert(data).execute()
    return result.data[0]


# --- PUT: owner o editor ---
@router.put("/{project_id}/{block_id}", response_model=BlockResponse)
def update_block(
    project_id: str,
    block_id: str,
    body: BlockUpdate,
    user: dict = Depends(require_role("owner", "editor")),
):
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

    updates = body.model_dump(exclude_none=True)
    if body.type and body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.type}")

    result = (
        supabase.table("blocks")
        .update(updates)
        .eq("id", block_id)
        .execute()
    )
    return result.data[0]


# --- DELETE: solo owner ---
@router.delete("/{project_id}/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(
    project_id: str,
    block_id: str,
    user: dict = Depends(require_role("owner")),
):
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
