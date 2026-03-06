from typing import Any, Optional

from pydantic import BaseModel, HttpUrl, field_validator
from fastapi import HTTPException


class PerfilContent(BaseModel):
    """Contenido de la sección de perfil del proyecto.

    Restricciones de seguridad:
        SEC-007: `name` máximo 200 caracteres, `bio` máximo 1.000 caracteres.
        SEC-008: `photo_url` validada con HttpUrl si se proporciona.

    Attributes:
        name: Nombre del dueño del proyecto.
        bio: Descripción breve o presentación.
        photo_url: URL de la foto de perfil (http/https). Opcional.
    """

    name: str = ""
    bio: str = ""
    photo_url: Optional[HttpUrl] = None

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v: str) -> str:
        if len(v) > 1_000:
            raise ValueError("La bio no puede superar 1.000 caracteres")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El nombre no puede superar 200 caracteres")
        return v


class ToolkitContent(BaseModel):
    """Contenido de la sección de herramientas/tecnologías.

    Restricciones de seguridad:
        SEC-007: Máximo 50 herramientas; cada nombre máximo 100 caracteres.

    Attributes:
        tools: Lista de nombres de herramientas o tecnologías.
    """

    tools: list[str] = []

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: list[str]) -> list[str]:
        if len(v) > 50:
            raise ValueError("La lista de herramientas no puede superar 50 elementos")
        for tool in v:
            if len(tool) > 100:
                raise ValueError(f"Nombre de herramienta demasiado largo: '{tool[:20]}...'")
        return v


class RecomendacionItem(BaseModel):
    """Item individual dentro de la sección de recomendaciones.

    Restricciones de seguridad:
        SEC-007: `title` máximo 200 caracteres.
        SEC-008: `link` validado con HttpUrl si se proporciona.

    Attributes:
        title: Título o nombre de la recomendación.
        link: URL de la recomendación. Opcional.
    """

    title: str
    link: Optional[HttpUrl] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El título no puede superar 200 caracteres")
        return v


class RecomendacionesContent(BaseModel):
    """Contenido de la sección de recomendaciones (libros, cursos, recursos).

    Restricciones de seguridad:
        SEC-007: Máximo 100 items en la lista.

    Attributes:
        items: Lista de recomendaciones, cada una con título y link opcional.
    """

    items: list[RecomendacionItem] = []

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: list[RecomendacionItem]) -> list[RecomendacionItem]:
        if len(v) > 100:
            raise ValueError("No se pueden tener más de 100 recomendaciones")
        return v


class ContactoContent(BaseModel):
    """Contenido de la sección de contacto y redes sociales.

    Restricciones de seguridad:
        SEC-007: `email` máximo 200 caracteres.
        SEC-008: `linkedin` y `twitter` validados con HttpUrl si se proporcionan.

    Attributes:
        email: Dirección de correo electrónico de contacto.
        linkedin: URL del perfil de LinkedIn. Opcional.
        twitter: URL del perfil de Twitter/X. Opcional.
    """

    email: str = ""
    linkedin: Optional[HttpUrl] = None
    twitter: Optional[HttpUrl] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("El email no puede superar 200 caracteres")
        return v


SECTION_VALIDATORS: dict[str, type[BaseModel]] = {
    "perfil": PerfilContent,
    "toolkit": ToolkitContent,
    "recomendaciones": RecomendacionesContent,
    "contacto": ContactoContent,
}

VALID_SECTION_TYPES: set[str] = set(SECTION_VALIDATORS.keys())


def validate_section_content(section_type: str, content_json: dict[str, Any]) -> dict[str, Any]:
    """Valida y normaliza el content_json según el tipo de sección.

    Instancia el modelo Pydantic correspondiente al tipo y serializa HttpUrl a str
    para que el resultado sea almacenable directamente en Supabase JSONB.

    Args:
        section_type: Tipo de sección ("perfil", "toolkit", "recomendaciones", "contacto").
        content_json: Diccionario con el contenido a validar.

    Returns:
        Diccionario validado y serializado (HttpUrl → str).

    Raises:
        HTTPException 422: Si el tipo es inválido o el content_json no cumple el esquema.
    """
    validator_class = SECTION_VALIDATORS.get(section_type)
    if not validator_class:
        raise HTTPException(status_code=422, detail=f"Tipo de sección inválido: {section_type}")
    try:
        validated = validator_class(**content_json)
        return validated.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"content_json inválido para sección '{section_type}': {str(e)}"
        )
