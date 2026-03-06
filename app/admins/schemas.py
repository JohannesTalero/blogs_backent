"""Schemas Pydantic para el módulo de administradores."""
import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class AdminCreate(BaseModel):
    """Payload para crear un nuevo administrador en el proyecto.

    Solo `owner` puede usar este schema. El rol `owner` no está permitido
    en el body; los únicos roles asignables son `editor` y `viewer`.

    Restricciones de seguridad:
        SEC-009: password mínimo 8 caracteres con al menos una letra y un número.

    Attributes:
        email: Email único del nuevo administrador.
        password: Contraseña en texto plano; se hashea con bcrypt antes de guardar.
        role: Rol asignado al nuevo admin (editor | viewer).
    """

    email: EmailStr
    password: str
    role: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """SEC-009: valida que la contraseña tenga fortaleza mínima.

        Reglas: mínimo 8 caracteres, al menos una letra, al menos un número.
        """
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r'[A-Za-z]', v):
            raise ValueError("La contraseña debe contener al menos una letra")
        if not re.search(r'[0-9]', v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v


class AdminResponse(BaseModel):
    """Esquema de respuesta de un administrador del proyecto.

    Nunca incluye `hashed_password`.

    Attributes:
        id: Identificador único del administrador.
        project_id: Proyecto al que pertenece.
        email: Dirección de correo electrónico.
        role: Rol asignado (owner | editor | viewer).
        created_at: Timestamp de creación.
    """

    id: str
    project_id: str
    email: str
    role: str
    created_at: datetime
