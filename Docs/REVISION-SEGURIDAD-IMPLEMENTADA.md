# Revisión de Seguridad — Estado de Implementación

Revisión de todos los controles definidos en `SEGURIDAD.md` contra el código implementado.
Fecha de revisión: 2026-03-06.

---

## Resultado General

Todo lo que puede resolverse en la capa FastAPI está implementado. El único control pendiente (SEC-002) vive en el seed SQL de Supabase (HU-001), fuera de este repositorio.

---

## Estado por Control

### ✅ SEC-001 — Rate limiting en `/auth/login`

**Riesgo original:** Brute force ilimitado sobre credenciales de admin.

**Implementación:**
- `slowapi` instalado y configurado en `app/main.py`
- Límite: 5 intentos por minuto por IP
- Handler de error registrado: retorna `429 Too Many Requests` al superarlo

```python
# app/auth/router.py
@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest) -> TokenResponse:
```

**Nota de despliegue:** En Railway, verificar que `X-Forwarded-For` esté configurado correctamente para que `get_remote_address` obtenga la IP real del cliente y no la del proxy interno.

---

### ⚠️ SEC-002 — RLS real en Supabase

**Riesgo original:** Las políticas `USING (true)` equivalen a no tener RLS. Si alguien accede a Supabase con la `anon key`, ve todos los datos sin restricción.

**Estado:** Pendiente — requiere modificar el seed SQL en HU-001.

**Impacto en el comportamiento actual:** Ninguno. FastAPI usa `service_role` key que bypassa RLS. El código de la API es correcto y seguro. El riesgo existe solo si alguien accede directamente a Supabase con la `anon key`.

**Acción requerida antes de producción:**

```sql
-- Permitir lectura pública de bloques visibles
CREATE POLICY "blocks_public_read" ON blocks
    FOR SELECT USING (visible = true);

-- Permitir lectura pública de secciones
CREATE POLICY "sections_public_read" ON sections
    FOR SELECT USING (true);

-- admins: sin políticas públicas = denegado por defecto para anon/authenticated
-- La service_role (FastAPI) bypassa RLS automáticamente — sin cambios en el código.
```

**Regla de oro:** La `service_role` key nunca debe estar en el frontend. Usar la `anon key` en el frontend solo para operaciones públicas.

---

### ✅ SEC-003 — Timing attack en login

**Riesgo original:** La diferencia de tiempo entre "email no existe" (~5ms) y "password incorrecto" (~100ms por bcrypt) permitía enumerar emails registrados.

**Implementación:**

```python
# app/auth/router.py
_DUMMY_HASH = "$2b$12$/FIFBvClsci0I19RvmKH5eQjZ1XcGFHZGDlXScd44uzWmuCy.pWSW"

if not result.data:
    pwd_context.verify(body.password, _DUMMY_HASH)  # bcrypt siempre se ejecuta
    raise HTTPException(status_code=401, detail="Credenciales inválidas")
```

Además, el query selecciona solo los campos necesarios (`id, project_id, role, hashed_password`), no `SELECT *`.

---

### ✅ SEC-004 — JWT expira en 1h

**Riesgo original:** Con 24h de expiración, un admin eliminado seguía teniendo acceso activo casi todo un día.

**Implementación:**

```python
# app/config.py
jwt_expire_hours: int = 1  # ventana de abuso reducida a 1h
```

**Limitación conocida:** Si un admin es eliminado, su token sigue siendo válido hasta que expire (máximo 1h). Para el MVP esto es aceptable. Si en el futuro se requiere revocación inmediata, implementar una `token_denylist` en Supabase (ver `SEGURIDAD.md` SEC-004 Solución B).

---

### ✅ SEC-005 — XSS almacenado en bloques `text`

**Riesgo original:** Un editor con credenciales válidas podía almacenar `<script>` o `javascript:` en el campo `body` y ejecutar código en el navegador de los visitantes.

**Implementación:**

```python
# app/blocks/validator.py
@field_validator("body")
@classmethod
def validate_body(cls, v: str) -> str:
    if re.search(r'<[^>]+>', v, re.IGNORECASE):
        raise ValueError("El contenido no puede incluir etiquetas HTML")
    if re.search(r'javascript\s*:', v, re.IGNORECASE):
        raise ValueError("El contenido no puede incluir scripts")
    return v
```

**Defensa complementaria requerida en el frontend:** Usar `DOMPurify` o la opción `disallowedElements` de `react-markdown` al renderizar el markdown. La validación backend rechaza los casos obvios, pero la sanitización frontend es la última línea de defensa.

---

### ✅ SEC-006 — `/docs` deshabilitado en producción

**Riesgo original:** Swagger UI y ReDoc expuestos en producción revelan la estructura completa de la API y permiten ejecutar endpoints desde el navegador.

**Implementación:**

```python
# app/main.py
is_prod = settings.environment == "production"

app = FastAPI(
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)
```

Configurar en Railway: `ENVIRONMENT=production`.

---

### ✅ SEC-007 — Límites de longitud en `content_json`

**Riesgo original:** Sin límites, un editor podía enviar megabytes de texto inflando la DB o causando timeouts.

**Implementación en `app/blocks/validator.py`:**

| Campo | Límite |
|---|---|
| `TextContent.body` | 50.000 caracteres |
| `CardContent.title` | 200 caracteres |
| `CardContent.text` | 1.000 caracteres |
| `CtaContent.label` | 100 caracteres |
| `ImageContent.alt` | 200 caracteres |
| `DocumentContent.title` | 200 caracteres |

**Implementación en `app/sections/validator.py`:**

| Campo | Límite |
|---|---|
| `PerfilContent.name` | 200 caracteres |
| `PerfilContent.bio` | 1.000 caracteres |
| `ContactoContent.email` | 200 caracteres |
| `ToolkitContent.tools` | 50 elementos |
| Nombre de herramienta | 100 caracteres |
| `RecomendacionesContent.items` | 100 elementos |
| Título de recomendación | 200 caracteres |

---

### ✅ SEC-008 — Validación de URLs

**Riesgo original:** Campos URL aceptaban cualquier string, incluyendo `javascript:alert(1)`.

**Implementación:** `HttpUrl` de Pydantic v2 en todos los campos de tipo URL:

- `ImageContent.url`
- `CardContent.link` (opcional)
- `CtaContent.url`
- `DocumentContent.url`
- `PerfilContent.photo_url` (opcional)
- `RecomendacionItem.link` (opcional)
- `ContactoContent.linkedin` (opcional)
- `ContactoContent.twitter` (opcional)

`HttpUrl` rechaza automáticamente `javascript:`, `file://`, URLs relativas y cualquier esquema distinto de `http` o `https`.

---

### ✅ SEC-009 — Fortaleza de contraseña en `/admins`

**Riesgo original:** `POST /admins` aceptaba `"a"` como contraseña.

**Implementación:**

```python
# app/admins/schemas.py
@field_validator("password")
@classmethod
def validate_password_strength(cls, v: str) -> str:
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if not re.search(r'[A-Za-z]', v):
        raise ValueError("La contraseña debe contener al menos una letra")
    if not re.search(r'[0-9]', v):
        raise ValueError("La contraseña debe contener al menos un número")
    return v
```

---

### ✅ SEC-010 — CORS restrictivo

**Riesgo original:** `allow_methods=["*"]` y `allow_headers=["*"]` en producción incluían métodos y headers no necesarios.

**Implementación:**

```python
# app/main.py
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
```

---

### ✅ SEC-011 — `.gitignore` protege `.env`

`.gitignore` incluye `.env`, `.venv/`, `__pycache__/`, y archivos de IDE. Verificar antes del primer `git push` que `.env` no aparece en `git status`.

---

### ✅ SEC-012 — PyJWT en lugar de python-jose

`python-jose` tiene CVEs históricos por confusión de algoritmos. El proyecto usa `PyJWT` desde el inicio:

```python
import jwt as pyjwt
```

---

### ✅ SEC-013 — `/health` no filtra información interna

```python
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

No expone versión, entorno, URL de DB ni ningún dato interno.

---

## Resumen de Pendientes

| Prioridad | Control | Acción |
|---|---|---|
| **Antes de producción** | SEC-002 | Reemplazar políticas `USING (true)` en seed SQL |
| **Antes de producción** | SEC-002 | Nunca poner `service_role` key en el frontend |
| **Futuro** | SEC-004 (B) | Implementar `token_denylist` si el sistema escala y se necesita revocación inmediata |
| **Frontend** | SEC-005 | Sanitizar markdown renderizado con `DOMPurify` o `disallowedElements` |

---

## Lo que el diseño hace bien (sin cambios requeridos)

- Mensajes de error genéricos en login — no revelan si el email existe
- `hashed_password` nunca incluido en `AdminResponse`
- `project_id` del JWT validado contra la URL en cada endpoint protegido — centralizado en `assert_project_ownership` (`dependencies.py`)
- Owner no puede eliminarse a sí mismo (`user["sub"] == admin_id`)
- Rol `owner` no asignable via API (`VALID_ROLES = {"editor", "viewer"}`)
- Tipo de bloque validado con lista blanca (`VALID_TYPES`)
- HTTPS gestionado por Railway en producción
