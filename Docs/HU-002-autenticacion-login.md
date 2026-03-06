# HU-002: Autenticación del Admin (Login)

**Historia:** Como dueño de proyecto, quiero iniciar sesión en mi panel para gestionar el contenido de mi página.

---

## Contexto Técnico

- Framework: FastAPI
- Auth: JWT con `PyJWT` (HS256) — se usa PyJWT en lugar de python-jose por mejor mantenimiento y menos CVEs históricos
- Hash de passwords: `passlib[bcrypt]`
- Rate limiting: `slowapi`
- Cliente DB: `supabase-py`
- El JWT lleva `project_id` y `role` en el payload
- Expiración: **1 hora** (reducido de 24h para limitar la ventana de tokens comprometidos)

---

## Estructura de Archivos a Crear

```
blogs_backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   └── auth/
│       ├── __init__.py
│       ├── router.py
│       └── schemas.py
├── tests/
│   ├── conftest.py          # Fixtures compartidos
│   └── test_auth.py
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Implementación

### `requirements.txt`

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
supabase>=2.4.0
PyJWT>=2.8.0
passlib[bcrypt]>=1.7.4
pydantic-settings>=2.2.1
python-dotenv>=1.0.1
slowapi>=0.1.9

# Testing
pytest>=8.2.0
pytest-mock>=3.14.0
httpx>=0.27.0
```

### `.gitignore`

```gitignore
# Entorno — nunca subir al repo
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

### `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 1      # SEC-004: reducido de 24h a 1h
    environment: str = "development"  # SEC-006: controla si se exponen /docs

    class Config:
        env_file = ".env"

settings = Settings()
```

### `app/database.py`

```python
from supabase import create_client, Client
from app.config import settings

supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)
```

### `app/auth/schemas.py`

```python
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

### `app/auth/router.py`

```python
from fastapi import APIRouter, HTTPException, Request, status
from datetime import datetime, timedelta, timezone
import jwt as pyjwt
from passlib.context import CryptContext
from app.auth.schemas import LoginRequest, TokenResponse
from app.database import supabase
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SEC-003: hash dummy para igualar tiempo de respuesta cuando el email no existe
# Evita enumeración de emails por timing attack
_DUMMY_HASH = "$2b$12$dummy.hash.prevents.timing.attack.padding.xxxxxxxxxxxxxxx"


@router.post("/login", response_model=TokenResponse)
def login(request: Request, body: LoginRequest):
    # SEC-001: rate limiting aplicado en main.py vía @limiter.limit sobre este endpoint
    # (ver app/main.py — el decorador se aplica desde allí para mantener el router limpio)

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
```

### `app/dependencies.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt
from app.config import settings

bearer_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    token = credentials.credentials
    try:
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

def require_role(*roles: str):
    def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return user
    return checker
```

### `app/main.py`

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.auth.router import router as auth_router

# SEC-001: rate limiter global, clave por IP real del cliente
limiter = Limiter(key_func=get_remote_address)

# SEC-006: deshabilitar /docs y /redoc en producción
is_prod = settings.environment == "production"
app = FastAPI(
    title="Blogs Backend API",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not is_prod else [
        "https://johannesta.com",
        "https://admin.johannesta.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Aplicar rate limit al endpoint de login: 5 intentos/minuto por IP
@app.post("/auth/login")
@limiter.limit("5/minute")
async def login_proxy(request: Request):
    pass  # El router maneja la lógica, este decorador solo aplica el límite

app.include_router(auth_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

> **Nota sobre el rate limiter y el router:** `slowapi` requiere que `@limiter.limit` esté en la función de la app, no en el router. La forma más limpia es registrar el límite directamente en `main.py` sobre el path string, usando `app.state.limiter`:
>
> ```python
> # Alternativa más limpia con slowapi:
> from slowapi import Limiter
> from slowapi.util import get_remote_address
>
> # En auth/router.py, importar el limiter desde main:
> # from app.main import limiter  ← cuidado con importaciones circulares
>
> # La forma más segura: registrar en main.py usando add_api_route con dependencias
> ```
>
> Para el MVP, la forma más simple es agregar el decorador directamente en `auth/router.py` e instanciar el limiter como singleton en un módulo separado (`app/limiter.py`).

### `app/limiter.py` (evitar importaciones circulares)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

Luego en `auth/router.py`:
```python
from app.limiter import limiter

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    ...
```

Y en `main.py`:
```python
from app.limiter import limiter
app.state.limiter = limiter
```

### `.env.example`

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
JWT_SECRET=genera_con_openssl_rand_hex_32
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=1
ENVIRONMENT=development
```

---

## Flujo del Endpoint

```
POST /auth/login
Body: { "email": "admin@johannesta.com", "password": "..." }

1. Rate limiter: ¿más de 5 intentos/min desde esta IP? → 429
2. Query DB: SELECT id, project_id, role, hashed_password WHERE email = ?
3. Si email no existe → bcrypt(dummy) → 401  (mismo tiempo de respuesta)
4. Si existe → bcrypt.verify(password, hash)
5. Si falla → 401
6. Si pasa → generar JWT con project_id + role + exp (1h)
7. Retornar { access_token, token_type: "bearer" }
```

---

## Enfoque TDD

### Setup: `tests/conftest.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from app.main import app
from app.config import settings

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def make_token(project_id: str, role: str, admin_id: str = "admin-uuid-001") -> str:
    payload = {
        "sub": admin_id,
        "project_id": project_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

@pytest.fixture
def owner_token():
    return make_token("proj-001", "owner")

@pytest.fixture
def editor_token():
    return make_token("proj-001", "editor")

@pytest.fixture
def viewer_token():
    return make_token("proj-001", "viewer")

@pytest.fixture
def other_project_token():
    return make_token("proj-002", "owner")
```

### `tests/test_auth.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from passlib.context import CryptContext
import time

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_HASH = pwd_context.hash("Password123")
MOCK_ADMIN = {
    "id": "admin-uuid-001",
    "project_id": "proj-001",
    "role": "owner",
    "hashed_password": VALID_HASH,
}

# --- RED: escribir el test primero ---

def test_login_success(client):
    """Login con credenciales correctas retorna JWT."""
    with patch("app.auth.router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[MOCK_ADMIN])

        response = client.post("/auth/login", json={
            "email": "admin@johannesta.com",
            "password": "Password123",
        })

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

def test_login_wrong_password(client):
    """Password incorrecto retorna 401 con mensaje genérico."""
    with patch("app.auth.router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[MOCK_ADMIN])

        response = client.post("/auth/login", json={
            "email": "admin@johannesta.com",
            "password": "WrongPassword",
        })

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"

def test_login_email_not_found(client):
    """Email inexistente retorna 401 (mismo mensaje que password incorrecto)."""
    with patch("app.auth.router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[])

        response = client.post("/auth/login", json={
            "email": "noexiste@ejemplo.com",
            "password": "cualquiera",
        })

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"

def test_login_timing_attack_protection(client):
    """
    SEC-003: El tiempo de respuesta cuando el email no existe debe ser similar
    al tiempo cuando existe pero el password es incorrecto (ambos corren bcrypt).
    """
    with patch("app.auth.router.supabase") as mock_db:
        # Email no existe
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[])

        t0 = time.perf_counter()
        client.post("/auth/login", json={"email": "noexiste@x.com", "password": "pass"})
        t_no_email = time.perf_counter() - t0

        # Email existe, password malo
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[MOCK_ADMIN])

        t0 = time.perf_counter()
        client.post("/auth/login", json={"email": "admin@johannesta.com", "password": "mal"})
        t_bad_pass = time.perf_counter() - t0

    # Ambos deben tardar al menos 50ms (bcrypt) y no diferir más de 2x
    assert t_no_email > 0.05, "Sin email: debería correr bcrypt (~100ms)"
    assert abs(t_no_email - t_bad_pass) < t_bad_pass, "Diferencia de tiempo sospechosa"

def test_jwt_payload_contains_required_fields(client):
    """El JWT contiene project_id, role y exp."""
    import jwt as pyjwt
    from app.config import settings

    with patch("app.auth.router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[MOCK_ADMIN])

        response = client.post("/auth/login", json={
            "email": "admin@johannesta.com",
            "password": "Password123",
        })

    token = response.json()["access_token"]
    payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    assert payload["project_id"] == "proj-001"
    assert payload["role"] == "owner"
    assert "exp" in payload

def test_login_rate_limit(client):
    """
    SEC-001: Más de 5 intentos por minuto desde la misma IP retorna 429.
    """
    with patch("app.auth.router.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[])

        responses = [
            client.post("/auth/login", json={"email": "x@x.com", "password": "x"})
            for _ in range(7)
        ]

    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, "El rate limiter debería haber retornado 429"

def test_expired_token_rejected(client):
    """Token expirado retorna 401."""
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    expired_payload = {
        "sub": "admin-uuid-001",
        "project_id": "proj-001",
        "role": "owner",
        "exp": datetime.now(timezone.utc) - timedelta(hours=2),  # ya expiró
    }
    expired_token = pyjwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = client.get(
        "/blocks/proj-001/admin/all",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
```

### Flujo RED → GREEN → REFACTOR

```
RED:   Escribir test_login_success → falla porque el endpoint no existe
GREEN: Crear auth/router.py con POST /auth/login mínimo
RED:   Escribir test_login_timing_attack_protection → falla porque no hay dummy hash
GREEN: Agregar _DUMMY_HASH y la llamada cuando email no existe
RED:   Escribir test_login_rate_limit → falla porque no hay slowapi
GREEN: Agregar slowapi + limiter
REFACTOR: Extraer limiter a app/limiter.py para evitar importaciones circulares
```

---

## Criterios de Aceptación Técnicos

- [ ] `POST /auth/login` con credenciales correctas retorna JWT válido
- [ ] JWT contiene `project_id`, `role`, `exp` (1h desde emisión)
- [ ] Email inexistente retorna 401 con mensaje genérico
- [ ] Password incorrecto retorna 401 con mensaje genérico
- [ ] Tiempo de respuesta es similar en ambos casos de error (bcrypt siempre corre)
- [ ] Más de 5 intentos/min desde misma IP retorna 429
- [ ] `/docs` y `/redoc` no accesibles cuando `ENVIRONMENT=production`
- [ ] Token expirado retorna 401 con mensaje "Token expirado"
- [ ] Token inválido/malformado retorna 401

---

## Dependencias

- HU-001 completada (tabla `admins` con seed)
- Variables de entorno en `.env`
