import pytest
from unittest.mock import patch, MagicMock

PROJECT_ID = "proj-001"


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_text_block_xss_rejected(client, owner_token):
    """SEC-005: bloque tipo text con script tag es rechazado."""
    with patch("app.blocks.router.supabase"):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
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
    with patch("app.blocks.router.supabase"):
        response = client.post(
            f"/blocks/{PROJECT_ID}",
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
        "project_id": PROJECT_ID,
        "type": "cta",
        "content_json": {"label": "Ver más", "url": "https://example.com"},
        "order": 1,
        "visible": True,
        "created_at": "2025-01-01T00:00:00",
    }
    with patch("app.blocks.router.supabase") as mock_db:
        mock_db.table.return_value.insert.return_value.execute.return_value \
            = MagicMock(data=[mock_block])

        response = client.post(
            f"/blocks/{PROJECT_ID}",
            json={
                "type": "cta",
                "content_json": {"label": "Ver más", "url": "https://example.com"},
                "order": 1,
            },
            headers=auth_headers(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["type"] == "cta"
