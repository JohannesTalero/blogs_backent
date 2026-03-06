# Completitud del Backend y Plan de Despliegue

---

## ¿El Backend Queda Completo con las 8 HU?

**SI, el backend queda completo para el MVP** definido en el PRD. Aquí el detalle:

### Cobertura por Requerimiento Funcional

| RF del PRD | HU que lo cubre | Estado |
|---|---|---|
| FR-1: Auth email/password → JWT con project_id + role | HU-002 | Completo |
| FR-2: Escritura requiere JWT con rol suficiente | HU-002, HU-003, HU-007, HU-008 | Completo |
| FR-3: GET blocks y GET sections son públicos | HU-003, HU-008 | Completo |
| FR-4: 5 tipos de bloques con content_json flexible | HU-004 | Completo |
| FR-5: Campo `order` en bloques | HU-001, HU-003 | Completo |
| FR-6: Campo `visible` en bloques | HU-001, HU-003 | Completo |
| FR-7: RLS / aislamiento por project_id | HU-001, HU-006 | Completo |
| FR-8: Página pública renderiza sin auth | HU-005 (frontend) | Backend completo |
| FR-9: Panel admin en /admin con login previo | HU-005 (frontend) | Backend completo |
| FR-10: Solo owner puede invitar admins | HU-007 | Completo |
| FR-11: Solo owner elimina bloques | HU-003, HU-007 | Completo |
| FR-12: Secciones editables por owner y editor | HU-008 | Completo |

### Lo que NO está cubierto por el backend (fuera de alcance o frontend)

- **Panel admin UI** → Frontend (React + Vite, repo independiente)
- **Página pública UI** → Frontend
- **Google Analytics** → Script en el `<head>` del frontend, sin backend
- **Upload de archivos** → Explícitamente fuera de alcance en el PRD

---

## Estructura Final del Proyecto Backend

```
blogs_backend/
├── app/
│   ├── main.py                    # FastAPI app + routers + CORS
│   ├── config.py                  # Settings con pydantic-settings
│   ├── database.py                # Cliente Supabase singleton
│   ├── dependencies.py            # get_current_user + require_role
│   ├── auth/
│   │   ├── router.py              # POST /auth/login
│   │   └── schemas.py
│   ├── blocks/
│   │   ├── router.py              # CRUD /blocks/{project_id}
│   │   ├── schemas.py
│   │   └── validator.py           # Validación por tipo de bloque
│   ├── sections/
│   │   ├── router.py              # GET + PUT /sections/{project_id}
│   │   ├── schemas.py
│   │   └── validator.py           # Validación por tipo de sección
│   └── admins/
│       ├── router.py              # CRUD /admins/{project_id}
│       └── schemas.py
├── migrations/
│   ├── 001_create_tables.sql
│   └── 002_seed_initial_data.sql
├── requirements.txt
├── .env.example
├── .env                           # gitignored
├── Procfile                       # Para Railway: web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
└── runtime.txt                    # python-3.12.x
```

---

## Endpoints Completos del Backend

| Método | Endpoint | Auth requerida | Descripción |
|---|---|---|---|
| GET | `/health` | No | Health check |
| POST | `/auth/login` | No | Login → JWT |
| GET | `/blocks/{project_id}` | No | Bloques públicos (visible=true) |
| GET | `/blocks/{project_id}/admin/all` | JWT (any role) | Todos los bloques (panel admin) |
| POST | `/blocks/{project_id}` | owner, editor | Crear bloque |
| PUT | `/blocks/{project_id}/{block_id}` | owner, editor | Editar bloque |
| DELETE | `/blocks/{project_id}/{block_id}` | owner | Eliminar bloque |
| GET | `/sections/{project_id}` | No | Todas las secciones públicas |
| PUT | `/sections/{project_id}/{type}` | owner, editor | Editar sección |
| GET | `/admins/{project_id}` | owner | Listar admins del proyecto |
| POST | `/admins/{project_id}` | owner | Invitar nuevo admin |
| DELETE | `/admins/{project_id}/{admin_id}` | owner | Eliminar admin |

---

## Plan de Despliegue

### Stack de Despliegue

| Componente | Servicio | Notas |
|---|---|---|
| Backend (FastAPI) | **Railway** | Tier gratuito suficiente para MVP |
| Base de datos | **Supabase** | Ya en la nube, solo necesita project ID |
| Frontend (React) | **Vercel** | Repo independiente |

### Paso 1: Preparar el repo para Railway

**`Procfile`**
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**`runtime.txt`**
```
python-3.12.0
```

También válido usar `nixpacks.toml` para Railway:
```toml
[phases.build]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

### Paso 2: Variables de entorno en Railway

En el Dashboard de Railway → Variables:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
JWT_SECRET=genera_con_openssl_rand_hex_32
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
```

> Generar JWT_SECRET seguro: `openssl rand -hex 32`

### Paso 3: Aplicar migraciones en Supabase

Antes del primer despliegue, ejecutar las migraciones usando el MCP de Supabase o el SQL Editor del Dashboard:

1. Ejecutar `001_create_tables.sql`
2. Generar el hash bcrypt del password del owner
3. Actualizar y ejecutar `002_seed_initial_data.sql`

### Paso 4: Configurar CORS para producción

En `app/main.py`, cambiar `allow_origins=["*"]` por los dominios reales:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://johannesta.com",      # Frontend público
        "https://admin.johannesta.com", # Panel admin (si es subdominio)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Paso 5: Desplegar en Railway

```bash
# Opción A: conectar repo GitHub (recomendado)
# En Railway Dashboard → New Project → Deploy from GitHub repo

# Opción B: Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

### Paso 6: Desplegar Frontend en Vercel

```bash
# En Vercel Dashboard → New Project → Import repo frontend
# Variables de entorno en Vercel:
VITE_API_URL=https://tu-backend.railway.app
VITE_PROJECT_ID=00000000-0000-0000-0000-000000000001
```

---

## Orden de Implementación Recomendado

Las HU deben implementarse en este orden (por dependencias):

```
HU-001 (DB)
    ↓
HU-002 (Auth)
    ↓
HU-003 (CRUD Bloques)  →  HU-004 (Tipos de Bloques)
    ↓
HU-008 (Secciones)
    ↓
HU-007 (Roles y Admins)
    ↓
HU-006 (Verificar Aislamiento - test transversal)
    ↓
HU-005 (Página pública - mayormente frontend)
```

---

## Checklist de Despliegue Final

### Backend
- [ ] Migraciones aplicadas en Supabase (tablas + seed)
- [ ] Variables de entorno configuradas en Railway
- [ ] CORS restringido a dominios del frontend
- [ ] `GET /health` responde 200 en la URL de Railway
- [ ] `POST /auth/login` funciona con credenciales del owner
- [ ] Todos los endpoints responden correctamente desde Postman/curl

### Frontend
- [ ] `VITE_API_URL` apunta a Railway
- [ ] `VITE_PROJECT_ID` tiene el UUID correcto del proyecto
- [ ] Página pública carga secciones y bloques desde la API de producción
- [ ] Panel admin hace login y opera correctamente

### Seguridad
- [ ] `JWT_SECRET` es único y generado con `openssl rand -hex 32`
- [ ] `SUPABASE_SERVICE_KEY` nunca se expone en el frontend
- [ ] CORS no acepta `*` en producción
- [ ] Las variables de entorno en Railway están marcadas como secretas
