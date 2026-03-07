import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"
PROJECT_ID_OTHER = "proj-002"
POST_ID = "post-uuid-001"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


MOCK_POST = {
    "id": POST_ID,
    "project_id": PROJECT_ID,
    "slug": "mi-primer-post",
    "title": "Mi primer post",
    "order": 1,
    "visible": True,
    "created_at": "2025-01-01T00:00:00",
}

MOCK_BLOCK = {
    "id": "block-001",
    "post_id": POST_ID,
    "type": "text",
    "content_json": {"body": "Contenido"},
    "order": 1,
    "visible": True,
    "created_at": "2025-01-01T00:00:00",
}


# ============================================================
# GET público — lista de posts
# ============================================================

class TestGetPosts:

    def test_returns_visible_posts(self, client):
        """GET público solo retorna posts con visible=True."""
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_POST])
            response = client.get(f"/posts/{PROJECT_ID}")
        assert response.status_code == 200
        assert all(p["visible"] for p in response.json())

    def test_no_auth_required(self, client):
        """GET /posts es público."""
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/posts/{PROJECT_ID}")
        assert response.status_code == 200


# ============================================================
# GET público — post por slug (la "URL" del post)
# ============================================================

class TestGetPostBySlug:

    def test_returns_post_with_blocks(self, client):
        """GET /{project_id}/{slug} retorna el post con bloques embebidos."""
        with patch("app.posts.router.supabase") as mock_db:
            # posts query: 3 .eq() calls (project_id, slug, visible)
            mock_db.table.return_value.select.return_value \
                .eq.return_value.eq.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=[MOCK_POST])
            # blocks query: 2 .eq() + order
            mock_db.table.return_value.select.return_value \
                .eq.return_value.eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_BLOCK])
            response = client.get(f"/posts/{PROJECT_ID}/mi-primer-post")
        assert response.status_code == 200
        body = response.json()
        assert body["slug"] == "mi-primer-post"
        assert "blocks" in body
        assert isinstance(body["blocks"], list)

    def test_nonexistent_slug_returns_404(self, client):
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value \
                .eq.return_value.eq.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/posts/{PROJECT_ID}/no-existe")
        assert response.status_code == 404

    def test_no_auth_required(self, client):
        """GET por slug es público."""
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value \
                .eq.return_value.eq.return_value.eq.return_value.execute.return_value \
                = MagicMock(data=[MOCK_POST])
            mock_db.table.return_value.select.return_value \
                .eq.return_value.eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/posts/{PROJECT_ID}/mi-primer-post")
        assert response.status_code == 200


# ============================================================
# GET admin/all (protegido)
# ============================================================

class TestGetPostsAdmin:

    def test_owner_sees_all_posts(self, client, owner_token):
        """GET admin retorna posts visibles e invisibles."""
        invisible = {**MOCK_POST, "id": "post-002", "visible": False}
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .order.return_value.execute.return_value \
                = MagicMock(data=[MOCK_POST, invisible])
            response = client.get(
                f"/posts/{PROJECT_ID}/admin/all",
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_no_token_returns_401(self, client):
        response = client.get(f"/posts/{PROJECT_ID}/admin/all")
        assert response.status_code == 401

    def test_other_project_returns_403(self, client, owner_token):
        """JWT de proj-001 no puede ver admin posts de proj-002."""
        response = client.get(
            f"/posts/{PROJECT_ID_OTHER}/admin/all",
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# POST — crear post
# ============================================================

class TestCreatePost:

    def test_owner_creates_post(self, client, owner_token):
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[MOCK_POST])
            response = client.post(
                f"/posts/{PROJECT_ID}",
                json={"slug": "mi-primer-post", "title": "Mi primer post"},
                headers=auth(owner_token),
            )
        assert response.status_code == 201
        assert response.json()["slug"] == "mi-primer-post"

    def test_editor_creates_post(self, client, editor_token):
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.insert.return_value.execute.return_value \
                = MagicMock(data=[MOCK_POST])
            response = client.post(
                f"/posts/{PROJECT_ID}",
                json={"slug": "nuevo-post", "title": "Nuevo"},
                headers=auth(editor_token),
            )
        assert response.status_code == 201

    def test_viewer_cannot_create(self, client, viewer_token):
        response = client.post(
            f"/posts/{PROJECT_ID}",
            json={"slug": "x", "title": "X"},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_cross_project_blocked(self, client, owner_token):
        """JWT de proj-001 no puede crear post en proj-002."""
        response = client.post(
            f"/posts/{PROJECT_ID_OTHER}",
            json={"slug": "x", "title": "X"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_no_auth_returns_401(self, client):
        response = client.post(
            f"/posts/{PROJECT_ID}",
            json={"slug": "x", "title": "X"},
        )
        assert response.status_code == 401


# ============================================================
# PUT — actualizar post
# ============================================================

class TestUpdatePost:

    def test_owner_updates_post(self, client, owner_token):
        updated = {**MOCK_POST, "title": "Título nuevo"}
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": POST_ID}])
            mock_db.table.return_value.update.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[updated])
            response = client.put(
                f"/posts/{PROJECT_ID}/{POST_ID}",
                json={"title": "Título nuevo"},
                headers=auth(owner_token),
            )
        assert response.status_code == 200
        assert response.json()["title"] == "Título nuevo"

    def test_nonexistent_post_returns_404(self, client, owner_token):
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])
            response = client.put(
                f"/posts/{PROJECT_ID}/nonexistent",
                json={"title": "X"},
                headers=auth(owner_token),
            )
        assert response.status_code == 404

    def test_viewer_cannot_update(self, client, viewer_token):
        response = client.put(
            f"/posts/{PROJECT_ID}/{POST_ID}",
            json={"title": "X"},
            headers=auth(viewer_token),
        )
        assert response.status_code == 403

    def test_cross_project_blocked(self, client, owner_token):
        response = client.put(
            f"/posts/{PROJECT_ID_OTHER}/{POST_ID}",
            json={"title": "X"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# DELETE — eliminar post
# ============================================================

class TestDeletePost:

    def test_owner_deletes_post(self, client, owner_token):
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[{"id": POST_ID}])
            mock_db.table.return_value.delete.return_value.eq.return_value \
                .execute.return_value = MagicMock()
            response = client.delete(
                f"/posts/{PROJECT_ID}/{POST_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 204

    def test_editor_cannot_delete(self, client, editor_token):
        response = client.delete(
            f"/posts/{PROJECT_ID}/{POST_ID}",
            headers=auth(editor_token),
        )
        assert response.status_code == 403

    def test_nonexistent_post_returns_404(self, client, owner_token):
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.execute.return_value = MagicMock(data=[])
            response = client.delete(
                f"/posts/{PROJECT_ID}/nonexistent",
                headers=auth(owner_token),
            )
        assert response.status_code == 404

    def test_cross_project_blocked(self, client, owner_token):
        response = client.delete(
            f"/posts/{PROJECT_ID_OTHER}/{POST_ID}",
            headers=auth(owner_token),
        )
        assert response.status_code == 403
