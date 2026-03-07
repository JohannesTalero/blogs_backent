import pytest
from unittest.mock import patch, MagicMock

POST_ID = "post-uuid-001"
PROJECT_ID = "proj-001"


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_mock(post_project_id=PROJECT_ID):
    """Supabase mock con post lookup y blocks chain separados."""
    mock = MagicMock()
    posts_chain = MagicMock()
    posts_chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"project_id": post_project_id}]
    )
    blocks_chain = MagicMock()
    mock.table.side_effect = lambda name: posts_chain if name == "posts" else blocks_chain
    return mock, blocks_chain


def test_create_text_block_xss_rejected(client, owner_token):
    """SEC-005: bloque tipo text con script tag es rechazado."""
    mock, _ = _make_mock()
    with patch("app.blocks.router.supabase", mock):
        response = client.post(
            f"/blocks/{POST_ID}",
            json={
                "type": "text",
                "content_json": {"body": "<script>alert(1)</script>"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 422


def test_create_image_block_javascript_url_rejected(client, owner_token):
    """SEC-008: URL con javascript: en bloque imagen es rechazada."""
    mock, _ = _make_mock()
    with patch("app.blocks.router.supabase", mock):
        response = client.post(
            f"/blocks/{POST_ID}",
            json={
                "type": "image",
                "content_json": {"url": "javascript:alert(document.cookie)"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 422


def test_create_valid_block_persists(client, owner_token):
    """Bloque válido se persiste en DB."""
    mock_block = {
        "id": "block-001",
        "post_id": POST_ID,
        "type": "cta",
        "content_json": {"label": "Ver más", "url": "https://example.com"},
        "order": 1,
        "visible": True,
        "created_at": "2025-01-01T00:00:00",
    }
    mock, blocks_chain = _make_mock()
    blocks_chain.insert.return_value.execute.return_value = MagicMock(data=[mock_block])
    with patch("app.blocks.router.supabase", mock):
        response = client.post(
            f"/blocks/{POST_ID}",
            json={
                "type": "cta",
                "content_json": {"label": "Ver más", "url": "https://example.com"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["type"] == "cta"
