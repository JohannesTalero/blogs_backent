"""
HU-008: Tests del módulo sections (validador + endpoints).
"""
import pytest
from unittest.mock import patch, MagicMock
from app.sections.validator import validate_section_content
from fastapi import HTTPException

PROJECT_ID = "proj-001"
OTHER_PROJECT_ID = "proj-002"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# Validador unitario
# ============================================================

class TestSectionValidator:

    # perfil
    def test_valid_perfil(self):
        result = validate_section_content("perfil", {
            "name": "Johannes", "bio": "Bio.", "photo_url": "https://cdn.example.com/foto.jpg"
        })
        assert result["name"] == "Johannes"
        assert isinstance(result["photo_url"], str)  # HttpUrl serializado como str

    def test_perfil_without_photo_url(self):
        result = validate_section_content("perfil", {"name": "Jo", "bio": "Bio."})
        assert result["photo_url"] is None

    def test_perfil_javascript_photo_url_rejected(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_section_content("perfil", {"photo_url": "javascript:evil()"})

    def test_perfil_bio_too_long(self):
        # SEC-007
        with pytest.raises(HTTPException):
            validate_section_content("perfil", {"bio": "x" * 1_001})

    # toolkit
    def test_valid_toolkit(self):
        result = validate_section_content("toolkit", {"tools": ["Python", "React"]})
        assert "Python" in result["tools"]

    def test_toolkit_too_many_tools(self):
        # SEC-007: máximo 50
        with pytest.raises(HTTPException):
            validate_section_content("toolkit", {"tools": [f"tool{i}" for i in range(51)]})

    def test_toolkit_tool_name_too_long(self):
        with pytest.raises(HTTPException):
            validate_section_content("toolkit", {"tools": ["x" * 101]})

    # recomendaciones
    def test_valid_recomendacion_with_link(self):
        result = validate_section_content("recomendaciones", {
            "items": [{"title": "FastAPI", "link": "https://fastapi.tiangolo.com"}]
        })
        assert len(result["items"]) == 1

    def test_recomendacion_without_link(self):
        result = validate_section_content("recomendaciones", {
            "items": [{"title": "Sin link"}]
        })
        assert result["items"][0]["link"] is None

    def test_recomendacion_javascript_link_rejected(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_section_content("recomendaciones", {
                "items": [{"title": "Click", "link": "javascript:evil()"}]
            })

    def test_too_many_recomendaciones(self):
        # SEC-007: máximo 100
        with pytest.raises(HTTPException):
            validate_section_content("recomendaciones", {
                "items": [{"title": f"Item {i}"} for i in range(101)]
            })

    # contacto
    def test_valid_contacto(self):
        result = validate_section_content("contacto", {
            "email": "yo@ejemplo.com",
            "linkedin": "https://linkedin.com/in/yo",
            "twitter": "https://twitter.com/yo",
        })
        assert result["email"] == "yo@ejemplo.com"

    def test_contacto_without_social_links(self):
        result = validate_section_content("contacto", {"email": "yo@ejemplo.com"})
        assert result["linkedin"] is None
        assert result["twitter"] is None

    def test_contacto_javascript_linkedin_rejected(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_section_content("contacto", {
                "email": "yo@ejemplo.com",
                "linkedin": "javascript:alert(1)",
            })

    def test_invalid_section_type(self):
        with pytest.raises(HTTPException) as exc:
            validate_section_content("about", {})
        assert exc.value.status_code == 422


# ============================================================
# Endpoint: GET /sections/{project_id}
# ============================================================

class TestGetSections:

    def test_get_sections_public_no_auth(self, client):
        """GET es público, no requiere token."""
        sections_data = [
            {"id": "s1", "project_id": PROJECT_ID, "type": "perfil", "content_json": {"name": "Jo"}},
        ]
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=sections_data)
            response = client.get(f"/sections/{PROJECT_ID}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_sections_returns_all_four(self, client):
        """GET retorna las 4 secciones."""
        sections_data = [
            {"id": f"s{i}", "project_id": PROJECT_ID, "type": t, "content_json": {}}
            for i, t in enumerate(["perfil", "toolkit", "recomendaciones", "contacto"])
        ]
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=sections_data)
            response = client.get(f"/sections/{PROJECT_ID}")
        assert len(response.json()) == 4


# ============================================================
# Endpoint: PUT /sections/{project_id}/{type}
# ============================================================

class TestUpdateSection:

    def _mock_existing_and_update(self, mock_db, updated_data):
        mock_db.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[{"id": "s1"}])
        mock_db.table.return_value.update.return_value.eq.return_value \
            .eq.return_value.execute.return_value = MagicMock(data=[updated_data])

    def test_owner_can_update_perfil(self, client, owner_token):
        updated = {
            "id": "s1", "project_id": PROJECT_ID, "type": "perfil",
            "content_json": {"name": "Johannes", "bio": "Dev.", "photo_url": None},
        }
        with patch("app.sections.router.supabase") as mock_db:
            self._mock_existing_and_update(mock_db, updated)
            response = client.put(
                f"/sections/{PROJECT_ID}/perfil",
                json={"content_json": {"name": "Johannes", "bio": "Dev."}},
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert response.json()["content_json"]["name"] == "Johannes"

    def test_editor_can_update_toolkit(self, client, editor_token):
        updated = {
            "id": "s2", "project_id": PROJECT_ID, "type": "toolkit",
            "content_json": {"tools": ["Python"]},
        }
        with patch("app.sections.router.supabase") as mock_db:
            self._mock_existing_and_update(mock_db, updated)
            response = client.put(
                f"/sections/{PROJECT_ID}/toolkit",
                json={"content_json": {"tools": ["Python"]}},
                headers=auth(editor_token),
            )
        assert response.status_code == 200

    def test_viewer_cannot_update(self, client, viewer_token):
        response = client.put(
            f"/sections/{PROJECT_ID}/perfil",
            json={"content_json": {"name": "x"}},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_invalid_section_type_returns_422(self, client, owner_token):
        response = client.put(
            f"/sections/{PROJECT_ID}/about",
            json={"content_json": {}},
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede modificar secciones de proj-002."""
        response = client.put(
            f"/sections/{OTHER_PROJECT_ID}/perfil",
            json={"content_json": {"name": "Hacker"}},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_javascript_url_in_photo_rejected(self, client, owner_token):
        """SEC-008: photo_url con javascript: es rechazada."""
        response = client.put(
            f"/sections/{PROJECT_ID}/perfil",
            json={"content_json": {"photo_url": "javascript:alert(1)"}},
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_bio_too_long_rejected(self, client, owner_token):
        """SEC-007: bio mayor a 1000 chars es rechazada."""
        response = client.put(
            f"/sections/{PROJECT_ID}/perfil",
            json={"content_json": {"bio": "x" * 1_001}},
            headers=auth(owner_token),
        )
        assert response.status_code == 422
