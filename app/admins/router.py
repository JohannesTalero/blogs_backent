"""Router de administradores: gestión de usuarios con roles por proyecto."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext

from app.admins.schemas import AdminCreate, AdminResponse
from app.database import supabase
from app.dependencies import require_role, assert_project_ownership

router = APIRouter(prefix="/admins", tags=["admins"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_ROLES: set[str] = {"editor", "viewer"}


@router.get("/{project_id}", response_model=list[AdminResponse])
def list_admins(
    project_id: str,
    user: dict[str, Any] = Depends(require_role("owner")),
) -> list[dict[str, Any]]:
    """Lista todos los administradores del proyecto. Solo accesible por `owner`.

    Args:
        project_id: ID del proyecto cuyos admins se listan.
        user: Payload del JWT inyectado por `require_role`.

    Returns:
        Lista de admins del proyecto (sin `hashed_password`).

    Raises:
        HTTPException 403: Rol insuficiente o token de otro proyecto.
    """
    assert_project_ownership(user, project_id)
    result = (
        supabase.table("admins")
        .select("id, project_id, email, role, created_at")
        .eq("project_id", project_id)
        .execute()
    )
    return result.data


@router.post("/{project_id}", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    project_id: str,
    body: AdminCreate,
    user: dict[str, Any] = Depends(require_role("owner")),
) -> dict[str, Any]:
    """Crea un nuevo administrador en el proyecto. Solo accesible por `owner`.

    El rol `owner` no puede asignarse via API; solo `editor` y `viewer` son válidos.
    La contraseña se hashea con bcrypt antes de persistir.

    Args:
        project_id: ID del proyecto donde se crea el admin.
        body: Datos del nuevo admin (email, password, rol).
        user: Payload del JWT inyectado por `require_role`.

    Returns:
        El admin creado (sin `hashed_password`).

    Raises:
        HTTPException 403: Rol insuficiente o token de otro proyecto.
        HTTPException 409: Email ya registrado en el proyecto.
        HTTPException 422: Rol inválido o password no cumple SEC-009.
    """
    assert_project_ownership(user, project_id)

    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Rol inválido: '{body.role}'. Permitidos: {sorted(VALID_ROLES)}",
        )

    existing = (
        supabase.table("admins")
        .select("id")
        .eq("project_id", project_id)
        .eq("email", body.email)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Ya existe un admin con ese email en este proyecto")

    hashed = pwd_context.hash(body.password)
    data: dict[str, Any] = {
        "project_id": project_id,
        "email": body.email,
        "hashed_password": hashed,
        "role": body.role,
    }
    result = supabase.table("admins").insert(data).execute()
    return result.data[0]


@router.delete("/{project_id}/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    project_id: str,
    admin_id: str,
    user: dict[str, Any] = Depends(require_role("owner")),
) -> None:
    """Elimina un administrador del proyecto. Solo accesible por `owner`.

    Un owner no puede eliminarse a sí mismo.

    Args:
        project_id: ID del proyecto al que pertenece el admin.
        admin_id: ID del admin a eliminar.
        user: Payload del JWT inyectado por `require_role`.

    Raises:
        HTTPException 400: El owner intenta eliminarse a sí mismo.
        HTTPException 403: Rol insuficiente o token de otro proyecto.
        HTTPException 404: Admin no encontrado en el proyecto.
    """
    assert_project_ownership(user, project_id)

    if user["sub"] == admin_id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    existing = (
        supabase.table("admins")
        .select("id")
        .eq("id", admin_id)
        .eq("project_id", project_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Admin no encontrado")

    supabase.table("admins").delete().eq("id", admin_id).execute()
