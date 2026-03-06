import pytest
from fastapi.testclient import TestClient
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from app.main import app
from app.config import settings
from app.limiter import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter._limiter.storage.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_token(project_id: str, role: str, admin_id: str = "admin-uuid-001") -> str:
    payload = {
        "sub": admin_id,
        "project_id": project_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def owner_token():
    return make_token("proj-001", "owner")


@pytest.fixture
def editor_token():
    return make_token("proj-001", "editor")


@pytest.fixture
def viewer_token():
    return make_token("proj-001", "viewer")


@pytest.fixture
def other_project_token():
    return make_token("proj-002", "owner")
