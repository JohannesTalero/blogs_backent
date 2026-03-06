# PRD: Sistema de Bloques para Páginas Multi-Proyecto
**Proyecto piloto:** JohannesTa.com

## Introducción

Los dueños de proyectos no pueden actualizar el contenido de sus páginas sin depender de un desarrollador. La solución es una plataforma donde cada proyecto tiene su propia página web con secciones estáticas editables (perfil, toolkit, recomendaciones, contacto) y un sistema de bloques dinámicos, todo gestionable desde un panel admin sin tocar código. El backend es compartido (FastAPI + Supabase) pero cada proyecto opera de forma completamente independiente y aislada. Analytics se delega a Google Analytics vía script embebido en el frontend.

---

## Objetivos

- Dueño del proyecto gestiona todo su contenido sin escribir código
- Sistema de bloques extensible con 5 tipos: texto, imagen, tarjeta, CTA, documento
- Secciones estáticas editables desde el panel admin (perfil, toolkit, recomendaciones, contacto)
- Múltiples usuarios por proyecto con roles diferenciados: `owner`, `editor`, `viewer`
- Aislamiento total de datos entre proyectos vía Supabase RLS
- Flujo end-to-end funcional: login → editar contenido → visible en página pública

---

## Historias de Usuario

### US-001: Configuración de base de datos en Supabase
**Descripción:** Como desarrollador, necesito crear el esquema de base de datos para que los datos persistan correctamente y estén aislados por proyecto.

**Criterios de aceptación:**
- [ ] Tabla `projects`: `id`, `name`, `slug`, `created_at`
- [ ] Tabla `admins`: `id`, `project_id`, `email`, `hashed_password`, `role`
- [ ] Tabla `sections`: `id`, `project_id`, `type`, `content_json`
- [ ] Tabla `blocks`: `id`, `project_id`, `type`, `content_json`, `order`, `visible`, `created_at`
- [ ] RLS activado: cada proyecto solo accede a sus propios datos
- [ ] Seed inicial con proyecto `johannesta` y su `owner`
- [ ] Migraciones ejecutadas sin errores

---

### US-002: Autenticación del admin (login)
**Descripción:** Como dueño de proyecto, quiero iniciar sesión en mi panel para gestionar el contenido de mi página.

**Criterios de aceptación:**
- [ ] `POST /auth/login` recibe `email` + `password`, retorna JWT
- [ ] JWT incluye `project_id` y `role` en el payload
- [ ] Credenciales incorrectas retornan `401 Unauthorized`
- [ ] JWT expira en 24 horas
- [ ] Frontend muestra formulario de login y redirige al panel tras éxito
- [ ] Verificar flujo en navegador

---

### US-003: CRUD de bloques dinámicos
**Descripción:** Como dueño de proyecto, quiero agregar, editar y eliminar bloques desde una interfaz simple para actualizar mi página sin tocar código.

**Criterios de aceptación:**
- [ ] `GET /blocks/{project_id}` — público, sin auth
- [ ] `POST /blocks/{project_id}` — requiere JWT con rol `owner` o `editor`
- [ ] `PUT /blocks/{project_id}/{block_id}` — requiere JWT con rol `owner` o `editor`
- [ ] `DELETE /blocks/{project_id}/{block_id}` — requiere JWT con rol `owner` únicamente
- [ ] Panel admin lista bloques existentes con botones de editar/eliminar según rol
- [ ] Formulario permite seleccionar tipo de bloque antes de crear
- [ ] Verificar flujo en navegador

---

### US-004: Soporte para 5 tipos de bloques
**Descripción:** Como dueño de proyecto, quiero crear diferentes tipos de bloques según el contenido que quiero mostrar.

**Criterios de aceptación:**
- [ ] `text`: campo de texto con soporte markdown básico
- [ ] `image`: URL de imagen + alt text/descripción
- [ ] `card`: título + texto + URL de link
- [ ] `cta`: texto del botón + URL de destino
- [ ] `document`: título + URL del documento (PDF, Drive, etc.)
- [ ] Cada tipo tiene su propio formulario en el panel admin
- [ ] Cada tipo tiene su propio componente de renderizado en la página pública
- [ ] Verificar todos los tipos en navegador

---

### US-005: Página pública con secciones + bloques
**Descripción:** Como visitante, quiero ver la página del proyecto con secciones estáticas y bloques dinámicos actualizados.

**Criterios de aceptación:**
- [ ] Página pública muestra secciones: perfil, toolkit, recomendaciones, contacto
- [ ] Bloques dinámicos se renderizan ordenados por campo `order`
- [ ] Solo bloques con `visible = true` se muestran al público
- [ ] Página carga sin autenticación
- [ ] Verificar renderizado en navegador

---

### US-006: Aislamiento de datos entre proyectos
**Descripción:** Como desarrollador, necesito garantizar que cada proyecto solo pueda ver y modificar sus propios datos.

**Criterios de aceptación:**
- [ ] RLS de Supabase impide que proyecto A lea datos de proyecto B
- [ ] JWT de proyecto A retorna `403` al intentar modificar recursos de proyecto B
- [ ] Test manual con dos proyectos distintos confirma aislamiento completo

---

### US-007: Múltiples usuarios con roles por proyecto
**Descripción:** Como owner, quiero invitar a otros usuarios con roles específicos para que me ayuden a gestionar el contenido sin darles acceso total.

**Criterios de aceptación:**
- [ ] Campo `role` soporta: `owner`, `editor`, `viewer`
- [ ] `POST /admins/{project_id}` — solo `owner` puede invitar nuevos admins con rol asignado
- [ ] `owner`: CRUD de bloques + secciones + gestión de admins
- [ ] `editor`: crear y editar bloques y secciones, no puede eliminar ni gestionar usuarios
- [ ] `viewer`: acceso de solo lectura al panel, sin editar
- [ ] Middleware de FastAPI valida el rol antes de cada endpoint protegido
- [ ] Panel admin muestra/oculta opciones según rol del usuario autenticado
- [ ] Verificar comportamiento por rol en navegador

---

### US-008: Secciones estáticas editables desde el panel admin
**Descripción:** Como dueño de proyecto, quiero editar las secciones estáticas de mi página (perfil, toolkit, recomendaciones, contacto) desde el panel admin sin tocar código.

**Criterios de aceptación:**
- [ ] `GET /sections/{project_id}` — público, sin auth, retorna todas las secciones
- [ ] `PUT /sections/{project_id}/{type}` — requiere JWT con rol `owner` o `editor`
- [ ] Panel admin tiene pestaña "Secciones" con formulario específico por tipo
- [ ] Sección `perfil`: nombre, bio, foto (URL)
- [ ] Sección `toolkit`: lista de herramientas/tecnologías
- [ ] Sección `recomendaciones`: lista de items con título y link
- [ ] Sección `contacto`: email, LinkedIn, y otros links sociales
- [ ] Cambios se reflejan en la página pública inmediatamente
- [ ] Verificar todos los formularios en navegador

---

## Requerimientos Funcionales

- **FR-1:** Auth con email/password → JWT con `project_id` y `role`
- **FR-2:** Endpoints de escritura requieren JWT con rol suficiente según operación
- **FR-3:** `GET /blocks/{project_id}` y `GET /sections/{project_id}` son públicos
- **FR-4:** 5 tipos de bloques con `content_json` flexible por tipo
- **FR-5:** Campo `order` en bloques para controlar posición
- **FR-6:** Campo `visible` en bloques para publicar/ocultar sin eliminar
- **FR-7:** RLS en Supabase garantiza aislamiento por `project_id`
- **FR-8:** Página pública renderiza secciones y bloques sin auth
- **FR-9:** Panel admin accesible en `/admin` con login previo
- **FR-10:** Solo `owner` puede invitar admins vía `POST /admins/{project_id}`
- **FR-11:** Solo `owner` puede eliminar bloques; `editor` solo crea y edita
- **FR-12:** Secciones estáticas editables por `owner` y `editor`, no por `viewer`

---

## Fuera del Alcance

- No subida directa de archivos — imágenes y documentos se referencian por URL
- No drag-and-drop para reordenar bloques — orden numérico en MVP
- No notificaciones de ningún tipo
- No internacionalización (i18n) — audiencia 100% hispanohablante en MVP
- Analytics vía Google Analytics embebido en frontend, sin backend propio
- No previsualización en tiempo real antes de guardar

---

## Consideraciones Técnicas

| Capa | Tecnología | Notas |
|---|---|---|
| Backend | FastAPI (Python) | `python-jose`, `passlib[bcrypt]`, `supabase-py` |
| Base de datos | Supabase (PostgreSQL) | RLS por `project_id`, seed con proyecto `johannesta` |
| Frontend | React + Vite | Repo independiente por proyecto |
| Auth | JWT Bearer Token | Payload: `project_id` + `role` |
| Analytics | Google Analytics | Script en el `<head>` del frontend |
| Deploy sugerido | Railway (backend) + Vercel (frontend) | |

**`content_json` por tipo de bloque:**
```json
{ "body": "..." }                                          // text
{ "url": "https://...", "alt": "..." }                     // image
{ "title": "...", "text": "...", "link": "https://..." }   // card
{ "label": "Ver más", "url": "https://..." }               // cta
{ "title": "...", "url": "https://drive.google.com/..." }  // document
```

**`content_json` por tipo de sección:**
```json
{ "name": "Johannes", "bio": "...", "photo_url": "..." }           // perfil
{ "tools": ["Python", "FastAPI", "React"] }                        // toolkit
{ "items": [{ "title": "...", "link": "..." }] }                   // recomendaciones
{ "email": "...", "linkedin": "...", "twitter": "..." }            // contacto
```

---

## Métricas de Éxito

- Flujo end-to-end funciona: login → crear bloque → visible en página pública
- Admin no técnico agrega un bloque en menos de 3 minutos
- Datos de proyecto A inaccesibles desde proyecto B
- Un `editor` no puede eliminar bloques ni gestionar usuarios
- Secciones estáticas editables y reflejadas en tiempo real en la página pública
