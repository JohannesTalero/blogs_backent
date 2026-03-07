import io
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"
PROJECT_ID_OTHER = "proj-002"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _image_file(content=b"fake-image-data", content_type="image/jpeg", filename="test.jpg"):
    return ("file", (filename, io.BytesIO(content), content_type))


# ============================================================
# Upload de imagen
# ============================================================

class TestUploadImage:

    def test_owner_uploads_image(self, client, owner_token):
        with patch("app.images.router.supabase") as mock_storage:
            mock_storage.storage.from_.return_value.upload.return_value = MagicMock()
            mock_storage.storage.from_.return_value.get_public_url.return_value = \
                "https://supabase.io/storage/v1/object/public/images/proj-001/uuid.jpg"
            response = client.post(
                f"/images/{PROJECT_ID}",
                files=[_image_file()],
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        body = response.json()
        assert "url" in body
        assert body["url"].startswith("https://")

    def test_editor_uploads_image(self, client, editor_token):
        with patch("app.images.router.supabase") as mock_storage:
            mock_storage.storage.from_.return_value.upload.return_value = MagicMock()
            mock_storage.storage.from_.return_value.get_public_url.return_value = \
                "https://supabase.io/storage/v1/object/public/images/proj-001/uuid.jpg"
            response = client.post(
                f"/images/{PROJECT_ID}",
                files=[_image_file()],
                headers=auth(editor_token),
            )
        assert response.status_code == 200

    def test_viewer_cannot_upload(self, client, viewer_token):
        """Viewer no tiene permisos para subir imágenes."""
        response = client.post(
            f"/images/{PROJECT_ID}",
            files=[_image_file()],
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_no_auth_returns_401(self, client):
        """Sin token no se puede subir imagen."""
        response = client.post(
            f"/images/{PROJECT_ID}",
            files=[_image_file()],
        )
        assert response.status_code == 401

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede subir imágenes a proj-002."""
        response = client.post(
            f"/images/{PROJECT_ID_OTHER}",
            files=[_image_file()],
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_svg_content_type_rejected(self, client, owner_token):
        """SVG rechazado (riesgo XSS)."""
        response = client.post(
            f"/images/{PROJECT_ID}",
            files=[_image_file(content_type="image/svg+xml", filename="bad.svg")],
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_pdf_content_type_rejected(self, client, owner_token):
        """PDF rechazado — solo imágenes permitidas."""
        response = client.post(
            f"/images/{PROJECT_ID}",
            files=[_image_file(content_type="application/pdf", filename="doc.pdf")],
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_file_too_large_rejected(self, client, owner_token):
        """Archivo mayor a 5 MB es rechazado."""
        large_content = b"x" * (5 * 1024 * 1024 + 1)
        response = client.post(
            f"/images/{PROJECT_ID}",
            files=[_image_file(content=large_content)],
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_path_stored_under_project_id(self, client, owner_token):
        """La imagen se guarda bajo el project_id en Storage."""
        captured_path = []

        def capture_upload(path, content, opts):
            captured_path.append(path)

        with patch("app.images.router.supabase") as mock_storage:
            mock_storage.storage.from_.return_value.upload.side_effect = capture_upload
            mock_storage.storage.from_.return_value.get_public_url.return_value = \
                f"https://supabase.io/storage/v1/object/public/images/{PROJECT_ID}/uuid.jpg"
            client.post(
                f"/images/{PROJECT_ID}",
                files=[_image_file()],
                headers=auth(owner_token),
            )
        assert len(captured_path) == 1
        assert captured_path[0].startswith(f"{PROJECT_ID}/")
