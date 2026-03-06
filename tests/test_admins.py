"""
HU-007: Tests del módulo admins (validación de password + endpoints CRUD).
"""
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"
OTHER_PROJECT_ID = "proj-002"
ADMIN_ID = "admin-to-delete-uuid"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# Password strength (SEC-009) — tests unitarios del schema
# ============================================================

class TestAdminCreatePasswordValidation:

    def test_rejects_short_password(self):
        """SEC-009: password menor a 8 chars es rechazada."""
        from pydantic import ValidationError
        from app.admins.schemas import AdminCreate
        with pytest.raises(ValidationError, match="8 caracteres"):
            AdminCreate(email="a@b.com", password="Ab1", role="editor")

    def test_rejects_password_without_letters(self):
        """SEC-009: password solo numérica es rechazada."""
        from pydantic import ValidationError
        from app.admins.schemas import AdminCreate
        with pytest.raises(ValidationError, match="letra"):
            AdminCreate(email="a@b.com", password="12345678", role="editor")

    def test_rejects_password_without_numbers(self):
        """SEC-009: password solo alfabética es rechazada."""
        from pydantic import ValidationError
        from app.admins.schemas import AdminCreate
        with pytest.raises(ValidationError, match="número"):
            AdminCreate(email="a@b.com", password="abcdefgh", role="editor")

    def test_accepts_valid_password(self):
        """Password con letras y números de longitud >= 8 es aceptada."""
        from app.admins.schemas import AdminCreate
        admin = AdminCreate(email="a@b.com", password="Password1", role="editor")
        assert admin.password == "Password1"


# ============================================================
# Endpoint: POST /admins/{project_id}
# ============================================================

class TestCreateAdmin:

    def test_owner_can_create_editor(self, client, owner_token):
        """Owner puede crear un admin con rol editor."""
        new_admin = {
            "id": "new-uuid",
            "project_id": PROJECT_ID,
            "email": "editor@test.com",
            "role": "editor",
            "created_at": "2025-01-01T00:00:00",
        }
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[new_admin])

            response = client.post(
                f"/admins/{PROJECT_ID}",
                json={"email": "editor@test.com", "password": "SecurePass1", "role": "editor"},
                headers=auth(owner_token),
            )

        assert response.status_code == 201
        body = response.json()
        assert body["role"] == "editor"
        assert "hashed_password" not in body

    def test_editor_cannot_create_admin(self, client, editor_token):
        """Editor no puede invitar nuevos admins."""
        response = client.post(
            f"/admins/{PROJECT_ID}",
            json={"email": "x@x.com", "password": "SecurePass1", "role": "viewer"},
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_owner_role_rejected_in_body(self, client, owner_token):
        """No se puede crear un admin con rol owner via API."""
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.post(
                f"/admins/{PROJECT_ID}",
                json={"email": "x@x.com", "password": "SecurePass1", "role": "owner"},
                headers=auth(owner_token),
            )
        assert response.status_code == 422

    def test_weak_password_rejected(self, client, owner_token):
        """SEC-009: password débil retorna 422 antes de tocar la DB."""
        response = client.post(
            f"/admins/{PROJECT_ID}",
            json={"email": "x@x.com", "password": "abc", "role": "editor"},
            headers=auth(owner_token),
        )
        assert response.status_code == 422

    def test_duplicate_email_returns_409(self, client, owner_token):
        """Email ya existente en el proyecto retorna 409."""
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": "existing"}])

            response = client.post(
                f"/admins/{PROJECT_ID}",
                json={"email": "dupe@test.com", "password": "SecurePass1", "role": "editor"},
                headers=auth(owner_token),
            )
        assert response.status_code == 409

    def test_cross_project_access_denied(self, client, owner_token):
        """JWT de proj-001 no puede crear admin en proj-002."""
        response = client.post(
            f"/admins/{OTHER_PROJECT_ID}",
            json={"email": "x@x.com", "password": "SecurePass1", "role": "editor"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Endpoint: DELETE /admins/{project_id}/{admin_id}
# ============================================================

class TestDeleteAdmin:

    def test_owner_can_delete_other_admin(self, client, owner_token):
        """Owner puede eliminar a otro admin del mismo proyecto."""
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": ADMIN_ID}])
            mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value \
                = MagicMock()

            response = client.delete(
                f"/admins/{PROJECT_ID}/{ADMIN_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 204

    def test_owner_cannot_delete_self(self, client):
        """El owner no puede eliminarse a sí mismo."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from app.config import settings

        self_id = "owner-self-uuid"
        token = pyjwt.encode(
            {
                "sub": self_id,
                "project_id": PROJECT_ID,
                "role": "owner",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        response = client.delete(
            f"/admins/{PROJECT_ID}/{self_id}",
            headers=auth(token),
        )
        assert response.status_code == 400

    def test_editor_cannot_delete_admin(self, client, editor_token):
        """Editor no puede eliminar admins."""
        response = client.delete(
            f"/admins/{PROJECT_ID}/{ADMIN_ID}",
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_delete_nonexistent_admin_returns_404(self, client, owner_token):
        """Admin inexistente retorna 404."""
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.delete(
                f"/admins/{PROJECT_ID}/nonexistent-uuid",
                headers=auth(owner_token),
            )
        assert response.status_code == 404


# ============================================================
# Endpoint: GET /admins/{project_id}
# ============================================================

class TestListAdmins:

    def test_owner_can_list_admins(self, client, owner_token):
        """Owner puede listar todos los admins del proyecto."""
        admins_data = [
            {
                "id": "a1",
                "project_id": PROJECT_ID,
                "email": "a@b.com",
                "role": "owner",
                "created_at": "2025-01-01T00:00:00",
            },
        ]
        with patch("app.admins.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=admins_data)

            response = client.get(f"/admins/{PROJECT_ID}", headers=auth(owner_token))

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_editor_cannot_list_admins(self, client, editor_token):
        """Editor no puede listar admins."""
        response = client.get(f"/admins/{PROJECT_ID}", headers=auth(editor_token))
        assert response.status_code == 403
