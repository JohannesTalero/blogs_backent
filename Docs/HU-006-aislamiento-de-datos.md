# HU-006: Aislamiento de Datos entre Proyectos

**Historia:** Como desarrollador, necesito garantizar que cada proyecto solo pueda ver y modificar sus propios datos.

---

## Contexto Técnico

El aislamiento se implementa en **dos capas complementarias**:

1. **Capa de aplicación (FastAPI):** El `project_id` del JWT se compara con el `project_id` de la URL en cada endpoint protegido. Si no coinciden → 403.
2. **Capa de base de datos (Supabase):** Todos los queries de FastAPI filtran por `project_id` explícitamente. El cliente usa `service_role` key, pero nunca retorna datos de otro proyecto porque los queries siempre incluyen `.eq("project_id", ...)`.

> La `service_role` key bypassa RLS, pero el código de FastAPI actúa como la primera línea de defensa. RLS podría activarse con políticas más estrictas en el futuro, pero para el MVP la validación en FastAPI es suficiente y más controlable.

---

## Mecanismo de Aislamiento

### En cada endpoint protegido

La función `_assert_project_ownership` ya definida en HU-003 hace la validación:

```python
def _assert_project_ownership(user: dict, project_id: str):
    if user["project_id"] != project_id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
```

Esta función se llama al inicio de cada endpoint protegido antes de tocar la DB.

### En queries públicos

Los endpoints públicos (`GET /blocks/{project_id}`, `GET /sections/{project_id}`) filtran siempre por `project_id` de la URL:

```python
supabase.table("blocks").select("*").eq("project_id", str(project_id)).execute()
```

Un visitante que conoce el `project_id` de otro proyecto puede leer sus datos públicos (bloques visibles, secciones). Esto es intencional: la información pública de cada proyecto es, por definición, pública.

---

## Archivos a Crear/Modificar

```
blogs_backend/
└── app/
    └── dependencies.py   # Ya existe desde HU-002, sin cambios adicionales
```

No se requieren nuevos archivos. El aislamiento es transversal y se aplica en cada router.

---

## Checklist de Implementación

Verificar que **todos los routers** protegidos llaman a `_assert_project_ownership`:

- [ ] `app/blocks/router.py` → POST, PUT, DELETE
- [ ] `app/sections/router.py` → PUT
- [ ] `app/admins/router.py` → POST, GET (lista admins del proyecto)

---

## Test Manual de Aislamiento

### Setup necesario

Crear un segundo proyecto en DB para las pruebas:

```sql
INSERT INTO projects (id, name, slug) VALUES
    ('00000000-0000-0000-0000-000000000002', 'Proyecto B', 'proyecto-b');

INSERT INTO admins (project_id, email, hashed_password, role) VALUES
    ('00000000-0000-0000-0000-000000000002', 'admin@proyectob.com', '<hash>', 'owner');

INSERT INTO blocks (project_id, type, content_json, "order") VALUES
    ('00000000-0000-0000-0000-000000000002', 'text', '{"body": "Datos privados de B"}', 1);
```

### Escenarios de prueba

```bash
# 1. Obtener JWT de Proyecto A
TOKEN_A=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@johannesta.com", "password": "..."}' | jq -r .access_token)

PROJECT_A_ID="00000000-0000-0000-0000-000000000001"
PROJECT_B_ID="00000000-0000-0000-0000-000000000002"

# 2. Intentar crear bloque en Proyecto B con JWT de A → debe retornar 403
curl -X POST http://localhost:8000/blocks/$PROJECT_B_ID \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"type": "text", "content_json": {"body": "Intrusión"}, "order": 1}'
# Esperado: 403 Forbidden

# 3. Intentar eliminar bloque de Proyecto B con JWT de A → debe retornar 403
BLOCK_B_ID="<uuid-de-bloque-de-B>"
curl -X DELETE http://localhost:8000/blocks/$PROJECT_B_ID/$BLOCK_B_ID \
  -H "Authorization: Bearer $TOKEN_A"
# Esperado: 403 Forbidden

# 4. Intentar editar sección de Proyecto B con JWT de A → debe retornar 403
curl -X PUT http://localhost:8000/sections/$PROJECT_B_ID/perfil \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"name": "Hacker"}'
# Esperado: 403 Forbidden
```

---

## Criterios de Aceptación Técnicos

- [ ] JWT de proyecto A con `POST /blocks/{project_B_id}` retorna 403
- [ ] JWT de proyecto A con `PUT /blocks/{project_B_id}/{block_id}` retorna 403
- [ ] JWT de proyecto A con `DELETE /blocks/{project_B_id}/{block_id}` retorna 403
- [ ] JWT de proyecto A con `PUT /sections/{project_B_id}/{type}` retorna 403
- [ ] JWT de proyecto A con `POST /admins/{project_B_id}` retorna 403
- [ ] `GET /blocks/{project_B_id}` (público) retorna solo bloques visibles de proyecto B (comportamiento correcto e intencional)
- [ ] No existe endpoint que retorne datos mezclados de múltiples proyectos

---

## Enfoque TDD

Los tests de aislamiento son **tests de integración transversales**: verifican que ningún router permite acceso entre proyectos. Se ejecutan con dos tokens de proyectos distintos.

### `tests/test_isolation.py`

```python
import pytest
from unittest.mock import patch, MagicMock

PROJECT_A = "proj-001"
PROJECT_B = "proj-002"
BLOCK_B_ID = "block-in-proj-b"

def auth(token): return {"Authorization": f"Bearer {token}"}


# ============================================================
# Aislamiento en Bloques
# ============================================================

class TestBlocksIsolation:

    def test_cannot_create_block_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede crear bloque en proj-002."""
        response = client.post(
            f"/blocks/{PROJECT_B}",
            json={"type": "text", "content_json": {"body": "Intrusión"}, "order": 1},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_cannot_update_block_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede editar bloque de proj-002."""
        response = client.put(
            f"/blocks/{PROJECT_B}/{BLOCK_B_ID}",
            json={"visible": False},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_cannot_delete_block_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede eliminar bloque de proj-002."""
        response = client.delete(
            f"/blocks/{PROJECT_B}/{BLOCK_B_ID}",
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_cannot_see_hidden_blocks_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede ver bloques privados de proj-002."""
        response = client.get(
            f"/blocks/{PROJECT_B}/admin/all",
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Aislamiento en Secciones
# ============================================================

class TestSectionsIsolation:

    def test_cannot_update_section_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede editar sección de proj-002."""
        response = client.put(
            f"/sections/{PROJECT_B}/perfil",
            json={"content_json": {"name": "Hacker"}},
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Aislamiento en Admins
# ============================================================

class TestAdminsIsolation:

    def test_cannot_list_admins_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede listar admins de proj-002."""
        response = client.get(f"/admins/{PROJECT_B}", headers=auth(owner_token))
        assert response.status_code == 403

    def test_cannot_create_admin_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede crear admin en proj-002."""
        response = client.post(
            f"/admins/{PROJECT_B}",
            json={"email": "x@x.com", "password": "SecurePass1", "role": "editor"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_cannot_delete_admin_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede eliminar admin de proj-002."""
        response = client.delete(
            f"/admins/{PROJECT_B}/some-admin-uuid",
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Que SÍ es accesible (datos públicos de cualquier proyecto)
# ============================================================

class TestPublicDataIsAccessible:

    def test_public_blocks_of_any_project_are_readable(self, client):
        """GET /blocks es público para cualquier project_id — intencional."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/blocks/{PROJECT_B}")
        assert response.status_code == 200

    def test_public_sections_of_any_project_are_readable(self, client):
        """GET /sections es público para cualquier project_id — intencional."""
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[])
            response = client.get(f"/sections/{PROJECT_B}")
        assert response.status_code == 200
```

### Flujo RED → GREEN → REFACTOR

```
RED:   test_cannot_create_block_in_other_project → falla si _assert_project_ownership no existe
GREEN: Agregar _assert_project_ownership en POST /blocks (HU-003)
RED:   test_cannot_update_section_in_other_project → falla en PUT /sections
GREEN: Agregar _assert_project_ownership en PUT /sections (HU-008)
RED:   test_cannot_list_admins_of_other_project → falla en GET /admins
GREEN: Agregar _assert_project_ownership en GET /admins (HU-007)
REFACTOR: Centralizar _assert_project_ownership en dependencies.py como función reutilizable
          en lugar de duplicarla en cada router
```

> **Nota sobre la refactorización:** La función `_assert_project_ownership` aparece en `blocks/router.py`, `sections/router.py` y `admins/router.py`. El paso de refactoring la mueve a `dependencies.py` como función pura importable, eliminando la duplicación.

---

## Dependencias

- HU-002 (JWT con `project_id` en payload)
- HU-003 (bloques con `_assert_project_ownership`)
- HU-007 (admins con `_assert_project_ownership`)
- HU-008 (secciones con `_assert_project_ownership`)
