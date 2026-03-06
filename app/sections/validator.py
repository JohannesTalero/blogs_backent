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
