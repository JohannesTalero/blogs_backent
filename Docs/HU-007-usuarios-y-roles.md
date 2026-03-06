# HU-007: Múltiples Usuarios con Roles por Proyecto

**Historia:** Como owner, quiero invitar a otros usuarios con roles específicos para que me ayuden a gestionar el contenido sin darles acceso total.

---

## Contexto Técnico

- Los 3 roles son: `owner`, `editor`, `viewer`
- Solo el `owner` puede crear nuevos admins en su proyecto
- La validación de roles es responsabilidad de FastAPI
- No existe flujo de "invitación por email" en el MVP
- No hay endpoint de cambio de password en el MVP
- **SEC-009:** Validación de fortaleza de password al crear admins (mínimo 8 chars, letras + números)

---

## Matriz de Permisos Completa

| Operación | owner | editor | viewer |
|---|:---:|:---:|:---:|
| GET bloques (admin, con no-visibles) | SI | SI | SI |
| POST bloque | SI | SI | NO |
| PUT bloque | SI | SI | NO |
| DELETE bloque | SI | NO | NO |
| GET secciones (admin) | SI | SI | SI |
| PUT sección | SI | SI | NO |
| GET lista admins | SI | NO | NO |
| POST admin (invitar) | SI | NO | NO |
| DELETE admin | SI | NO | NO |

---

## Estructura de Archivos a Crear

```
blogs_backend/
├── app/
│   └── admins/
│       ├── __init__.py
│       ├── router.py
│       └── schemas.py
└── tests/
    └── test_admins.py
```

---

## Implementación

### `app/admins/schemas.py`

```python
import re
from pydantic import BaseModel, EmailStr, field_validator
from uuid import UUID
from datetime import datetime

class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    role: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # SEC-009: fortaleza mínima
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r'[A-Za-z]', v):
            raise ValueError("La contraseña debe contener al menos una letra")
        if not re.search(r'[0-9]', v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

class AdminResponse(BaseModel):
    id: UUID
    project_id: UUID
    email: str
    role: str
    created_at: datetime
```

### `app/admins/router.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from passlib.context import CryptContext
from app.admins.schemas import AdminCreate, AdminResponse
from app.database import supabase
from app.dependencies import require_role

router = APIRouter(prefix="/admins", tags=["admins"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_ROLES = {"editor", "viewer"}

def _assert_project_ownership(user: dict, project_id: str):
    if user["project_id"] != project_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

@router.get("/{project_id}", response_model=list[AdminResponse])
def list_admins(
    project_id: UUID,
    user: dict = Depends(require_role("owner")),
):
    _assert_project_ownership(user, str(project_id))
    result = (
        supabase.table("admins")
        .select("id, project_id, email, role, created_at")
        .eq("project_id", str(project_id))
        .execute()
    )
    return result.data

@router.post("/{project_id}", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    project_id: UUID,
    body: AdminCreate,
    user: dict = Depends(require_role("owner")),
):
    _assert_project_ownership(user, str(project_id))

    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Rol inválido: '{body.role}'. Permitidos: {sorted(VALID_ROLES)}"
        )

    existing = (
        supabase.table("admins")
        .select("id")
        .eq("project_id", str(project_id))
        .eq("email", body.email)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Ya existe un admin con ese email en este proyecto")

    hashed = pwd_context.hash(body.password)
    data = {
        "project_id": str(project_id),
        "email": body.email,
        "hashed_password": hashed,
        "role": body.role,
    }
    result = supabase.table("admins").insert(data).execute()
    return result.data[0]

@router.delete("/{project_id}/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    project_id: UUID,
    admin_id: UUID,
    user: dict = Depends(require_role("owner")),
):
    _assert_project_ownership(user, str(project_id))

    if user["sub"] == str(admin_id):
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    existing = (
        supabase.table("admins")
        .select("id")
        .eq("id", str(admin_id))
        .eq("project_id", str(project_id))
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Admin no encontrado")

    supabase.table("admins").delete().eq("id", str(admin_id)).execute()
```

### Registrar en `app/main.py`

```python
from app.admins.router import router as admins_router
app.include_router(admins_router)
```

---

## Enfoque TDD

### `tests/test_admins.py`

```python
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"
OTHER_PROJECT_ID = "proj-002"
ADMIN_ID = "admin-to-delete-uuid"

def auth(token): return {"Authorization": f"Bearer {token}"}


# ============================================================
# Password strength (SEC-009) — tests unitarios del schema
# ============================================================

class TestAdminCreatePasswordValidation:

    def test_rejects_short_password(self):
        from pydantic import ValidationError
        from app.admins.schemas import AdminCreate
        with pytest.raises(ValidationError, match="8 caracteres"):
            AdminCreate(email="a@b.com", password="Ab1", role="editor")

    def test_rejects_password_without_letters(self):
        from pydantic import ValidationError
        from app.admins.schemas import AdminCreate
        with pytest.raises(ValidationError, match="letra"):
            AdminCreate(email="a@b.com", password="12345678", role="editor")

    def test_rejects_password_without_numbers(self):
        from pydantic import ValidationError
        from app.admins.schemas import AdminCreate
        with pytest.raises(ValidationError, match="número"):
            AdminCreate(email="a@b.com", password="abcdefgh", role="editor")

    def test_accepts_valid_password(self):
        from app.admins.schemas import AdminCreate
        admin = AdminCreate(email="a@b.com", password="Password1", role="editor")
        assert admin.password == "Password1"


# ============================================================
# Endpoint: POST /admins/{project_id}
# ============================================================

class TestCreateAdmin:

    def test_owner_can_create_editor(self, client, owner_token):
        new_admin = {
            "id": "new-uuid",
            "project_id": PROJECT_ID,
            "email": "editor@test.com",
            "role": "editor",
            "created_at": "2025-01-01T00:00:00",
        }
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[new_admin])

            response = client.post(
                f"/admins/{PROJECT_ID}",
                json={"email": "editor@test.com", "password": "SecurePass1", "role": "editor"},
                headers=auth(owner_token),
            )

        assert response.status_code == 201
        body = response.json()
        assert body["role"] == "editor"
        assert "hashed_password" not in body  # nunca en la respuesta

    def test_editor_cannot_create_admin(self, client, editor_token):
        """editor no puede invitar nuevos admins."""
        response = client.post(
            f"/admins/{PROJECT_ID}",
            json={"email": "x@x.com", "password": "SecurePass1", "role": "viewer"},
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_owner_role_rejected_in_body(self, client, owner_token):
        """No se puede crear un admin con rol owner via API."""
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.post(
                f"/admins/{PROJECT_ID}",
                json={"email": "x@x.com", "password": "SecurePass1", "role": "owner"},
                headers=auth(owner_token),
            )
        assert response.status_code == 422

    def test_weak_password_rejected(self, client, owner_token):
        """SEC-009: password débil retorna 422."""
        response = client.post(
            f"/admins/{PROJECT_ID}",
            json={"email": "x@x.com", "password": "abc", "role": "editor"},
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_duplicate_email_returns_409(self, client, owner_token):
        with patch("app.admins.router.supabase") as mock_db:
            # email ya existe
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": "existing"}])

            response = client.post(
                f"/admins/{PROJECT_ID}",
                json={"email": "dupe@test.com", "password": "SecurePass1", "role": "editor"},
                headers=auth(owner_token),
            )
        assert response.status_code == 409

    def test_cross_project_access_denied(self, client, owner_token):
        """JWT de proj-001 no puede crear admin en proj-002."""
        response = client.post(
            f"/admins/{OTHER_PROJECT_ID}",
            json={"email": "x@x.com", "password": "SecurePass1", "role": "editor"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Endpoint: DELETE /admins/{project_id}/{admin_id}
# ============================================================

class TestDeleteAdmin:

    def test_owner_can_delete_other_admin(self, client, owner_token):
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": ADMIN_ID}])
            mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value \
                = MagicMock()

            response = client.delete(
                f"/admins/{PROJECT_ID}/{ADMIN_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 204

    def test_owner_cannot_delete_self(self, client):
        """El owner no puede eliminarse a sí mismo."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from app.config import settings

        # Token donde sub == el admin_id de la URL
        self_id = "owner-self-uuid"
        token = pyjwt.encode(
            {"sub": self_id, "project_id": PROJECT_ID, "role": "owner",
             "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            settings.jwt_secret, algorithm=settings.jwt_algorithm,
        )
        response = client.delete(
            f"/admins/{PROJECT_ID}/{self_id}",
            headers=auth(token),
        )
        assert response.status_code == 400

    def test_editor_cannot_delete_admin(self, client, editor_token):
        response = client.delete(
            f"/admins/{PROJECT_ID}/{ADMIN_ID}",
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_delete_nonexistent_admin_returns_404(self, client, owner_token):
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.delete(
                f"/admins/{PROJECT_ID}/nonexistent-uuid",
                headers=auth(owner_token),
            )
        assert response.status_code == 404


# ============================================================
# Endpoint: GET /admins/{project_id}
# ============================================================

class TestListAdmins:

    def test_owner_can_list_admins(self, client, owner_token):
        admins_data = [
            {"id": "a1", "project_id": PROJECT_ID, "email": "a@b.com", "role": "owner", "created_at": "2025-01-01T00:00:00"},
        ]
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=admins_data)

            response = client.get(f"/admins/{PROJECT_ID}", headers=auth(owner_token))

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_editor_cannot_list_admins(self, client, editor_token):
        response = client.get(f"/admins/{PROJECT_ID}", headers=auth(editor_token))
        assert response.status_code == 403
```

### Flujo RED → GREEN → REFACTOR

```
RED:   test_weak_password_rejected → falla porque AdminCreate.password es str sin validación
GREEN: Agregar field_validator("password") con checks de longitud y composición
RED:   test_owner_role_rejected_in_body → falla si VALID_ROLES no lo excluye
GREEN: Verificar que VALID_ROLES = {"editor", "viewer"} (ya correcto)
RED:   test_cross_project_access_denied → falla si no hay _assert_project_ownership
GREEN: Agregar _assert_project_ownership al inicio de cada endpoint
REFACTOR: Mover _assert_project_ownership a dependencies.py para reutilizar entre routers
```

---

## Criterios de Aceptación Técnicos

- [ ] `POST` con password menor a 8 chars retorna 422
- [ ] `POST` con password solo números retorna 422
- [ ] `POST` con password solo letras retorna 422
- [ ] `POST /admins/{project_id}` con JWT `owner` crea admin con rol `editor` o `viewer`
- [ ] `POST` con JWT `editor` retorna 403
- [ ] `POST` con rol `owner` en body retorna 422
- [ ] `POST` con email duplicado retorna 409
- [ ] `GET` con JWT `owner` lista admins sin `hashed_password`
- [ ] `GET` con JWT `editor` retorna 403
- [ ] `DELETE` con JWT `owner` elimina admin y retorna 204
- [ ] `DELETE` del propio owner retorna 400
- [ ] `DELETE` con JWT `editor` retorna 403
- [ ] `DELETE` de admin inexistente retorna 404
- [ ] Operación de otro proyecto con JWT válido retorna 403

---

## Dependencias

- HU-001 (tabla `admins`)
- HU-002 (`require_role` en `dependencies.py`)
