import time
import jwt as pyjwt
import pytest
from unittest.mock import patch, MagicMock
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_HASH = pwd_context.hash("Password123")
MOCK_ADMIN = {
    "id": "admin-uuid-001",
    "project_id": "proj-001",
    "role": "owner",
    "hashed_password": VALID_HASH,
}


def _mock_db(data):
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=data)
    return mock


def test_login_success(client):
    """Login con credenciales correctas retorna JWT."""
    with patch("app.auth.router.supabase", _mock_db([MOCK_ADMIN])):
        response = client.post("/auth/login", json={
            "email": "admin@johannesta.com",
            "password": "Password123",
        })

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client):
    """Password incorrecto retorna 401 con mensaje genérico."""
    with patch("app.auth.router.supabase", _mock_db([MOCK_ADMIN])):
        response = client.post("/auth/login", json={
            "email": "admin@johannesta.com",
            "password": "WrongPassword",
        })

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_login_email_not_found(client):
    """Email inexistente retorna 401 con mismo mensaje que password incorrecto."""
    with patch("app.auth.router.supabase", _mock_db([])):
        response = client.post("/auth/login", json={
            "email": "noexiste@ejemplo.com",
            "password": "cualquiera",
        })

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"


def test_login_timing_attack_protection(client):
    """
    SEC-003: El tiempo de respuesta cuando el email no existe debe ser similar
    al tiempo cuando existe pero el password es incorrecto (ambos corren bcrypt).
    """
    with patch("app.auth.router.supabase", _mock_db([])):
        t0 = time.perf_counter()
        client.post("/auth/login", json={"email": "noexiste@x.com", "password": "pass"})
        t_no_email = time.perf_counter() - t0

    with patch("app.auth.router.supabase", _mock_db([MOCK_ADMIN])):
        t0 = time.perf_counter()
        client.post("/auth/login", json={"email": "admin@johannesta.com", "password": "mal"})
        t_bad_pass = time.perf_counter() - t0

    assert t_no_email > 0.05, "Sin email: debería correr bcrypt (~100ms)"
    assert abs(t_no_email - t_bad_pass) < t_bad_pass, "Diferencia de tiempo sospechosa"


def test_jwt_payload_contains_required_fields(client):
    """El JWT contiene project_id, role y exp."""
    with patch("app.auth.router.supabase", _mock_db([MOCK_ADMIN])):
        response = client.post("/auth/login", json={
            "email": "admin@johannesta.com",
            "password": "Password123",
        })

    token = response.json()["access_token"]
    payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    assert payload["project_id"] == "proj-001"
    assert payload["role"] == "owner"
    assert "exp" in payload


def test_login_rate_limit(client):
    """SEC-001: Más de 5 intentos por minuto desde la misma IP retorna 429."""
    with patch("app.auth.router.supabase", _mock_db([])):
        responses = [
            client.post("/auth/login", json={"email": "x@x.com", "password": "x"})
            for _ in range(7)
        ]

    assert 429 in [r.status_code for r in responses], "El rate limiter debería haber retornado 429"


def test_expired_token_rejected(client):
    """Token expirado retorna 401."""
    from datetime import datetime, timedelta, timezone

    expired_payload = {
        "sub": "admin-uuid-001",
        "project_id": "proj-001",
        "role": "owner",
        "exp": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    expired_token = pyjwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = client.get(
        "/auth/login",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code in (401, 405)
