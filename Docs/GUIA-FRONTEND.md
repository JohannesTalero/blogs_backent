# Guía de Integración Frontend

Todo lo que el frontend necesita saber para conectarse correctamente al backend.

---

## Configuración base

### Variables de entorno (Vite)

```bash
# .env
VITE_API_URL=https://api.johannesta.com      # URL del backend en producción
VITE_PROJECT_ID=abc-123-uuid-del-proyecto    # ID del proyecto en Supabase
```

```bash
# .env.local (desarrollo)
VITE_API_URL=http://localhost:8000
VITE_PROJECT_ID=abc-123-uuid-del-proyecto
```

### Cliente HTTP base

Centralizar la configuración en un solo lugar evita repetir la URL base y el token en cada llamada.

```typescript
// src/lib/api.ts
const API_URL = import.meta.env.VITE_API_URL;

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = localStorage.getItem("access_token");

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (response.status === 401) {
    // Token expirado o inválido → redirigir a login
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  }

  return response;
}
```

---

## Autenticación

### Flujo de login

```typescript
// src/services/auth.ts

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (response.status === 401) {
    throw new Error("Credenciales inválidas");
  }

  if (response.status === 429) {
    throw new Error("Demasiados intentos. Espera un minuto.");
  }

  if (!response.ok) {
    throw new Error("Error del servidor");
  }

  const data: TokenResponse = await response.json();
  localStorage.setItem("access_token", data.access_token);
}

export function logout(): void {
  localStorage.removeItem("access_token");
}

export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function isLoggedIn(): boolean {
  return getToken() !== null;
}
```

### Leer el payload del JWT

El JWT contiene `project_id` y `role` en su payload. No hace falta llamar a un endpoint adicional para saber quién es el usuario.

```typescript
// src/lib/token.ts

interface TokenPayload {
  sub: string;         // ID del admin
  project_id: string;
  role: "owner" | "editor" | "viewer";
  exp: number;         // timestamp Unix de expiración
}

export function decodeToken(token: string): TokenPayload | null {
  try {
    const [, payloadB64] = token.split(".");
    const payload = JSON.parse(atob(payloadB64));
    return payload as TokenPayload;
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token);
  if (!payload) return true;
  return payload.exp * 1000 < Date.now();
}

// Uso en el cliente:
// const { role, project_id } = decodeToken(getToken()!)
```

> **Importante:** `decodeToken` solo decodifica el payload base64, no verifica la firma. La verificación real ocurre en el backend en cada petición. No usar el payload del frontend para decisiones de seguridad definitivas — úsalo solo para decisiones de UI (mostrar/ocultar botones).

### Expiración del token

El token expira en **1 hora**. El frontend debe manejar esto:

```typescript
// src/lib/api.ts — versión con manejo de expiración proactivo

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem("access_token");

  // Verificar expiración antes de enviar la petición
  if (token && isTokenExpired(token)) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
    return Promise.reject(new Error("Sesión expirada"));
  }

  // ... resto igual
}
```

---

## Página pública

No requiere autenticación. Llamar a los dos endpoints en paralelo para minimizar el tiempo de carga.

```typescript
// src/pages/PublicPage.tsx

const PROJECT_ID = import.meta.env.VITE_PROJECT_ID;

interface Block {
  id: string;
  type: "text" | "image" | "card" | "cta" | "document";
  content_json: Record<string, unknown>;
  order: number;
  visible: boolean;
  created_at: string;
}

interface Section {
  id: string;
  type: "perfil" | "toolkit" | "recomendaciones" | "contacto";
  content_json: Record<string, unknown>;
}

type SectionMap = Record<string, Record<string, unknown>>;

async function loadPublicPage(): Promise<{ blocks: Block[]; sections: SectionMap }> {
  const [blocksRes, sectionsRes] = await Promise.all([
    fetch(`${API_URL}/blocks/${PROJECT_ID}`),
    fetch(`${API_URL}/sections/${PROJECT_ID}`),
  ]);

  const blocks: Block[] = await blocksRes.json();
  const sectionsArray: Section[] = await sectionsRes.json();

  // Convertir array de secciones a mapa por tipo para acceso directo
  const sections: SectionMap = Object.fromEntries(
    sectionsArray.map((s) => [s.type, s.content_json])
  );

  return { blocks, sections };
}
```

### Renderizado de bloques

```typescript
// src/components/blocks/BlockRenderer.tsx

interface BlockProps {
  block: Block;
}

export function BlockRenderer({ block }: BlockProps) {
  switch (block.type) {
    case "text":
      return <TextBlock content={block.content_json as { body: string }} />;
    case "image":
      return <ImageBlock content={block.content_json as { url: string; alt: string }} />;
    case "card":
      return <CardBlock content={block.content_json as { title: string; text: string; link?: string }} />;
    case "cta":
      return <CtaBlock content={block.content_json as { label: string; url: string }} />;
    case "document":
      return <DocumentBlock content={block.content_json as { title: string; url: string }} />;
    default:
      return null;
  }
}
```

### Sanitización de markdown (obligatoria)

El backend rechaza HTML y `javascript:` obvios, pero la sanitización en el frontend es la última línea de defensa.

```bash
npm install react-markdown dompurify
npm install -D @types/dompurify
```

```typescript
// src/components/blocks/TextBlock.tsx
import ReactMarkdown from "react-markdown";
import DOMPurify from "dompurify";

interface TextBlockProps {
  content: { body: string };
}

export function TextBlock({ content }: TextBlockProps) {
  // Sanitizar antes de pasar a react-markdown
  const sanitized = DOMPurify.sanitize(content.body);

  return (
    <ReactMarkdown
      disallowedElements={["script", "iframe", "object", "embed"]}
      unwrapDisallowed
    >
      {sanitized}
    </ReactMarkdown>
  );
}
```

---

## Panel admin

### Guardar el project_id desde el token

```typescript
// src/stores/auth.ts (ejemplo con Zustand)
import { create } from "zustand";
import { decodeToken } from "../lib/token";

interface AuthState {
  token: string | null;
  role: "owner" | "editor" | "viewer" | null;
  projectId: string | null;
  setToken: (token: string) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("access_token"),
  role: null,
  projectId: null,

  setToken: (token: string) => {
    const payload = decodeToken(token);
    localStorage.setItem("access_token", token);
    set({
      token,
      role: payload?.role ?? null,
      projectId: payload?.project_id ?? null,
    });
  },

  clear: () => {
    localStorage.removeItem("access_token");
    set({ token: null, role: null, projectId: null });
  },
}));
```

### Control de visibilidad por rol

```typescript
// src/lib/permissions.ts

type Role = "owner" | "editor" | "viewer";

export const can = {
  createBlock: (role: Role) => role === "owner" || role === "editor",
  editBlock:   (role: Role) => role === "owner" || role === "editor",
  deleteBlock: (role: Role) => role === "owner",
  editSection: (role: Role) => role === "owner" || role === "editor",
  manageAdmins:(role: Role) => role === "owner",
};

// Uso en componentes:
// const { role } = useAuthStore()
// {can.deleteBlock(role) && <button onClick={handleDelete}>Borrar</button>}
```

> El backend también valida los roles en cada petición. El control de visibilidad en el frontend es solo UX — no es seguridad.

### Servicio de bloques

```typescript
// src/services/blocks.ts

const PROJECT_ID = import.meta.env.VITE_PROJECT_ID;

export interface BlockCreate {
  type: "text" | "image" | "card" | "cta" | "document";
  content_json: Record<string, unknown>;
  order: number;
  visible?: boolean;
}

export interface BlockUpdate {
  type?: string;
  content_json?: Record<string, unknown>;
  order?: number;
  visible?: boolean;
}

// GET público
export async function getPublicBlocks(): Promise<Block[]> {
  const res = await fetch(`${API_URL}/blocks/${PROJECT_ID}`);
  return res.json();
}

// GET admin (incluye no visibles)
export async function getAllBlocks(): Promise<Block[]> {
  const res = await apiFetch(`/blocks/${PROJECT_ID}/admin/all`);
  if (!res.ok) throw new Error("Error al obtener bloques");
  return res.json();
}

export async function createBlock(data: BlockCreate): Promise<Block> {
  const res = await apiFetch(`/blocks/${PROJECT_ID}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (res.status === 422) {
    const error = await res.json();
    throw new Error(error.detail);
  }
  if (!res.ok) throw new Error("Error al crear bloque");
  return res.json();
}

export async function updateBlock(blockId: string, data: BlockUpdate): Promise<Block> {
  const res = await apiFetch(`/blocks/${PROJECT_ID}/${blockId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  if (res.status === 404) throw new Error("Bloque no encontrado");
  if (res.status === 422) {
    const error = await res.json();
    throw new Error(error.detail);
  }
  if (!res.ok) throw new Error("Error al actualizar bloque");
  return res.json();
}

export async function deleteBlock(blockId: string): Promise<void> {
  const res = await apiFetch(`/blocks/${PROJECT_ID}/${blockId}`, {
    method: "DELETE",
  });
  if (res.status === 404) throw new Error("Bloque no encontrado");
  if (!res.ok) throw new Error("Error al eliminar bloque");
}
```

### Servicio de secciones

```typescript
// src/services/sections.ts

type SectionType = "perfil" | "toolkit" | "recomendaciones" | "contacto";

export async function getPublicSections(): Promise<Section[]> {
  const res = await fetch(`${API_URL}/sections/${PROJECT_ID}`);
  return res.json();
}

export async function updateSection(
  sectionType: SectionType,
  content_json: Record<string, unknown>
): Promise<Section> {
  const res = await apiFetch(`/sections/${PROJECT_ID}/${sectionType}`, {
    method: "PUT",
    body: JSON.stringify({ content_json }),
  });
  if (res.status === 422) {
    const error = await res.json();
    throw new Error(error.detail);
  }
  if (!res.ok) throw new Error("Error al actualizar sección");
  return res.json();
}
```

---

## Manejo de errores del API

El backend retorna errores con este formato:

```json
{ "detail": "mensaje de error" }
```

Los códigos que el frontend debe manejar:

| Código | Causa | Acción recomendada |
|---|---|---|
| `400` | Error de lógica (e.g. auto-eliminación) | Mostrar `detail` al usuario |
| `401` | Token ausente, inválido o expirado | Redirigir a login |
| `403` | Rol insuficiente o proyecto incorrecto | Mostrar "Sin permisos" |
| `404` | Recurso no encontrado | Mostrar "No encontrado" |
| `409` | Conflicto (e.g. email duplicado) | Mostrar `detail` al usuario |
| `422` | Validación fallida | Mostrar `detail` al usuario |
| `429` | Rate limit superado | Mostrar "Demasiados intentos. Espera un minuto." |
| `500` | Error interno del servidor | Mostrar mensaje genérico, no el `detail` |

```typescript
// src/lib/errors.ts

export function parseApiError(status: number, detail: string): string {
  switch (status) {
    case 401: return "Tu sesión expiró. Inicia sesión nuevamente.";
    case 403: return "No tienes permisos para realizar esta acción.";
    case 404: return "El recurso solicitado no existe.";
    case 409: return detail; // seguro mostrar al usuario
    case 422: return detail; // seguro mostrar al usuario
    case 429: return "Demasiados intentos. Espera un momento.";
    default:  return "Ocurrió un error. Intenta nuevamente.";
  }
}
```

---

## Estructura de archivos sugerida

```
src/
├── lib/
│   ├── api.ts          # apiFetch con token y manejo de 401
│   ├── token.ts        # decodeToken, isTokenExpired
│   ├── errors.ts       # parseApiError
│   └── permissions.ts  # can.deleteBlock, can.editSection, etc.
├── services/
│   ├── auth.ts         # login, logout, getToken
│   ├── blocks.ts       # getPublicBlocks, getAllBlocks, createBlock, ...
│   ├── sections.ts     # getPublicSections, updateSection
│   └── admins.ts       # listAdmins, createAdmin, deleteAdmin
├── stores/
│   └── auth.ts         # token, role, projectId (Zustand / Context)
├── pages/
│   ├── PublicPage.tsx
│   ├── LoginPage.tsx
│   └── admin/
│       ├── AdminLayout.tsx
│       ├── BlocksPage.tsx
│       ├── SectionsPage.tsx
│       └── AdminsPage.tsx
└── components/
    ├── blocks/
    │   ├── BlockRenderer.tsx
    │   ├── TextBlock.tsx
    │   ├── ImageBlock.tsx
    │   ├── CardBlock.tsx
    │   ├── CtaBlock.tsx
    │   └── DocumentBlock.tsx
    └── sections/
        ├── PerfilSection.tsx
        ├── ToolkitSection.tsx
        ├── RecomendacionesSection.tsx
        └── ContactoSection.tsx
```

---

## Checklist antes de desplegar el frontend

- [ ] `VITE_API_URL` apunta al backend de producción (Railway), no a `localhost`
- [ ] `VITE_PROJECT_ID` contiene el UUID real del proyecto en Supabase
- [ ] El `service_role` key de Supabase **no está** en el frontend (ni en variables de entorno del frontend)
- [ ] `DOMPurify` está instalado y usado en `TextBlock`
- [ ] Los errores `500` muestran un mensaje genérico, no el `detail` del servidor
- [ ] El token se elimina de `localStorage` al recibir un `401`
- [ ] La URL del backend en producción usa `https://`, no `http://`
- [ ] CORS: el dominio del frontend coincide con `allow_origins` en el backend (`johannesta.com`, `admin.johannesta.com`)
