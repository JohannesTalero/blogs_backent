from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Payload de la petición de login.

    Attributes:
        email: Email del administrador; validado como EmailStr.
        password: Contraseña en texto plano (se verifica contra el hash en DB).
    """

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Respuesta exitosa del endpoint de login.

    Attributes:
        access_token: JWT firmado con HS256; incluye `project_id`, `role` y `exp`.
        token_type: Siempre "bearer".
    """

    access_token: str
    token_type: str = "bearer"
