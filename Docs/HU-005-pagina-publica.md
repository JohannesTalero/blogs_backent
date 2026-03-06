# HU-005: Página Pública con Secciones + Bloques

**Historia:** Como visitante, quiero ver la página del proyecto con secciones estáticas y bloques dinámicos actualizados.

---

## Contexto Técnico

Esta HU es principalmente de **frontend** (React + Vite en repo separado). El backend ya expone los endpoints públicos necesarios. El trabajo de backend se limita a verificar que `GET /blocks/{project_id}` y `GET /sections/{project_id}` funcionen correctamente para consumo público.

El backend de esta HU **ya está cubierto por HU-003 y HU-008**. Esta HU documenta los requisitos de la página pública y el contrato de API que el frontend debe consumir.

---

## Responsabilidades por Capa

| Capa | Tarea |
|---|---|
| Backend | `GET /blocks/{project_id}` retorna bloques `visible=true` ordenados por `order` |
| Backend | `GET /sections/{project_id}` retorna todas las secciones del proyecto |
| Backend | Ambos endpoints sin autenticación |
| Frontend | Renderizar secciones fijas: perfil, toolkit, recomendaciones, contacto |
| Frontend | Renderizar bloques dinámicos según su `type` |
| Frontend | Obtener `project_id` desde config (variable de entorno Vite) |

---

## Contrato de API para el Frontend

### `GET /blocks/{project_id}`

**Response (200):**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "text",
    "content_json": { "body": "## Bienvenidos..." },
    "order": 1,
    "visible": true,
    "created_at": "2025-01-01T00:00:00Z"
  },
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "card",
    "content_json": { "title": "FastAPI", "text": "...", "link": "https://..." },
    "order": 2,
    "visible": true,
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```
- Ordenados por `order` ASC
- Solo `visible = true`
- Sin paginación en MVP

### `GET /sections/{project_id}`

**Response (200):**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "perfil",
    "content_json": { "name": "Johannes", "bio": "...", "photo_url": "https://..." }
  },
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "toolkit",
    "content_json": { "tools": ["Python", "FastAPI", "React"] }
  },
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "recomendaciones",
    "content_json": { "items": [{ "title": "...", "link": "https://..." }] }
  },
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "contacto",
    "content_json": { "email": "...", "linkedin": "https://...", "twitter": "https://..." }
  }
]
```

---

## Estructura Frontend (Referencia para el Repo React)

```
frontend/
├── src/
│   ├── pages/
│   │   └── PublicPage.tsx          # Página principal pública
│   ├── components/
│   │   ├── sections/
│   │   │   ├── PerfilSection.tsx
│   │   │   ├── ToolkitSection.tsx
│   │   │   ├── RecomendacionesSection.tsx
│   │   │   └── ContactoSection.tsx
│   │   └── blocks/
│   │       ├── BlockRenderer.tsx   # Switch por tipo
│   │       ├── TextBlock.tsx
│   │       ├── ImageBlock.tsx
│   │       ├── CardBlock.tsx
│   │       ├── CtaBlock.tsx
│   │       └── DocumentBlock.tsx
│   └── config.ts                   # PROJECT_ID desde import.meta.env
├── .env
└── vite.config.ts
```

### `BlockRenderer.tsx` (lógica clave)

```tsx
const BlockRenderer = ({ block }: { block: Block }) => {
  switch (block.type) {
    case "text":     return <TextBlock content={block.content_json} />;
    case "image":    return <ImageBlock content={block.content_json} />;
    case "card":     return <CardBlock content={block.content_json} />;
    case "cta":      return <CtaBlock content={block.content_json} />;
    case "document": return <DocumentBlock content={block.content_json} />;
    default:         return null;
  }
};
```

### `PublicPage.tsx` (lógica de fetch)

```tsx
const PROJECT_ID = import.meta.env.VITE_PROJECT_ID;

const [blocks, setBlocks] = useState([]);
const [sections, setSections] = useState({});

useEffect(() => {
  Promise.all([
    fetch(`${API_URL}/blocks/${PROJECT_ID}`).then(r => r.json()),
    fetch(`${API_URL}/sections/${PROJECT_ID}`).then(r => r.json()),
  ]).then(([blocksData, sectionsData]) => {
    setBlocks(blocksData);
    // Convertir array de secciones a objeto por tipo
    const sectionMap = Object.fromEntries(sectionsData.map(s => [s.type, s.content_json]));
    setSections(sectionMap);
  });
}, []);
```

---

## Verificaciones de Backend Necesarias

Antes de entregar esta HU, confirmar:

- [ ] `GET /blocks/{project_id}` retorna 200 sin token
- [ ] Los bloques vienen ordenados por `order` ASC
- [ ] Bloques con `visible=false` NO aparecen en el response
- [ ] `GET /sections/{project_id}` retorna 200 sin token
- [ ] Las 4 secciones del proyecto aparecen en el response
- [ ] CORS configurado para permitir el origen del frontend

---

## Criterios de Aceptación Técnicos

- [ ] La página pública carga sin errores en navegador
- [ ] Sección `perfil` muestra foto, nombre y bio
- [ ] Sección `toolkit` lista todas las herramientas
- [ ] Sección `recomendaciones` lista items con links
- [ ] Sección `contacto` muestra email y redes sociales
- [ ] Bloques dinámicos se renderizan en orden correcto
- [ ] Bloque tipo `text` renderiza markdown
- [ ] Solo bloques visibles aparecen en la página pública
- [ ] Página carga sin autenticación

---

## Enfoque TDD

Esta HU tiene dos capas de testing: **backend** (verificar los contratos de API) y **frontend** (verificar el renderizado de componentes).

### Backend: Verificación de contratos públicos

```python
# tests/test_public_endpoints.py

import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"

MOCK_BLOCKS = [
    {"id": "b1", "project_id": PROJECT_ID, "type": "text",
     "content_json": {"body": "Hola"}, "order": 1, "visible": True, "created_at": "2025-01-01T00:00:00"},
    {"id": "b2", "project_id": PROJECT_ID, "type": "card",
     "content_json": {"title": "Curso", "text": "Desc", "link": None}, "order": 2,
     "visible": True, "created_at": "2025-01-01T00:00:00"},
]

MOCK_SECTIONS = [
    {"id": "s1", "project_id": PROJECT_ID, "type": "perfil", "content_json": {"name": "Jo", "bio": "", "photo_url": None}},
    {"id": "s2", "project_id": PROJECT_ID, "type": "toolkit", "content_json": {"tools": ["Python"]}},
    {"id": "s3", "project_id": PROJECT_ID, "type": "recomendaciones", "content_json": {"items": []}},
    {"id": "s4", "project_id": PROJECT_ID, "type": "contacto", "content_json": {"email": "", "linkedin": None, "twitter": None}},
]


class TestPublicBlocksEndpoint:

    def test_no_auth_required(self, client):
        """GET /blocks es completamente público."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=MOCK_BLOCKS)
            response = client.get(f"/blocks/{PROJECT_ID}")
        assert response.status_code == 200

    def test_blocks_ordered_by_order_field(self, client):
        """Los bloques vienen ordenados por el campo order."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=MOCK_BLOCKS)
            response = client.get(f"/blocks/{PROJECT_ID}")
        blocks = response.json()
        orders = [b["order"] for b in blocks]
        assert orders == sorted(orders)

    def test_only_visible_blocks_returned(self, client):
        """Bloques con visible=False no aparecen en GET público."""
        visible_only = [b for b in MOCK_BLOCKS if b["visible"]]
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=visible_only)
            response = client.get(f"/blocks/{PROJECT_ID}")
        assert all(b["visible"] for b in response.json())

    def test_response_includes_required_fields(self, client):
        """Cada bloque tiene los campos esperados por el frontend."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=MOCK_BLOCKS)
            response = client.get(f"/blocks/{PROJECT_ID}")
        for block in response.json():
            assert "type" in block
            assert "content_json" in block
            assert "order" in block


class TestPublicSectionsEndpoint:

    def test_no_auth_required(self, client):
        """GET /sections es público."""
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=MOCK_SECTIONS)
            response = client.get(f"/sections/{PROJECT_ID}")
        assert response.status_code == 200

    def test_returns_all_four_section_types(self, client):
        """El response incluye las 4 secciones."""
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=MOCK_SECTIONS)
            response = client.get(f"/sections/{PROJECT_ID}")
        types = {s["type"] for s in response.json()}
        assert types == {"perfil", "toolkit", "recomendaciones", "contacto"}

    def test_response_includes_content_json(self, client):
        """Cada sección incluye content_json."""
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=MOCK_SECTIONS)
            response = client.get(f"/sections/{PROJECT_ID}")
        for section in response.json():
            assert "content_json" in section
            assert "type" in section
```

### Frontend: Testing de componentes (referencia para repo React)

```typescript
// BlockRenderer.test.tsx
import { render, screen } from "@testing-library/react";
import BlockRenderer from "./BlockRenderer";

test("renderiza bloque text como markdown", () => {
  render(<BlockRenderer block={{ type: "text", content_json: { body: "## Título" } }} />);
  expect(screen.getByRole("heading")).toBeInTheDocument();
});

test("renderiza bloque cta con link correcto", () => {
  render(<BlockRenderer block={{ type: "cta", content_json: { label: "Ver más", url: "https://example.com" } }} />);
  expect(screen.getByRole("link")).toHaveAttribute("href", "https://example.com");
});

test("no renderiza tipo desconocido", () => {
  const { container } = render(
    <BlockRenderer block={{ type: "unknown", content_json: {} } as any} />
  );
  expect(container.firstChild).toBeNull();
});
```

### Flujo RED → GREEN → REFACTOR

```
RED:   test_only_visible_blocks_returned → falla si el query no filtra visible=True
GREEN: Agregar .eq("visible", True) al query de GET público en blocks/router.py
RED:   test_returns_all_four_section_types → falla si el seed no existe
GREEN: Verificar que HU-001 seed está aplicado
RED:   test_response_includes_required_fields → falla si BlockResponse no incluye algún campo
GREEN: Completar BlockResponse schema con todos los campos necesarios
REFACTOR: Agregar índice en DB sobre (project_id, order) para mejor performance en GET
```

---

## Dependencias

- HU-001 (tablas y seed)
- HU-003 (`GET /blocks`)
- HU-008 (`GET /sections`)
- Repo frontend React + Vite (independiente de este repo)
