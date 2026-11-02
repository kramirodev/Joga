"""Testes dos endpoints de health check."""

from fastapi.testclient import TestClient

from app.infrastructure.database.dependency import get_database


class FakeDatabase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def check(self) -> None:
        self.calls += 1
        if self.error is not None:
            raise self.error


def test_live_does_not_touch_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ok_when_database_answers(client: TestClient) -> None:
    database = FakeDatabase()
    client.app.dependency_overrides[get_database] = lambda: database

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert database.calls == 1


def test_ready_returns_503_without_leaking_connection_details(client: TestClient) -> None:
    database = FakeDatabase(RuntimeError("password=joga host=db-interno"))
    client.app.dependency_overrides[get_database] = lambda: database

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": {"status": "unavailable", "database": "unavailable"}}
    assert "password" not in response.text
    assert "db-interno" not in response.text
