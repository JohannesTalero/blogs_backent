# HU-001: Configuración de Base de Datos en Supabase

**Historia:** Como desarrollador, necesito crear el esquema de base de datos para que los datos persistan correctamente y estén aislados por proyecto.

---

## Contexto Técnico

- Motor: PostgreSQL vía Supabase
- Aislamiento: Row Level Security (RLS) por `project_id`
- Herramienta de migraciones: SQL directo en Supabase (vía MCP o Dashboard)
- Seed inicial: proyecto `johannesta` con su `owner`

---

## Estructura de Archivos a Crear

```
blogs_backend/
└── migrations/
    ├── 001_create_tables.sql
    └── 002_seed_initial_data.sql
```

---

## Implementación

### Paso 1: Migración `001_create_tables.sql`

```sql
-- Tabla de proyectos
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabla de administradores
CREATE TABLE admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, email)
);

-- Tabla de secciones estáticas
CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('perfil', 'toolkit', 'recomendaciones', 'contacto')),
    content_json JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, type)
);

-- Tabla de bloques dinámicos
CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('text', 'image', 'card', 'cta', 'document')),
    content_json JSONB NOT NULL DEFAULT '{}',
    "order" INTEGER NOT NULL DEFAULT 0,
    visible BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Paso 2: Habilitar RLS y definir políticas restrictivas

> **SEC-002:** Las políticas anteriores usaban `USING (true)` en todas las tablas, lo que equivale a no tener RLS. Las políticas correctas deben denegar por defecto a roles no privilegiados.
>
> La `service_role` key de Supabase bypassa RLS automáticamente, por lo que FastAPI sigue operando sin restricciones. Las políticas aquí protegen el acceso directo con la `anon` key (por ejemplo, si el frontend alguna vez intentara acceder a Supabase directamente).

```sql
-- Habilitar RLS en todas las tablas
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE blocks ENABLE ROW LEVEL SECURITY;

-- projects: solo lectura pública (necesario si el frontend necesita resolver slugs)
CREATE POLICY "projects_public_read" ON projects
    FOR SELECT USING (true);
-- Sin políticas de escritura para anon/authenticated → INSERT/UPDATE/DELETE denegados

-- admins: sin ninguna política pública
-- Resultado: acceso DENEGADO para anon y authenticated
-- Solo service_role (FastAPI) puede leer/escribir
-- No crear ninguna política aquí — el silencio es denegación en RLS

-- sections: solo lectura pública
CREATE POLICY "sections_public_read" ON sections
    FOR SELECT USING (true);
-- Sin políticas de escritura → UPDATE denegado para anon/authenticated

-- blocks: solo lectura pública de bloques visibles
CREATE POLICY "blocks_public_visible_read" ON blocks
    FOR SELECT USING (visible = true);
-- Sin políticas de escritura → INSERT/UPDATE/DELETE denegados para anon/authenticated
```

> **Verificación:** Con estas políticas, si alguien usa la `anon` key directamente:
> - `projects`: puede listar proyectos (público intencional)
> - `admins`: no puede leer nada (emails y hashes protegidos)
> - `sections`: puede leer secciones (público intencional)
> - `blocks`: puede leer solo bloques con `visible=true` (público intencional)

### Paso 3: Seed `002_seed_initial_data.sql`

```sql
-- Insertar proyecto piloto
INSERT INTO projects (id, name, slug)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'JohannesTa',
    'johannesta'
);

-- Insertar owner (password hasheado con bcrypt — ver nota abajo)
INSERT INTO admins (project_id, email, hashed_password, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin@johannesta.com',
    '$2b$12$REEMPLAZAR_CON_HASH_REAL',
    'owner'
);

-- Insertar secciones vacías iniciales
INSERT INTO sections (project_id, type, content_json) VALUES
    ('00000000-0000-0000-0000-000000000001', 'perfil', '{"name": "Johannes", "bio": "", "photo_url": null}'),
    ('00000000-0000-0000-0000-000000000001', 'toolkit', '{"tools": []}'),
    ('00000000-0000-0000-0000-000000000001', 'recomendaciones', '{"items": []}'),
    ('00000000-0000-0000-0000-000000000001', 'contacto', '{"email": "", "linkedin": null, "twitter": null}');
```

> **Generación del hash real:** Antes de ejecutar el seed:
> ```python
> from passlib.context import CryptContext
> pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
> print(pwd_context.hash("tu_password_seguro_minimo_8_chars"))
> ```

### Paso 4: Aplicar migraciones vía MCP de Supabase

```bash
mcp__supabase__apply_migration(name="001_create_tables", query=<contenido_sql>)
mcp__supabase__apply_migration(name="002_seed_initial_data", query=<contenido_sql>)
```

---

## Enfoque TDD

Las migraciones SQL no tienen tests unitarios tradicionales, pero se verifican con queries de aserción ejecutados tras cada migración.

### Estructura

```
migrations/
├── 001_create_tables.sql
├── 002_seed_initial_data.sql
└── verify/
    ├── verify_001_schema.sql    # Aserciones de esquema
    └── verify_002_seed.sql      # Aserciones de datos iniciales
```

### `verify/verify_001_schema.sql`

```sql
-- Verificar que las tablas existen con las columnas correctas
DO $$
BEGIN
    -- projects
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'projects' AND column_name IN ('id','name','slug','created_at')) = 4,
        'Tabla projects: faltan columnas';

    -- admins
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'admins' AND column_name IN ('id','project_id','email','hashed_password','role','created_at')) = 6,
        'Tabla admins: faltan columnas';

    -- sections
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'sections' AND column_name IN ('id','project_id','type','content_json','updated_at')) = 5,
        'Tabla sections: faltan columnas';

    -- blocks
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name IN ('id','project_id','type','content_json','order','visible','created_at')) = 7,
        'Tabla blocks: faltan columnas';

    -- RLS habilitado
    ASSERT (SELECT COUNT(*) FROM pg_tables
        WHERE tablename IN ('projects','admins','sections','blocks') AND rowsecurity = true) = 4,
        'RLS no está habilitado en todas las tablas';

    -- CHECK constraint en admins.role
    BEGIN
        INSERT INTO admins (project_id, email, hashed_password, role)
        VALUES (gen_random_uuid(), 'test@test.com', 'hash', 'superadmin');
        ASSERT false, 'Debería haber fallado: rol inválido';
    EXCEPTION WHEN check_violation THEN
        NULL; -- Correcto
    END;

    RAISE NOTICE 'verify_001: todos los checks pasaron';
END $$;
```

### `verify/verify_002_seed.sql`

```sql
DO $$
BEGIN
    ASSERT (SELECT COUNT(*) FROM projects WHERE slug = 'johannesta') = 1,
        'Proyecto johannesta no existe';

    ASSERT (SELECT COUNT(*) FROM admins
        WHERE project_id = '00000000-0000-0000-0000-000000000001' AND role = 'owner') = 1,
        'Owner de johannesta no existe';

    ASSERT (SELECT COUNT(*) FROM sections
        WHERE project_id = '00000000-0000-0000-0000-000000000001') = 4,
        'Las 4 secciones iniciales no existen';

    ASSERT (SELECT COUNT(*) FROM sections
        WHERE project_id = '00000000-0000-0000-0000-000000000001'
        AND type IN ('perfil', 'toolkit', 'recomendaciones', 'contacto')) = 4,
        'Faltan tipos de sección';

    RAISE NOTICE 'verify_002: seed verificado correctamente';
END $$;
```

---

## Criterios de Aceptación Técnicos

- [ ] Las 4 tablas existen en Supabase con los campos correctos
- [ ] Constraints de `CHECK` en `role` y `type` rechazan valores inválidos
- [ ] `UNIQUE(project_id, email)` en `admins` previene duplicados
- [ ] `UNIQUE(project_id, type)` en `sections` garantiza una sección por tipo
- [ ] RLS activado en las 4 tablas
- [ ] Política `admins`: ninguna lectura posible con `anon` key
- [ ] Política `blocks`: solo `visible=true` accesible con `anon` key
- [ ] Seed ejecutado: proyecto `johannesta` y su `owner` existen
- [ ] Las 4 secciones iniciales existen para `johannesta`
- [ ] `verify_001_schema.sql` y `verify_002_seed.sql` ejecutan sin errores

---

## Dependencias

- Cuenta y proyecto en Supabase activo
- MCP de Supabase configurado o acceso al Dashboard
- Ninguna dependencia de otras HU (esta es la base de todo)
