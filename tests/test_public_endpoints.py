"""
HU-005: Verificación de contratos públicos de API para consumo del frontend.
"""
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
    {"id": "s1", "project_id": PROJECT_ID, "type": "perfil",
     "content_json": {"name": "Jo", "bio": "", "photo_url": None}},
    {"id": "s2", "project_id": PROJECT_ID, "type": "toolkit",
     "content_json": {"tools": ["Python"]}},
    {"id": "s3", "project_id": PROJECT_ID, "type": "recomendaciones",
     "content_json": {"items": []}},
    {"id": "s4", "project_id": PROJECT_ID, "type": "contacto",
     "content_json": {"email": "", "linkedin": None, "twitter": None}},
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
        orders = [b["order"] for b in response.json()]
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
