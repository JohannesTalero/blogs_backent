from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt

from app.config import settings

bearer_scheme = HTTPBearer()


def assert_project_ownership(user: dict[str, Any], project_id: str) -> None:
    """Verifica que el JWT corresponde al proyecto del recurso solicitado.

    Función centralizada usada por todos los routers protegidos para garantizar
    el aislamiento de datos entre proyectos.

    Args:
        user: Payload del JWT con clave `project_id`.
        project_id: ID del proyecto extraído de la URL.

    Raises:
        HTTPException 403: Si el project_id del token no coincide con el de la URL.
    """
    if user["project_id"] != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Decodifica y valida el Bearer JWT del header Authorization.

    Returns:
        Payload del token como diccionario con claves `sub`, `project_id`, `role`, `exp`.

    Raises:
        HTTPException 401: Si el token está expirado o es inválido.
    """
    token = credentials.credentials
    try:
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


def require_role(*roles: str) -> Callable[..., dict[str, Any]]:
    """Factory de dependencia que restringe el acceso a los roles indicados.

    Args:
        *roles: Roles permitidos (e.g. "owner", "editor", "viewer").

    Returns:
        Dependencia de FastAPI que valida el rol del usuario autenticado.

    Raises:
        HTTPException 403: Si el rol del token no está entre los permitidos.
    """
    def checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return user
    return checker
