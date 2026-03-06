# HU-004: Soporte para 5 Tipos de Bloques

**Historia:** Como dueño de proyecto, quiero crear diferentes tipos de bloques según el contenido que quiero mostrar.

---

## Contexto Técnico

Cada tipo de bloque tiene un `content_json` con estructura diferente. La validación ocurre en FastAPI con Pydantic. El almacenamiento en DB es JSONB genérico; la validación es solo en la capa de API.

Cambios de seguridad aplicados en esta HU:
- **SEC-005:** `TextContent.body` rechaza HTML/scripts (XSS almacenado)
- **SEC-007:** Límites de longitud en campos de texto
- **SEC-008:** Campos de URL validados con `HttpUrl` de Pydantic (rechaza `javascript:`, `file://`, etc.)

---

## Los 5 Tipos y su `content_json`

| Tipo | Campos requeridos | Opcionales |
|---|---|---|
| `text` | `body` (markdown, max 50k chars) | — |
| `image` | `url` (HttpUrl) | `alt` (str, max 200 chars) |
| `card` | `title` (max 200), `text` (max 1000) | `link` (HttpUrl \| None) |
| `cta` | `label` (max 100), `url` (HttpUrl) | — |
| `document` | `title` (max 200), `url` (HttpUrl) | — |

---

## Estructura de Archivos a Crear/Modificar

```
blogs_backend/
└── app/
    └── blocks/
        ├── schemas.py
        └── validator.py
```

---

## Implementación

### `app/blocks/validator.py`

```python
import re
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional
from fastapi import HTTPException

# --- Modelos por tipo con validaciones de seguridad ---

class TextContent(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        # SEC-007: límite de longitud
        if len(v) > 50_000:
            raise ValueError("El cuerpo no puede superar 50.000 caracteres")
        # SEC-005: rechazar HTML y javascript: para prevenir XSS almacenado
        if re.search(r'<[^>]+>', v, re.IGNORECASE):
            raise ValueError("El contenido no puede incluir etiquetas HTML")
        if re.search(r'javascript\s*:', v, re.IGNORECASE):
            raise ValueError("El contenido no puede incluir scripts")
        return v


class ImageContent(BaseModel):
    url: HttpUrl          # SEC-008: valida http/https, rechaza javascript: y file://
    alt: str = ""

    @field_validator("alt")
    @classmethod
    def validate_alt(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El alt text no puede superar 200 caracteres")
        return v


class CardContent(BaseModel):
    title: str
    text: str
    link: Optional[HttpUrl] = None  # SEC-008: URL opcional validada

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El título no puede superar 200 caracteres")
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v) > 1_000:
            raise ValueError("El texto no puede superar 1.000 caracteres")
        return v


class CtaContent(BaseModel):
    label: str
    url: HttpUrl          # SEC-008: URL requerida y validada

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("El label no puede superar 100 caracteres")
        return v


class DocumentContent(BaseModel):
    title: str
    url: HttpUrl          # SEC-008: URL requerida y validada

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El título no puede superar 200 caracteres")
        return v


CONTENT_VALIDATORS = {
    "text": TextContent,
    "image": ImageContent,
    "card": CardContent,
    "cta": CtaContent,
    "document": DocumentContent,
}


def validate_content_json(block_type: str, content_json: dict) -> dict:
    """Valida y normaliza el content_json según el tipo de bloque."""
    validator_class = CONTENT_VALIDATORS.get(block_type)
    if not validator_class:
        raise HTTPException(status_code=422, detail=f"Tipo de bloque inválido: {block_type}")
    try:
        validated = validator_class(**content_json)
        # Serializar: HttpUrl → str para almacenar en JSONB
        return validated.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"content_json inválido para tipo '{block_type}': {str(e)}"
        )
```

> **`model_dump(mode="json")`:** Pydantic v2 serializa `HttpUrl` como objeto propio. Usar `mode="json"` asegura que se conviertan a strings antes de guardar en Supabase.

---

## Ejemplos de Payloads Válidos por Tipo

### text
```json
{
  "type": "text",
  "content_json": { "body": "## Bienvenidos\n\nEste es mi blog personal." },
  "order": 1,
  "visible": true
}
```

### image
```json
{
  "type": "image",
  "content_json": { "url": "https://cdn.example.com/foto.jpg", "alt": "Mi foto" },
  "order": 2
}
```

### card
```json
{
  "type": "card",
  "content_json": { "title": "FastAPI", "text": "Framework moderno.", "link": "https://fastapi.tiangolo.com" },
  "order": 3
}
```

### cta
```json
{
  "type": "cta",
  "content_json": { "label": "Ver portfolio", "url": "https://johannesta.com/portfolio" },
  "order": 4
}
```

### document
```json
{
  "type": "document",
  "content_json": { "title": "Mi CV 2025", "url": "https://drive.google.com/file/d/xxxx/view" },
  "order": 5
}
```

---

## Payloads Inválidos (rechazados)

```json
// XSS en text body → 422
{ "type": "text", "content_json": { "body": "<script>alert(1)</script>" } }

// javascript: URL en image → 422
{ "type": "image", "content_json": { "url": "javascript:alert(1)" } }

// URL sin esquema en cta → 422
{ "type": "cta", "content_json": { "label": "Click", "url": "evil.com" } }

// Texto excesivamente largo → 422
{ "type": "text", "content_json": { "body": "a".repeat(50001) } }

// Campo requerido faltante → 422
{ "type": "cta", "content_json": { "label": "Sin URL" } }
```

---

## Enfoque TDD

### `tests/test_blocks_validator.py`

```python
import pytest
from app.blocks.validator import validate_content_json
from fastapi import HTTPException

# ============================================================
# TextContent
# ============================================================

class TestTextContent:

    def test_valid_markdown(self):
        result = validate_content_json("text", {"body": "## Título\n\nContenido normal."})
        assert result["body"] == "## Título\n\nContenido normal."

    def test_rejects_html_tags(self):
        # SEC-005: XSS via script tag
        with pytest.raises(HTTPException) as exc:
            validate_content_json("text", {"body": "<script>alert(1)</script>"})
        assert exc.value.status_code == 422

    def test_rejects_html_tags_in_markdown(self):
        # SEC-005: HTML embebido en markdown
        with pytest.raises(HTTPException):
            validate_content_json("text", {"body": "Texto con <img src=x onerror=alert(1)>"})

    def test_rejects_javascript_protocol(self):
        # SEC-005: javascript: en body
        with pytest.raises(HTTPException):
            validate_content_json("text", {"body": "[click](javascript:alert(1))"})

    def test_rejects_body_too_long(self):
        # SEC-007: límite de 50k
        with pytest.raises(HTTPException):
            validate_content_json("text", {"body": "a" * 50_001})

    def test_accepts_body_at_limit(self):
        result = validate_content_json("text", {"body": "a" * 50_000})
        assert len(result["body"]) == 50_000

    def test_missing_body_raises_422(self):
        with pytest.raises(HTTPException):
            validate_content_json("text", {})


# ============================================================
# ImageContent
# ============================================================

class TestImageContent:

    def test_valid_https_url(self):
        result = validate_content_json("image", {"url": "https://cdn.example.com/img.jpg"})
        assert "cdn.example.com" in result["url"]

    def test_rejects_javascript_url(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_content_json("image", {"url": "javascript:alert(1)"})

    def test_rejects_relative_url(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_content_json("image", {"url": "evil.com/img.jpg"})

    def test_optional_alt_defaults_to_empty(self):
        result = validate_content_json("image", {"url": "https://example.com/img.jpg"})
        assert result["alt"] == ""

    def test_alt_too_long_raises_422(self):
        # SEC-007
        with pytest.raises(HTTPException):
            validate_content_json("image", {
                "url": "https://example.com/img.jpg",
                "alt": "a" * 201,
            })


# ============================================================
# CardContent
# ============================================================

class TestCardContent:

    def test_valid_card_with_link(self):
        result = validate_content_json("card", {
            "title": "FastAPI",
            "text": "Framework rápido.",
            "link": "https://fastapi.tiangolo.com",
        })
        assert result["title"] == "FastAPI"

    def test_valid_card_without_link(self):
        result = validate_content_json("card", {"title": "T", "text": "Contenido."})
        assert result["link"] is None

    def test_rejects_javascript_link(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_content_json("card", {
                "title": "T", "text": "C", "link": "javascript:evil()",
            })

    def test_title_too_long(self):
        with pytest.raises(HTTPException):
            validate_content_json("card", {"title": "x" * 201, "text": "ok"})


# ============================================================
# CtaContent
# ============================================================

class TestCtaContent:

    def test_valid_cta(self):
        result = validate_content_json("cta", {"label": "Ver más", "url": "https://example.com"})
        assert result["label"] == "Ver más"

    def test_rejects_missing_url(self):
        with pytest.raises(HTTPException):
            validate_content_json("cta", {"label": "Click"})

    def test_rejects_non_http_url(self):
        with pytest.raises(HTTPException):
            validate_content_json("cta", {"label": "Click", "url": "ftp://files.example.com"})

    def test_label_too_long(self):
        with pytest.raises(HTTPException):
            validate_content_json("cta", {"label": "x" * 101, "url": "https://example.com"})


# ============================================================
# DocumentContent
# ============================================================

class TestDocumentContent:

    def test_valid_drive_url(self):
        result = validate_content_json("document", {
            "title": "Mi CV",
            "url": "https://drive.google.com/file/d/xxxx/view",
        })
        assert "drive.google.com" in result["url"]

    def test_rejects_missing_url(self):
        with pytest.raises(HTTPException):
            validate_content_json("document", {"title": "Mi CV"})


# ============================================================
# Tipo inválido
# ============================================================

def test_invalid_block_type():
    with pytest.raises(HTTPException) as exc:
        validate_content_json("video", {"src": "https://youtube.com"})
    assert exc.value.status_code == 422
    assert "inválido" in exc.value.detail
```

### `tests/test_blocks_api.py` (integración con router)

```python
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_text_block_xss_rejected(client, owner_token):
    """SEC-005: bloque tipo text con script tag es rechazado."""
    with patch("app.blocks.router.supabase"):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={
                "type": "text",
                "content_json": {"body": "<script>alert(1)</script>"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 422

def test_create_image_block_javascript_url_rejected(client, owner_token):
    """SEC-008: URL con javascript: en bloque imagen es rechazada."""
    with patch("app.blocks.router.supabase"):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={
                "type": "image",
                "content_json": {"url": "javascript:alert(document.cookie)"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 422

def test_create_valid_block_persists(client, owner_token):
    """Bloque válido se persiste en DB."""
    mock_block = {
        "id": "block-001",
        "project_id": PROJECT_ID,
        "type": "cta",
        "content_json": {"label": "Ver más", "url": "https://example.com"},
        "order": 1,
        "visible": True,
        "created_at": "2025-01-01T00:00:00",
    }
    with patch("app.blocks.router.supabase") as mock_db:
        mock_db.table.return_value.insert.return_value.execute.return_value \
            = MagicMock(data=[mock_block])

        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={
                "type": "cta",
                "content_json": {"label": "Ver más", "url": "https://example.com"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["type"] == "cta"
```

### Flujo RED → GREEN → REFACTOR

```
RED:   test_rejects_html_tags → falla porque TextContent.body acepta cualquier string
GREEN: Agregar field_validator("body") con regex de HTML
RED:   test_rejects_javascript_url en ImageContent → falla porque url es str
GREEN: Cambiar url: str → url: HttpUrl
RED:   test_label_too_long en CtaContent → falla sin validador
GREEN: Agregar field_validator("label") con len check
REFACTOR: Extraer límites a constantes MODULE-level (MAX_BODY_LENGTH = 50_000, etc.)
```

---

## Criterios de Aceptación Técnicos

- [ ] Bloque `text` con `<script>` en `body` retorna 422
- [ ] Bloque `text` con `javascript:` en `body` retorna 422
- [ ] Bloque `text` con `body` de 50.001 chars retorna 422
- [ ] Bloque `image` con `url: "javascript:alert(1)"` retorna 422
- [ ] Bloque `image` con URL relativa (sin `https://`) retorna 422
- [ ] Bloque `card` con `link: null` se acepta (campo opcional)
- [ ] Bloque `card` con `link: "javascript:evil()"` retorna 422
- [ ] Los 5 tipos se crean correctamente con sus campos requeridos
- [ ] URLs almacenadas en DB son strings normalizados (no objetos Pydantic)
- [ ] `PUT` con `content_json` inválido para el tipo retorna 422

---

## Buenas Prácticas de Código

### Anotaciones de tipo
- Todos los parámetros y retornos de funciones llevan anotación explícita
- `content_json` en `validate_content_json` se anota como `dict[str, Any]`, no `dict` genérico
- `validate_content_json` retorna `dict[str, Any]`; importar `Any` de `typing`
- `field_validator` siempre anota parámetro (`v: str`) y retorno (`-> str`)

### Docstrings
- Cada clase de contenido (`TextContent`, `ImageContent`, etc.) tiene docstring describiendo sus campos y restricciones de seguridad aplicadas (SEC-005, SEC-007, SEC-008)
- `validate_content_json` tiene docstring con `Args:` y `Returns:`
- Estilo: una línea para lógica evidente; multilinea con `Args:` y `Returns:` cuando hay lógica no trivial

---

## Dependencias

- HU-003 completada (router de bloques)
- No requiere cambios en DB
