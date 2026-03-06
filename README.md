# blogs-backend

API REST para gestión de contenido de páginas personales. Construida con FastAPI y Supabase.

## Stack

- **FastAPI** — framework web async
- **Supabase** — base de datos PostgreSQL + autenticación de servicio
- **PyJWT** — tokens JWT firmados con HS256
- **passlib[bcrypt]** — hashing de contraseñas
- **slowapi** — rate limiting por IP

## Endpoints

### Públicos (sin autenticación)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio |
| `GET` | `/blocks/{project_id}` | Bloques visibles del proyecto |
| `GET` | `/sections/{project_id}` | Todas las secciones del proyecto |

### Autenticados (requieren JWT)

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `POST` | `/auth/login` | — | Obtener token JWT |
| `GET` | `/blocks/{project_id}/admin/all` | owner, editor | Todos los bloques (incluye borradores) |
| `POST` | `/blocks/{project_id}` | owner, editor | Crear bloque |
| `PUT` | `/blocks/{project_id}/{block_id}` | owner, editor | Actualizar bloque |
| `DELETE` | `/blocks/{project_id}/{block_id}` | owner | Eliminar bloque |
| `PUT` | `/sections/{project_id}/{type}` | owner, editor | Actualizar sección |
| `GET` | `/admins/{project_id}` | owner | Listar admins |
| `POST` | `/admins/{project_id}` | owner | Crear admin (editor o viewer) |
| `DELETE` | `/admins/{project_id}/{admin_id}` | owner | Eliminar admin |

## Tipos de bloques

`text` · `image` · `card` · `cta` · `document`

## Tipos de secciones

`perfil` · `toolkit` · `recomendaciones` · `contacto`

## Variables de entorno

```bash
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
JWT_SECRET=<minimo_32_chars>
JWT_EXPIRE_HOURS=1
ENVIRONMENT=development   # "production" deshabilita /docs
```

Copiar `.env.example` a `.env` y completar los valores.

## Desarrollo local

```bash
# Instalar dependencias
pip install -e .

# Levantar servidor
uvicorn app.main:app --reload

# Correr tests
pytest tests/
```

Requiere Python 3.12+.

## Despliegue (Koyeb)

1. Conectar el repositorio en [koyeb.com](https://koyeb.com)
2. Seleccionar el archivo `koyeb.yaml` o configurar manualmente:
   - **Build command:** `pip install -r requirements.txt`
   - **Run command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. Agregar las variables de entorno en el panel de Koyeb (Secrets)
4. El health check apunta a `/health`

## Base de datos

Ejecutar las migraciones en Supabase SQL Editor en orden:

```
migrations/001_create_tables.sql   # tablas + RLS
migrations/002_seed_initial_data.sql  # proyecto y admin inicial
```

Antes de ejecutar `002`, generar el hash de la contraseña del owner:

```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('TuPassword'))"
```

Y reemplazar `SEED_ADMIN_HASHED_PASSWORD` en el archivo SQL.

## Seguridad

- Rate limiting: 5 intentos de login por minuto por IP
- JWT expira en 1 hora
- XSS bloqueado en campos de texto (regex + validación Pydantic)
- URLs validadas con `HttpUrl` (rechaza `javascript:`, `file://`, etc.)
- `/docs` deshabilitado en producción
- CORS restringido a dominios configurados en producción
- `hashed_password` nunca retornado en respuestas de la API
- RLS habilitado en Supabase; `service_role` key solo en backend

## Tests

```bash
pytest tests/ -v
```

106 tests. Sin dependencia de red — todos los accesos a Supabase están mockeados.
