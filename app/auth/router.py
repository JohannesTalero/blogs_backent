from fastapi import APIRouter, HTTPException, Request, status
from datetime import datetime, timedelta, timezone
import jwt as pyjwt
from passlib.context import CryptContext
from app.auth.schemas import LoginRequest, TokenResponse
from app.database import supabase
from app.config import settings
from app.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SEC-003: hash dummy para igualar tiempo de respuesta cuando el email no existe
# Evita enumeración de emails por timing attack
_DUMMY_HASH = "$2b$12$/FIFBvClsci0I19RvmKH5eQjZ1XcGFHZGDlXScd44uzWmuCy.pWSW"


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    # SEC-003: seleccionar solo campos necesarios, nunca select("*")
    result = (
        supabase.table("admins")
        .select("id, project_id, role, hashed_password")
        .eq("email", body.email)
        .execute()
    )

    if not result.data:
        # Siempre ejecutar bcrypt para igualar tiempo de respuesta
        pwd_context.verify(body.password, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    admin = result.data[0]

    if not pwd_context.verify(body.password, admin["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(admin["id"]),
        "project_id": str(admin["project_id"]),
        "role": admin["role"],
        "exp": expire,
    }
    token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    return TokenResponse(access_token=token)
