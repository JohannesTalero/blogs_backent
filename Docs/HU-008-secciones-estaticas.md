# HU-008: Secciones Estáticas Editables desde el Panel Admin

**Historia:** Como dueño de proyecto, quiero editar las secciones estáticas de mi página (perfil, toolkit, recomendaciones, contacto) desde el panel admin sin tocar código.

---

## Contexto Técnico

- Las secciones son fijas: `perfil`, `toolkit`, `recomendaciones`, `contacto`
- Una sola fila por tipo por proyecto (constraint UNIQUE en DB)
- `GET` es público, `PUT` requiere `owner` o `editor`
- No se crean ni eliminan secciones vía API: existen desde el seed
- **SEC-007:** Límites de longitud en campos de texto
- **SEC-008:** Campos de URL opcionales validados con `Optional[HttpUrl]` — rechaza `javascript:` y URLs malformadas

---

## Estructura de Archivos a Crear

```
blogs_backend/
├── app/
│   └── sections/
│       ├── __init__.py
│       ├── router.py
│       ├── schemas.py
│       └── validator.py
└── tests/
    └── test_sections.py
```

---

## Implementación

### `app/sections/schemas.py`

```python
from pydantic import BaseModel
from typing import Any
from uuid import UUID

class SectionResponse(BaseModel):
    id: UUID
    project_id: UUID
    type: str
    content_json: dict[str, Any]
```

### `app/sections/validator.py`

```python
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional
from fastapi import HTTPException

class PerfilContent(BaseModel):
    name: str = ""
    bio: str = ""
    photo_url: Optional[HttpUrl] = None   # SEC-008: URL opcional validada

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v: str) -> str:
        if len(v) > 1_000:                # SEC-007
            raise ValueError("La bio no puede superar 1.000 caracteres")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El nombre no puede superar 200 caracteres")
        return v


class ToolkitContent(BaseModel):
    tools: list[str] = []

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: list[str]) -> list[str]:
        if len(v) > 50:                   # SEC-007: máximo 50 herramientas
            raise ValueError("La lista de herramientas no puede superar 50 elementos")
        for tool in v:
            if len(tool) > 100:
                raise ValueError(f"Nombre de herramienta demasiado largo: '{tool[:20]}...'")
        return v


class RecomendacionItem(BaseModel):
    title: str
    link: Optional[HttpUrl] = None        # SEC-008: URL opcional validada

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El título no puede superar 200 caracteres")
        return v


class RecomendacionesContent(BaseModel):
    items: list[RecomendacionItem] = []

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: list[RecomendacionItem]) -> list[RecomendacionItem]:
        if len(v) > 100:                  # SEC-007: máximo 100 recomendaciones
            raise ValueError("No se pueden tener más de 100 recomendaciones")
        return v


class ContactoContent(BaseModel):
    email: str = ""
    linkedin: Optional[HttpUrl] = None    # SEC-008: URL social validada
    twitter: Optional[HttpUrl] = None     # SEC-008: URL social validada

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El email no puede superar 200 caracteres")
        return v


SECTION_VALIDATORS = {
    "perfil": PerfilContent,
    "toolkit": ToolkitContent,
    "recomendaciones": RecomendacionesContent,
    "contacto": ContactoContent,
}

VALID_SECTION_TYPES = set(SECTION_VALIDATORS.keys())


def validate_section_content(section_type: str, content_json: dict) -> dict:
    validator_class = SECTION_VALIDATORS.get(section_type)
    if not validator_class:
        raise HTTPException(status_code=422, detail=f"Tipo de sección inválido: {section_type}")
    try:
        validated = validator_class(**content_json)
        # mode="json" serializa HttpUrl → str antes de guardar en Supabase
        return validated.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"content_json inválido para sección '{section_type}': {str(e)}"
        )
```

### `app/sections/router.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
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
        raise HTTPException(status_code=403, detail="Acceso denegado")

@router.get("/{project_id}", response_model=list[SectionResponse])
def get_sections(project_id: UUID):
    result = (
        supabase.table("sections")
        .select("*")
        .eq("project_id", str(project_id))
        .execute()
    )
    return result.data

@router.put("/{project_id}/{section_type}", response_model=SectionResponse)
def update_section(
    project_id: UUID,
    section_type: str,
    body: SectionUpdate,
    user: dict = Depends(require_role("owner", "editor")),
):
    _assert_project_ownership(user, str(project_id))

    if section_type not in VALID_SECTION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido: '{section_type}'. Válidos: {sorted(VALID_SECTION_TYPES)}"
        )

    validated_content = validate_section_content(section_type, body.content_json)

    existing = (
        supabase.table("sections")
        .select("id")
        .eq("project_id", str(project_id))
        .eq("type", section_type)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Sección no encontrada. Ejecutar seed primero.")

    result = (
        supabase.table("sections")
        .update({"content_json": validated_content, "updated_at": "now()"})
        .eq("project_id", str(project_id))
        .eq("type", section_type)
        .execute()
    )
    return result.data[0]
```

---

## Ejemplos de Payloads

### `perfil` — con `photo_url` opcional
```json
{ "content_json": { "name": "Johannes", "bio": "Desarrollador.", "photo_url": "https://cdn.example.com/foto.jpg" } }
{ "content_json": { "name": "Johannes", "bio": "Sin foto." } }
```

### `toolkit`
```json
{ "content_json": { "tools": ["Python", "FastAPI", "React"] } }
```

### `recomendaciones` — link opcional por item
```json
{
  "content_json": {
    "items": [
      { "title": "FastAPI Docs", "link": "https://fastapi.tiangolo.com" },
      { "title": "Sin link" }
    ]
  }
}
```

### `contacto` — redes sociales opcionales
```json
{ "content_json": { "email": "yo@ejemplo.com", "linkedin": "https://linkedin.com/in/yo" } }
```

---

## Enfoque TDD

### `tests/test_sections.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from app.sections.validator import validate_section_content
from fastapi import HTTPException

PROJECT_ID = "proj-001"
OTHER_PROJECT_ID = "proj-002"

def auth(token): return {"Authorization": f"Bearer {token}"}


# ============================================================
# Validador unitario
# ============================================================

class TestSectionValidator:

    # perfil
    def test_valid_perfil(self):
        result = validate_section_content("perfil", {
            "name": "Johannes", "bio": "Bio.", "photo_url": "https://cdn.example.com/foto.jpg"
        })
        assert result["name"] == "Johannes"
        assert isinstance(result["photo_url"], str)  # HttpUrl serializado como str

    def test_perfil_without_photo_url(self):
        result = validate_section_content("perfil", {"name": "Jo", "bio": "Bio."})
        assert result["photo_url"] is None

    def test_perfil_javascript_photo_url_rejected(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_section_content("perfil", {"photo_url": "javascript:evil()"})

    def test_perfil_bio_too_long(self):
        # SEC-007
        with pytest.raises(HTTPException):
            validate_section_content("perfil", {"bio": "x" * 1_001})

    # toolkit
    def test_valid_toolkit(self):
        result = validate_section_content("toolkit", {"tools": ["Python", "React"]})
        assert "Python" in result["tools"]

    def test_toolkit_too_many_tools(self):
        # SEC-007: máximo 50
        with pytest.raises(HTTPException):
            validate_section_content("toolkit", {"tools": [f"tool{i}" for i in range(51)]})

    def test_toolkit_tool_name_too_long(self):
        with pytest.raises(HTTPException):
            validate_section_content("toolkit", {"tools": ["x" * 101]})

    # recomendaciones
    def test_valid_recomendacion_with_link(self):
        result = validate_section_content("recomendaciones", {
            "items": [{"title": "FastAPI", "link": "https://fastapi.tiangolo.com"}]
        })
        assert len(result["items"]) == 1

    def test_recomendacion_without_link(self):
        result = validate_section_content("recomendaciones", {
            "items": [{"title": "Sin link"}]
        })
        assert result["items"][0]["link"] is None

    def test_recomendacion_javascript_link_rejected(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_section_content("recomendaciones", {
                "items": [{"title": "Click", "link": "javascript:evil()"}]
            })

    def test_too_many_recomendaciones(self):
        # SEC-007: máximo 100
        with pytest.raises(HTTPException):
            validate_section_content("recomendaciones", {
                "items": [{"title": f"Item {i}"} for i in range(101)]
            })

    # contacto
    def test_valid_contacto(self):
        result = validate_section_content("contacto", {
            "email": "yo@ejemplo.com",
            "linkedin": "https://linkedin.com/in/yo",
            "twitter": "https://twitter.com/yo",
        })
        assert result["email"] == "yo@ejemplo.com"

    def test_contacto_without_social_links(self):
        result = validate_section_content("contacto", {"email": "yo@ejemplo.com"})
        assert result["linkedin"] is None
        assert result["twitter"] is None

    def test_contacto_javascript_linkedin_rejected(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_section_content("contacto", {
                "email": "yo@ejemplo.com",
                "linkedin": "javascript:alert(1)",
            })

    def test_invalid_section_type(self):
        with pytest.raises(HTTPException) as exc:
            validate_section_content("about", {})
        assert exc.value.status_code == 422


# ============================================================
# Endpoint: GET /sections/{project_id}
# ============================================================

class TestGetSections:

    def test_get_sections_public_no_auth(self, client):
        """GET es público, no requiere token."""
        sections_data = [
            {"id": "s1", "project_id": PROJECT_ID, "type": "perfil", "content_json": {"name": "Jo"}},
        ]
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=sections_data)

            response = client.get(f"/sections/{PROJECT_ID}")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_sections_returns_all_four(self, client):
        """GET retorna las 4 secciones."""
        sections_data = [
            {"id": f"s{i}", "project_id": PROJECT_ID, "type": t, "content_json": {}}
            for i, t in enumerate(["perfil", "toolkit", "recomendaciones", "contacto"])
        ]
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=sections_data)

            response = client.get(f"/sections/{PROJECT_ID}")

        assert len(response.json()) == 4


# ============================================================
# Endpoint: PUT /sections/{project_id}/{type}
# ============================================================

class TestUpdateSection:

    def _mock_existing_and_update(self, mock_db, updated_data):
        # select para verificar existencia
        mock_db.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[{"id": "s1"}])
        # update
        mock_db.table.return_value.update.return_value.eq.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[updated_data])

    def test_owner_can_update_perfil(self, client, owner_token):
        updated = {
            "id": "s1", "project_id": PROJECT_ID, "type": "perfil",
            "content_json": {"name": "Johannes", "bio": "Dev.", "photo_url": None},
        }
        with patch("app.sections.router.supabase") as mock_db:
            self._mock_existing_and_update(mock_db, updated)
            response = client.put(
                f"/sections/{PROJECT_ID}/perfil",
                json={"content_json": {"name": "Johannes", "bio": "Dev."}},
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert response.json()["content_json"]["name"] == "Johannes"

    def test_editor_can_update_toolkit(self, client, editor_token):
        updated = {
            "id": "s2", "project_id": PROJECT_ID, "type": "toolkit",
            "content_json": {"tools": ["Python"]},
        }
        with patch("app.sections.router.supabase") as mock_db:
            self._mock_existing_and_update(mock_db, updated)
            response = client.put(
                f"/sections/{PROJECT_ID}/toolkit",
                json={"content_json": {"tools": ["Python"]}},
                headers=auth(editor_token),
            )
        assert response.status_code == 200

    def test_viewer_cannot_update(self, client, viewer_token):
        response = client.put(
            f"/sections/{PROJECT_ID}/perfil",
            json={"content_json": {"name": "x"}},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_invalid_section_type_returns_422(self, client, owner_token):
        response = client.put(
            f"/sections/{PROJECT_ID}/about",
            json={"content_json": {}},
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede modificar secciones de proj-002."""
        response = client.put(
            f"/sections/{OTHER_PROJECT_ID}/perfil",
            json={"content_json": {"name": "Hacker"}},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_javascript_url_in_photo_rejected(self, client, owner_token):
        """SEC-008: photo_url con javascript: es rechazada."""
        response = client.put(
            f"/sections/{PROJECT_ID}/perfil",
            json={"content_json": {"photo_url": "javascript:alert(1)"}},
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_bio_too_long_rejected(self, client, owner_token):
        """SEC-007: bio mayor a 1000 chars es rechazada."""
        response = client.put(
            f"/sections/{PROJECT_ID}/perfil",
            json={"content_json": {"bio": "x" * 1_001}},
            headers=auth(owner_token),
        )
        assert response.status_code == 422
```

### Flujo RED → GREEN → REFACTOR

```
RED:   test_perfil_javascript_photo_url_rejected → falla porque photo_url es str
GREEN: Cambiar photo_url: str = "" → photo_url: Optional[HttpUrl] = None
RED:   test_perfil_bio_too_long → falla sin validador de longitud
GREEN: Agregar field_validator("bio") con len check
RED:   test_contacto_javascript_linkedin_rejected → falla porque linkedin es str
GREEN: Cambiar linkedin: str = "" → linkedin: Optional[HttpUrl] = None
RED:   test_too_many_recomendaciones → falla sin validador de lista
GREEN: Agregar field_validator("items") con len check
REFACTOR: Agrupar constantes de límites en un dict SECTION_LIMITS para mantenibilidad
```

---

## Criterios de Aceptación Técnicos

- [ ] `GET /sections/{project_id}` retorna 200 sin auth
- [ ] `PUT /sections/{project_id}/perfil` con JWT `owner` actualiza correctamente
- [ ] `PUT /sections/{project_id}/toolkit` con JWT `editor` actualiza correctamente
- [ ] `PUT` con JWT `viewer` retorna 403
- [ ] `PUT` con tipo `about` retorna 422
- [ ] `PUT` de otro proyecto retorna 403
- [ ] `photo_url` con `javascript:` retorna 422
- [ ] `linkedin` con `javascript:` retorna 422
- [ ] `bio` de más de 1.000 chars retorna 422
- [ ] Lista de `tools` con más de 50 elementos retorna 422
- [ ] Lista de `items` con más de 100 elementos retorna 422
- [ ] URLs opcionales con valor `null` se aceptan y almacenan como `null`
- [ ] `model_dump(mode="json")` convierte `HttpUrl` a string antes de guardar en DB

---

## Buenas Prácticas de Código

### Anotaciones de tipo
- Todos los parámetros y retornos de funciones llevan anotación explícita
- `content_json` en `validate_section_content` se anota como `dict[str, Any]`, no `dict` genérico
- `validate_section_content` retorna `dict[str, Any]`; importar `Any` de `typing`
- `field_validator` siempre anota parámetro y retorno; listas se anotan como `list[str]` o `list[RecomendacionItem]`
- `_assert_project_ownership` retorna `-> None` explícitamente

### Docstrings
- Cada clase de sección (`PerfilContent`, `ToolkitContent`, etc.) tiene docstring describiendo sus campos y restricciones (SEC-007, SEC-008)
- `SectionUpdate` y `SectionResponse` tienen docstring en el nivel de clase
- Todos los endpoints tienen docstring con rol requerido y errores posibles
- Estilo: una línea para lógica evidente; multilinea con `Args:` y `Returns:` cuando hay lógica no trivial

---

## Dependencias

- HU-001 (tabla `sections` con seed inicial)
- HU-002 (`require_role` en `dependencies.py`)
