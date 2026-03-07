import pytest
from unittest.mock import patch, MagicMock

POST_ID = "post-uuid-001"
POST_ID_OTHER = "post-uuid-in-proj-002"
PROJECT_ID = "proj-001"
PROJECT_ID_OTHER = "proj-002"
BLOCK_ID = "block-uuid-001"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


MOCK_BLOCK = {
    "id": BLOCK_ID,
    "post_id": POST_ID,
    "type": "text",
    "content_json": {"body": "Hola"},
    "order": 1,
    "visible": True,
    "created_at": "2025-01-01T00:00:00",
}


def _make_mock(post_project_id=PROJECT_ID, post_exists=True):
    """Supabase mock que diferencia entre tabla 'posts' y 'blocks'."""
    mock = MagicMock()
    posts_chain = MagicMock()
    posts_chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"project_id": post_project_id}] if post_exists else []
    )
    blocks_chain = MagicMock()
    mock.table.side_effect = lambda name: posts_chain if name == "posts" else blocks_chain
    return mock, blocks_chain


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
            response = client.get(f"/blocks/{POST_ID}")
        assert response.status_code == 200
        assert all(b["visible"] for b in response.json())

    def test_no_auth_required(self, client):
        """GET no requiere token."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/blocks/{POST_ID}")
        assert response.status_code == 200


# ============================================================
# GET admin/all (protegido)
# ============================================================

class TestGetBlocksAdmin:

    def test_owner_sees_all_blocks(self, client, owner_token):
        """GET admin retorna bloques visibles e invisibles."""
        invisible = {**MOCK_BLOCK, "id": "block-002", "visible": False}
        mock, blocks_chain = _make_mock()
        blocks_chain.select.return_value.eq.return_value.order.return_value.execute.return_value \
            = MagicMock(data=[MOCK_BLOCK, invisible])
        with patch("app.blocks.router.supabase", mock):
            response = client.get(
                f"/blocks/{POST_ID}/admin/all",
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_no_token_returns_401(self, client):
        response = client.get(f"/blocks/{POST_ID}/admin/all")
        assert response.status_code == 401

    def test_other_project_returns_403(self, client, owner_token):
        """JWT de proj-001 no puede ver bloques de un post de proj-002."""
        mock, _ = _make_mock(post_project_id=PROJECT_ID_OTHER)
        with patch("app.blocks.router.supabase", mock):
            response = client.get(
                f"/blocks/{POST_ID_OTHER}/admin/all",
                headers=auth(owner_token),
            )
        assert response.status_code == 403


# ============================================================
# POST — crear bloque
# ============================================================

class TestCreateBlock:

    def test_owner_creates_block(self, client, owner_token):
        mock, blocks_chain = _make_mock()
        blocks_chain.insert.return_value.execute.return_value = MagicMock(data=[MOCK_BLOCK])
        with patch("app.blocks.router.supabase", mock):
            response = client.post(
                f"/blocks/{POST_ID}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(owner_token),
            )
        assert response.status_code == 201
        assert response.json()["type"] == "text"

    def test_editor_creates_block(self, client, editor_token):
        mock, blocks_chain = _make_mock()
        blocks_chain.insert.return_value.execute.return_value = MagicMock(data=[MOCK_BLOCK])
        with patch("app.blocks.router.supabase", mock):
            response = client.post(
                f"/blocks/{POST_ID}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(editor_token),
            )
        assert response.status_code == 201

    def test_viewer_cannot_create(self, client, viewer_token):
        response = client.post(
            f"/blocks/{POST_ID}",
            json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede crear bloque en un post de proj-002."""
        mock, _ = _make_mock(post_project_id=PROJECT_ID_OTHER)
        with patch("app.blocks.router.supabase", mock):
            response = client.post(
                f"/blocks/{POST_ID_OTHER}",
                json={"type": "text", "content_json": {"body": "Hola"}, "order": 1},
                headers=auth(owner_token),
            )
        assert response.status_code == 403

    def test_invalid_type_returns_422(self, client, owner_token):
        mock, _ = _make_mock()
        with patch("app.blocks.router.supabase", mock):
            response = client.post(
                f"/blocks/{POST_ID}",
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
        mock, blocks_chain = _make_mock()
        blocks_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[{"id": BLOCK_ID, "type": "text"}])
        blocks_chain.update.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[updated])
        with patch("app.blocks.router.supabase", mock):
            response = client.put(
                f"/blocks/{POST_ID}/{BLOCK_ID}",
                json={"content_json": {"body": "Actualizado"}},
                headers=auth(owner_token),
            )
        assert response.status_code == 200

    def test_nonexistent_block_returns_404(self, client, owner_token):
        mock, blocks_chain = _make_mock()
        blocks_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[])
        with patch("app.blocks.router.supabase", mock):
            response = client.put(
                f"/blocks/{POST_ID}/nonexistent",
                json={"content_json": {"body": "X"}},
                headers=auth(owner_token),
            )
        assert response.status_code == 404

    def test_editor_can_update(self, client, editor_token):
        updated = {**MOCK_BLOCK, "visible": False}
        mock, blocks_chain = _make_mock()
        blocks_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[{"id": BLOCK_ID, "type": "text"}])
        blocks_chain.update.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[updated])
        with patch("app.blocks.router.supabase", mock):
            response = client.put(
                f"/blocks/{POST_ID}/{BLOCK_ID}",
                json={"visible": False},
                headers=auth(editor_token),
            )
        assert response.status_code == 200

    def test_viewer_cannot_update(self, client, viewer_token):
        response = client.put(
            f"/blocks/{POST_ID}/{BLOCK_ID}",
            json={"visible": False},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403


# ============================================================
# DELETE — eliminar bloque
# ============================================================

class TestDeleteBlock:

    def test_owner_deletes_block(self, client, owner_token):
        mock, blocks_chain = _make_mock()
        blocks_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[{"id": BLOCK_ID}])
        blocks_chain.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        with patch("app.blocks.router.supabase", mock):
            response = client.delete(
                f"/blocks/{POST_ID}/{BLOCK_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 204

    def test_editor_cannot_delete(self, client, editor_token):
        response = client.delete(
            f"/blocks/{POST_ID}/{BLOCK_ID}",
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_nonexistent_block_returns_404(self, client, owner_token):
        mock, blocks_chain = _make_mock()
        blocks_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value \
            = MagicMock(data=[])
        with patch("app.blocks.router.supabase", mock):
            response = client.delete(
                f"/blocks/{POST_ID}/nonexistent",
                headers=auth(owner_token),
            )
        assert response.status_code == 404
