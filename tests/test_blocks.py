import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"
OTHER_PROJECT_ID = "proj-002"
BLOCK_ID = "block-uuid-001"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


MOCK_BLOCK = {
    "id": BLOCK_ID,
    "project_id": PROJECT_ID,
    "type": "text",
    "content_json": {"body": "Hola"},
    "order": 1,
    "visible": True,
    "created_at": "2025-01-01T00:00:00",
}


# ============================================================
# GET público
# ============================================================

class TestGetBlocksPublic:

    def test_returns_only_visible_blocks(self, client):
        """GET público solo retorna bloques con visible=True."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])

            response = client.get(f"/blocks/{PROJECT_ID}")

        assert response.status_code == 200
        assert all(b["visible"] for b in response.json())

    def test_no_auth_required(self, client):
        """GET no requiere token."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/blocks/{PROJECT_ID}")
        assert response.status_code == 200


# ============================================================
# GET admin/all (protegido)
# ============================================================

class TestGetBlocksAdmin:

    def test_owner_sees_all_blocks(self, client, owner_token):
        """GET admin retorna bloques visibles e invisibles."""
        invisible = {**MOCK_BLOCK, "id": "block-002", "visible": False}
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK, invisible])

            response = client.get(
                f"/blocks/{PROJECT_ID}/admin/all",
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_no_token_returns_401(self, client):
        response = client.get(f"/blocks/{PROJECT_ID}/admin/all")
        assert response.status_code == 401


# ============================================================
# POST — crear bloque
# ============================================================

class TestCreateBlock:

    def test_owner_creates_block(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])

            response = client.post(
                f"/blocks/{PROJECT_ID}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(owner_token),
            )
        assert response.status_code == 201
        assert response.json()["type"] == "text"

    def test_editor_creates_block(self, client, editor_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])

            response = client.post(
                f"/blocks/{PROJECT_ID}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(editor_token),
            )
        assert response.status_code == 201

    def test_viewer_cannot_create(self, client, viewer_token):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede crear bloque en proj-002."""
        response = client.post(
            f"/blocks/{OTHER_PROJECT_ID}",
            json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_invalid_type_returns_422(self, client, owner_token):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={"type": "video", "content_json": {}, "order": 1},
            headers=auth(owner_token),
        )
        assert response.status_code == 422


# ============================================================
# PUT — editar bloque
# ============================================================

class TestUpdateBlock:

    def test_owner_updates_block(self, client, owner_token):
        updated = {**MOCK_BLOCK, "content_json": {"body": "Actualizado"}}
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": BLOCK_ID}])
            mock_db.table.return_value.update.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[updated])

            response = client.put(
                f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
                json={"content_json": {"body": "Actualizado"}},
                headers=auth(owner_token),
            )
        assert response.status_code == 200

    def test_nonexistent_block_returns_404(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.put(
                f"/blocks/{PROJECT_ID}/nonexistent",
                json={"content_json": {"body": "X"}},
                headers=auth(owner_token),
            )
        assert response.status_code == 404

    def test_editor_can_update(self, client, editor_token):
        updated = {**MOCK_BLOCK, "visible": False}
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": BLOCK_ID}])
            mock_db.table.return_value.update.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[updated])

            response = client.put(
                f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
                json={"visible": False},
                headers=auth(editor_token),
            )
        assert response.status_code == 200

    def test_viewer_cannot_update(self, client, viewer_token):
        response = client.put(
            f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
            json={"visible": False},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403


# ============================================================
# DELETE — eliminar bloque
# ============================================================

class TestDeleteBlock:

    def test_owner_deletes_block(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": BLOCK_ID}])
            mock_db.table.return_value.delete.return_value.eq.return_value \
                .execute.return_value = MagicMock()

            response = client.delete(
                f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 204

    def test_editor_cannot_delete(self, client, editor_token):
        response = client.delete(
            f"/blocks/{PROJECT_ID}/{BLOCK_ID}",
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_nonexistent_block_returns_404(self, client, owner_token):
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])

            response = client.delete(
                f"/blocks/{PROJECT_ID}/nonexistent",
                headers=auth(owner_token),
            )
        assert response.status_code == 404
