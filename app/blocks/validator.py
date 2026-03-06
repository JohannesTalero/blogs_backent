import re
from typing import Any, Optional

from pydantic import BaseModel, HttpUrl, field_validator
from fastapi import HTTPException

MAX_BODY_LENGTH = 50_000
MAX_TITLE_LENGTH = 200
MAX_TEXT_LENGTH = 1_000
MAX_LABEL_LENGTH = 100
MAX_ALT_LENGTH = 200


class TextContent(BaseModel):
    """Contenido de un bloque de texto con soporte markdown.

    Restricciones de seguridad:
        SEC-005: Rechaza etiquetas HTML y protocolo `javascript:` (previene XSS almacenado).
        SEC-007: Máximo 50.000 caracteres.
    """

    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        if len(v) > MAX_BODY_LENGTH:
            raise ValueError(f"El cuerpo no puede superar {MAX_BODY_LENGTH:,} caracteres")
        if re.search(r'<[^>]+>', v, re.IGNORECASE):
            raise ValueError("El contenido no puede incluir etiquetas HTML")
        if re.search(r'javascript\s*:', v, re.IGNORECASE):
            raise ValueError("El contenido no puede incluir scripts")
        return v


class ImageContent(BaseModel):
    """Contenido de un bloque de imagen.

    Restricciones de seguridad:
        SEC-007: `alt` máximo 200 caracteres.
        SEC-008: `url` validada con HttpUrl (rechaza javascript:, file://, URLs relativas).

    Attributes:
        url: URL pública de la imagen (http/https obligatorio).
        alt: Texto alternativo para accesibilidad. Por defecto cadena vacía.
    """

    url: HttpUrl
    alt: str = ""

    @field_validator("alt")
    @classmethod
    def validate_alt(cls, v: str) -> str:
        if len(v) > MAX_ALT_LENGTH:
            raise ValueError(f"El alt text no puede superar {MAX_ALT_LENGTH} caracteres")
        return v


class CardContent(BaseModel):
    """Contenido de un bloque tipo tarjeta con título, texto y link opcional.

    Restricciones de seguridad:
        SEC-007: `title` máximo 200 caracteres, `text` máximo 1.000 caracteres.
        SEC-008: `link` validado con HttpUrl si se proporciona.

    Attributes:
        title: Título de la tarjeta.
        text: Cuerpo descriptivo de la tarjeta.
        link: URL de destino opcional.
    """

    title: str
    text: str
    link: Optional[HttpUrl] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > MAX_TITLE_LENGTH:
            raise ValueError(f"El título no puede superar {MAX_TITLE_LENGTH} caracteres")
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f"El texto no puede superar {MAX_TEXT_LENGTH:,} caracteres")
        return v


class CtaContent(BaseModel):
    """Contenido de un bloque Call-To-Action (botón con URL).

    Restricciones de seguridad:
        SEC-007: `label` máximo 100 caracteres.
        SEC-008: `url` validada con HttpUrl (http/https obligatorio).

    Attributes:
        label: Texto visible del botón.
        url: URL de destino del CTA.
    """

    label: str
    url: HttpUrl

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if len(v) > MAX_LABEL_LENGTH:
            raise ValueError(f"El label no puede superar {MAX_LABEL_LENGTH} caracteres")
        return v


class DocumentContent(BaseModel):
    """Contenido de un bloque de documento (PDF, Google Drive, etc.).

    Restricciones de seguridad:
        SEC-007: `title` máximo 200 caracteres.
        SEC-008: `url` validada con HttpUrl (http/https obligatorio).

    Attributes:
        title: Nombre o descripción del documento.
        url: URL pública del documento.
    """

    title: str
    url: HttpUrl

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > MAX_TITLE_LENGTH:
            raise ValueError(f"El título no puede superar {MAX_TITLE_LENGTH} caracteres")
        return v


CONTENT_VALIDATORS: dict[str, type[BaseModel]] = {
    "text": TextContent,
    "image": ImageContent,
    "card": CardContent,
    "cta": CtaContent,
    "document": DocumentContent,
}


def validate_content_json(block_type: str, content_json: dict[str, Any]) -> dict[str, Any]:
    """Valida y normaliza el content_json según el tipo de bloque.

    Instancia el modelo Pydantic correspondiente al tipo y serializa HttpUrl a str
    para que el resultado sea almacenable directamente en Supabase JSONB.

    Args:
        block_type: Tipo de bloque ("text", "image", "card", "cta", "document").
        content_json: Diccionario con el contenido a validar.

    Returns:
        Diccionario validado y serializado (HttpUrl → str).

    Raises:
        HTTPException 422: Si el tipo es inválido o el content_json no cumple el esquema.
    """
    validator_class = CONTENT_VALIDATORS.get(block_type)
    if not validator_class:
        raise HTTPException(status_code=422, detail=f"Tipo de bloque inválido: {block_type}")
    try:
        validated = validator_class(**content_json)
        return validated.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"content_json inválido para tipo '{block_type}': {str(e)}"
        )
