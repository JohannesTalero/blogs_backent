"""
HU-006: Tests de aislamiento transversal entre proyectos.

Verifican que ningún router permite a un JWT de un proyecto acceder
a recursos de otro proyecto.
"""
import pytest
from unittest.mock import patch, MagicMock

PROJECT_A = "proj-001"
PROJECT_B = "proj-002"
POST_IN_B = "post-uuid-in-proj-b"
BLOCK_B_ID = "block-in-proj-b"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_post_in_project(project_id: str):
    """Mock supabase donde el post lookup retorna el project_id dado."""
    mock = MagicMock()
    posts_chain = MagicMock()
    posts_chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"project_id": project_id}]
    )
    blocks_chain = MagicMock()
    mock.table.side_effect = lambda name: posts_chain if name == "posts" else blocks_chain
    return mock


# ============================================================
# Aislamiento en Bloques
# ============================================================

class TestBlocksIsolation:

    def test_cannot_create_block_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede crear bloque en un post de proj-002."""
        mock = _mock_post_in_project(PROJECT_B)
        with patch("app.blocks.router.supabase", mock):
            response = client.post(
                f"/blocks/{POST_IN_B}",
                json={"type": "text", "content_json": {"body": "Intrusión"}, "order": 1},
                headers=auth(owner_token),
            )
        assert response.status_code == 403

    def test_cannot_update_block_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede editar bloque de proj-002."""
        mock = _mock_post_in_project(PROJECT_B)
        with patch("app.blocks.router.supabase", mock):
            response = client.put(
                f"/blocks/{POST_IN_B}/{BLOCK_B_ID}",
                json={"visible": False},
                headers=auth(owner_token),
            )
        assert response.status_code == 403

    def test_cannot_delete_block_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede eliminar bloque de proj-002."""
        mock = _mock_post_in_project(PROJECT_B)
        with patch("app.blocks.router.supabase", mock):
            response = client.delete(
                f"/blocks/{POST_IN_B}/{BLOCK_B_ID}",
                headers=auth(owner_token),
            )
        assert response.status_code == 403

    def test_cannot_see_hidden_blocks_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede ver bloques privados de proj-002 vía admin/all."""
        mock = _mock_post_in_project(PROJECT_B)
        with patch("app.blocks.router.supabase", mock):
            response = client.get(
                f"/blocks/{POST_IN_B}/admin/all",
                headers=auth(owner_token),
            )
        assert response.status_code == 403


# ============================================================
# Aislamiento en Secciones
# ============================================================

class TestSectionsIsolation:

    def test_cannot_update_section_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede editar sección de proj-002."""
        response = client.put(
            f"/sections/{PROJECT_B}/perfil",
            json={"content_json": {"name": "Hacker"}},
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Aislamiento en Posts
# ============================================================

class TestPostsIsolation:

    def test_cannot_create_post_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede crear post en proj-002."""
        response = client.post(
            f"/posts/{PROJECT_B}",
            json={"slug": "intrusion", "title": "Intrusión"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_cannot_see_admin_posts_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede ver posts admin de proj-002."""
        response = client.get(
            f"/posts/{PROJECT_B}/admin/all",
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Aislamiento en Admins
# ============================================================

class TestAdminsIsolation:

    def test_cannot_list_admins_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede listar admins de proj-002."""
        response = client.get(f"/admins/{PROJECT_B}", headers=auth(owner_token))
        assert response.status_code == 403

    def test_cannot_create_admin_in_other_project(self, client, owner_token):
        """JWT de proj-001 no puede crear admin en proj-002."""
        response = client.post(
            f"/admins/{PROJECT_B}",
            json={"email": "x@x.com", "password": "SecurePass1", "role": "editor"},
            headers=auth(owner_token),
        )
        assert response.status_code == 403

    def test_cannot_delete_admin_of_other_project(self, client, owner_token):
        """JWT de proj-001 no puede eliminar admin de proj-002."""
        response = client.delete(
            f"/admins/{PROJECT_B}/some-admin-uuid",
            headers=auth(owner_token),
        )
        assert response.status_code == 403


# ============================================================
# Que SÍ es accesible (datos públicos de cualquier proyecto)
# ============================================================

class TestPublicDataIsAccessible:

    def test_public_blocks_of_any_post_are_readable(self, client):
        """GET /blocks/{post_id} es público — comportamiento intencional."""
        with patch("app.blocks.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/blocks/{POST_IN_B}")
        assert response.status_code == 200

    def test_public_sections_of_any_project_are_readable(self, client):
        """GET /sections es público para cualquier project_id — comportamiento intencional."""
        with patch("app.sections.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=[])
            response = client.get(f"/sections/{PROJECT_B}")
        assert response.status_code == 200

    def test_public_posts_of_any_project_are_readable(self, client):
        """GET /posts/{project_id} es público — comportamiento intencional."""
        with patch("app.posts.router.supabase") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value \
                .eq.return_value.order.return_value.execute.return_value \
                = MagicMock(data=[])
            response = client.get(f"/posts/{PROJECT_B}")
        assert response.status_code == 200
