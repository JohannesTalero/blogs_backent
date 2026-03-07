# Guía de integración Frontend

## Qué cambió (breaking changes)

La API introdujo el concepto de **post**. Antes los bloques vivían directamente bajo un proyecto; ahora viven bajo un post. Un proyecto puede tener múltiples posts, cada uno con su propia URL.

```
ANTES:  proyecto → bloques
AHORA:  proyecto → posts (slug/URL) → bloques
```

---

## Nueva arquitectura de datos

```
project_id (ej. "proj-abc123")
└── Post { id, slug, title, order, visible }
    └── Block { id, type, content_json, order, visible }
    └── Block { ... }
└── Post { ... }
    └── Block { ... }
```

---

## Endpoints de Posts

### Listar posts públicos
```
GET /posts/{project_id}
```
No requiere autenticación. Solo retorna posts con `visible: true`.

**Respuesta:**
```json
[
  {
    "id": "uuid",
    "project_id": "proj-abc123",
    "slug": "mi-primer-post",
    "title": "Mi primer post",
    "order": 1,
    "visible": true,
    "created_at": "2025-01-01T00:00:00"
  }
]
```

---

### Obtener un post con sus bloques (la URL del post)
```
GET /posts/{project_id}/{slug}
```
No requiere autenticación. Solo retorna el post si `visible: true`.
Este es el endpoint principal para renderizar una entrada de blog.

**Respuesta:**
```json
{
  "id": "uuid",
  "project_id": "proj-abc123",
  "slug": "mi-primer-post",
  "title": "Mi primer post",
  "order": 1,
  "visible": true,
  "created_at": "2025-01-01T00:00:00",
  "blocks": [
    {
      "id": "uuid",
      "post_id": "uuid-del-post",
      "type": "text",
      "content_json": { "body": "## Hola mundo\n\nContenido en markdown." },
      "order": 1,
      "visible": true,
      "created_at": "2025-01-01T00:00:00"
    },
    {
      "id": "uuid",
      "post_id": "uuid-del-post",
      "type": "image",
      "content_json": { "url": "https://...", "alt": "Descripción" },
      "order": 2,
      "visible": true,
      "created_at": "2025-01-01T00:00:00"
    }
  ]
}
```

**Errores:**
- `404` — slug no existe o post no visible

---

### Listar todos los posts (admin)
```
GET /posts/{project_id}/admin/all
Authorization: Bearer <token>
```
Incluye posts con `visible: false`. Requiere rol `owner`, `editor` o `viewer`.

---

### Crear post
```
POST /posts/{project_id}
Authorization: Bearer <token>
Content-Type: application/json
```
Requiere rol `owner` o `editor`.

**Body:**
```json
{
  "slug": "mi-nuevo-post",
  "title": "Mi nuevo post",
  "order": 1,
  "visible": true
}
```

> El `slug` debe ser único dentro del proyecto. Se recomienda kebab-case (`"como-aprendi-python"`). Si ya existe un post con ese slug en el mismo proyecto, Supabase retorna error de constraint único.

**Respuesta:** `201 Created` con el post creado.

---

### Actualizar post
```
PUT /posts/{project_id}/{post_id}
Authorization: Bearer <token>
Content-Type: application/json
```
Requiere rol `owner` o `editor`. Todos los campos son opcionales.

**Body:**
```json
{
  "title": "Título actualizado",
  "visible": false
}
```

---

### Eliminar post
```
DELETE /posts/{project_id}/{post_id}
Authorization: Bearer <token>
```
Requiere rol `owner`. Eliminar un post **elimina en cascada todos sus bloques**.

---

## Endpoints de Bloques (actualización)

> **Cambio importante:** Las rutas de bloques ahora usan `post_id` en lugar de `project_id`.

### Antes vs. ahora

| Acción | Antes | Ahora |
|--------|-------|-------|
| Listar públicos | `GET /blocks/{project_id}` | `GET /blocks/{post_id}` |
| Listar admin | `GET /blocks/{project_id}/admin/all` | `GET /blocks/{post_id}/admin/all` |
| Crear | `POST /blocks/{project_id}` | `POST /blocks/{post_id}` |
| Actualizar | `PUT /blocks/{project_id}/{block_id}` | `PUT /blocks/{post_id}/{block_id}` |
| Eliminar | `DELETE /blocks/{project_id}/{block_id}` | `DELETE /blocks/{post_id}/{block_id}` |

### Listar bloques de un post (público)
```
GET /blocks/{post_id}
```
No requiere autenticación. Solo retorna bloques con `visible: true`, ordenados por `order`.

> Si ya usas `GET /posts/{project_id}/{slug}`, los bloques vienen embebidos en la respuesta. No necesitas hacer esta llamada adicional.

### Crear bloque
```
POST /blocks/{post_id}
Authorization: Bearer <token>
Content-Type: application/json
```
Requiere rol `owner` o `editor`.

**Body:**
```json
{
  "type": "text",
  "content_json": { "body": "Contenido en markdown." },
  "order": 1,
  "visible": true
}
```

### Cambio en la respuesta de bloques

El campo `project_id` fue reemplazado por `post_id`:

```json
// ANTES
{ "id": "...", "project_id": "proj-abc123", "type": "text", ... }

// AHORA
{ "id": "...", "post_id": "uuid-del-post", "type": "text", ... }
```

---

## Subida de imágenes

Nuevo endpoint para subir imágenes a Supabase Storage.

```
POST /images/{project_id}
Authorization: Bearer <token>
Content-Type: multipart/form-data
```
Requiere rol `owner` o `editor`.

**Form field:** `file` — archivo de imagen.

**Tipos aceptados:** `image/jpeg`, `image/png`, `image/gif`, `image/webp`
**Tamaño máximo:** 5 MB

**Respuesta `200`:**
```json
{
  "url": "https://<ref>.supabase.co/storage/v1/object/public/images/proj-abc123/uuid.jpg"
}
```

**Errores:**
- `401` — sin token
- `403` — rol insuficiente o token de otro proyecto
- `422` — tipo de archivo no permitido o tamaño excedido

### Flujo típico: subir imagen y crear bloque

```js
// 1. Subir imagen
const formData = new FormData()
formData.append('file', fileInput.files[0])

const { url } = await fetch(`/images/${projectId}`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
  body: formData,
}).then(r => r.json())

// 2. Crear bloque de imagen con la URL obtenida
await fetch(`/blocks/${postId}`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    type: 'image',
    content_json: { url, alt: 'Descripción de la imagen' },
    order: 3,
  }),
})
```

---

## Tipos de bloques (sin cambios)

| Tipo | Campos de `content_json` |
|------|--------------------------|
| `text` | `body: string` (markdown, máx 50.000 chars) |
| `image` | `url: string (https)`, `alt?: string` |
| `card` | `title: string`, `text: string`, `link?: string (https)` |
| `cta` | `label: string`, `url: string (https)` |
| `document` | `title: string`, `url: string (https)` |

---

## Endpoints sin cambios

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio |
| `POST` | `/auth/login` | Obtener token JWT |
| `GET` | `/sections/{project_id}` | Secciones estáticas (público) |
| `PUT` | `/sections/{project_id}/{type}` | Actualizar sección |
| `GET` | `/admins/{project_id}` | Listar admins |
| `POST` | `/admins/{project_id}` | Crear admin |
| `DELETE` | `/admins/{project_id}/{admin_id}` | Eliminar admin |

---

## Flujo de integración recomendado

```
1. GET /sections/{project_id}        → datos estáticos del perfil (hero, toolkit, etc.)
2. GET /posts/{project_id}           → lista de posts para el índice del blog
3. GET /posts/{project_id}/{slug}    → post completo con bloques al navegar a una URL
```
