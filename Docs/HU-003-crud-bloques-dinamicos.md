# HU-003: CRUD de Bloques Dinámicos

**Historia:** Como dueño de proyecto, quiero agregar, editar y eliminar bloques desde una interfaz simple para actualizar mi página sin tocar código.

---

## Contexto Técnico

- Cada bloque pertenece a un `project_id`
- El `project_id` del JWT debe coincidir con el `project_id` de la URL (aislamiento)
- `GET` es público; `POST` y `PUT` requieren `owner` o `editor`; `DELETE` requiere solo `owner`
- Los bloques tienen campo `order` (entero) y `visible` (booleano)

---

## Estructura de Archivos a Crear

```
blogs_backend/
└── app/
    └── blocks/
        ├── __init__.py
        ├── router.py       # Los 4 endpoints CRUD
        └── schemas.py      # BlockCreate, BlockUpdate, BlockResponse
```

---

## Implementación

### `app/blocks/schemas.py`

```python
from pydantic import BaseModel
from typing import Any
from uuid import UUID
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
    id: UUID
    project_id: UUID
    type: str
    content_json: dict[str, Any]
    order: int
    visible: bool
    created_at: datetime
```

### `app/blocks/router.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.blocks.schemas import BlockCreate, BlockUpdate, BlockResponse
from app.database import supabase
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/blocks", tags=["blocks"])

VALID_TYPES = {"text", "image", "card", "cta", "document"}

def _assert_project_ownership(user: dict, project_id: str):
    """Garantiza que el JWT pertenece al mismo proyecto del recurso."""
    if user["project_id"] != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

# --- GET público ---
@router.get("/{project_id}", response_model=list[BlockResponse])
def get_blocks(project_id: UUID):
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("project_id", str(project_id))
        .eq("visible", True)
        .order("order")
        .execute()
    )
    return result.data

# --- POST: owner o editor ---
@router.post("/{project_id}", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
def create_block(
    project_id: UUID,
    body: BlockCreate,
    user: dict = Depends(require_role("owner", "editor")),
):
    _assert_project_ownership(user, str(project_id))

    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.type}")

    data = {
        "project_id": str(project_id),
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
    project_id: UUID,
    block_id: UUID,
    body: BlockUpdate,
    user: dict = Depends(require_role("owner", "editor")),
):
    _assert_project_ownership(user, str(project_id))

    # Verificar que el bloque existe y pertenece al proyecto
    existing = (
        supabase.table("blocks")
        .select("id")
        .eq("id", str(block_id))
        .eq("project_id", str(project_id))
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
        .eq("id", str(block_id))
        .execute()
    )
    return result.data[0]

# --- DELETE: solo owner ---
@router.delete("/{project_id}/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(
    project_id: UUID,
    block_id: UUID,
    user: dict = Depends(require_role("owner")),
):
    _assert_project_ownership(user, str(project_id))

    existing = (
        supabase.table("blocks")
        .select("id")
        .eq("id", str(block_id))
        .eq("project_id", str(project_id))
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    supabase.table("blocks").delete().eq("id", str(block_id)).execute()
```

### Registrar en `app/main.py`

```python
from app.blocks.router import router as blocks_router
app.include_router(blocks_router)
```

---

## Tabla de Permisos por Endpoint

| Endpoint | Método | Rol requerido | Notas |
|---|---|---|---|
| `/blocks/{project_id}` | GET | Ninguno (público) | Solo retorna `visible=true` |
| `/blocks/{project_id}` | POST | `owner`, `editor` | JWT debe coincidir con project_id |
| `/blocks/{project_id}/{block_id}` | PUT | `owner`, `editor` | Verifica existencia del bloque |
| `/blocks/{project_id}/{block_id}` | DELETE | `owner` | Solo owner puede eliminar |

---

## Endpoint GET para Admin (con bloques no visibles)

El panel admin necesita ver todos los bloques (incluyendo `visible=false`) para poder gestionarlos. Agregar endpoint protegido adicional:

```python
@router.get("/{project_id}/admin/all", response_model=list[BlockResponse])
def get_all_blocks_admin(
    project_id: UUID,
    user: dict = Depends(require_role("owner", "editor", "viewer")),
):
    _assert_project_ownership(user, str(project_id))
    result = (
        supabase.table("blocks")
        .select("*")
        .eq("project_id", str(project_id))
        .order("order")
        .execute()
    )
    return result.data
```

---

## Criterios de Aceptación Técnicos

- [ ] `GET /blocks/{project_id}` retorna solo bloques `visible=true`, ordenados por `order`, sin auth
- [ ] `POST /blocks/{project_id}` con JWT de `owner` o `editor` crea bloque y retorna 201
- [ ] `POST` con JWT de `viewer` retorna 403
- [ ] `POST` con JWT de otro proyecto retorna 403
- [ ] `PUT /blocks/{project_id}/{block_id}` actualiza campos enviados (PATCH-like)
- [ ] `PUT` con `block_id` inexistente retorna 404
- [ ] `DELETE /blocks/{project_id}/{block_id}` con JWT `owner` elimina y retorna 204
- [ ] `DELETE` con JWT `editor` retorna 403
- [ ] `DELETE` con `block_id` inexistente retorna 404
- [ ] Tipo inválido en POST/PUT retorna 422

---

## Enfoque TDD

### `tests/test_blocks.py`

```python
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"
OTHER_PROJECT_ID = "proj-002"
BLOCK_ID = "block-uuid-001"

def auth(token): return {"Authorization": f"Bearer {token}"}

MOCK_BLOCK = {
    "id": BLOCK_ID,
    "project_id": PROJECT_ID,
    "type": "text",
    "content_json": {"body": "Hola"},
    "order": 1,
    "visible": True,
    "created_at": "2025-01-01T00:00:00",
}


# ============================================================
# GET público
# ============================================================

class TestGetBlocksPublic:

    def test_returns_only_visible_blocks(self, client):
        """GET público solo retorna bloques con visible=True."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])

            response = client.get(f"/blocks/{PROJECT_ID}")

        assert response.status_code == 200
        assert all(b["visible"] for b in response.json())

    def test_no_auth_required(self, client):
        """GET no requiere token."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/blocks/{PROJECT_ID}")
        assert response.status_code == 200


# ============================================================
# GET admin/all (protegido)
# ============================================================

class TestGetBlocksAdmin:

    def test_owner_sees_all_blocks(self, client, owner_token):
        """GET admin retorna bloques visibles e invisibles."""
        invisible = {**MOCK_BLOCK, "id": "block-002", "visible": False}
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK, invisible])

            response = client.get(
                f"/blocks/{PROJECT_ID}/admin/all",
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_no_token_returns_403(self, client):
        response = client.get(f"/blocks/{PROJECT_ID}/admin/all")
        assert response.status_code == 403


# ============================================================
# POST — crear bloque
# ============================================================

class TestCreateBlock:

    def test_owner_creates_block(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])

            response = client.post(
                f"/blocks/{PROJECT_ID}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(owner_token),
            )
        assert response.status_code == 201
        assert response.json()["type"] == "text"

    def test_editor_creates_block(self, client, editor_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])

            response = client.post(
                f"/blocks/{PROJECT_ID}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(editor_token),
            )
        assert response.status_code == 201

    def test_viewer_cannot_create(self, client, viewer_token):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede crear bloque en proj-002."""
        response = client.post(
            f"/blocks/{OTHER_PROJECT_ID}",
            json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_invalid_type_returns_422(self, client, owner_token):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={"type": "video", "content_json": {}, "order": 1},
            headers=auth(owner_token),
        )
        assert response.status_code == 422


# ============================================================
# PUT — editar bloque
# ============================================================

class TestUpdateBlock:

    def test_owner_updates_block(self, client, owner_token):
        updated = {**MOCK_BLOCK, "content_json": {"body": "Actualizado"}}
        with patch("app.blocks.router.supabase") as mock_db:
            # select para verificar existencia
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": BLOCK_ID}])
            # update
            mock_db.table.return_value.update.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[updated])

            response = client.put(
                f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
                json={"content_json": {"body": "Actualizado"}},
                headers=auth(owner_token),
            )
        assert response.status_code == 200

    def test_nonexistent_block_returns_404(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.put(
                f"/blocks/{PROJECT_ID}/nonexistent",
                json={"content_json": {"body": "X"}},
                headers=auth(owner_token),
            )
        assert response.status_code == 404

    def test_editor_can_update(self, client, editor_token):
        updated = {**MOCK_BLOCK, "visible": False}
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": BLOCK_ID}])
            mock_db.table.return_value.update.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[updated])

            response = client.put(
                f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
                json={"visible": False},
                headers=auth(editor_token),
            )
        assert response.status_code == 200

    def test_viewer_cannot_update(self, client, viewer_token):
        response = client.put(
            f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
            json={"visible": False},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403


# ============================================================
# DELETE — eliminar bloque
# ============================================================

class TestDeleteBlock:

    def test_owner_deletes_block(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": BLOCK_ID}])
            mock_db.table.return_value.delete.return_value.eq.return_value \
                .execute.return_value = MagicMock()

            response = client.delete(
                f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 204

    def test_editor_cannot_delete(self, client, editor_token):
        response = client.delete(
            f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_nonexistent_block_returns_404(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.delete(
                f"/blocks/{PROJECT_ID}/nonexistent",
                headers=auth(owner_token),
            )
        assert response.status_code == 404
```

### Flujo RED → GREEN → REFACTOR

```
RED:   test_viewer_cannot_create → falla si require_role no está en el endpoint
GREEN: Agregar Depends(require_role("owner", "editor")) al POST
RED:   test_cross_project_blocked → falla si no hay _assert_project_ownership
GREEN: Agregar llamada a _assert_project_ownership al inicio del POST
RED:   test_editor_cannot_delete → falla si DELETE usa mismo rol que POST
GREEN: Cambiar DELETE a Depends(require_role("owner"))
RED:   test_nonexistent_block_returns_404 → falla si no se verifica existencia antes de actualizar
GREEN: Agregar query de existencia antes del update/delete
REFACTOR: Extraer _assert_project_ownership a dependencies.py (evitar duplicar en cada router)
```

---

## Buenas Prácticas de Código

### Anotaciones de tipo
- Todos los parámetros de funciones llevan anotación explícita de tipo
- Todas las funciones incluyen anotación de retorno (`-> ReturnType` o `-> None`)
- `dict` genérico se escribe como `dict[str, Any]`; importar `Any` de `typing`
- Funciones helper internas (e.g. `_assert_project_ownership`) retornan `-> None` explícitamente

### Docstrings
- Todas las clases Pydantic (`BlockCreate`, `BlockUpdate`, `BlockResponse`) tienen docstring describiendo propósito y campos clave
- Todos los endpoints tienen docstring describiendo: comportamiento, rol requerido y errores posibles (403, 404, 422)
- Funciones helper tienen docstring indicando su efecto (ej. qué excepción lanza y cuándo)
- Estilo: una línea para lógica evidente; multilinea con `Args:` y `Returns:` cuando hay lógica no trivial

---

## Dependencias

- HU-001 completada (tabla `blocks`)
- HU-002 completada (`dependencies.py` con `get_current_user` y `require_role`)
