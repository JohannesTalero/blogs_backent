# Decisiones Técnicas

Registro de decisiones de arquitectura, librerías y tecnologías del proyecto. Cada decisión incluye el contexto, la alternativa considerada y la razón de la elección.

---

## DT-001: Framework Backend — FastAPI

**Decisión:** Usar FastAPI como framework HTTP para el backend.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| Django REST Framework | Demasiado opinionado y pesado para una API sin modelos ORM propios |
| Flask | Sin validación de esquemas nativa; requiere más librerías para llegar al mismo punto |
| Litestar | Menor ecosistema y comunidad en 2025 |

**Razones de la elección:**
- Validación automática de request/response con Pydantic sin código extra
- Documentación OpenAPI generada automáticamente (útil durante desarrollo)
- Tipado estático nativo: errores de tipo detectados en IDE antes de correr el servidor
- Alto rendimiento asíncrono cuando se necesite escalar
- `Depends()` para inyección de dependencias limpia (auth, roles)

---

## DT-002: Base de Datos — Supabase (PostgreSQL)

**Decisión:** Usar Supabase como BaaS para la base de datos.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| PostgreSQL self-hosted | Requiere infraestructura propia y mantenimiento de backups |
| PlanetScale (MySQL) | Sin soporte para JSONB nativo; no es PostgreSQL |
| Firebase Firestore | NoSQL; sin joins ni constraints; modelo de datos menos adecuado para este proyecto |
| Neon | Menos features BaaS (sin storage, sin auth integrada para el futuro) |

**Razones de la elección:**
- PostgreSQL con JSONB: almacenamiento flexible de `content_json` sin schema rígido por tipo de bloque
- Row Level Security (RLS) nativo para aislamiento a nivel de DB como defensa en profundidad
- MCP (Model Context Protocol) disponible para aplicar migraciones desde el IDE directamente
- Dashboard visual para inspeccionar datos durante desarrollo
- Storage integrado disponible para futuras versiones (si se agrega upload de archivos)
- Tier gratuito generoso para MVP

**Nota importante:** FastAPI se conecta con la `service_role` key (bypassa RLS). El aislamiento real por `project_id` es responsabilidad de FastAPI. El RLS provee una segunda capa de defensa para accesos directos a Supabase.

---

## DT-003: Autenticación — JWT Stateless con HS256

**Decisión:** JWT stateless firmado con HS256, expiración de 1 hora.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| Sessions con Redis | Requiere infraestructura de Redis; más complejo de deployar |
| OAuth2 / Supabase Auth | Overkill para admin interno con pocos usuarios; añade dependencia de Supabase Auth |
| RS256 (asimétrico) | Necesario solo cuando hay múltiples servicios verificando tokens; innecesario aquí |
| Tokens de larga duración (24h+) | Ventana de abuso demasiado grande si el token se compromete |

**Razones de la elección:**
- Stateless: no requiere almacenamiento de sesiones
- HS256 es suficiente para un backend single-service donde el mismo servidor firma y verifica
- El payload incluye `project_id` y `role` para autorización sin consulta a DB en cada request
- 1 hora de expiración como balance entre UX (no forzar re-login constante) y seguridad

**Trade-off conocido:** Sin blacklist de tokens, un admin eliminado retiene acceso durante la ventana de 1 hora restante. Aceptado para MVP; documentado en SEC-004.

---

## DT-004: Librería JWT — PyJWT

**Decisión:** Usar `PyJWT` en lugar de `python-jose`.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| `python-jose` | CVEs históricos relacionados con algorithm confusion; mantenimiento más lento |
| `authlib` | Más completo pero más pesado; orientado a OAuth2 completo |

**Razones de la elección:**
- `PyJWT` es el estándar de facto en el ecosistema Python para JWT simple
- Mantenimiento activo (Jazzband)
- API más simple para el caso de uso de HS256

---

## DT-005: Hash de Passwords — bcrypt vía passlib

**Decisión:** Usar `passlib[bcrypt]` para hashear contraseñas.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| `argon2-cffi` | Argon2 es más moderno, pero bcrypt es ampliamente probado y suficiente |
| SHA-256/MD5 | Inaceptable — no son funciones de hash de passwords (sin factor de trabajo) |
| `bcrypt` directo | `passlib` añade una capa de abstracción que facilita migrar algoritmos en el futuro |

**Razones de la elección:**
- bcrypt tiene factor de trabajo configurable (costo computacional intencional que frena brute force)
- `passlib` gestiona el salt automáticamente
- Interoperable: el hash es estándar y puede ser verificado por cualquier librería bcrypt

---

## DT-006: Rate Limiting — slowapi

**Decisión:** Usar `slowapi` para rate limiting en `/auth/login`.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| Rate limiting en el proxy (Nginx/Railway) | Railway no ofrece rate limiting configurable en su tier básico |
| Redis + custom middleware | Requiere Redis; overkill para el volumen de tráfico del MVP |
| Sin rate limiting | Inaceptable — brute force ilimitado en login |

**Razones de la elección:**
- Integración directa con FastAPI como decorador
- Sin dependencias externas (usa memoria en proceso para MVP)
- Suficiente para proteger el endpoint de login en un MVP de un solo proceso

**Limitación conocida:** En memoria significa que el contador se reinicia si el servidor se reinicia, y no funciona en deployments multi-proceso. Suficiente para MVP; escalar a Redis si hay múltiples instancias.

---

## DT-007: Validación de Datos — Pydantic v2

**Decisión:** Usar Pydantic v2 para validación de schemas (ya incluido en FastAPI).

**Por qué Pydantic v2 sobre v1:**
- `model_dump(mode="json")` serializa tipos especiales como `HttpUrl` a strings directamente
- `field_validator` más limpio que los `validator` de v1
- Mejor rendimiento (core en Rust)

**Decisión específica: `HttpUrl` para validar URLs externas**

Todos los campos de URL en bloques y secciones usan `HttpUrl` de Pydantic en lugar de `str`. Esto rechaza automáticamente:
- `javascript:alert(1)`
- `file:///etc/passwd`
- URLs sin esquema como `evil.com`
- Strings vacíos en campos requeridos

Para campos opcionales: `Optional[HttpUrl] = None` en lugar de `str = ""`.

---

## DT-008: Estrategia de Testing — pytest + mocks de Supabase

**Decisión:** Tests con `pytest`, `httpx` y mocks de `supabase-py` vía `unittest.mock`.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| Tests contra Supabase real (staging) | Lento, requiere red, no determinista, difícil de limpiar datos |
| Supabase local con Docker | Válido pero añade complejidad de setup; para MVP los mocks son suficientes |
| `pytest-asyncio` + async client | No necesario si los endpoints de FastAPI son síncronos |

**Razones de la elección:**
- Mocks de Supabase: tests rápidos (ms, no segundos), sin dependencias de red
- `TestClient` de Starlette corre el servidor ASGI en memoria
- `conftest.py` centraliza fixtures reutilizables (tokens, client)
- Estrategia TDD: tests fallan primero (RED), luego se implementa el mínimo para pasar (GREEN), luego se refactoriza

**Estructura de tests:**
```
tests/
├── conftest.py              # Fixtures compartidos (client, tokens)
├── test_auth.py             # HU-002: login, rate limit, timing
├── test_blocks.py           # HU-003: CRUD, permisos por rol
├── test_blocks_validator.py # HU-004: validación por tipo
├── test_sections.py         # HU-008: secciones + validación URLs
├── test_admins.py           # HU-007: CRUD admins, password strength
├── test_public_endpoints.py # HU-005: contratos públicos
└── test_isolation.py        # HU-006: aislamiento entre proyectos
```

---

## DT-009: Arquitectura de Módulos — Routers por dominio

**Decisión:** Organizar el código en módulos por dominio (`auth`, `blocks`, `sections`, `admins`), cada uno con su `router.py`, `schemas.py` y `validator.py`.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| Un solo archivo `main.py` | No escala; difícil de testear en aislamiento |
| Arquitectura hexagonal (ports & adapters) | Overkill para el tamaño del proyecto |
| Organización por capa (routers/, schemas/, validators/) | Menos cohesión: cambiar un dominio requiere tocar 3 carpetas |

**Razones de la elección:**
- Alta cohesión: todo lo relacionado con `blocks` vive en `app/blocks/`
- Bajo acoplamiento: cada módulo importa solo `database.py` y `dependencies.py`
- Escalable: agregar un nuevo dominio es agregar una carpeta nueva

**Estructura resultante:**
```
app/
├── main.py           # Composición: registra routers, middleware
├── config.py         # Settings desde .env
├── database.py       # Singleton cliente Supabase
├── dependencies.py   # get_current_user, require_role (compartidos)
├── limiter.py        # Rate limiter singleton (evita importaciones circulares)
├── auth/
├── blocks/
├── sections/
└── admins/
```

---

## DT-010: Aislamiento de Datos — Validación en FastAPI, no solo en RLS

**Decisión:** El aislamiento por `project_id` se valida en la capa de FastAPI mediante `_assert_project_ownership`, complementado con políticas RLS reales en Supabase (no `USING (true)`).

**Razones:**
- FastAPI tiene control total sobre la lógica de negocio; RLS es la segunda línea de defensa
- Si un bug omite el filtro por `project_id` en un query, RLS bloquea el acceso con `anon` key
- La `service_role` key de FastAPI bypassa RLS, por lo que el control primario siempre es FastAPI

**Patrón en cada endpoint protegido:**
```python
def _assert_project_ownership(user: dict, project_id: str):
    if user["project_id"] != project_id:
        raise HTTPException(status_code=403)
```

---

## DT-011: Despliegue — Railway (backend) + Vercel (frontend)

**Decisión:** Railway para FastAPI, Vercel para React.

**Alternativas consideradas:**
| Servicio | Razón de descarte / notas |
|---|---|
| Render | Alternativa válida; Railway tiene mejor DX para Python |
| Fly.io | Más control pero más configuración (Dockerfile requerido) |
| AWS/GCP/Azure | Overkill para MVP; costo y complejidad no justificados |
| Heroku | Eliminó tier gratuito |

**Razones de la elección:**
- Railway: deploy desde GitHub sin Dockerfile, variables de entorno en UI, dominio HTTPS automático
- Vercel: deploy de React en segundos, CDN global, preview URLs por PR
- Ambos soportan variables de entorno secretas (no visibles en logs)

**Configuración Railway:**
- `Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Variables de entorno marcadas como secretas en Railway dashboard

---

## DT-012: Gestión de Dependencias y Entorno Virtual — uv

**Decisión:** Usar `uv` como gestor de paquetes y entornos virtuales, reemplazando pip y venv.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| `pip` + `venv` | Lento, sin lock file nativo, gestión manual del entorno |
| `poetry` | Más establecido pero más lento; `uv` ofrece la misma funcionalidad 10-100x más rápido |
| `pipenv` | Considerado legado en 2026; desarrollo lento |
| `conda` | Orientado a data science; exceso de peso para un backend web |

**Razones de la elección:**
- Escrito en Rust: instalación de dependencias 10-100x más rápida que pip
- Reemplaza pip, venv, pip-tools y pip-compile en un solo binario
- Genera `uv.lock` (lock file determinista) que garantiza builds reproducibles en CI y producción
- Compatible con `pyproject.toml` estándar (PEP 517/518)
- Gestiona la versión de Python del proyecto (similar a `pyenv`)
- Adoptado ampliamente en el ecosistema Python como estándar de facto en 2025-2026

**Comandos clave:**

```bash
# Instalar uv (una sola vez en la máquina)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Inicializar proyecto (crea pyproject.toml + .venv + uv.lock)
uv init

# Especificar versión de Python del proyecto
uv python pin 3.12

# Agregar dependencias de producción
uv add fastapi uvicorn[standard] supabase PyJWT passlib[bcrypt] \
       pydantic-settings slowapi

# Agregar dependencias de desarrollo/testing (no van a producción)
uv add --dev pytest pytest-mock httpx

# Instalar todas las dependencias desde uv.lock (equivale a pip install -r requirements.txt)
uv sync

# Correr el servidor dentro del entorno virtual (sin activarlo)
uv run uvicorn app.main:app --reload

# Correr tests
uv run pytest

# Activar el entorno virtual manualmente (opcional)
source .venv/bin/activate
```

**Estructura de archivos resultante:**

```
blogs_backend/
├── pyproject.toml    # Dependencias y metadata del proyecto (reemplaza requirements.txt)
├── uv.lock           # Lock file determinista (commitear al repo)
├── .python-version   # Versión de Python fijada por uv (ej: "3.12")
└── .venv/            # Entorno virtual local (gitignored)
```

**`pyproject.toml` resultante:**

```toml
[project]
name = "blogs-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "supabase>=2.4.0",
    "PyJWT>=2.8.0",
    "passlib[bcrypt]>=1.7.4",
    "pydantic-settings>=2.2.1",
    "slowapi>=0.1.9",
]

[dependency-groups]
dev = [
    "pytest>=8.2.0",
    "pytest-mock>=3.14.0",
    "httpx>=0.27.0",
]
```

**`.gitignore` — agregar entorno virtual:**
```gitignore
.venv/
```

> `uv.lock` SÍ se commitea al repo. `.venv/` NO se commitea.

**En Railway (producción):** Railway detecta `pyproject.toml` automáticamente con Nixpacks y ejecuta `uv sync --no-dev` antes de arrancar el servidor. Si no lo detecta, agregar `nixpacks.toml`:
```toml
[phases.setup]
nixPkgs = ["python312"]
cmds = ["pip install uv"]

[phases.install]
cmds = ["uv sync --no-dev"]

[start]
cmd = "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

---

## DT-013: Configuración — pydantic-settings

**Decisión:** Usar `pydantic-settings` para cargar variables de entorno.

**Alternativas consideradas:**
| Alternativa | Razón de descarte |
|---|---|
| `os.environ` directo | Sin validación de tipos ni defaults declarativos |
| `python-dotenv` solo | Sin tipado ni validación |
| `dynaconf` | Mayor complejidad para el caso de uso |

**Razones de la elección:**
- Validación automática al arrancar: si falta `SUPABASE_URL`, el servidor no arranca con error claro
- Tipado: `jwt_expire_hours: int` convierte el string de `.env` a entero automáticamente
- Integración nativa con `.env` y variables del sistema operativo (Railway las inyecta como env vars)

---

## DT-013: CORS — Restringido en producción

**Decisión:** `allow_origins=["*"]` solo en desarrollo; dominios específicos en producción.

**Configuración de producción:**
```python
allow_origins=["https://johannesta.com", "https://admin.johannesta.com"]
allow_methods=["GET", "POST", "PUT", "DELETE"]
allow_headers=["Authorization", "Content-Type"]
```

**Razón:** CORS abierto en producción permitiría que cualquier sitio web haga requests autenticados al backend en nombre de un usuario logueado (CSRF vía credenciales compartidas).

---

## DT-014: Contenido — Markdown sin HTML en bloques `text`

**Decisión:** Los bloques tipo `text` aceptan markdown plano pero rechazan HTML y `javascript:` via validación en Pydantic.

**Razones:**
- Markdown es suficiente para el caso de uso (headers, listas, negritas, links)
- HTML embebido en markdown puede contener XSS almacenado (SEC-005)
- La sanitización ocurre en el backend (fuente de verdad) y también debe ocurrir en el frontend al renderizar

**El frontend debe igualmente:** usar `react-markdown` con `disallowedElements={["script", "iframe"]}` o `DOMPurify` antes de renderizar como HTML.

---

## Resumen de Stack Tecnológico

| Capa | Tecnología | Versión mínima | Decisión |
|---|---|---|---|
| Backend framework | FastAPI | 0.111 | DT-001 |
| Servidor ASGI | Uvicorn | 0.29 | — |
| Base de datos | Supabase (PostgreSQL) | — | DT-002 |
| Cliente DB | supabase-py | 2.4 | — |
| Auth | PyJWT + HS256 | 2.8 | DT-003, DT-004 |
| Hash passwords | passlib[bcrypt] | 1.7 | DT-005 |
| Rate limiting | slowapi | 0.1.9 | DT-006 |
| Validación | Pydantic v2 | incluido en FastAPI | DT-007 |
| Config | pydantic-settings | 2.2 | DT-013 |
| Gestor de paquetes | uv | — | DT-012 |
| Testing | pytest + httpx | 8.2 / 0.27 | DT-008 |
| Deploy backend | Railway | — | DT-011 |
| Deploy frontend | Vercel | — | DT-011 |
| Frontend | React + Vite | — | (repo independiente) |
