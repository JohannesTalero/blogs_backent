from typing import Any

from pydantic import BaseModel


class SectionResponse(BaseModel):
    """Esquema de respuesta de una sección estática del proyecto.

    Las secciones son fijas (perfil, toolkit, recomendaciones, contacto) y
    existen desde el seed inicial; no se crean ni eliminan vía API.

    Attributes:
        id: Identificador único de la sección.
        project_id: Proyecto al que pertenece la sección.
        type: Tipo de sección (perfil | toolkit | recomendaciones | contacto).
        content_json: Contenido estructurado; esquema varía según `type`.
    """

    id: str
    project_id: str
    type: str
    content_json: dict[str, Any]
