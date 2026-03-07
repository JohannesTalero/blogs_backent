from typing import Any
from datetime import datetime

from pydantic import BaseModel


class BlockCreate(BaseModel):
    """Payload para crear un nuevo bloque dinámico.

    Attributes:
        type: Tipo de bloque. Valores válidos: text | image | card | cta | document.
        content_json: Contenido estructurado según el tipo; validado por `validate_content_json`.
        order: Posición del bloque en la página (ascendente). Por defecto 0.
        visible: Si es False el bloque no aparece en el GET público. Por defecto True.
    """

    type: str
    content_json: dict[str, Any]
    order: int = 0
    visible: bool = True


class BlockUpdate(BaseModel):
    """Payload para actualización parcial de un bloque (PATCH-like via PUT).

    Todos los campos son opcionales; solo los campos enviados se actualizan.

    Attributes:
        type: Nuevo tipo de bloque; si se cambia, `content_json` debe ser compatible.
        content_json: Nuevo contenido; se revalida con el tipo efectivo del bloque.
        order: Nueva posición en la página.
        visible: Nuevo estado de visibilidad.
    """

    type: str | None = None
    content_json: dict[str, Any] | None = None
    order: int | None = None
    visible: bool | None = None


class BlockResponse(BaseModel):
    """Esquema de respuesta de un bloque dinámico.

    Attributes:
        id: Identificador único del bloque.
        post_id: Post al que pertenece el bloque.
        type: Tipo de bloque (text | image | card | cta | document).
        content_json: Contenido estructurado y validado.
        order: Posición en la página.
        visible: True si el bloque es visible en la página pública.
        created_at: Timestamp de creación.
    """

    id: str
    post_id: str
    type: str
    content_json: dict[str, Any]
    order: int
    visible: bool
    created_at: datetime
