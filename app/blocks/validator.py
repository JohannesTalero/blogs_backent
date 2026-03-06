import re
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional
from fastapi import HTTPException

MAX_BODY_LENGTH = 50_000
MAX_TITLE_LENGTH = 200
MAX_TEXT_LENGTH = 1_000
MAX_LABEL_LENGTH = 100
MAX_ALT_LENGTH = 200


class TextContent(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        # SEC-007: límite de longitud
        if len(v) > MAX_BODY_LENGTH:
            raise ValueError(f"El cuerpo no puede superar {MAX_BODY_LENGTH:,} caracteres")
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
        if len(v) > MAX_ALT_LENGTH:
            raise ValueError(f"El alt text no puede superar {MAX_ALT_LENGTH} caracteres")
        return v


class CardContent(BaseModel):
    title: str
    text: str
    link: Optional[HttpUrl] = None  # SEC-008: URL opcional validada

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
    label: str
    url: HttpUrl          # SEC-008: URL requerida y validada

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if len(v) > MAX_LABEL_LENGTH:
            raise ValueError(f"El label no puede superar {MAX_LABEL_LENGTH} caracteres")
        return v


class DocumentContent(BaseModel):
    title: str
    url: HttpUrl          # SEC-008: URL requerida y validada

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > MAX_TITLE_LENGTH:
            raise ValueError(f"El título no puede superar {MAX_TITLE_LENGTH} caracteres")
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
