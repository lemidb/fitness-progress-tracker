from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_register_and_login_flow(client: TestClient):
    username = f"user_{uuid4().hex[:8]}"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["username"] == username
    assert payload["user_id"]
    assert "access_token" in payload
    assert "refresh_token" in payload
    assert payload["token_type"] == "bearer"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me_response.status_code == 200
    profile = me_response.json()
    assert profile["username"] == username
    assert profile["user_id"] == payload["user_id"]
