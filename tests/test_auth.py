from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.middleware import auth as auth_module
from src.main import app


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    response = FakeResponse(200, {})

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url: str, headers: dict):
        assert url == "https://example.supabase.co/auth/v1/user"
        assert headers["apikey"] == "test-anon-key"
        assert headers["Authorization"] == "Bearer supabase-access-token"
        return self.response


def test_auth_me_uses_supabase_verified_identity(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_anon_key="test-anon-key",
        ),
    )
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "id": "c3a2f12d-448f-4a37-9e56-93a34852f2e1",
            "email": "athlete@example.com",
            "user_metadata": {"username": "GymAthlete"},
        },
    )
    monkeypatch.setattr(auth_module.httpx, "AsyncClient", FakeAsyncClient)

    response = TestClient(app).get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer supabase-access-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "c3a2f12d-448f-4a37-9e56-93a34852f2e1",
        "username": "GymAthlete",
        "email": "athlete@example.com",
    }


def test_auth_me_rejects_invalid_supabase_token(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_anon_key="test-anon-key",
        ),
    )
    FakeAsyncClient.response = FakeResponse(401, {"message": "invalid token"})
    monkeypatch.setattr(auth_module.httpx, "AsyncClient", FakeAsyncClient)

    response = TestClient(app).get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer supabase-access-token"},
    )

    assert response.status_code == 401


def test_auth_me_requires_bearer_token():
    response = TestClient(app).get("/api/v1/auth/me")
    assert response.status_code == 401
