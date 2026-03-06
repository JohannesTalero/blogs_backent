import pytest
from app.blocks.validator import validate_content_json
from fastapi import HTTPException


# ============================================================
# TextContent
# ============================================================

class TestTextContent:

    def test_valid_markdown(self):
        result = validate_content_json("text", {"body": "## Título\n\nContenido normal."})
        assert result["body"] == "## Título\n\nContenido normal."

    def test_rejects_html_tags(self):
        # SEC-005: XSS via script tag
        with pytest.raises(HTTPException) as exc:
            validate_content_json("text", {"body": "<script>alert(1)</script>"})
        assert exc.value.status_code == 422

    def test_rejects_html_tags_in_markdown(self):
        # SEC-005: HTML embebido en markdown
        with pytest.raises(HTTPException):
            validate_content_json("text", {"body": "Texto con <img src=x onerror=alert(1)>"})

    def test_rejects_javascript_protocol(self):
        # SEC-005: javascript: en body
        with pytest.raises(HTTPException):
            validate_content_json("text", {"body": "[click](javascript:alert(1))"})

    def test_rejects_body_too_long(self):
        # SEC-007: límite de 50k
        with pytest.raises(HTTPException):
            validate_content_json("text", {"body": "a" * 50_001})

    def test_accepts_body_at_limit(self):
        result = validate_content_json("text", {"body": "a" * 50_000})
        assert len(result["body"]) == 50_000

    def test_missing_body_raises_422(self):
        with pytest.raises(HTTPException):
            validate_content_json("text", {})


# ============================================================
# ImageContent
# ============================================================

class TestImageContent:

    def test_valid_https_url(self):
        result = validate_content_json("image", {"url": "https://cdn.example.com/img.jpg"})
        assert "cdn.example.com" in result["url"]

    def test_rejects_javascript_url(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_content_json("image", {"url": "javascript:alert(1)"})

    def test_rejects_relative_url(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_content_json("image", {"url": "evil.com/img.jpg"})

    def test_optional_alt_defaults_to_empty(self):
        result = validate_content_json("image", {"url": "https://example.com/img.jpg"})
        assert result["alt"] == ""

    def test_alt_too_long_raises_422(self):
        # SEC-007
        with pytest.raises(HTTPException):
            validate_content_json("image", {
                "url": "https://example.com/img.jpg",
                "alt": "a" * 201,
            })


# ============================================================
# CardContent
# ============================================================

class TestCardContent:

    def test_valid_card_with_link(self):
        result = validate_content_json("card", {
            "title": "FastAPI",
            "text": "Framework rápido.",
            "link": "https://fastapi.tiangolo.com",
        })
        assert result["title"] == "FastAPI"

    def test_valid_card_without_link(self):
        result = validate_content_json("card", {"title": "T", "text": "Contenido."})
        assert result["link"] is None

    def test_rejects_javascript_link(self):
        # SEC-008
        with pytest.raises(HTTPException):
            validate_content_json("card", {
                "title": "T", "text": "C", "link": "javascript:evil()",
            })

    def test_title_too_long(self):
        with pytest.raises(HTTPException):
            validate_content_json("card", {"title": "x" * 201, "text": "ok"})


# ============================================================
# CtaContent
# ============================================================

class TestCtaContent:

    def test_valid_cta(self):
        result = validate_content_json("cta", {"label": "Ver más", "url": "https://example.com"})
        assert result["label"] == "Ver más"

    def test_rejects_missing_url(self):
        with pytest.raises(HTTPException):
            validate_content_json("cta", {"label": "Click"})

    def test_rejects_non_http_url(self):
        with pytest.raises(HTTPException):
            validate_content_json("cta", {"label": "Click", "url": "ftp://files.example.com"})

    def test_label_too_long(self):
        with pytest.raises(HTTPException):
            validate_content_json("cta", {"label": "x" * 101, "url": "https://example.com"})


# ============================================================
# DocumentContent
# ============================================================

class TestDocumentContent:

    def test_valid_drive_url(self):
        result = validate_content_json("document", {
            "title": "Mi CV",
            "url": "https://drive.google.com/file/d/xxxx/view",
        })
        assert "drive.google.com" in result["url"]

    def test_rejects_missing_url(self):
        with pytest.raises(HTTPException):
            validate_content_json("document", {"title": "Mi CV"})


# ============================================================
# Tipo inválido
# ============================================================

def test_invalid_block_type():
    with pytest.raises(HTTPException) as exc:
        validate_content_json("video", {"src": "https://youtube.com"})
    assert exc.value.status_code == 422
    assert "inválido" in exc.value.detail
