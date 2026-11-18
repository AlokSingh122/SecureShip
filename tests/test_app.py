from fastapi.testclient import TestClient

from app.app import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_home_page_explains_the_security_pipeline():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Ship fast." in response.text
    assert "Gitleaks" in response.text
    assert "Trivy" in response.text
    assert "Checkov" in response.text
    assert "GitHub OIDC" in response.text


def test_version_reports_git_sha(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc123")
    body = client.get("/version").json()
    assert body["git_sha"] == "abc123"
    assert body["version"]


def test_greet_valid_name():
    r = client.get("/api/greet", params={"name": "Aayush"})
    assert r.status_code == 200
    assert r.json() == {"message": "Hello, Aayush!"}


def test_greet_rejects_markup_characters():
    assert client.get("/api/greet", params={"name": "<script>"}).status_code == 422


def test_greet_rejects_too_long_name():
    assert client.get("/api/greet", params={"name": "a" * 51}).status_code == 422


def test_docs_are_not_exposed():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
